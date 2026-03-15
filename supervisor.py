#!/usr/bin/env python3
"""
Multiagent Development Supervisor
4-agent workflow: Architekt → Kodér → Reviewer → Integrátor
With proper FAIL handling - Integrator only runs after PASS from Reviewer.
With retry feedback - Coder receives Reviewer's FAIL output on retry.
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
import litellm
litellm.num_retries = 5
litellm.retry_after = 10

os.environ["LITELLM_NUM_RETRIES"] = "5"
os.environ["LITELLM_RETRY_AFTER"] = "10"

# ---------------------------------------------------------------------------
# Single-instance guard
# ---------------------------------------------------------------------------
_LOCK_FILE = "/tmp/multiagent_supervisor.lock"

def _acquire_lock() -> None:
    if os.path.exists(_LOCK_FILE):
        with open(_LOCK_FILE) as f:
            old_pid = f.read().strip()
        if old_pid and os.path.exists(f"/proc/{old_pid}"):
            print(f"❌ Supervisor již běží (PID {old_pid}). Ukonči ho nejdřív.")
            print(f"   kill {old_pid}")
            sys.exit(1)
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


def extract_fail_issues(reviewer_output: str, max_chars: int = 1500) -> str:
    """Extrahuj jen strukturované problémy z reviewer outputu.
    
    Vrací zkrácený, čistý seznam issues místo celého raw outputu.
    """
    if not reviewer_output:
        return "(žádný feedback)"
    
    lines = reviewer_output.strip().splitlines()
    issues = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("-", "*", "•")) or (
            len(stripped) > 1 and stripped[0].isdigit() and "." in stripped[:4]
        ):
            issues.append(stripped)
    
    if issues:
        result = "\n".join(issues)
        return result[:max_chars]
    
    upper = reviewer_output.upper()
    fail_idx = upper.find("FAIL")
    if fail_idx >= 0:
        return reviewer_output[fail_idx:fail_idx + max_chars].strip()
    
    return reviewer_output[:max_chars].strip()


USAGE_FILE = "logs/usage.json"

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
    "gemini-2.5-flash":             {"input": 0.15, "output": 0.60},
    "gemini/gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash-lite":        {"input": 0.075, "output": 0.30},
    "gemini/gemini-3.1-flash-lite": {"input": 0.25,  "output": 1.50},
    "gemini-3.1-flash-lite":        {"input": 0.25,  "output": 1.50},
})


def save_usage(agents_map: dict, usage_file: str = USAGE_FILE):
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
    for candidate in [
        os.path.join(project_path, "PROGRESS.md"),
        os.path.join(project_path, "specs", "PROGRESS.md"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return os.path.join(project_path, "specs", "PROGRESS.md")


def read_current_task(pfile: str) -> str:
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
                    if stripped.startswith("- [ ]"):
                        return name
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
    if not completed_task or completed_task == "?":
        return
    try:
        with open(pfile, encoding="utf-8") as f:
            lines = f.readlines()

        import re as _re
        seen_phases: set[str] = set()
        clean_lines = []
        for line in lines:
            phase_m = _re.match(r"^## Phase \d+:", line)
            if phase_m:
                key = phase_m.group(0)
                if key in seen_phases:
                    while clean_lines and clean_lines[-1].strip() in ("---", ""):
                        clean_lines.pop()
                    break
                seen_phases.add(key)
            clean_lines.append(line)

        for i, line in enumerate(clean_lines):
            if f"**{completed_task}**" in line and "← CURRENT" in line:
                clean_lines[i] = line.replace("- [ ]", "- [x]").replace(" ← CURRENT", "").replace("← CURRENT", "")

        for i, line in enumerate(clean_lines):
            if "← CURRENT" in line and not line.strip().startswith(">"):
                clean_lines[i] = line.replace(" ← CURRENT", "").replace("← CURRENT", "")

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

def create_architect_task(architect, project_path: str, output_dir: str, current_task_name: str):
    """Create architect task - runs ONCE per task."""
    specs = find_spec_file(project_path, "SPECS.md") or find_spec_file(project_path, "SPEC.md")
    progress_file_path = (
        os.path.join(project_path, "PROGRESS.md")
        if os.path.exists(os.path.join(project_path, "PROGRESS.md"))
        else os.path.join(project_path, "specs", "PROGRESS.md")
    )
    progress = extract_current_context(progress_file_path)
    instructions = read_file(os.path.join(project_path, "instructions.md"))

    task_grounding = (
        f"══════════════════════════════════════════════════\n"
        f"⚠️  AKTUÁLNÍ TASK: \"{current_task_name}\"\n"
        f"Pracuješ POUZE na tomto tasku. Ignoruj ostatní.\n"
        f"══════════════════════════════════════════════════\n\n"
    )

    if len(specs) > 3000:
        specs = specs[:3000] + "\n... (truncated) ..."
    if len(instructions) > 1000:
        instructions = instructions[:1000] + "\n... (truncated) ..."

    rules_architect = load_rules(project_path)
    specs_list = list_specs_files(project_path)

    file_path_hint = (
        f"IMPORTANT: When using file_reader, always use the full path, "
        f"e.g. '{project_path}/specs/technical.md'. "
        f"Do NOT use short paths like 'spec/' or 'specs/' without the project prefix."
    )

    return Task(
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


def create_coder_task(coder, project_path: str, output_dir: str, current_task_name: str, architect_task, previous_reviewer_feedback: str = ""):
    """Create coder task - runs after architect. On retry, includes previous reviewer feedback."""
    specs = find_spec_file(project_path, "SPECS.md") or find_spec_file(project_path, "SPEC.md")
    progress_file_path = (
        os.path.join(project_path, "PROGRESS.md")
        if os.path.exists(os.path.join(project_path, "PROGRESS.md"))
        else os.path.join(project_path, "specs", "PROGRESS.md")
    )
    progress = extract_current_context(progress_file_path)

    task_grounding = (
        f"══════════════════════════════════════════════════\n"
        f"⚠️  AKTUÁLNÍ TASK: \"{current_task_name}\"\n"
        f"Pracuješ POUZE na tomto tasku. Ignoruj ostatní.\n"
        f"══════════════════════════════════════════════════\n\n"
    )

    if len(specs) > 3000:
        specs = specs[:3000] + "\n... (truncated) ..."

    rules_coder = load_rules(project_path)
    specs_list = list_specs_files(project_path)

    file_path_hint = (
        f"IMPORTANT: When using file_reader, always use the full path, "
        f"e.g. '{project_path}/specs/technical.md'. "
        f"Do NOT use short paths like 'spec/' or 'specs/' without the project prefix."
    )

    # Add previous reviewer feedback if this is a retry
    retry_feedback = ""
    if previous_reviewer_feedback:
        retry_feedback = f"""
