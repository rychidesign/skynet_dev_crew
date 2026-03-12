#!/usr/bin/env python3
"""
Multiagent Development Supervisor
4-agent workflow: Architekt → Kodér → Reviewer → Integrátor
"""

import json
import logging
import os
import sys
import time
import yaml
from dotenv import load_dotenv
from crewai import Crew, Task, Process

from agents.architect import create_architect_agent
from agents.coder import create_coder_agent
from agents.reviewer import create_reviewer_agent
from agents.integrator import create_integrator_agent
from tools.telegram_notify import send_telegram_message, setup_telegram_listener


load_dotenv()

# Enable INFO logging so token usage from CrewAI providers is captured
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

# Configure LiteLLM to retry empty/None API responses automatically.
# This intercepts the error at the LiteLLM layer before CrewAI sees it,
# preventing "Invalid response from LLM call - None or empty" exceptions.

# Method 1: Direct litellm configuration (before any LLM objects are created)
import litellm
litellm.num_retries = 5          # retry up to 5 times per LLM call
litellm.retry_after = 10         # wait 10s between retries

# Method 2: Also set via environment for extra redundancy
os.environ["LITELLM_NUM_RETRIES"] = "5"
os.environ["LITELLM_RETRY_AFTER"] = "10"

# ---------------------------------------------------------------------------
# Single-instance guard — prevents running multiple supervisors simultaneously
# ---------------------------------------------------------------------------
_LOCK_FILE = "/tmp/multiagent_supervisor.lock"

