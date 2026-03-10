# Multiagent Integration Workflow – CRÍTICO

## Problem 1: "Agent Integrator asks who marks task as complete?"

This document clarifies the **exact responsibilities** for each agent role when managing PROGRESS.md.

## Problem 2: "Why doesn't Coder automatically retry when Reviewer returns FAIL?"

**Context:** When Reviewer finds bugs and returns FAIL with feedback, Coder should automatically try to fix them.

**Solution:** Supervisor now implements **automatic retry loop** (max 3 attempts per session):

1. **Run 1:** Architect → Coder → Reviewer
   - Reviewer returns FAIL with feedback
2. **Supervisor parses verdict:** Detects "FAIL" in output
3. **Retry triggered:** Supervisor waits 5s and runs the same crew again
4. **Run 2:** Architect (updates plan) → Coder (reads feedback, fixes) → Reviewer
   - If PASS: Done! advance_progress() runs
   - If FAIL again: Continue to Run 3
5. **Run 3:** Same pipeline, final attempt
6. **After attempt 3:** If still FAIL, supervisor stops and awaits manual intervention

---

## Architecture: Supervisor-Driven Progress Management

```
┌─────────────────────────────────────────────────────────────────┐
│                        SUPERVISOR                               │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ for attempt in range(1, 4):                               │  │
│ │   - Reads current task from PROGRESS.md (← CURRENT)       │  │
│ │   - Creates 4-stage crew: Architect → Coder → Reviewer    │  │
│ │                           → Integrator                     │  │
│ │   - Executes crew.kickoff()                               │  │
│ │   - PARSES reviewer verdict (PASS or FAIL)                │  │
│ │   - IF PASS:   advance_progress() marks [x] & moves ←     │  │
│ │            break (exit loop)                              │  │
│ │   - IF FAIL:                                              │  │
│ │        if attempt < 3: wait 5s & continue (retry)         │  │
│ │        else: stop, await manual intervention               │  │
│ └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Clear Role Definition

### 🏗️ Architect
- **Role:** Plan
- **Task:** Create detailed implementation plan
- **Progress.md:** ❌ DO NOT TOUCH
- **On Retry:** Updates plan based on Reviewer's feedback (if needed)

### 💻 Coder
- **Role:** Implement
- **Task:** Write code according to plan
- **Progress.md:** ❌ DO NOT TOUCH
- **On Retry:** Reads Reviewer's FAIL feedback and fixes the issues
- **Expected:** Fixes should be applied in 2nd/3rd attempt

### 🔍 Reviewer
- **Role:** QA / Security / Code Review
- **Output:** Structured review with verdict: **PASS** or **FAIL**
- **Progress.md:** ❌ DO NOT TOUCH
- **Delegation:** Can return to Coder via `allow_delegation=True` (within same kickoff)
- **IMPORTANT:** Must start output with either **"PASS:"** or **"FAIL:"** for Supervisor to detect it

### 🔗 Integrator
- **Role:** Assembly & Final Checks
- **Task:** Update imports, routing, barrel exports, verify consistency
- **Progress.md:** ❌ **ABSOLUTELY DO NOT TOUCH**
- **Why?** Supervisor handles ALL progress state based on Reviewer verdict

### 👑 Supervisor
- **Role:** Orchestrator + Retry Loop Manager
- **Task:** Manage workflow and task state
- **Progress.md:** ✅ **ONLY SUPERVISOR MODIFIES IT**
- **Verdict Parsing:**
  - If `result.contains("PASS")`: calls `advance_progress()` → marks [x], moves ←, breaks loop
  - If `result.contains("FAIL")`: If attempt < 3 → retry with same crew, else stop
- **Max Retries:** 3 attempts per session (configurable)

---

## Workflow Examples

### Example 1: Task FAILS once, then PASSES

**Run 1 (Attempt 1/3):**
```
Supervisor reads:  [ ] ← CURRENT Task 4.2
Architect → Plan (detailed breakdown)
Coder → Implement according to plan
Reviewer → FAIL: "Missing error handling in ClientList component"
Integrator → (not called, crew exits with FAIL verdict)
Supervisor parses: result contains "FAIL"
Action: Do NOT call advance_progress()
Decision: attempt=1 < max_attempts=3 → wait 5s → continue
```

**Run 2 (Attempt 2/3):**
```
Supervisor reads:  [ ] ← CURRENT Task 4.2  (same as before!)
Architect → Updates plan with error handling patterns
Coder → Reads Reviewer's feedback, adds error handling
Reviewer → PASS: "Error handling looks good!"
Integrator → Verifies imports, consistency
Supervisor parses: result contains "PASS"
Action: Call advance_progress("Task 4.2")
Result: PROGRESS.md updated:
        [x] Task 4.2
        [ ] ← CURRENT Task 4.3  (moved forward)
Break loop → session ends successfully
```

### Example 2: Task FAILS 3 times → manual intervention

**Run 1, 2, 3:**
- All return FAIL with different feedback from Reviewer
- Each time Coder tries to fix but new issues arise

**After Attempt 3:**
```
Supervisor parses: result contains "FAIL" AND attempt=3 >= max_attempts=3
Action: Do NOT call advance_progress()
Message:
  ❌ Task FAILED po 3 pokusech: Task 4.2
  🔄 Vrácen Kodérovi — prosím, zkontroluj manuálně.
  ⏳ Oprav a spusť supervisor znovu.
Break loop → session ends, awaits manual fix
```

Human must manually debug, fix the issue in `output/`, then re-run supervisor.

---

## Integration Notes

### For Reviewer Agent
- **Output format:** Start with **"PASS:"** or **"FAIL:"** (case-insensitive)
- **When FAIL:** Include specific problems with file locations and suggested fixes
- **Delegation:** When problems are found, you can return to Coder for fixes
- **Within same kickoff:** Your feedback is read by Coder in the same run

### For Coder Agent
- **On Retry:** You will see the same plan + Reviewer's feedback together
- **Read feedback carefully:** Each retry is a chance to fix specific issues
- **Expected:** Most issues should be fixable within 2-3 attempts

### For Supervisor
- **Verdict detection:**
  ```python
  result_text = str(result).upper() if result else ""
  is_fail_verdict = "FAIL" in result_text
  ```
- **Retry loop:**
  ```python
  for attempt in range(1, max_attempts + 1):
    result = crew.kickoff()
    if not is_fail_verdict:
      advance_progress(...)
      break
    elif attempt < max_attempts:
      wait 5s
      continue
    else:
      stop & await manual fix
  ```

### For Task Definitions
- Reviewer output goes directly to `result` object (not saved to file)
- Each retry uses fresh crew instance with same tasks
- Task file paths don't change between retries

---

## Related Code

- `supervisor.py` — Main loop with retry logic (lines ~600-700)
- `agents/reviewer.py` — Verdict format + delegation
- `agents/coder.py` — Retry feedback handling
- `projects/taskmanager/specs/PROGRESS.md` — Task definitions
- `SUPERVISOR_USAGE.md` — Usage guide and troubleshooting