════════════════════════════════════════════════════════
⚠️  RETRY — Předchozí pokus selhal. Oprav TYTO problémy:
════════════════════════════════════════════════════════

{previous_reviewer_feedback}

════════════════════════════════════════════════════════
INSTRUKCE:
- Oprav KAŽDÝ bod výše
- Po opravě VŽDY spusť file_size_check na každý upravený soubor
- NEPIŠ znovu soubory které jsou v pořádku — oprav JEN problematické
════════════════════════════════════════════════════════

"""

    return Task(
        description=f"""{task_grounding}Implementuj kód přesně podle plánu od Architekta.

{file_path_hint}

{retry_feedback}PROGRESS.md:
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


def create_reviewer_task(reviewer, project_path: str, output_dir: str, current_task_name: str):
    """Create reviewer task - runs after coder."""
    progress_file_path = (
        os.path.join(project_path, "PROGRESS.md")
        if os.path.exists(os.path.join(project_path, "PROGRESS.md"))
        else os.path.join(project_path, "specs", "PROGRESS.md")
    )
    progress = extract_current_context(progress_file_path)

    task_grounding = (
        f"══════════════════════════════════════════════════\n"
        f"⚠️  AKTUÁLNÍ TASK: \"{current_task_name}\"\n"
        f"Pracuješ POUZE na tomto tasku. Ignoruj ostatní.\n"
        f"══════════════════════════════════════════════════\n\n"
    )

    rules_reviewer = load_rules(project_path)

    file_path_hint = (
        f"IMPORTANT: When using file_reader, always use the full path, "
        f"e.g. '{project_path}/specs/technical.md'. "
        f"Do NOT use short paths like 'spec/' or 'specs/' without the project prefix."
    )

    return Task(
        description=f"""{task_grounding}Zkontroluj kód od Kodéra pro task: {current_task_name}

POVINNÉ KROKY (musíš provést VŠECHNY):
1. Použij list_dir na "{output_dir}/" — podívej se jaké soubory existují
2. Přečti plán: {output_dir}/plan.md pomocí file_reader
3. Přečti KAŽDÝ nově vytvořený soubor v {output_dir}/ pomocí file_reader
4. Použij directory_size_check na "{output_dir}/" — ověř limity velikostí
5. Teprve POTOM vydej verdikt PASS nebo FAIL

Pokud vynecháš jakýkoli krok, tvůj review je NEPLATNÝ.

⚠️  KRITICKÉ: Tvůj review MUSÍ obsahovat název tasku "{current_task_name}".
Pokud reviewuješ jiný task, je to CHYBA.

Zaměř se na to, co je potřeba pro dokončení tohoto konkrétního tasku.

{file_path_hint}

PROGRESS.md:
{progress}

RULES:
{rules_reviewer}

Tvoje úkoly:
1. Přečti plán: {output_dir}/plan.md
2. Přečti všechny nově vytvořené soubory v {output_dir}/ pomocí file_reader
3. Zkontroluj:
   - SECURITY: Does it meet security requirements from specs and rules?
   - FUNCTIONALITY: Is the implementation complete? Do imports/references match? Does it match the plan?
   - PERFORMANCE: Are there obvious performance problems?
   - FILE SIZE: Are all files within limits (200 lines backend, 150 lines frontend)?
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
    )


def create_integrator_task(integrator, project_path: str, output_dir: str, current_task_name: str, reviewer_task):
    """Create integrator task - runs ONLY after PASS from reviewer."""
    progress_file_path = (
        os.path.join(project_path, "PROGRESS.md")
        if os.path.exists(os.path.join(project_path, "PROGRESS.md"))
        else os.path.join(project_path, "specs", "PROGRESS.md")
    )
    progress = extract_current_context(progress_file_path)

    task_grounding = (
        f"══════════════════════════════════════════════════\n"
        f"⚠️  AKTUÁLNÍ TASK: \"{current_task_name}\"\n"
        f"Pracuješ POUZE na tomto tasku. Ignoruj ostatní.\n"
        f"══════════════════════════════════════════════════\n\n"
    )

    rules_integrator = load_rules(project_path, only=["general.md", "do-not.md"])

    file_path_hint = (
        f"IMPORTANT: When using file_reader, always use the full path, "
        f"e.g. '{project_path}/specs/technical.md'. "
        f"Do NOT use short paths like 'spec/' or 'specs/' without the project prefix."
    )

    return Task(
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


def check_reviewer_verdict(reviewer_output: str, current_task_name: str) -> tuple[bool, str]:
    """Check if reviewer output contains PASS or FAIL verdict.
    
    Kontroluje POUZE první neprázdný řádek outputu — ignoruje PASS/FAIL
    uvnitř textu review.
    
    Returns:
        (is_pass: bool, reason: str)
    """
    if not reviewer_output:
        return False, "Empty reviewer output"
    
    for line in reviewer_output.strip().splitlines():
        stripped = line.strip()
        if stripped:
            first_line = stripped.upper()
            break
    else:
        return False, "Reviewer output is empty or whitespace only"
    
    import re
    task_id_match = re.search(r"Task\s+(\d+\.\d+)", current_task_name)
    task_id = task_id_match.group(1) if task_id_match else None
    
    is_pass = first_line.startswith("PASS")
    is_fail = first_line.startswith("FAIL")
    
    if is_fail:
        return False, "Reviewer returned FAIL"
    
    if is_pass:
        if task_id and task_id not in reviewer_output[:200]:
            return False, f"Reviewer PASS but task ID '{task_id}' not found in first 200 chars"
        return True, "Reviewer returned PASS"
    
    return False, f"Reviewer output does not start with PASS or FAIL. First line: '{first_line[:80]}'"


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
    save_usage(agents_map)

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

        start_msg = f"››› Začínám ›››\n{current_task_name}\n"
        send_telegram_message(start_msg)
        print(start_msg)

        # ── PHASE 1: ARCHITECT (runs once) ─────────────────────────────────────
        print("=" * 60)
        print("📐 FÁZE 1: ARCHITEKT")
        print("=" * 60 + "\n")
        
        architect_task = create_architect_task(architect, project_path, output_dir, current_task_name)
        
        crew_architect = Crew(
            agents=[architect],
            tasks=[architect_task],
            verbose=True,
            process=Process.sequential,
            step_callback=_step_callback,
        )
        
        try:
            crew_architect.kickoff()
        except Exception as e:
            error_message = f"❌ Architekt selhal: {str(e)[:500]}"
            print(error_message)
            send_telegram_message(error_message)
            sys.exit(1)
        
        save_usage(agents_map)

        # ── PHASE 2: CODER + REVIEWER LOOP (retry until PASS) ───────────────────
        max_attempts = 5
        reviewer_passed = False
        previous_reviewer_feedback = ""
        
        for attempt in range(1, max_attempts + 1):
            print("\n" + "=" * 60)
            print(f"🔄 FÁZE 2: KODÉR + REVIEWER (pokus {attempt}/{max_attempts})")
            print("=" * 60 + "\n")
            
            # Pass previous reviewer feedback to coder on retry
            coder_task = create_coder_task(coder, project_path, output_dir, current_task_name, architect_task, previous_reviewer_feedback)
            
            # 2a: Kodér pracuje samostatně
            crew_coder = Crew(
                agents=[coder],
                tasks=[coder_task],
                verbose=True,
                process=Process.sequential,
                step_callback=_step_callback,
            )
            
            try:
                crew_coder.kickoff()
            except Exception as e:
                error_str = str(e)
                is_transient = (
                    "429" in error_str or "rate_limit" in error_str
                    or "timeout" in error_str.lower()
                    or "connection" in error_str.lower()
                    or "503" in error_str or "502" in error_str
                    or "UNAVAILABLE" in error_str
                    or "None or empty" in error_str
                )
                
                if is_transient and attempt < max_attempts:
                    wait = min(10 * attempt, 60)
                    print(f"▶ Přechodná chyba, čekám {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    error_message = f"❌ Fatální chyba (Kodér): {error_str[:500]}"
                    print(error_message)
                    send_telegram_message(error_message)
                    sys.exit(1)
            
            save_usage(agents_map)
            
            # 2b: Reviewer pracuje samostatně — čte soubory z disku, ne z context
            reviewer_task = create_reviewer_task(reviewer, project_path, output_dir, current_task_name)
            
            crew_reviewer = Crew(
                agents=[reviewer],
                tasks=[reviewer_task],
                verbose=True,
                process=Process.sequential,
                step_callback=_step_callback,
            )
            
            try:
                crew_reviewer.kickoff()
            except Exception as e:
                error_str = str(e)
                is_transient = (
                    "429" in error_str or "rate_limit" in error_str
                    or "timeout" in error_str.lower()
                    or "connection" in error_str.lower()
                    or "503" in error_str or "502" in error_str
                    or "UNAVAILABLE" in error_str
                    or "None or empty" in error_str
                )
                
                if is_transient and attempt < max_attempts:
                    wait = min(10 * attempt, 60)
                    print(f"▶ Přechodná chyba, čekám {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    error_message = f"❌ Fatální chyba (Reviewer): {error_str[:500]}"
                    print(error_message)
                    send_telegram_message(error_message)
                    sys.exit(1)
            
            save_usage(agents_map)
            
            # Check reviewer verdict
            reviewer_output = ""
            if reviewer_task.output:
                reviewer_output = str(reviewer_task.output)
            
            is_pass, reason = check_reviewer_verdict(reviewer_output, current_task_name)
            
            if is_pass:
                print(f"\n✅ Reviewer: PASS - {reason}")
                reviewer_passed = True
                break
            else:
                print(f"\n⚠️  Reviewer: FAIL - {reason}")
                print(f"   Pokus {attempt}/{max_attempts}")
                
                # Store reviewer feedback for next retry (extracted and condensed)
                previous_reviewer_feedback = extract_fail_issues(reviewer_output, max_chars=1500)
                
                # Na 3+ pokusu přidej eskalační instrukci
                if attempt >= 3:
                    previous_reviewer_feedback = (
                        f"⚠️ POKUS {attempt}/{max_attempts} — předchozí pokusy selhaly na STEJNÉM problému.\n"
                        f"NEOPAKUJ stejný přístup. Použij ZÁSADNĚ JINÝ způsob řešení.\n"
                        f"Pokud je soubor příliš velký, rozděl ho na víc souborů.\n"
                        f"Pokud chybí import, přidej ho. Pokud je špatná logika, přepiš ji.\n\n"
                        f"KONKRÉTNÍ PROBLÉMY K OPRAVĚ:\n"
                        f"{extract_fail_issues(reviewer_output, max_chars=1000)}"
                    )
                
                if attempt < max_attempts:
                    wait = 5
                    print(f"⏳ Čekám {wait}s před retry...\n")
                    time.sleep(wait)
                else:
                    message = (
                        f"✕ Task FAILED po {max_attempts} pokusech: {current_task_name}\n"
                        f" › Vrácen Kodérovi — prosím, zkontroluj manuálně.\n"
                        f" › Oprav a spusť supervisor znovu."
                    )
                    send_telegram_message(message)
                    print(message)
                    return  # Exit - manual intervention needed
        
        if not reviewer_passed:
            return  # Exit - already sent failure message
        
        # ── PHASE 3: INTEGRATOR (runs only after PASS) ───────────────────────────
        print("\n" + "=" * 60)
        print("🔗 FÁZE 3: INTEGRÁTOR")
        print("=" * 60 + "\n")
        
        integrator_task = create_integrator_task(integrator, project_path, output_dir, current_task_name, reviewer_task)
        
        crew_integrator = Crew(
            agents=[integrator],
            tasks=[integrator_task],
            verbose=True,
            process=Process.sequential,
            step_callback=_step_callback,
        )
        
        try:
            crew_integrator.kickoff()
        except Exception as e:
            error_message = f"❌ Integrátor selhal: {str(e)[:500]}"
            print(error_message)
            send_telegram_message(error_message)
            sys.exit(1)
        
        save_usage(agents_map)
        
        # ── SUCCESS: Advance progress ───────────────────────────────────────────
        print("\n" + "=" * 60)
        print("✅ HOTOVO!")
        print("=" * 60 + "\n")
        
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
            message = (
                f"🎉 Projekt '{project_name}' je KOMPLETNĚ hotový!\n"
                f"📁 Soubory: {os.path.abspath(output_dir)}"
            )
        send_telegram_message(message)
        print(message)
        tasks_done += 1

        if remaining == 0:
            break


if __name__ == "__main__":
    main()
