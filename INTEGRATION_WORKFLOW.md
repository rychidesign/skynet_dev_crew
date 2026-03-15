# Multiagent Integration Workflow – AKTUALIZOVÁNO 2025-03-14

## Historie změn

| Datum | Verze | Změna |
|-------|-------|-------|
| 2025-03-15 | 3.2.1 | **HARDENING v3.2**: Guardrails extrahovány do `guardrails.py`, plural `guardrails=[]` místo singular `guardrail=`, strukturované JSONL logování (`log_retry_event()`), 5 typů událostí (PASS, FAIL, ESCALATION, EMPTY_OUTPUT, EXHAUSTED), rozšířené indikátory tool evidence. |
| 2025-03-15 | 3.2 | **Guardrails & Orchestration Refactoring**: Task Guardrail pro Reviewer validaci, `guardrail_max_retries=2`, fallback logging s Telegram notifikací, extrahované orchestrace funkce (`run_architect_phase()`, `run_code_review_phase()`, `run_integrator_phase()`, `_is_transient_error()`), `_main_body()` zredukováno z ~200 na ~50 řádků. |
| 2025-03-15 | 3.1 | **Crew Separation**: Kodér a Reviewer odděleny do nezávislých Crews. Reviewer čte soubory z disku (ne z kontextu). `extract_fail_issues()` zkracuje feedback na 1.5k znaků. Robustní `check_reviewer_verdict()` kontroluje jen první řádek. Escalation instrukce při 3+ retry pokusech. |
| 2025-03-14 | 3.0 | **3-fázové workflow**: Integrátor běží jen po PASS od Reviewera. Retry smyčka pro Kodér+Reviewer. Nové nástroje pro kontrolu délky souborů. |
| 2025-03-11 | 2.0 | Přidán task grounding, validace výstupu, output sanity check, audit log |
| Původní | 1.0 | Init: Retry loop, Supervisor-driven progress |

---

## ⚠️ PROBLÉM VYŘEŠEN (v3.0): Integrátor se spouštěl i po FAIL

**Původní problém:**
- Všichni 4 agenti běželi sekvenčně: `Architekt → Kodér → Reviewer → Integrátor`
- Integrátor se spustil i když Reviewer vrátil FAIL
- Při retry se spustili všichni agenti znovu (neefektivní)

**Příklad chyby:**
```
Run 1: Architekt → Kodér → Reviewer (FAIL) → Integrátor (zbytečně spuštěn!)
Retry: Architekt → Kodér → Reviewer → Integrátor (všichni znovu)
```

**Řešení (v3.0):**
- **3-fázové workflow** místo lineárního
- **Integrátor běží jen po PASS** od Reviewera
- **Retry smyčka** jen pro Kodér+Reviewer (max 5 pokusů)
- **Architekt běží jen jednou**

---

## Architecture: 3-Phase Workflow (v3.2.1)

