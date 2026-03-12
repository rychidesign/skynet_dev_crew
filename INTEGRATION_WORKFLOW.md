# Multiagent Integration Workflow – AKTUALIZOVÁNO 2025-03-11

## Historie změn

| Datum | Verze | Změna |
|-------|-------|-------|
| 2025-03-11 | 2.0 | Přidán task grounding, validace výstupu, output sanity check, audit log |
| Původní | 1.0 | Init: Retry loop, Supervisor-driven progress |

---

## Problém: Reviewer reviewuje špatný task

**Příklad chyby:** Task 2.4 (Generate images), ale Reviewer dal PASS pro Task 1.1 (HTML skeleton).

**Důsledky:**
- PROGRESS.md posunut na základě nevalidního review
- Obrázky nikdy negenerovány
- Dominový efekt chyb

**Řešení (v2.0):**
1. **Task grounding prefix** — každý task dostává explicitní "AKTUÁLNÍ TASK: X"
2. **Validace výstupu** — Supervisor kontroluje, zda výstup obsahuje správný task ID
3. **Output sanity check** — pro image tasky se ověřuje existence souborů

---

## Problém: Integrátor se ukončí uprostřed práce

**Příklad chyby:** Integrator Final Answer obsahuje jen "Action: list_dir" místo skutečné odpovědi.

**Důsledky:**
- Neúplný výstup
- Chybějící finalizace

**Řešení (v2.0):**
- Graceful exit instrukce v Integrator backstory
- max_iterations: 30 (dostatek pro dokončení práce)

---

## Architecture: Supervisor-Driven Progress Management

```
┌─────────────────────────────────────────────────────────────────┐
│                        SUPERVISOR                               │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ for attempt in range(1, max_attempts+1):                  │  │
│ │   - Reads current task from PROGRESS.md (← CURRENT)       │  │
│ │   - Creates fresh crew with task_grounding prefix         │  │
│ │   - Executes: Architekt → Kodér → Reviewer → Integrátor  │  │
│ │   - VALIDATES: reviewer output contains correct task ID   │  │
│ │   - OUTPUT CHECK: verify expected files exist             │  │
│ │   - PARSES verdict (PASS or FAIL)                        │  │
│ │   - IF PASS:  advance_progress() → [x] & ← move          │  │
│ │   - IF FAIL:  if attempt < max → retry else stop         │  │
│ └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Clear Role Definition

### 🏛️ Architekt
- **Role:** Plan
- **Task:** Create detailed implementation plan
- **Progress.md:** ❌ DO NOT TOUCH
- **Task grounding:** Dostává explicitní "AKTUÁLNÍ TASK: X"
- **On Retry:** Updates plan based on Reviewer's feedback

### 💻 Kodér
- **Role:** Implement
- **Task:** Write code according to plan
- **Progress.md:** ❌ DO NOT TOUCH
- **Task grounding:** Dostává explicitní "AKTUÁLNÍ TASK: X"
- **On Retry:** Reads Reviewer's FAIL feedback and fixes issues

### 🔍 Reviewer
- **Role:** QA / Security / Code Review
- **Output:** Structured review with verdict: **PASS** or **FAIL**
- **Progress.md:** ❌ DO NOT TOUCH
- **Task grounding:** Dostává explicitní "AKTUÁLNÍ TASK: X"
- **Validace:** Supervisor ověřuje, že output obsahuje správný task ID
- **⚠️ IMPORTANT:** Must start output with **"PASS:"** or **"FAIL:"**
- **⚠️ DELEGATION REMOVED:** Cannot delegate — return FAIL and Supervisor handles retry

### 🔗 Integrátor
- **Role:** Assembly & Final Checks
- **Task:** Update imports, routing, verify consistency
- **Progress.md:** ❌ **ABSOLUTELY DO NOT TOUCH**
- **Task grounding:** Dostává explicitní "AKTUÁLNÍ TASK: X"
- **Graceful exit:** Musí dokončit VŠECHNY tool caily před finální odpovědí

### 👑 Supervisor
- **Role:** Orchestrator + Retry Loop Manager
- **Task:** Manage workflow, validate outputs, task state
- **Progress.md:** ✅ **ONLY SUPERVISOR MODIFIES IT**

---

## Nové bezpečnostní mechanismy (v2.0)

### 1. Task Grounding Prefix
```
══════════════════════════════════════════════════
⚠️  AKTUÁLNÍ TASK: "Task 2.4: Generate hero + service images"
Pracuješ POUZE na tomto tasku. Ignoruj ostatní.
══════════════════════════════════════════════════
```

### 2. Reviewer Output Validation
```python
# Ověř, že Reviewer reviewoval SPRÁVNÝ task
task_id_match = re.search(r"Task\s+(\d+\.\d+)", current_task_name)
task_id = task_id_match.group(1) if task_id_match else current_task_name

