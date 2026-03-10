# IMPLEMENTATION PLAN: Model Registry + New Models + Universal Agents

Complete step-by-step plan for an AI agent to execute.
Contains exact files, line numbers, and copy-paste ready code.

---

## OVERVIEW

Three simultaneous changes:
1. **New file `models.py`** — central model catalog, switching = one line change
2. **New models** — via Vercel AI Gateway + OpenCode Go
3. **Universal agents** — removed hardcoded React/TypeScript/Supabase references

### Models

| Agent | New model | Provider | Model string |
|-------|-----------|----------|-------------|
| Architect | Gemini 3.1 Pro | Vercel | `google/gemini-3.1-pro-preview` |
| Coder | GPT-5.1-Codex-Mini | Vercel | `openai/gpt-5.1-codex-mini` |
| Reviewer | Claude Sonnet 4.6 | Vercel | `anthropic/claude-sonnet-4.6` |
| Integrator | Kimi K2.5 | Vercel | `moonshotai/kimi-k2.5` |

Additional models in catalog (OpenCode Go): GLM-5, Kimi K2.5, MiniMax M2.5

### Files to modify

| # | File | Action |
|---|------|--------|
| 1 | `models.py` | **NEW** — create |
| 2 | `agents/architect.py` | replace entire file |
| 3 | `agents/coder.py` | replace entire file |
| 4 | `agents/reviewer.py` | replace entire file |
| 5 | `agents/integrator.py` | replace entire file |
| 6 | `agents/junior.py` | replace entire file |
| 7 | `.env` | rewrite |
| 8 | `supervisor.py` | 6 targeted edits |
| 9 | `README.md` | update table |

---

## STEP 1: Create `models.py`

**Path:** `multiagent/models.py` (new file in project root, next to supervisor.py)

The `models.py` file is delivered as a separate file and is ready to use.
It contains: PROVIDERS, MODELS, AGENT_MODELS, AGENT_MAX_TOKENS dicts,
`get_llm()` factory, `get_model_pricing()` for supervisor, `print_catalog()` for debug.

---

## STEP 2: Replace `agents/architect.py`

**Replace the entire file with:**

```python
import os
from crewai import Agent
from models import get_llm
from tools.ask_human import AskHuman
from tools.file_reader import create_file_reader


def create_architect_agent(project_path: str):
    """Architect (Planner) — model per models.AGENT_MODELS['architect']."""
    llm = get_llm("architect")

    return Agent(
        role="Architekt",
        goal=(
            "Analyze the specification, decompose the task into subtasks, "
            "design file and component structure. "
            "You do NOT write production code — you create a detailed plan for the Coder."
        ),
        backstory=f"""You are a senior software architect with 20+ years of experience.
You specialize in system design, proper task decomposition,
and defining clean interfaces between modules.

Your output is always a structured plan containing:
- List of files to create/modify with content description
- Interfaces and data structures (if the project requires them)
- Dependencies between components
- Implementation order

IMPORTANT: Adapt the plan to the project's technology stack. Read SPECS.md
and rules/ to determine what tech stack the project uses. Do not generate
TypeScript interfaces for an HTML project or React components for a backend API.

You are working on a project in: {project_path}
If unsure, ask the human via ask_human.""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[
            AskHuman,
            create_file_reader(project_path),
        ],
        max_iterations=15,
        max_execution_time=1800,
    )
```

---

## STEP 3: Replace `agents/coder.py`

**Replace the entire file with:**

```python
import os
from crewai import Agent
from models import get_llm
from tools.file_reader import create_file_reader
from tools.file_writer import create_file_writer
from tools.list_dir import create_list_dir
from tools.search_content import create_search_content


def create_coder_agent(project_path: str, output_path: str = ""):
    """Coder (Implementer) — model per models.AGENT_MODELS['coder']."""
    llm = get_llm("coder")
    code_base = output_path or project_path

    return Agent(
        role="Kodér",
        goal=(
            "Implement code exactly according to the Architect's plan. "
            "Write clean, functional, and complete files using the technologies "
            "the project requires."
        ),
        backstory=f"""You are an experienced full-stack developer capable of working
with any tech stack — from simple HTML/CSS through React/Vue/Svelte to backends
in Node.js, Python, Go, or any other language.

Adapt to the project's technologies — read SPECS.md and rules/ to determine
what stack is used. Do not implement anything the project does not require.

You receive clear instructions from the Architect — your job is to implement them.
You write COMPLETE files — never truncate, skip, or use comments like
"... rest of code".

IMPORTANT: When a task comes back from the Reviewer with a FAIL verdict:
- Carefully read the feedback
- Fix the code based on the criticism
- Try again with the fixes

Rules for file_writer:
- Always provide COMPLETE file content
- If a file is too large, split it into multiple files
- Never call file_writer with empty content
- Always specify BOTH file_path AND content

You are working on a project in: {project_path}""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[
            create_file_reader(code_base),
            create_file_writer(code_base),
            create_list_dir(code_base),
            create_search_content(code_base),
        ],
        max_iterations=30,
        max_execution_time=3600,
    )
```