```
┌─────────────────────────────────────────────────────────────────┐
│                      SUPERVISOR (v3.2.1)                        │
│                                                                 │
│  ══════════════════════════════════════════════════════════    │
│  FÁZE 1: ARCHITEKT (spustí se jednou)                          │
│  ══════════════════════════════════════════════════════════    │
│  - Čte PROGRESS.md, SPECS.md, rules/                           │
│  - Vytvoří technický plán v output/plan.md                    │
│  - Běží POUZE JEDNOU (ne při retry)                           │
│  - Orchestrace: run_architect_phase()                         │
│                                                                 │
│  ══════════════════════════════════════════════════════════    │
│  FÁZE 2: KODÉR + REVIEWER (smyčka s retry)                    │
│  ══════════════════════════════════════════════════════════    │
│  NOVÉ (v3.1): Oddělené Crews                                   │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │  CODER CREW     │    │  REVIEWER CREW  │                   │
│  │  (samostatný)   │───▶│  (samostatný)   │                   │
│  │                 │    │  Čte z DISKU    │                   │
│  └─────────────────┘    └─────────────────┘                   │
│                                                                 │
│  NOVÉ (v3.2): Guardrail validace (guardrails.py)              │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ validate_reviewer_verdict_format()                      │  │
│  │ - Kontroluje PASS/FAIL na prvním řádku                  │  │
│  │                                                         │  │
│  │ validate_reviewer_mentions_tools()                      │  │
│  │ - Kontroluje evidence použití list_dir                  │  │
│  │ - Kontroluje evidence použití size_check                │  │
│  │                                                         │  │
│  │ guardrails=[...] (sekvenční validace)                   │  │
│  │ guardrail_max_retries=2                                 │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│  for attempt in range(1, max_attempts+1):                     │
│      Kodér → Implementuje podle plánu                         │
│      Reviewer → Kontroluje kód (čte z disku)                  │
│      Guardrail → Validuje výstup                              │
│      if PASS: break → pokračuj na FÁZE 3                      │
│      if FAIL: extract_fail_issues() → retry                   │
│      if 3+ attempts: Escalation instrukce                     │
│                                                                 │
│  ══════════════════════════════════════════════════════════    │
│  FÁZE 3: INTEGRÁTOR (jen po PASS od Reviewera)                │
│  ══════════════════════════════════════════════════════════    │
│  - Sjednotí kód, aktualizuje importy                          │
│  - Ověří konzistenci                                          │
│  - Běží JEN KDYŽ Reviewer vrátil PASS                          │
│  - Orchestrace: run_integrator_phase()                        │
│                                                                 │
│  ══════════════════════════════════════════════════════════    │
│  SUCCESS: advance_progress() → [x] & ← move to next task      │
│  ══════════════════════════════════════════════════════════    │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ PROBLÉM VYŘEŠEN (v3.1): Kodér↔Reviewer nekonečná smyčka

**Původní problém:**
- Kodér a Reviewer běželi ve stejném Crew kontextu
- Reviewer dostával celý kontext od Kodéra (velké token využití)
- Feedback nebyl strukturovaný → dlouhé, nepřehledné zprávy
- `check_reviewer_verdict()` hledal PASS/FAIL kdekoliv v textu (falešné pozitivy)

**Řešení (v3.1):**
- **Oddělené Crews**: Kodér Crew a Reviewer Crew jsou nyní nezávislé
- **Reviewer čte z disku**: Místo kontextu od Kodéra čte Reviewer soubory přímo z disku
- **`extract_fail_issues()`**: Zkracuje FAIL feedback na max 1.5k znaků
- **Robustní `check_reviewer_verdict()`**: Kontroluje JEN první řádek výstupu
- **Escalation instrukce**: Při 3+ retry pokusech dostane Kodér speciální instrukce

---

## ⚠️ PROBLÉM VYŘEŠEN (v3.2): Guardrails & Orchestration Refactoring

**Původní problém:**
- Reviewer mohl vrátit nevalidní výstup (bez PASS/FAIL)
- Reviewer mohl vrátit PASS bez tool usage evidence
- Prázdny výstup od Reviewera nebyl ošetřen
- `_main_body()` byla ~200 řádků (špatná čitelnost)

**Řešení (v3.2):**
- **Extrahované guardrails do `guardrails.py`**:
  ```python
  # guardrails.py - separátní modul
  validate_reviewer_verdict_format()  # PASS/FAIL na prvním řádku
  validate_reviewer_mentions_tools()   # evidence použití nástrojů
  ```
- **Plural `guardrails=[]` místo singular `guardrail=`**:
  ```python
  reviewer_task = Task(
      ...,
      guardrails=[
          validate_reviewer_verdict_format,
          validate_reviewer_mentions_tools,
      ],
      guardrail_max_retries=2,
  )
  ```
- **Strukturované JSONL logování** (`logs/retry_events.jsonl`):
  - 5 typů událostí: PASS, FAIL, ESCALATION, EMPTY_OUTPUT, EXHAUSTED
  - Timestamp, task name, attempt, max_attempts, details
- **Fallback logging**: Prázdny výstup → log + Telegram notifikace
- **Extrahované funkce**:
  ```python
  run_architect_phase()      # FÁZE 1
  run_code_review_phase()    # FÁZE 2 (s retry loop)
  run_integrator_phase()     # FÁZE 3
  _is_transient_error()      # Detekce dočasných chyb
  log_retry_event()          # Strukturované logování
  ```
- **`_main_body()` zredukováno**: z ~200 na ~50 řádků

---

## Nové nástroje pro kontrolu délky souborů (v3.0)

### FileSizeCheckTool
Kontroluje délku jednotlivých souborů:
- Backend soubory (.py, .go, .rs, .java, .rb, .php): **max 200 řádků**
- Frontend soubory (.tsx, .ts, .jsx, .js, .vue, .svelte, .css): **max 150 řádků**

### DirectorySizeCheckTool
Kontroluje všechny soubory v adresáři najednou.

### Integrace s agenty:
- **Kodér**: Používá `file_size_check` PŘED odesláním kódu
- **Reviewer**: Používá `directory_size_check` PŘED vydáním PASS

---

## Clear Role Definition

### 🏛️ Architekt
- **Role:** Plan
- **Task:** Create detailed implementation plan
- **Progress.md:** ❌ DO NOT TOUCH
- **Task grounding:** Dostává explicitní "AKTUÁLNÍ TASK: X"
- **On Retry:** NEBĚŽÍ ZNOVU - plán je už vytvořen

### 💻 Kodér
- **Role:** Implement
- **Task:** Write code according to plan
- **Progress.md:** ❌ DO NOT TOUCH
- **Task grounding:** Dostává explicitní "AKTUÁLNÍ TASK: X"
- **On Retry:** Čte Reviewerův FAIL feedback a opravuje
- **File Size:** MUSÍ použít `file_size_check` před odesláním
- **🆕 v3.1:** Běží v SAMOSTATNÉM Crew (odděleno od Reviewera)
- **🆕 v3.1:** Při 3+ retry dostane escalation instrukce
- **🆕 v3.1:** FAIL feedback zkrácen na 1.5k znaků (`extract_fail_issues()`)

### 🔍 Reviewer
- **Role:** QA / Security / Code Review
- **Output:** Structured review with verdict: **PASS** or **FAIL**
- **Progress.md:** ❌ DO NOT TOUCH
- **Task grounding:** Dostává explicitní "AKTUÁLNÍ TASK: X"
- **Validace:** Supervisor ověřuje, že output obsahuje správný task ID
- **File Size:** MUSÍ použít `directory_size_check` před PASS
- **⚠️ IMPORTANT:** Must start output with **"PASS:"** or **"FAIL:"**
- **🆕 v3.1:** Běží v SAMOSTATNÉM Crew (čte soubory z disku, ne z kontextu)
- **🆕 v3.2.1:** Guardrails validují výstup (`guardrails.py`)
  - `validate_reviewer_verdict_format()` — PASS/FAIL formát
  - `validate_reviewer_mentions_tools()` — evidence použití nástrojů
- **🆕 v3.2.1:** `guardrails=[...]` — sekvenční validace (plural)
- **🆕 v3.2.1:** `guardrail_max_retries=2` — max 2 interní retry

### 🔗 Integrátor
- **Role:** Assembly & Final Checks
- **Task:** Update imports, routing, verify consistency
- **Progress.md:** ❌ **ABSOLUTELY DO NOT TOUCH**
- **Task grounding:** Dostává explicitní "AKTUÁLNÍ TASK: X"
- **Graceful exit:** Musí dokončit VŠECHNY tool cally před finální odpovědí
- **⚠️ NOVÉ:** Běží JEN PO PASS od Reviewera

### 👑 Supervisor
- **Role:** Orchestrator + Phase Manager
- **Task:** Manage 3-phase workflow, validate outputs, task state
- **Progress.md:** ✅ **ONLY SUPERVISOR MODIFIES IT**

---

## Workflow Example: Task with Validation (v3.0)

**Task 2.4: Generate hero + service images**

```
Supervisor reads:  [ ] ← CURRENT Task 2.4: Generate hero + service images

