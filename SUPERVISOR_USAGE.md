# Bezpečné spuštění Supervisoru & Monitoru

## 🚀 Supervisor

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