if task_id and task_id not in str(result):
    print(f"⚠️ VALIDACE: Reviewer reviewoval špatný task!")
    is_fail_verdict = True  # Vynutit retry
```

### 3. Output Sanity Check
```python
# Pro image tasky ověř, že soubory existují
if "image" in task_name.lower() or "Generate" in task_name:
    images_dir = os.path.join(output_dir, "public", "images")
    if not os.path.exists(images_dir) or not os.listdir(images_dir):
        is_fail_verdict = True  # Vynutit retry
```

### 4. Audit Log
```python
# Ulož strukturovaný záznam každého tasku
audit_entry = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "task": current_task_name,
    "attempt": attempt,
    "verdict": "FAIL" if is_fail_verdict else "PASS",
    "output_files": sorted(os.listdir(output_dir)),
}
# → logs/tasks_audit.jsonl
```

---

## Retry Loop (max 5 attempts)

```
Run 1: Architekt → Kodér → Reviewer → Integrátor
       ↓
Supervisor validates: task ID present? files exist?
       ↓
If PASS: advance_progress() → next task
If FAIL: retry (max 5 attempts)
```

**Na rozdíl od v1.0:**
- Tasks se regenerují při každém retry (čerstvý os.listdir)
- step_callback se předává i do retry crew
- Output sanity check před advance_progress

---

## Workflow Example: Task with Validation

**Task 2.4: Generate hero + service images**

```
Supervisor reads:  [ ] ← CURRENT Task 2.4: Generate hero + service images

[TASK GROUNDING PREFIX APPLIED]

Run 1:
  Architekt → Plan (image generation prompts)
  Kodér → Calls image_generator tool
  Reviewer → FAIL: "Images not generated - no output directory"
  Integrátor → (not called due to FAIL)

Supervisor validates:
  ✓ Task ID "2.4" found in output? ❌ NO (Reviewer mentioned Task 1.1!)
  → VALIDATION FAIL → is_fail_verdict = True

Retry 2:
  [FRESH TASKS REGENERATED]
  Kodér → Generates images, saves to output/public/images/
  Reviewer → PASS
  Integrátor → Verifies files exist

Supervisor output check:
  ✓ images/public/ exists with files? YES
  → advance_progress() → Task 2.4 marked [x]
```

---

## Integration Notes

### For Reviewer Agent
- **Output format:** Start with **"PASS:"** or **"FAIL:"** (case-insensitive)
- **Task grounding:** Your prompt explicitly states which task to review
- **Validation:** Supervisor will reject if your output doesn't contain the correct task ID
- **Delegation:** REMOVED — return FAIL and Supervisor handles retry

### For Coder Agent
- **On Retry:** You will see fresh output directory listing
- **Image generation:** Use `image_generator` tool for image tasks
- **Verify output:** Always check that files were created

### For Integrator Agent
- **Graceful exit:** Complete ALL tool calls before returning final answer
- **Final output:** Must be "OK" or "PROBLÉMY:" + list
- **Never exit mid-tool-call**

### For Supervisor
- **Validation flow:**
  ```python
  result = crew.kickoff()
  result_text = str(result).upper()
  is_fail_verdict = "FAIL" in result_text

  # 1. Validate task ID
  if task_id not in result_text:
      is_fail_verdict = True  # Force retry

  # 2. Output sanity check
  if "image" in task_name and not images_exist:
      is_fail_verdict = True  # Force retry

  # 3. Advance or retry
  if not is_fail_verdict:
      advance_progress()
  ```

---

## Related Code

| Soubor | Popis |
|--------|-------|
| `supervisor.py` | Main loop, task grounding, validation, retry (lines ~350-840) |
| `agents/reviewer.py` | Verdict format |
| `agents/integrator.py` | Graceful exit instructions |
| `agents/coder.py` | Image generator tool |
| `logs/tasks_audit.jsonl` | Audit log (v2.0+) |

---

## Konfigurace (models.py)

```python
AGENT_MODELS = {
    "architect":   "gemini-3.1-pro",
    "coder":       "gpt-5.1-codex-mini",
    "reviewer":    "minimax-m2.5",  # ← ZMĚNA z glm-5
    "integrator":  "kimi-k2.5",
}

# Retry config
max_attempts = 5  # ↑ ZMĚNA z 3
```