═══════════════════════════════════════════════════════════════
FÁZE 1: ARCHITEKT (spustí se jednou)
═══════════════════════════════════════════════════════════════
  Architekt → Plan (image generation prompts)
  → Uloženo do output/plan.md

═══════════════════════════════════════════════════════════════
FÁZE 2: KODÉR + REVIEWER (smyčka s retry)
═══════════════════════════════════════════════════════════════

  Pokus 1:
    Kodér → Calls image_generator tool
    Reviewer → FAIL: "Images not generated - no output directory"
    → Retry (čeká 5s)

  Pokus 2:
    [FRESH TASKS REGENERATED]
    Kodér → Generates images, saves to output/public/images/
    Reviewer → PASS: "All files created, sizes OK"
    → Konec smyčky

═══════════════════════════════════════════════════════════════
FÁZE 3: INTEGRÁTOR (jen po PASS)
═══════════════════════════════════════════════════════════════
  Integrátor → Verifies files exist, checks imports
  → "OK"

═══════════════════════════════════════════════════════════════
SUCCESS: advance_progress()
═══════════════════════════════════════════════════════════════
  Task 2.4 marked [x]
  ← CURRENT moved to Task 2.5
```

---

## Retry Loop (max 5 attempts)

**Pouze FÁZE 2 (Kodér+Reviewer) se opakuje:**

```
FÁZE 1: Architekt → jednou
FÁZE 2: Kodér → Reviewer → [PASS → FÁZE 3 | FAIL → retry]
FÁZE 3: Integrátor → jednou (jen po PASS)
```

**Na rozdíl od v2.0:**
- Architekt neběží při retry (úspora tokenů)
- Integrátor neběží po FAIL (úspora tokenů)
- Retry smyčka jen pro Kodér+Reviewer

---

## Nové bezpečnostní mechanismy (v3.0 - v3.2)

### 1. File Size Limits
```python
# Backend: max 200 lines
# Frontend: max 150 lines

