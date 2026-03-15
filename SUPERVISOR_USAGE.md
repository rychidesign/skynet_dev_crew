# Bezpečné spuštění Supervisoru & Monitoru

## 🚀 Supervisor (v3.2.1)

### Nové 3-fázové workflow

Supervisor nyní používá **3-fázové workflow** místo lineárního:

```
FÁZE 1: ARCHITEKT (spustí se jednou)
    ↓
FÁZE 2: KODÉR + REVIEWER (smyčka s retry, max 5 pokusů)
    ↓
    ├─ PASS → pokračuj na FÁZE 3
    └─ FAIL → retry nebo ukonči
    ↓
FÁZE 3: INTEGRÁTOR (jen po PASS od Reviewera)
```

**Výhody:**
- Architekt neběží při retry (úspora tokenů)
- Integrátor neběží po FAIL (úspora tokenů)
- Retry smyčka jen pro Kodér+Reviewer

### 🆕 v3.1: Oddělené Crews

Kodér a Reviewer běží v **oddělených Crews**:

```
┌─────────────────┐         ┌─────────────────┐
│  CODER CREW     │         │  REVIEWER CREW  │
│  (samostatný)   │────────▶│  (samostatný)   │
│                 │         │  Čte z DISKU    │
└─────────────────┘         └─────────────────┘
```

**Výhody:**
- Reviewer čte soubory přímo z disku (ne z kontextu)
- Menší token využití
- Lepší izolace chyb

### 🆕 v3.2: Task Guardrails

Reviewer má nyní **guardrail validaci** pomocí separátního modulu `guardrails.py`:

```python
from guardrails import validate_reviewer_verdict_format, validate_reviewer_mentions_tools

# Reviewer task s guardrails (plural!)
reviewer_task = Task(
    ...,
    guardrails=[
        validate_reviewer_verdict_format,   # 1. PASS/FAIL formát
        validate_reviewer_mentions_tools,   # 2. evidence nástrojů
    ],
    guardrail_max_retries=2,  # Max 2 interní retry
)
```

**Co guardrails kontrolují (sekvenčně):**

1. **`validate_reviewer_verdict_format()`**
   - Kontroluje PASS/FAIL na prvním řádku
   - Ignoruje PASS/FAIL uvnitř textu review

2. **`validate_reviewer_mentions_tools()`**
   - Kontroluje evidence použití `list_dir`
   - Kontroluje evidence použití `directory_size_check` / `file_size_check`
   - Hledá indikátory jako: `├──`, `└──`, `files in`, `size_check`, `lines`, atd.

**Pokud guardrail selže:**
- Reviewer dostane až 2 interní retry pokusy
- Po vyčerpání retry → FAIL a pokračuje se v hlavní retry smyčce

**Strukturované logování:**
Všechny retry události se logují do `logs/retry_events.jsonl`:
```json
{"timestamp":"2025-03-15T14:30:00","event":"FAIL","task":"Task 2.4","attempt":2,"max_attempts":5}
```

---

## 🔄 Retry Behavior (v3.1 - v3.2)

### FAIL Feedback Extraction

Při FAIL od Reviewera se feedback **zkracuje** na 1.5k znaků:

```python
def extract_fail_issues(reviewer_output: str, max_chars: int = 1500) -> str:
    """Extrahuje a zkracuje FAIL feedback pro Kodér."""
    # Zachová nejdůležitější issues
    # Zabrání nekonečné smyčce
```

**Proč?**
- Dlouhý feedback → Kodér se zacyklí ve stejných chybách
- Zkrácený feedback → Kodér se soustředí na klíčové issues

### Escalation při 3+ Retry

Při 3+ retry pokusech dostane Kodér **escalation instrukce**:

```
⚠️ ESCALATION: Toto je pokus č. 3+
Zaměř se na:
1. Přesně dodržuj specifikaci
2. Kontroluj každý soubor před odesláním
3. Pokud si nejsi jistý, zeptej se
```

### Fallback pro Empty Output

Pokud Reviewer vrátí **prázdný výstup**:

```python
if not reviewer_output or reviewer_output.strip() == "":
    # Detailní diagnostika
    empty_msg = (
        f"⚠️  VAROVÁNÍ: reviewer_task.output je None\n"
        f"   Pokus: {attempt}/{max_attempts}\n"
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
    
    continue  # Retry
```

**Notifikace:**
- Log do konzole
- Log do `logs/retry_events.jsonl`
- Telegram zpráva pro monitoring

### Pravidlo: MAX 1 instance najednou

Supervisor má **single-instance lock** — nelze spustit dvakrát.

#### ✅ Správné použití:

```bash
# V terminálu 1
cd ~/multiagent
source venv/bin/activate
python3 supervisor.py taskmanager
```

**To je všechno!** Supervisor běží, agent pracují.

#### ❌ Co se stane, když zkusíš spustit znovu:

```bash
# V terminálu 2
python3 supervisor.py taskmanager
# Výstup: ❌ Supervisor již běží (PID 12345). Ukonči ho nejdřív.
#         kill 12345
```

#### Jak zastavit supervisor:

```bash
# Pokud běží v foreground
Ctrl+C

# Pokud běží v background
kill <PID>

# Nebo si nechej info
ps aux | grep supervisor.py | grep taskmanager
```

---

## 📊 Monitor

### Pravidlo: Multiple instance jsou povoleny (je to jen viewer)

Monitor **NEMÁ lock** — můžeš spustit několik v různých terminálech pro tutéž log.

#### ✅ Správné použití:

```bash
# V terminálu 1 (Live realtime log)
cd ~/multiagent
python3 monitor.py

# V terminálu 2 (stejný log, odlišný view)
cd ~/multiagent
python3 monitor.py

# V terminálu 3 (jiný log)
cd ~/multiagent
python3 monitor.py logs/other_project.log
```

Všechny monitory běží **bez konfliktu**. Každá instance má vlastní ID.

#### Co monitory dělají:

- Zobrazuje live activity (agents, tokens, costs)
- Zpřístupňuje timeline  
- Nápomáhá debugovat workflow
- **Žádné zásahy do supervisor logiky** — jen viewer

---

## 📋 Bezpečný Workflow

### 1. Příprava

```bash
cd ~/multiagent
source venv/bin/activate
```

### 2. Spuštění Supervisoru (1× terminal)

```bash
# Terminal 1 — SUPERVISOR
python3 supervisor.py taskmanager
# Bude běhat cca 5-120 minut podle tasku
```

### 3. Monitoring (libovolné počty terminálů)

```bash
# Terminal 2 — MONITOR #1
python3 monitor.py

# Terminal 3 — MONITOR #2  
python3 monitor.py

# Terminal 4 — Cokoliv dalšího (git, vim, atd)
# ...
```

### 4. Po Skončení

```bash
# Supervisor se sám vypnul v Terminálů 1
# Monitory si přestaly mít co dělat → skončily

# Zkontroluj výsledek
head -20 projects/taskmanager/output/plan.md
tail -20 projects/taskmanager/PROGRESS.md
```

---

## 🛡️ Ochrana proti chybám

### Já jdu do sleep a zapomenu supervisor zastavit

```bash
# Supervisor běží 180 minut max (auto-timeout)
# Pak se sám vypne
```

### Chci zastavit supervisor aby se tím ušetřily peníze

```bash
# Terminál 1
Ctrl+C

# Supervisor okamžitě skončí, uvolní lock
# Lock se AUTOMATICKY smaže

# Můžeš hned spustit znovu:
python3 supervisor.py taskmanager
```

### Supervisor se vzbudil s chybou a lock zůstal

```bash
# Vzácný případ — supervisor se zwalal bez cleanup

# Smaž lock ručně:
rm /tmp/multiagent_supervisor.lock

# Pak spusť znovu:
python3 supervisor.py taskmanager
```

### Více monitorů v jednom terminálů (backgrounding)

```bash
# Spusť oba v background
python3 monitor.py &
sleep 1
python3 monitor.py logs/other.log &

# Oba běží, můžeš zadávat další příkazy
ls
cd projects/taskmanager

# Vrátit do foreground:
fg %1  # monitor 1
fg %2  # monitor 2
```

---

## 🎯 Příklad: Optimální Setup

```bash
# Terminal 1: Supervisor
$ python3 supervisor.py taskmanager

# Terminal 2: Monitor realtime
$ python3 monitor.py

# Terminal 3: Pracuj na něčem jiném
$ cd projects/taskmanager && git status

# Terminal 4: Telegafu notifikace
$ tail -f logs/taskmanager.log | grep ERROR
```

---

## ⚠️ Opakujeme: CO NE DĚLAT

❌ **Nespouštěj dva supervisory najednou** — lock tě zastaví  
❌ **Nespouštěj supervisor bez `source venv/bin/activate`** — chybí packages  
❌ **Nesmažeš `/tmp/multiagent_supervisor.lock` během běhu** — supervisor by se zhroutil  
✅ **Spouštěj monitory jak chceš** — jsou read-only  
✅ **Ctrl+C supervisor pokud je třeba** — lock se sám uvolní  
✅ **Spouštěj supervisor vždycky ze `~/multiagent`** — cesty jsou relativní  

---

## 🔧 Advanced: Limitování Cost

Pokud vidíš `Invalid response from LLM - None or empty`:

```bash
# To znamená rate limit od AI provideru
# Příčiny:
# 1. Dva supervisory najednou (dnes fixnuto)
# 2. Prompt je příliš velký (fixnuto — truncation na 5000 znaků)
# 3. Opakující se retry (fixnuto — zkráceno z 60s/120s na 10s/20s)

# Řešení: počkej 5 minut a zkus znovu
sleep 300
python3 supervisor.py taskmanager
```

---

## 📞 Troubleshooting