def _acquire_lock() -> None:
    """Exit immediately if another supervisor is already running."""
    if os.path.exists(_LOCK_FILE):
        with open(_LOCK_FILE) as f:
            old_pid = f.read().strip()
        if old_pid and os.path.exists(f"/proc/{old_pid}"):
            print(f"❌ Supervisor již běží (PID {old_pid}). Ukonči ho nejdřív.")
            print(f"   kill {old_pid}")
            sys.exit(1)
        # Stale lock — previous run crashed without cleanup
        os.remove(_LOCK_FILE)

    with open(_LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def _release_lock() -> None:
    try:
        os.remove(_LOCK_FILE)
    except OSError:
        pass



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_project_config(project_name: str) -> dict:
    config_path = "config.yaml"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            return config.get("projects", {}).get(project_name, {})
    return {}


def read_file(filepath: str) -> str:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def find_spec_file(project_path: str, filename: str) -> str:
    for folder in ["", "specs"]:
        path = os.path.join(project_path, folder, filename) if folder else os.path.join(project_path, filename)
        if os.path.exists(path):
            return read_file(path)
    return ""


def find_specs_folder(project_path: str) -> str:
    path = os.path.join(project_path, "specs")
    return path if os.path.exists(path) else ""


def find_rules_folder(project_path: str) -> str:
    path = os.path.join(project_path, "rules")
    return path if os.path.exists(path) else ""


def load_rules(project_path: str, only: list[str] | None = None) -> str:
    rules_folder = find_rules_folder(project_path)
    if not rules_folder:
        return ""
    combined = ""
    for filename in sorted(os.listdir(rules_folder)):
        if not filename.endswith(".md"):
            continue
        if only is not None and filename not in only:
            continue
        filepath = os.path.join(rules_folder, filename)
        content = read_file(filepath)
        if content:
            combined += f"\n\n=== rules/{filename} ===\n{content}\n"
    return combined


def list_specs_files(project_path: str) -> str:
    specs_folder = find_specs_folder(project_path)
    if not specs_folder:
        return "(žádné spec soubory nenalezeny)"
    lines = []
    for filename in sorted(os.listdir(specs_folder)):
        if filename.endswith(".md"):
            lines.append(f"  - {project_path}/specs/{filename}")
    return "\n".join(lines)


USAGE_FILE = "logs/usage.json"

# Per-model pricing — dynamically from models.py + legacy entries for old logs
from models import get_model_pricing
MODEL_PRICING = get_model_pricing()
MODEL_PRICING.update({
    "anthropic/claude-opus-4-6":    {"input": 15.0,  "output": 75.0},
    "claude-opus-4-6":              {"input": 15.0,  "output": 75.0},
    "anthropic/claude-sonnet-4-6":  {"input": 3.0,   "output": 15.0},
    "claude-sonnet-4-6":            {"input": 3.0,   "output": 15.0},
    "anthropic/claude-haiku-4-5":   {"input": 0.8,   "output": 4.0},
    "claude-haiku-4-5":             {"input": 0.8,   "output": 4.0},
    "gemini/gemini-2.5-flash":      {"input": 0.15,  "output": 0.60},
    "gemini-2.5-flash":             {"input": 0.15,  "output": 0.60},
    "gemini/gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash-lite":        {"input": 0.075, "output": 0.30},
    "gemini/gemini-3.1-flash-lite": {"input": 0.25,  "output": 1.50},
    "gemini-3.1-flash-lite":        {"input": 0.25,  "output": 1.50},
})


def save_usage(agents_map: dict, usage_file: str = USAGE_FILE):
    """Save token usage from all agent LLMs to a JSON file for the monitor."""
    data = {}
    total_input = 0
    total_output = 0
    total_cost = 0.0

    for name, agent in agents_map.items():
        llm = agent.llm
        model_full = getattr(llm, "model", "unknown")
        model_bare = model_full.split("/")[-1] if "/" in model_full else model_full
        usage = getattr(llm, "_token_usage", {})
        inp = usage.get("prompt_tokens", 0)
        out = usage.get("completion_tokens", 0)
        cached = usage.get("cached_prompt_tokens", 0)

        pricing = MODEL_PRICING.get(model_full, MODEL_PRICING.get(model_bare, {"input": 0, "output": 0}))
        model = model_full
        cost_in = (inp / 1_000_000) * pricing["input"]
        cost_out = (out / 1_000_000) * pricing["output"]
        cost = cost_in + cost_out

        data[name] = {
            "model": model,
            "input_tokens": inp,
            "output_tokens": out,
            "cached_tokens": cached,
            "cost_input": round(cost_in, 4),
            "cost_output": round(cost_out, 4),
            "cost_total": round(cost, 4),
        }
        total_input += inp
        total_output += out
        total_cost += cost

    data["_total"] = {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cost_usd": round(total_cost, 4),
    }
    data["_updated"] = time.time()

    os.makedirs(os.path.dirname(usage_file), exist_ok=True)
    with open(usage_file, "w") as f:
        json.dump(data, f, indent=2)


def find_progress_file(project_path: str) -> str:
    """Find PROGRESS.md — check project root first, then specs/ subfolder."""
    for candidate in [
        os.path.join(project_path, "PROGRESS.md"),
        os.path.join(project_path, "specs", "PROGRESS.md"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return os.path.join(project_path, "specs", "PROGRESS.md")  # fallback


def read_current_task(pfile: str) -> str:
    """Return name of current task from PROGRESS.md.

    Priority:
    1. Line with '← CURRENT' that is NOT yet completed ([ ])
    2. Line with '← CURRENT' on any line (even [x]) — Integrator forgot to move it
    3. First uncompleted task [ ] in the file (fallback)
    """
    try:
        fallback_current = None
        first_pending = None
        with open(pfile, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                has_current = "← CURRENT" in stripped
                has_marker = "**" in stripped

                if has_current and has_marker:
                    name = stripped.split("**")[1]
                    # Prefer CURRENT on an uncompleted task
                    if stripped.startswith("- [ ]"):
                        return name
                    # Keep as fallback if CURRENT is on completed task
                    fallback_current = name

                if first_pending is None and stripped.startswith("- [ ]") and has_marker:
                    first_pending = stripped.split("**")[1]

        return fallback_current or first_pending or "?"
    except Exception:
        return "?"


def count_remaining(pfile: str) -> int:
    try:
        with open(pfile, encoding="utf-8") as f:
            return sum(1 for l in f if l.strip().startswith("- [ ]"))
    except Exception:
        return 0


def extract_current_context(pfile: str, context_lines: int = 5) -> str:
    """Return only the ← CURRENT task line plus surrounding context lines.

    Reduces PROGRESS.md injection from ~5000 chars to ~300 chars per agent,
    while still giving agents enough context to understand where they are.
    Falls back to first pending task if ← CURRENT is missing.
    """
    try:
        with open(pfile, encoding="utf-8") as f:
            lines = f.readlines()

        current_idx = None
        for i, line in enumerate(lines):
            if "← CURRENT" in line:
                current_idx = i
                break

        if current_idx is None:
            for i, line in enumerate(lines):
                if line.strip().startswith("- [ ]"):
                    current_idx = i
                    break

        if current_idx is None:
            return "".join(lines[:20])

        start = max(0, current_idx - context_lines)
        end = min(len(lines), current_idx + context_lines + 1)
        return "".join(lines[start:end])
    except Exception:
        return ""


def advance_progress(pfile: str, completed_task: str) -> None:
    """After a successful crew run, mark completed task as [x] and move ← CURRENT.

    This makes PROGRESS.md updates reliable without depending on the Integrator.
    Operates only on lines matching the exact completed_task name to avoid false edits.
    Also removes any duplicate trailing sections that agents may have appended.
    """
    if not completed_task or completed_task == "?":
        return
    try:
        with open(pfile, encoding="utf-8") as f:
            lines = f.readlines()

        # ── Step 1: Remove any duplicate sections appended by agents ─────────
        # Keep only content up to and including the first occurrence of Phase headers
        seen_phases: set[str] = set()
        clean_lines = []
        for line in lines:
            # Detect phase headers like "## Phase N:"
            import re as _re
            phase_m = _re.match(r"^## Phase \d+:", line)
            if phase_m:
                key = phase_m.group(0)
                if key in seen_phases:
                    # Second occurrence → stop here (remove everything from prior ---)
                    while clean_lines and clean_lines[-1].strip() in ("---", ""):
                        clean_lines.pop()
                    break
                seen_phases.add(key)
            clean_lines.append(line)

        # ── Step 2: Mark completed task as [x] and remove ← CURRENT ─────────
        for i, line in enumerate(clean_lines):
            if f"**{completed_task}**" in line and "← CURRENT" in line:
                clean_lines[i] = line.replace("- [ ]", "- [x]").replace(" ← CURRENT", "").replace("← CURRENT", "")

        # ── Step 3: Move ← CURRENT to next uncompleted task ──────────────────
        # Remove any remaining stale ← CURRENT markers
        for i, line in enumerate(clean_lines):
            if "← CURRENT" in line and not line.strip().startswith(">"):
                clean_lines[i] = line.replace(" ← CURRENT", "").replace("← CURRENT", "")

        # Find first [ ] task and add ← CURRENT to it
        for i, line in enumerate(clean_lines):
            stripped = line.strip()
            if stripped.startswith("- [ ] **Task") and "← CURRENT" not in line:
                clean_lines[i] = line.rstrip().rstrip() + " ← CURRENT\n"
                break

        with open(pfile, "w", encoding="utf-8") as f:
            f.writelines(clean_lines)

    except Exception as e:
        print(f"⚠️ advance_progress selhal: {e}")


# ---------------------------------------------------------------------------
# Task definitions
# ---------------------------------------------------------------------------

def create_tasks(architect, coder, reviewer, integrator, project_path: str):
    """Create the 4-stage pipeline: Plan → Code → Review → Integrate."""

    specs = find_spec_file(project_path, "SPECS.md") or find_spec_file(project_path, "SPEC.md")
    progress_file_path = (
        os.path.join(project_path, "PROGRESS.md")
        if os.path.exists(os.path.join(project_path, "PROGRESS.md"))
        else os.path.join(project_path, "specs", "PROGRESS.md")
    )
    progress = extract_current_context(progress_file_path)
    current_task_name = read_current_task(progress_file_path)
    instructions = read_file(os.path.join(project_path, "instructions.md"))

    task_grounding = (
        f"══════════════════════════════════════════════════\n"
        f"⚠️  AKTUÁLNÍ TASK: \"{current_task_name}\"\n"
        f"Pracuješ POUZE na tomto tasku. Ignoruj ostatní.\n"
        f"══════════════════════════════════════════════════\n\n"
    )

    # LIMIT: Truncate specs to avoid huge prompts (max 3000 chars)
    if len(specs) > 3000:
        specs = specs[:3000] + "\n... (truncated) ..."
    
    # LIMIT: Truncate instructions (max 1000 chars)
    if len(instructions) > 1000:
        instructions = instructions[:1000] + "\n... (truncated) ..."

    rules_architect = load_rules(project_path)
    rules_coder = load_rules(project_path)
    rules_reviewer = load_rules(project_path)
    rules_integrator = load_rules(project_path, only=["general.md", "do-not.md"])

    specs_list = list_specs_files(project_path)
    output_dir = os.path.join(project_path, "output")
    os.makedirs(output_dir, exist_ok=True)

    file_path_hint = (
        f"IMPORTANT: When using file_reader, always use the full path, "
        f"e.g. '{project_path}/specs/technical.md'. "
        f"Do NOT use short paths like 'spec/' or 'specs/' without the project prefix."
    )

    # --- 1. ARCHITEKT (Plan) ---
    architect_task = Task(
        description=f"""{task_grounding}Analyzuj specifikaci projektu a vytvoř detailní technický plán
pro AKTUÁLNÍ task označený ← CURRENT v PROGRESS.md.

{file_path_hint}

PROGRESS.md (aktuální úkoly):
{progress}

SPECS.md (přehled projektu):
{specs}

Dostupné spec soubory (přečti pomocí file_reader):
{specs_list}

RULES:
{rules_architect}

Instrukce:
{instructions}

Tvoje úkoly:
1. Najdi aktuální task (← CURRENT) v PROGRESS.md
2. Přečti relevantní spec soubory
3. Rozlož task na subtasky — definuj PŘESNĚ:
   - Jaké soubory vytvořit/upravit (s cestami v {output_dir}/)
   - Interfaces and data structures (if the project requires them)
   - Závislosti mezi komponentami
   - Pořadí implementace
4. Vrať plán jako svůj výstup — systém ho uloží do {output_dir}/plan.md
   (NEPOUŽÍVEJ file_writer — nemáš ho k dispozici)
""",
        agent=architect,
        expected_output="Detailní technický plán s dekompozicí na subtasky, soubory a interfaces",
        output_file=os.path.join(output_dir, "plan.md"),
    )

    # --- 2. KODÉR (Implement) ---
    coder_task = Task(
        description=f"""{task_grounding}Implementuj kód přesně podle plánu od Architekta.

{file_path_hint}

PROGRESS.md:
{progress}

SPECS.md:
{specs}

Dostupné spec soubory:
{specs_list}

RULES:
{rules_coder}

Tvoje úkoly:
1. Přečti plán: {output_dir}/plan.md
2. Implementuj VŠECHNY soubory zmíněné v plánu
3. Dodržuj interfaces a typy definované Architektem
4. Piš KOMPLETNÍ soubory — nikdy nezkracuj

Pravidla pro file_writer:
- Vždy poskytni KOMPLETNÍ obsah souboru — nikdy nezkracuj
- Pokud je soubor příliš velký (SQL migrace), rozděl na více souborů
- Nikdy nevolej file_writer s prázdným content
- Vždy uveď BOTH file_path AND content
""",
        agent=coder,
        expected_output="Kompletně implementované soubory v output/ adresáři",
        context=[architect_task],
    )

    # --- 3. REVIEWER (QA) ---
    reviewer_task = Task(
        description=f"""{task_grounding}Zkontroluj kód od Kodéra pro task: {current_task_name}

⚠️  KRITICKÉ: Tvůj review MUSÍ obsahovat název tasku "{current_task_name}".
Pokud reviewuješ jiný task, je to CHYBA.

Zaměř se na to, co je potřeba pro dokončení tohoto konkrétního tasku.

{file_path_hint}

PROGRESS.md:
{progress}

RULES:
{rules_reviewer}

Pro aktuální seznam souborů v {output_dir}/ použij nástroj list_dir.

Tvoje úkoly:
1. Přečti plán: {output_dir}/plan.md
2. Přečti všechny nově vytvořené soubory v {output_dir}/ pomocí file_reader
3. Zkontroluj:
   - SECURITY: Does it meet security requirements from specs and rules?
   - FUNCTIONALITY: Is the implementation complete? Do imports/references match? Does it match the plan?
   - PERFORMANCE: Are there obvious performance problems?
   - KONVENCE: Dodržuje coding standards z rules?
4. Pokud najdeš KRITICKÉ problémy, vrať FAIL s popisem — Supervisor zajistí retry.
5. Vrať strukturovaný review jako svůj výstup.

⚠️  POVINNÝ FORMÁT VÝSTUPU:
Tvůj výstup MUSÍ začínat PŘESNĚ jedním z těchto řádků:
  PASS: {current_task_name}
  FAIL: {current_task_name}
Následovaný popisem. Pokud tento formát nedodržíš, Supervisor vynutí retry.
Příklad:
  PASS: {current_task_name}
  Kód splňuje všechny požadavky...
""",
        agent=reviewer,
        expected_output=f"Strukturovaný code review pro '{current_task_name}' — výstup MUSÍ začínat 'PASS: Task X.X' nebo 'FAIL: Task X.X' následovaný popisem",
        context=[coder_task],
    )

    # --- 4. INTEGRÁTOR (Assemble) ---
    integrator_task = Task(
        description=f"""{task_grounding}Finalizuj task — sjednoť kód, aktualizuj importy a ověř konzistenci.

{file_path_hint}

PROGRESS.md:
{progress}

RULES:
{rules_integrator}

Pro aktuální seznam souborů v {output_dir}/ použij nástroj list_dir.

Tvoje úkoly:
1. Přečti review od Reviewera
2. Přečti soubory v {output_dir}/ a ověř konzistenci
3. Update inter-file links (imports, exports, references) if needed
4. Aktualizuj routing pokud je potřeba
5. Aktualizuj README.md pokud je potřeba
6. Ověř, že všechny soubory jsou konzistentní a připravené k deploymentu

KRITICKÁ PRAVIDLA:
- NEMĚŇ PROGRESS.md! To dělá Supervisor automaticky.
- Tvůj výstup by měl být "OK" nebo popis zbývajících problémů.
- Pokud najdeš problémy s konzistencí, vrať je k Reviewerovi.

Pravidla pro file_writer:
- Vždy poskytni KOMPLETNÍ obsah souboru
- Nikdy nevolej file_writer s prázdným content
- Vždy uveď BOTH file_path AND content
""",
        agent=integrator,
        expected_output="Finalizované soubory a ověření konzistence",
        context=[reviewer_task],
    )

    return [architect_task, coder_task, reviewer_task, integrator_task]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _acquire_lock()

    try:
        _main_body()
    finally:
        _release_lock()


def _main_body():
    import argparse
    parser = argparse.ArgumentParser(description="Multiagent supervisor")
    parser.add_argument("project_name")
    parser.add_argument("--tasks", type=int, default=None,
                        help="Počet tasků ke zpracování (default: všechny zbývající)")
    args = parser.parse_args()
    project_name = args.project_name
    max_sequential = args.tasks if args.tasks is not None else 10_000

    project_path = os.path.join("projects", project_name)

    if not os.path.exists(project_path):
        print(f"❌ Projekt '{project_name}' neexistuje v {project_path}")
        sys.exit(1)

    specs_path = os.path.join(project_path, "SPECS.md")
    if not os.path.exists(specs_path):
        print(f"❌ Chybí {specs_path}")
        sys.exit(1)

    print(f"\n🚀 Spouštím multiagentní vývoj pro projekt: {project_name}")
    print(f"📁 Cesta: {project_path}\n")

    setup_telegram_listener()

    progress_file = find_progress_file(project_path)
    output_dir = os.path.join(project_path, "output")

    architect = create_architect_agent(project_path)
    coder = create_coder_agent(project_path, output_path=output_dir)
    reviewer = create_reviewer_agent(project_path, output_path=output_dir)
    integrator = create_integrator_agent(project_path, output_path=output_dir)

    agents_map = {
        "Architekt": architect,
        "Kodér": coder,
        "Reviewer": reviewer,
        "Integrátor": integrator,
    }

    # Periodically save usage in background thread
    import threading

    def _usage_saver():
        while True:
            try:
                save_usage(agents_map)
            except Exception:
                pass
            time.sleep(10)

    threading.Thread(target=_usage_saver, daemon=True).start()
    save_usage(agents_map)  # initial write

    _current_agent_log = {}
    def _step_callback(step_output):
        agent_role = (
            getattr(step_output, "agent_role", None)
            or getattr(step_output, "role", None)
            or getattr(getattr(step_output, "agent", None), "role", None)
            or (step_output.__class__.__name__ if step_output else "?")
        )
        _current_agent_log["active_agent"] = agent_role

    tasks_done = 0
    remaining = 0
    while tasks_done < max_sequential:
        current_task_name = read_current_task(progress_file)
        if current_task_name == "?":
            print("ℹ️  Žádné další tasky v PROGRESS.md.")
            break

        start_msg = (
            f"››› Začínám ›››\n"
            f"{current_task_name}\n"
        )
        send_telegram_message(start_msg)
        print(start_msg)

        tasks = create_tasks(architect, coder, reviewer, integrator, project_path)

        crew = Crew(
            agents=[architect, coder, reviewer, integrator],
            tasks=tasks,
            verbose=True,
            process=Process.sequential,
            step_callback=_step_callback,
        )

        print("=" * 60)
        print("🤖 AGENTI PRACUJÍ...")
        from models import AGENT_MODELS
        print(f"   Architekt ({AGENT_MODELS['architect']}) → Kodér ({AGENT_MODELS['coder']}) → Reviewer ({AGENT_MODELS['reviewer']}) → Integrátor ({AGENT_MODELS['integrator']})")
        print("=" * 60 + "\n")

        max_attempts = 5  # Increased from 3 to handle more transient failures
        task_succeeded = False
        for attempt in range(1, max_attempts + 1):
            try:
                result = crew.kickoff()

                print("\n" + "=" * 60)
                print("✅ HOTOVO!")
                print("=" * 60 + "\n")

                save_usage(agents_map)

                # ── Parse reviewer verdict ──────────────────────────
                # DŮLEŽITÉ: crew.kickoff() vrací výstup POSLEDNÍHO tasku
                # (Integrátor), ne Reviewera. Proto musíme číst tasks[2].output.
                reviewer_output = ""
                if len(tasks) > 2 and tasks[2].output:
                    reviewer_output = str(tasks[2].output)
                else:
                    # Fallback: pokud task output není dostupný, použij result
                    reviewer_output = str(result) if result else ""

                reviewer_text_upper = reviewer_output.upper()
                is_fail_verdict = "FAIL" in reviewer_text_upper

                # Validace — Reviewer reviewoval SPRÁVNÝ task?
                if not is_fail_verdict:
                    import re
                    task_id_match = re.search(r"Task\s+(\d+\.\d+)", current_task_name)
                    task_id = task_id_match.group(1) if task_id_match else None

                    if task_id and task_id not in reviewer_output:
                        print(f"⚠️  VALIDACE: Reviewer pravděpodobně reviewoval špatný task!")
                        print(f"   Očekáváno: {current_task_name} (id: {task_id})")
                        print(f"   Ve výstupu Reviewera nenalezeno.")
                        print(f"   Reviewer output (300 zn.): {reviewer_output[:300]}")
                        send_telegram_message(
                            f"⚠️ Reviewer reviewoval špatný task!\n"
                            f"Očekáváno: {current_task_name}\n"
                            f"Vynucen FAIL → retry"
                        )
                        is_fail_verdict = True
                # ── Konec reviewer validace ─────────────────────────

                # Audit log pro task výsledky
                try:
                    output_dir = os.path.join(project_path, "output")
                    audit_entry = {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "task": current_task_name,
                        "attempt": attempt,
                        "verdict": "FAIL" if is_fail_verdict else "PASS",
                        "result_preview": str(result)[:500] if result else None,
                        "output_files": sorted(os.listdir(output_dir)) if os.path.exists(output_dir) else [],
                    }
                    audit_path = "logs/tasks_audit.jsonl"
                    os.makedirs("logs", exist_ok=True)
                    with open(audit_path, "a") as f:
                        f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
                except Exception as e:
                    pass  # Audit log je best-effort

                # Supervisor sám posune PROGRESS.md — ale JEN když je PASS
                # Pokud je FAIL, task zůstane v [ ] a ← CURRENT zůstane tam
                if not is_fail_verdict:
                    # Output sanity check: ověř, že očekávané soubory existují
                    output_dir = os.path.join(project_path, "output")
                    expected_outputs_missing = False
                    
                    if "image" in current_task_name.lower() or "Generate" in current_task_name:
                        images_dir = os.path.join(output_dir, "public", "images")
                        if not os.path.exists(images_dir) or not os.listdir(images_dir):
                            print(f"⚠️  OUTPUT CHECK: Task {current_task_name} měl generovat obrázky, ale images/ je prázdný!")
                            expected_outputs_missing = True
                    
                    if expected_outputs_missing:
                        print(f"   Vynucen FAIL → retry")
                        is_fail_verdict = True
                    else:
                        advance_progress(progress_file, current_task_name)
                        remaining = count_remaining(progress_file)
                        next_task = read_current_task(progress_file)

                        if remaining > 0:
                            next_line = f"Další: → {next_task}" if next_task and next_task != "?" else ""
                            message = (
                                f"✓ Hotovo:\n"
                                f" ⌊ {current_task_name}\n"
                                f" ⌊ {next_line}\n"
                                f" Zbývá {remaining} tasků"
                            )
                        else:
                            output_path = os.path.join(project_path, "output")
                            message = (
                                f"🎉 Projekt '{project_name}' je KOMPLETNĚ hotový!\n"
                                f"📁 Soubory: {os.path.abspath(output_path)}"
                            )
                        send_telegram_message(message)
                        print(message)
                        tasks_done += 1
                        task_succeeded = True
                        break
                else:
                    # Task FAILED — zkusit znovu v rámci session (max 3 pokusy)
                    print(f"⚠️  Task {current_task_name} FAILED review — automaticky zkouším znovu...")
                    print(f"   Pokus {attempt}/{max_attempts}\n")

                    if attempt < max_attempts:
                        # Vytvořit nový crew a zkusit znovu (Kodér opraví na základě Reviewerova feedbacku)
                        wait = 5
                        print(f"⏳ Čekám {wait}s před retry...\n")
                        time.sleep(wait)

                        tasks = create_tasks(architect, coder, reviewer, integrator, project_path)
                        crew = Crew(
                            agents=[architect, coder, reviewer, integrator],
                            tasks=tasks,
                            verbose=True,
                            process=Process.sequential,
                            step_callback=_step_callback,
                        )
                        # continue = zkusit znovu z for loopu
                        continue
                    else:
                        # Vyčerpáni všechny pokusy — zastavit se
                        message = (
                            f"✕ Task FAILED po {max_attempts} pokusech: {current_task_name}\n"
                            f" › Vrácen Kodérovi — prosím, zkontroluj manuálně.\n"
                            f" › Oprav a spusť supervisor znovu."
                        )
                        send_telegram_message(message)
                        print(message)
                        break

            except Exception as e:
                error_str = str(e)

                is_rate_limit = "429" in error_str or "rate_limit" in error_str
                is_transient = (
                    is_rate_limit
                    or "timeout" in error_str.lower()
                    or "connection" in error_str.lower()
                    or "503" in error_str
                    or "502" in error_str
                    or "UNAVAILABLE" in error_str
                    or "None or empty" in error_str
                    or "Invalid response from LLM" in error_str
                    or "overloaded" in error_str.lower()
                )

                if is_transient and attempt < max_attempts:
                    wait = min(10 * attempt, 60)
                    msg = (
                        f"▶ Přechodná chyba (pokus {attempt}/{max_attempts}), "
                        f"čekám {wait}s...\n{error_str[:200]}"
                    )
                    print(msg)
                    send_telegram_message(msg)
                    time.sleep(wait)
                    tasks = create_tasks(architect, coder, reviewer, integrator, project_path)
                    crew = Crew(
                        agents=[architect, coder, reviewer, integrator],
                        tasks=tasks,
                        verbose=True,
                        process=Process.sequential,
                        step_callback=_step_callback,
                    )
                    continue

                error_message = f"❌ Fatální chyba (pokus {attempt}): {error_str[:500]}"
                print(error_message)
                save_usage(agents_map)
                send_telegram_message(error_message)
                sys.exit(1)

        if not task_succeeded:
            break

        if remaining == 0:
            break


if __name__ == "__main__":
    main()