# Kodér MUSÍ použít file_size_check před odesláním
# Reviewer MUSÍ použít directory_size_check před PASS
```

### 2. 3-Phase Workflow
```python
# FÁZE 1: Architekt (jednou)
architect_task = create_architect_task(...)
crew_architect.kickoff()

# FÁZE 2: Kodér + Reviewer (smyčka)
for attempt in range(1, max_attempts + 1):
    coder_task = create_coder_task(...)
    reviewer_task = create_reviewer_task(...)
    crew_code_review.kickoff()
    
    is_pass, reason = check_reviewer_verdict(reviewer_output, task_name)
    if is_pass:
        break

# FÁZE 3: Integrátor (jen po PASS)
if reviewer_passed:
    integrator_task = create_integrator_task(...)
    crew_integrator.kickoff()
```

### 3. Reviewer Verdict Check (v3.1 - robustní)
```python
def check_reviewer_verdict(reviewer_output: str, current_task_name: str) -> tuple[bool, str]:
    """Check if reviewer output contains PASS or FAIL for the correct task.
    
    NOVÉ (v3.1): Kontroluje JEN první řádek výstupu.
    """
    first_line = reviewer_output.strip().split('\n')[0].upper()
    if "FAIL" in first_line:
        return False, "Reviewer returned FAIL"
    if "PASS" in first_line:
        return True, "Reviewer returned PASS"
    return False, "Reviewer output does not contain PASS or FAIL"
```

### 4. Task Guardrails (v3.2 - NOVÉ)

Guardrails jsou extrahovány do separátního modulu `guardrails.py`:

```python
# guardrails.py
from typing import Tuple, Any

def validate_reviewer_verdict_format(result) -> Tuple[bool, Any]:
    """Ověří, že Reviewer output začíná PASS: nebo FAIL:.
    
    Kontroluje POUZE první neprázdný řádek outputu.
    
    Args:
        result: TaskOutput z CrewAI (má atribut .raw)
    
    Returns:
        (True, raw_output) pokud formát je správný
        (False, chybová_zpráva) pokud formát je špatný
    """
    raw = getattr(result, 'raw', None)
    if not raw or not raw.strip():
        return (False, "⚠️ Tvůj výstup je prázdný...")
    
    first_line = ""
    for line in raw.strip().splitlines():
        stripped = line.strip()
        if stripped:
            first_line = stripped.upper()
            break
    
    if first_line.startswith("PASS:") or first_line.startswith("FAIL:"):
        return (True, raw)
    
    return (False, "⚠️ Tvůj výstup MUSÍ začínat 'PASS:' nebo 'FAIL:'...")


def validate_reviewer_mentions_tools(result) -> Tuple[bool, Any]:
    """Ověří, že Reviewer zmínil výsledky z povinných nástrojů.
    
    Hledá evidence, že Reviewer skutečně:
    1. Prozkoumal adresářovou strukturu (list_dir)
    2. Zkontroloval velikosti souborů (directory_size_check)
    
    Returns:
        (True, raw_output) pokud evidence existuje
        (False, chybová_zpráva) pokud evidence chybí
    """
    # Indikátory použití list_dir
    dir_indicators = [
        "list_dir", "directory listing", "soubory v",
        "files in", "file structure", "adresářová struktura",
        "├──", "└──", "──", "[dir]", "[file]",
    ]
    
    # Indikátory použití size_check
    size_indicators = [
        "size_check", "directory_size", "file_size",
        "lines (max", "within size limits", "exceed",
        "řádků", "lines", "file size", "velikost",
    ]
    
    # ... kontrola přítomnosti indikátorů ...