---

## STEP 4: Replace `agents/reviewer.py`

**Replace the entire file with:**

```python
import os
from crewai import Agent
from models import get_llm
from tools.file_reader import create_file_reader
from tools.list_dir import create_list_dir
from tools.find_files import create_find_files
from tools.search_content import create_search_content
from tools.lint_check import create_lint_check


def create_reviewer_agent(project_path: str):
    """Reviewer (QA) — model per models.AGENT_MODELS['reviewer']."""
    llm = get_llm("reviewer")

    return Agent(
        role="Reviewer",
        goal=(
            "Review code from the Coder — look for bugs, security holes, "
            "performance problems, and coding convention violations. "
            "Return a clear, structured review."
        ),
        backstory=f"""You are a thorough code reviewer focused on:
- Security — authentication, authorization, injection, XSS, path traversal
- Functionality — complete implementation, correct imports, logic errors
- Performance — unnecessary complexity, inefficient operations
- Conventions — compliance with coding standards defined in rules/

Adapt your review to the project's tech stack. Read SPECS.md and rules/
to know what to check. Do not check React hooks in an HTML project.
Do not check CSS styling in a backend API.

You review code systematically:
1. Security — does it meet security requirements from rules and specs?
2. Functionality — is the implementation complete and matches the Architect's plan?
3. Performance — are there obvious performance problems?
4. Conventions — does it follow coding standards from rules?

Your output is ALWAYS a structured review:

## PASS
Code is fine and can proceed to the Integrator.
(Write "PASS:" at the beginning of your output)

## FAIL
List of specific problems with solutions:
- Problem 1: [exact location in file] - [how to fix]
- Problem 2: [exact location in file] - [how to fix]

(Write "FAIL:" at the beginning of your output)

IMPORTANT: The Supervisor automatically detects PASS/FAIL from your output.

You are working on a project in: {project_path}""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[
            create_file_reader(project_path),
            create_list_dir(project_path),
            create_find_files(project_path),
            create_search_content(project_path),
            create_lint_check(project_path),
        ],
        max_iterations=15,
        max_execution_time=1800,
    )
```

---

## STEP 5: Replace `agents/integrator.py`

**Replace the entire file with:**

```python
import os
from crewai import Agent
from models import get_llm
from tools.file_reader import create_file_reader
from tools.file_writer import create_file_writer
from tools.list_dir import create_list_dir


def create_integrator_agent(project_path: str, output_path: str = ""):
    """Integrator (Assembler) — model per models.AGENT_MODELS['integrator']."""
    llm = get_llm("integrator")
    code_base = output_path or project_path

    return Agent(
        role="Integrátor",
        goal=(
            "Take approved code from the Reviewer, assemble it — "
            "verify consistency, update inter-file references, "
            "and prepare final files."
        ),
        backstory=f"""You are a precise integrator responsible for making sure
everything fits together and the project can run.

Your tasks:
1. Verify consistency of all files — no broken imports, missing references
2. Update inter-file links (imports, exports, routing) if needed
3. Update README.md if needed
4. Return "OK" or description of remaining problems

Adapt to the project's tech stack. For HTML projects, check correct
file references (CSS, JS, images). For Node.js projects, check imports
and package.json. Read SPECS.md and rules/.

IMPORTANT: Do NOT modify PROGRESS.md! The Supervisor handles that automatically.

Rules for file_writer:
- Always provide COMPLETE file content
- Never call file_writer with empty content
- Always specify BOTH file_path AND content

You are working on a project in: {project_path}""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[
            create_file_reader(code_base),
            create_file_writer(code_base),
            create_list_dir(code_base),
        ],
        max_iterations=30,
        max_execution_time=3600,
    )
```