| Symptom | Příčina | Řešení |
|---------|--------|--------|
| `❌ Supervisor již běží` | Jiná instance běží | `kill <PID>` nebo čekej na skončení |
| `ModuleNotFoundError: crewai` | Venv není aktivován | `source venv/bin/activate` |
| `Invalid response from LLM` | Rate limit | Čekej 5 minut a zkus znovu |
| Monitor se nespustí | Log file neexistuje | `mkdir -p logs && touch logs/taskmanager.log` |
| Integrátor běží po FAIL | Stará verze supervisoru | Aktualizuj na v3.0+ |
| 🆕 `Guardrail failed` | Reviewer nevalidní výstup | Automaticky retry (max 2) |
| 🆕 `Empty reviewer output` | Reviewer neodpověděl | Log + Telegram notifikace, retry |
| 🆕 `Escalation mode` | 3+ retry pokusy | Normální chování, Kodér dostane speciální instrukce |
| 🆕 `Feedback truncated` | FAIL feedback > 1.5k znaků | Normální chování, zkráceno pro efektivitu |
| 🆕 `logs/retry_events.jsonl` chybí | První spuštění | Vytvoří se automaticky při prvním retry |

**Kde najít logy:**
- `logs/retry_events.jsonl` — strukturované retry události (PASS, FAIL, ESCALATION, EMPTY_OUTPUT, EXHAUSTED)
- `logs/usage.json` — token usage a cost tracking
- `logs/<project>.log` — hlavní log projektu

---

## 🆕 Nové funkce v3.0 - v3.2

### v3.2.1: Guardrails Module & Structured Logging

```python
# guardrails.py - separátní modul
from guardrails import validate_reviewer_verdict_format, validate_reviewer_mentions_tools

# Reviewer task s plural guardrails=[]
reviewer_task = Task(
    guardrails=[
        validate_reviewer_verdict_format,   # 1. PASS/FAIL formát
        validate_reviewer_mentions_tools,   # 2. evidence nástrojů
    ],
    guardrail_max_retries=2,
)

# Strukturované JSONL logování
log_retry_event("FAIL", task_name, attempt, max_attempts, {
    "reason": "Reviewer returned FAIL",
    "reviewer_output_length": 1234,
})
# → logs/retry_events.jsonl
```

**5 typů událostí:**
- `PASS` — Reviewer vrátí PASS
- `FAIL` — Reviewer vrátí FAIL
- `ESCALATION` — 3+ retry pokusy
- `EMPTY_OUTPUT` — Reviewer vrátí prázdný výstup
- `EXHAUSTED` — Vyčerpány všechny pokusy

### v3.2: Guardrails & Orchestration

```python
# Extrahované orchestrace funkce
run_architect_phase()      # FÁZE 1
run_code_review_phase()    # FÁZE 2 (s retry loop)
run_integrator_phase()     # FÁZE 3

# Fallback pro empty output s detailní diagnostikou
if not reviewer_output:
    empty_msg = (
        f"⚠️  VAROVÁNÍ: reviewer_task.output je None\n"
        f"   Reviewer max_iter: {getattr(reviewer, 'max_iterations', '?')}\n"
        f"   Reviewer max_time: {getattr(reviewer, 'max_execution_time', '?')}s\n"
    )
    send_telegram_message(empty_msg)
    log_retry_event("EMPTY_OUTPUT", ...)
```

### v3.1: Crew Separation & Feedback

```python
# Oddělené Crews
coder_crew = Crew(agents=[coder], tasks=[coder_task])
reviewer_crew = Crew(agents=[reviewer], tasks=[reviewer_task])

# Reviewer čte z disku (ne z kontextu)
# FAIL feedback zkrácen na 1.5k znaků
feedback = extract_fail_issues(reviewer_output, max_chars=1500)

# Robustní verdict check (jen první řádek)
first_line = output.strip().split('\n')[0]
if "PASS" in first_line.upper():
    return True
```

### v3.0: File Size Limits

Kodér a Reviewer nyní kontrolují délku souborů:

```python
# Backend: max 200 lines
# Frontend: max 150 lines

# Nástroje:
# - file_size_check: kontrola jednotlivých souborů
# - directory_size_check: kontrola všech souborů v adresáři
```

### v3.0: 3-Phase Workflow

```python
# FÁZE 1: Architekt (jednou)
# FÁZE 2: Kodér + Reviewer (smyčka s retry)
# FÁZE 3: Integrátor (jen po PASS)
```

### Retry Logic

```python
# Retry smyčka jen pro Kodér+Reviewer
# Architekt neběží při retry
# Integrátor neběží po FAIL
# v3.1: FAIL feedback zkrácen na 1.5k znaků
# v3.2: Guardrail max 2 interní retry pro Reviewer
# v3.2.1: Guardrails v guardrails.py, plural guardrails=[]
# v3.2.1: Strukturované JSONL logování (logs/retry_events.jsonl)
```