```

**Použití v Reviewer task (plural `guardrails=[]`):**
```python
from guardrails import validate_reviewer_verdict_format, validate_reviewer_mentions_tools

reviewer_task = Task(
    ...,
    guardrails=[
        validate_reviewer_verdict_format,   # 1. formát PASS/FAIL
        validate_reviewer_mentions_tools,   # 2. evidence nástrojů
    ],
    guardrail_max_retries=2,  # Max 2 interní retry
)
```

**Sekvenční validace:**
1. `validate_reviewer_verdict_format` — kontroluje PASS/FAIL na prvním řádku
2. `validate_reviewer_mentions_tools` — kontroluje evidence použití nástrojů

Pokud první guardrail selže, druhý se nespustí (CrewAI chování).

### 5. Feedback Extraction (v3.1 - NOVÉ)
```python
def extract_fail_issues(reviewer_output: str, max_chars: int = 1500) -> str:
    """Extrahuje a zkracuje FAIL feedback pro Kodér.
    
    Zabraňuje nekonečné smyčce tím, že:
    - Zkracuje feedback na max_chars
    - Zachovává nejdůležitější issues
    """
    # Extrahuje issues z FAIL výstupu
    issues = parse_issues_from_output(reviewer_output)
    
    # Zformátuje a zkrátí
    formatted = format_issues(issues)
    if len(formatted) > max_chars:
        formatted = formatted[:max_chars] + "\n... (zkráceno)"
    
    return formatted
```

### 6. Fallback Logging (v3.2 - NOVÉ)
```python
# Při prázdném výstupu od Reviewera:
if not reviewer_output or reviewer_output.strip() == "":
    # Detailní diagnostika
    empty_msg = (
        f"⚠️  VAROVÁNÍ: reviewer_task.output je None\n"
        f"   Pokus: {attempt}/{max_attempts}\n"
        f"   Task: {current_task_name}\n"
        f"   Reviewer max_iter: {getattr(reviewer, 'max_iterations', '?')}\n"
        f"   Reviewer max_time: {getattr(reviewer, 'max_execution_time', '?')}s\n"
        f"   Guardrail max_retries: 2\n"
    )
    print(empty_msg)
    send_telegram_message(empty_msg)
    
    # Strukturované JSONL logování
    log_retry_event("EMPTY_OUTPUT", current_task_name, attempt, max_attempts, {
        "reviewer_max_iterations": getattr(reviewer, 'max_iterations', None),
        "reviewer_max_execution_time": getattr(reviewer, 'max_execution_time', None),
    })
    
    continue  # Retry smyčka
```

### 7. Strukturované Retry Logování (v3.2.1 - NOVÉ)

Všechny retry události se logují do `logs/retry_events.jsonl`:

```python
def log_retry_event(
    event: str,          # PASS, FAIL, ESCALATION, EMPTY_OUTPUT, EXHAUSTED
    task_name: str,      # Název aktuálního tasku
    attempt: int,        # Číslo pokusu
    max_attempts: int,   # Maximum pokusů
    details: dict | None = None,  # Volitelné detaily
):
    entry = {
        "timestamp": "2025-03-15T14:30:00",
        "event": "FAIL",
        "task": "Task 2.4: Generate hero images",
        "attempt": 2,
        "max_attempts": 5,
        "reason": "Reviewer returned FAIL",
        "reviewer_output_length": 1234,
    }
    # Log do konzole i JSONL souboru