---

## STEP 6: Replace `agents/junior.py`

**Replace the entire file with:**

```python
import os
from crewai import Agent
from models import get_llm
from tools.ask_human import AskHuman
from tools.file_reader import create_file_reader
from tools.file_writer import create_file_writer


def create_junior_agent(project_path: str):
    """Junior developer — model per models.AGENT_MODELS['junior']."""
    llm = get_llm("junior")

    return Agent(
        role="Junior vývojář",
        goal="Complete tests, documentation, and minor code adjustments",
        backstory=f"""You are a young, enthusiastic developer eager to learn and improve.
You carefully write tests and documentation. You are responsible for quality and details.

You are working on a project in: {project_path}
If unsure about anything, don't hesitate to ask a more experienced colleague
or the human.""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[AskHuman, create_file_reader(project_path), create_file_writer(project_path)],
        max_iterations=30,
    )
```

---

## STEP 7: Rewrite `.env`

**Replace the entire file with:**

```env
# === Vercel AI Gateway (Gemini, GPT, Claude, Kimi via Vercel) ===
# Get at: https://vercel.com/ai-gateway → Settings → API Keys
VERCEL_AI_GATEWAY_API_KEY=

# === OpenCode Go / Zen (GLM-5, Kimi K2.5, MiniMax M2.5) ===
# Get at: https://opencode.ai/zen → API Keys
OPENCODE_API_KEY=

# === Legacy keys (commented out — keep as fallback) ===
# ANTHROPIC_API_KEY=sk-ant-api03-...
# GOOGLE_API_KEY=AIzaSy...

# Telegram Bot
TELEGRAM_BOT_TOKEN=8720526729:AAFwv0gYrBCV0z_QRhr12RU6vKy4kBJfVYU
TELEGRAM_CHAT_ID=1103425474
```

---

## STEP 8: Targeted edits in `supervisor.py`

### 8a) MODEL_PRICING — replace static dict with dynamic (lines 137–151)

**Find (lines 137–151):**
```python
# Per-model pricing (USD per 1M tokens) — keys match both prefixed and bare names
MODEL_PRICING = {
    "anthropic/claude-opus-4-6":    {"input": 15.0,  "output": 75.0},
    "claude-opus-4-6":              {"input": 15.0,  "output": 75.0},
    "anthropic/claude-sonnet-4-6":  {"input": 3.0,   "output": 15.0},
    "claude-sonnet-4-6":            {"input": 3.0,   "output": 15.0},
    "anthropic/claude-haiku-4-5":   {"input": 0.8,   "output": 4.0},
    "claude-haiku-4-5":             {"input": 0.8,   "output": 4.0},
    "gemini/gemini-2.5-flash":      {"input": 0.15,  "output": 0.60},
    "gemini-2.5-flash":             {"input": 0.15,  "output": 0.60},
    "gemini/gemini-2.5-flash-lite":  {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash-lite":         {"input": 0.075, "output": 0.30},
    "gemini/gemini-3.1-flash-lite":  {"input": 0.25,  "output": 1.50},
    "gemini-3.1-flash-lite":         {"input": 0.25,  "output": 1.50},
}
```

**Replace with:**
```python
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
```

---

### 8b) Rules loading — remove hardcoded filters (lines 366–369)

**Find:**
```python
    rules_architect = load_rules(project_path, only=["general.md", "architecture.md"])
    rules_coder = load_rules(project_path, only=["general.md", "architecture.md", "components.md", "supabase.md", "do-not.md"])
    rules_reviewer = load_rules(project_path, only=["general.md", "architecture.md", "components.md", "supabase.md", "do-not.md", "testing.md"])
    rules_integrator = load_rules(project_path, only=["general.md", "do-not.md"])
```

**Replace with:**
```python
    rules_architect = load_rules(project_path)
    rules_coder = load_rules(project_path)
    rules_reviewer = load_rules(project_path)
    rules_integrator = load_rules(project_path, only=["general.md", "do-not.md"])
```

---

### 8c) Architect task — generic wording (line 408)

**Find:**
```python
   - TypeScript interfaces a typy pro každý soubor
```

**Replace with:**
```python
   - Interfaces and data structures (if the project requires them)
```

---

### 8d) Reviewer task — generic wording (lines 473–475)

