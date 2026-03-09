# Multiagent Development System

## Struktura

```
multiagent/
├── supervisor.py           # Hlavní orchestrátor
├── .env                   # API klíče
├── requirements.txt       # Python závislosti
├── config.yaml           # Konfigurace
├── agents/               # Definice agentů
│   ├── architect.py      # Claude Opus
│   ├── coder.py          # Claude Sonnet
│   └── junior.py         # Gemini Flash
├── tools/                # Nástroje
│   ├── telegram_notify.py
│   ├── ask_human.py
│   ├── file_writer.py
│   └── file_reader.py
└── projects/
    ├── taskmanager/      # Projekt 1: PWA Task Manager
    ├── smarthomeapp/     # Projekt 2: Electron.js
    └── mojewebportfolio/ # Projekt 3: Statické stránky
```

## Jak spustit projekt

```bash
# 1. Nainstaluj závislosti
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Uprav .env (vlož API klíče)

# 3. Spusti agenta
python supervisor.py taskmanager
python supervisor.py smarthomeapp
python supervisor.py mojewebportfolio
```

## Každý projekt

Každý projekt má vlastní složku v `projects/`:
- `SPECS.md` - co se má vytvořit
- `instructions.md` - instrukce pro agenty
- `output/` - výsledky (vytvoří agenti)

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