```

**5 typů událostí:**

| Event | Kdy se loguje | Detaily |
|-------|---------------|---------|
| `PASS` | Reviewer vrátí PASS | `reason`, `reviewer_output_length` |
| `FAIL` | Reviewer vrátí FAIL | `reason`, `reviewer_output_length` |
| `ESCALATION` | 3+ retry pokusy | `feedback_length` |
| `EMPTY_OUTPUT` | Reviewer vrátí prázdný výstup | `reviewer_max_iterations`, `reviewer_max_execution_time` |
| `EXHAUSTED` | Vyčerpány všechny pokusy | `reason` nebo `message` |

**Příklad JSONL záznamu:**
```json
{"timestamp":"2025-03-15T14:30:00","event":"FAIL","task":"Task 2.4","attempt":2,"max_attempts":5,"reason":"Reviewer returned FAIL","reviewer_output_length":1234}
```

---

## Related Code

| Soubor | Popis |
|--------|-------|
| `supervisor.py` | 3-phase workflow, retry loop, validation, orchestration functions |
| `supervisor.py` → `run_architect_phase()` | FÁZE 1 orchestrace (v3.2) |
| `supervisor.py` → `run_code_review_phase()` | FÁZE 2 orchestrace s retry loop (v3.2) |
| `supervisor.py` → `run_integrator_phase()` | FÁZE 3 orchestrace (v3.2) |
| `supervisor.py` → `extract_fail_issues()` | FAIL feedback extrakce a zkrácení (v3.1) |
| `supervisor.py` → `check_reviewer_verdict()` | Robustní PASS/FAIL kontrola prvního řádku (v3.1) |
| `supervisor.py` → `log_retry_event()` | Strukturované JSONL logování retry událostí (v3.2.1) |
| `supervisor.py` → `_is_transient_error()` | Detekce dočasných chyb (v3.2) |
| `guardrails.py` | **NOVÉ (v3.2.1)**: Guardrails pro Reviewer validaci |
| `guardrails.py` → `validate_reviewer_verdict_format()` | Kontrola PASS/FAIL formátu na prvním řádku |
| `guardrails.py` → `validate_reviewer_mentions_tools()` | Kontrola evidence použití nástrojů |
| `agents/coder.py` | File size check tool integration, escalation handling |
| `agents/reviewer.py` | Directory size check tool integration, separate Crew (v3.1) |
| `tools/file_size_check.py` | FileSizeCheckTool + DirectorySizeCheckTool |
| `logs/retry_events.jsonl` | **NOVÉ (v3.2.1)**: Strukturované logy retry událostí |
| `projects/*/rules/do-not.md` | File Size Limits (CRITICAL) |
| `projects/*/rules/general.md` | File Size section |

---

## Konfigurace (models.py)

```python
AGENT_MODELS = {
    "architect":   "gemini-3.1-pro",
    "coder":       "gpt-5.1-codex-mini",
    "reviewer":    "minimax-m2.5",
    "integrator":  "kimi-k2.5",
}

# Retry config
max_attempts = 5  # Max retry pro Kodér+Reviewer smyčku
```

---

## Integration Notes

### For Reviewer Agent
- **Output format:** Start with **"PASS:"** or **"FAIL:"** (case-insensitive)
- **Task grounding:** Your prompt explicitly states which task to review
- **Validation:** Supervisor will reject if your output doesn't contain the correct task ID
- **File size:** MUST use `directory_size_check` before issuing PASS
- **Delegation:** REMOVED — return FAIL and Supervisor handles retry
- **🆕 v3.1:** Runs in SEPARATE Crew (reads files from disk, not from context)
- **🆕 v3.2:** Guardrail validates your output format AND tool usage evidence
- **🆕 v3.2:** `guardrail_max_retries=2` — max 2 internal retries on invalid output

### For Coder Agent
- **On Retry:** You will see fresh output directory listing
- **Image generation:** Use `image_generator` tool for image tasks
- **File size:** MUST use `file_size_check` before submitting
- **Verify output:** Always check that files were created
- **🆕 v3.1:** Runs in SEPARATE Crew (isolated from Reviewer)
- **🆕 v3.1:** FAIL feedback is shortened to 1.5k chars (`extract_fail_issues()`)
- **🆕 v3.1:** On 3+ retry attempts, receives escalation instructions

### For Integrator Agent
- **Graceful exit:** Complete ALL tool calls before returning final answer
- **Final output:** Must be "OK" or "PROBLÉMY:" + list
- **Never exit mid-tool-call**
- **NEW:** Only runs after PASS from Reviewer

### For Supervisor
- **Phase management:**
  ```python
  # Phase 1: Architect (once)
  run_architect_phase()
  
  # Phase 2: Coder + Reviewer (loop until PASS)
  run_code_review_phase()
  
  # Phase 3: Integrator (only after PASS)
  run_integrator_phase()
  ```
- **Validation flow:**
  ```python
  is_pass, reason = check_reviewer_verdict(reviewer_output, task_name)
  if is_pass:
      # Run Integrator
      run_integrator()
      advance_progress()
  else:
      # Extract and shorten feedback
      feedback = extract_fail_issues(reviewer_output, max_chars=1500)
      
      # Retry Coder + Reviewer
      if attempt < max_attempts:
          continue
      else:
          # Give up
          send_failure_message()
  ```
- **🆕 v3.2:** Empty reviewer output → log + Telegram notification