**Find:**
```python
   - BEZPEČNOST: RLS policies pokrývají CRUD? Auth je správný? XSS/injection?
   - FUNKČNOST: Kompletní komponenty? Importy sedí? Typy odpovídají plánu?
   - PERFORMANCE: Zbytečné re-rendery? Chybějící React.memo/useMemo?
```

**Replace with:**
```python
   - SECURITY: Does it meet security requirements from specs and rules?
   - FUNCTIONALITY: Is the implementation complete? Do imports/references match? Does it match the plan?
   - PERFORMANCE: Are there obvious performance problems?
```

---

### 8e) Integrator task — generic wording (line 502)

**Find:**
```python
3. Aktualizuj barrel exporty (index.ts) pokud je potřeba
```

**Replace with:**
```python
3. Update inter-file links (imports, exports, references) if needed
```

---

### 8f) Console output — dynamic from models.py (line 630)

**Find:**
```python
        print(f"   Architekt (Sonnet) → Kodér (Flash) → Reviewer (Haiku) → Integrátor (Flash)")
```

**Replace with:**
```python
        from models import AGENT_MODELS
        print(f"   Architekt ({AGENT_MODELS['architect']}) → Kodér ({AGENT_MODELS['coder']}) → Reviewer ({AGENT_MODELS['reviewer']}) → Integrátor ({AGENT_MODELS['integrator']})")
```

---

## STEP 9: Update `README.md` (lines 49–55)

**Find:**
```markdown
## Modely

| Agent | Model |
|-------|-------|
| Architekt | Claude Opus 4.6 |
| Kodér | Claude Sonnet 4.6 |
| Junior | Gemini 2.5 Flash |
```

**Replace with:**
```markdown
## Models

Model configuration lives in `models.py`. To switch a model for any agent,
edit the `AGENT_MODELS` dict — no other files need to change.

| Agent | Model | Provider |
|-------|-------|----------|
| Architect | Gemini 3.1 Pro | Vercel AI Gateway |
| Coder | GPT-5.1-Codex-Mini | Vercel AI Gateway |
| Reviewer | Claude Sonnet 4.6 | Vercel AI Gateway |
| Integrator | Kimi K2.5 | Vercel AI Gateway |

Additional models: GLM-5, MiniMax M2.5 (OpenCode Go) — run `python models.py`
```

---

## CHECKLIST

```
[ ] Step 1:  Create models.py (delivered as separate file)
[ ] Step 2:  agents/architect.py — replace entire file
[ ] Step 3:  agents/coder.py — replace entire file
[ ] Step 4:  agents/reviewer.py — replace entire file
[ ] Step 5:  agents/integrator.py — replace entire file
[ ] Step 6:  agents/junior.py — replace entire file
[ ] Step 7:  .env — rewrite (two new keys)
[ ] Step 8:  supervisor.py — 6 targeted edits:
     [ ] 8a: MODEL_PRICING (lines 137-151)
     [ ] 8b: rules loading (lines 366-369)
     [ ] 8c: architect task (line 408)
     [ ] 8d: reviewer task (lines 473-475)
     [ ] 8e: integrator task (line 502)
     [ ] 8f: console output (line 630)
[ ] Step 9:  README.md (lines 49-55)
[ ] Step 10: Verify — python models.py (prints catalog)
[ ] Step 11: Verify — python supervisor.py taskmanager
```

---

## HOW TO SWITCH MODELS (after implementation)

Open `models.py`, find `AGENT_MODELS`, change the string:

```python
AGENT_MODELS = {
    "architect":   "glm-5",              # was "gemini-3.1-pro"
    "coder":       "minimax-m2.5",       # was "gpt-5.1-codex-mini"
    "reviewer":    "claude-sonnet-4.6",  # keep
    "integrator":  "kimi-k2.5",          # switch to OpenCode Go version
}
```

Nothing else needs to change.

---

## RISKS

| Risk | Mitigation |
|------|-----------|
| OpenCode Go 500 error (known bug with usage tokens) | `litellm.num_retries = 5` already set in supervisor.py |
| Extended thinking Sonnet 4.6 not activating | max_tokens=16000; fallback: extra_headers |
| Kimi K2.5 tool calling incompatible with CrewAI | Fallback: kimi-k2 (more stable) |
| Large rules/ folders after removing only= filter | Add max_chars param to load_rules() |
| Vercel free tier ($5/30d) insufficient | Pro plan or BYOK |
