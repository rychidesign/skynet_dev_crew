# Multiagent Integration Workflow – AKTUALIZOVÁNO 2025-03-14

## Historie změn

| Datum | Verze | Změna |
|-------|-------|-------|
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

## Architecture: 3-Phase Workflow (v3.0)

```
┌─────────────────────────────────────────────────────────────────┐
│                        SUPERVISOR (v3.0)                        │
│                                                                 │
│  ══════════════════════════════════════════════════════════    │
│  FÁZE 1: ARCHITEKT (spustí se jednou)                          │
│  ══════════════════════════════════════════════════════════    │
│  - Čte PROGRESS.md, SPECS.md, rules/                           │
│  - Vytvoří technický plán v output/plan.md                    │
│  - Běží POUZE JEDNOU (ne při retry)                           │
│                                                                 │
│  ══════════════════════════════════════════════════════════    │
│  FÁZE 2: KODÉR + REVIEWER (smyčka s retry)                    │
│  ══════════════════════════════════════════════════════════    │
│  for attempt in range(1, max_attempts+1):                     │
│      Kodér → Implementuje podle plánu                         │
│      Reviewer → Kontroluje kód                                │
│      if PASS: break → pokračuj na FÁZE 3                      │
│      if FAIL: retry (max 5 pokusů)                             │
│                                                                 │
│  ══════════════════════════════════════════════════════════    │
│  FÁZE 3: INTEGRÁTOR (jen po PASS od Reviewera)                │
│  ══════════════════════════════════════════════════════════    │
│  - Sjednotí kód, aktualizuje importy                          │
│  - Ověří konzistenci                                          │
│  - Běží JEN KDYŽ Reviewer vrátil PASS                          │
│                                                                 │
│  ══════════════════════════════════════════════════════════    │
│  SUCCESS: advance_progress() → [x] & ← move to next task      │
│  ══════════════════════════════════════════════════════════    │
└─────────────────────────────────────────────────────────────────┘
```

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

### 🔍 Reviewer
- **Role:** QA / Security / Code Review
- **Output:** Structured review with verdict: **PASS** or **FAIL**
- **Progress.md:** ❌ DO NOT TOUCH
- **Task grounding:** Dostává explicitní "AKTUÁLNÍ TASK: X"
- **Validace:** Supervisor ověřuje, že output obsahuje správný task ID
- **File Size:** MUSÍ použít `directory_size_check` před PASS
- **⚠️ IMPORTANT:** Must start output with **"PASS:"** or **"FAIL:"**

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

## Nové bezpečnostní mechanismy (v3.0)

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

### 3. Reviewer Verdict Check
```python
def check_reviewer_verdict(reviewer_output: str, current_task_name: str) -> tuple[bool, str]:
    """Check if reviewer output contains PASS or FAIL for the correct task."""
    if "FAIL" in reviewer_output.upper():
        return False, "Reviewer returned FAIL"
    if "PASS" in reviewer_output.upper():
        return True, "Reviewer returned PASS"
    return False, "Reviewer output does not contain PASS or FAIL"
```

---

## Related Code

| Soubor | Popis |
|--------|-------|
| `supervisor.py` | 3-phase workflow, retry loop, validation (lines ~350-852) |
| `agents/coder.py` | File size check tool integration |
| `agents/reviewer.py` | Directory size check tool integration |
| `tools/file_size_check.py` | FileSizeCheckTool + DirectorySizeCheckTool |
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

### For Coder Agent
- **On Retry:** You will see fresh output directory listing
- **Image generation:** Use `image_generator` tool for image tasks
- **File size:** MUST use `file_size_check` before submitting
- **Verify output:** Always check that files were created

### For Integrator Agent
- **Graceful exit:** Complete ALL tool calls before returning final answer
- **Final output:** Must be "OK" or "PROBLÉMY:" + list
- **Never exit mid-tool-call**
- **NEW:** Only runs after PASS from Reviewer

### For Supervisor
- **Phase management:**
  ```python
  # Phase 1: Architect (once)
  # Phase 2: Coder + Reviewer (loop until PASS)
  # Phase 3: Integrator (only after PASS)
  ```
- **Validation flow:**
  ```python
  is_pass, reason = check_reviewer_verdict(reviewer_output, task_name)
  if is_pass:
      # Run Integrator
      run_integrator()
      advance_progress()
  else:
      # Retry Coder + Reviewer
      if attempt < max_attempts:
          continue
      else:
          # Give up
          send_failure_message()
  ```
