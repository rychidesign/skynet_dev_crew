# Multiagent Development Supervisor

Systém pro automatický vývoj softwaru pomocí koordinované spolupráce AI agentů.

## Přehled

Multiagent Supervisor koordinuje čtyři specializované AI agenty (Architekt, Kodér, Reviewer, Integrátor), které spolupracují na implementaci softwarových tasků podle specifikací.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   ARCHITEKT  │ ──► │    KODÉR    │ ──► │   REVIEWER   │ ──► │  INTEGRÁTOR  │
│  Plánuje     │     │ Implementuje │     │ Kontroluje   │     │ Finalizuje   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                            │                    │
                            │    ┌───────────────┘
                            │    │
                            ▼    ▼
                         FAIL: Retry (max 5x)
                         PASS: Pokračuj na Integrátor
```

## Rychlý start

```bash
# Instalace závislostí
pip install -r requirements.txt

# Nastavení environment proměnných
cp .env.example .env
# Uprav .env s API klíči

# Spuštění supervisoru
python supervisor.py <project_name>

# S omezením počtu tasků
python supervisor.py <project_name> --tasks 3
```

## Struktura projektu

```
multiagent/
├── supervisor.py           # Hlavní orchestrátor
├── agents/
│   ├── architect.py        # Agent pro plánování
│   ├── coder.py            # Agent pro implementaci
│   ├── reviewer.py          # Agent pro kontrolu
│   └── integrator.py        # Agent pro finalizaci
├── tools/
│   ├── file_reader.py       # Čtení souborů
│   ├── file_writer.py       # Zápis souborů
│   ├── file_size_check.py   # Kontrola délky souborů
│   ├── list_dir.py          # Výpis adresářů
│   ├── find_files.py        # Hledání souborů
│   ├── search_content.py    # Vyhledávání v obsahu
│   ├── lint_check.py        # Kontrola syntaxe
│   ├── image_generator.py   # Generování obrázků
│   ├── telegram_notify.py   # Telegram notifikace
│   └── ask_human.py         # Dotazy na uživatele
├── models.py               # Konfigurace LLM modelů
├── projects/
│   └── <project_name>/
│       ├── SPECS.md         # Specifikace projektu
│       ├── PROGRESS.md      # Seznam tasků
│       ├── rules/           # Pravidla pro agenty
│       │   ├── general.md
│       │   └── do-not.md
│       ├── specs/           # Detailní specifikace
│       └── output/          # Vygenerovaný kód
└── docs/
    └── WORKFLOW.md          # Detailní dokumentace workflow
```

## Workflow

### Tři fáze zpracování

#### Fáze 1: ARCHITEKT
- Spustí se **jednou** na začátku tasku
- Analyzuje specifikace a vytváří technický plán
- Výstup: `output/plan.md`

#### Fáze 2: KODÉR + REVIEWER (smyčka)
- **Kodér** implementuje kód podle plánu
- **Reviewer** kontroluje implementaci
- Pokud Reviewer vrátí **FAIL**, Kodér opravuje a proces se opakuje
- Maximálně **5 pokusů**
- Teprve po **PASS** pokračuje na Fázi 3

#### Fáze 3: INTEGRÁTOR
- Spustí se **pouze po PASS** od Reviewera
- Sjednocuje kód, aktualizuje importy
- Ověřuje konzistenci pro deployment

### Klíčová změna oproti původnímu workflow

**Původní problém:** Integrátor se spouštěl i když Reviewer vrátil FAIL.

**Řešení:** Nové workflow ve 3 fázích s explicitní kontrolou PASS/FAIL před spuštěním Integrátoru.

Více detailů v [docs/WORKFLOW.md](docs/WORKFLOW.md).

## Nástroje pro kontrolu délky souborů

### Proč je to důležité

Velké soubory jsou:
- Těžší na údržbu a review
- Častěji obsahují chyby
- Obtížněji se testují
- Porušují princip Single Responsibility

### Limity

| Typ souboru | Maximální počet řádků |
|-------------|----------------------|
| Backend (`.py`, `.go`, `.rs`, `.java`, `.rb`, `.php`) | 200 |
| Frontend (`.tsx`, `.ts`, `.jsx`, `.js`, `.vue`, `.svelte`, `.css`) | 150 |

### Použití

Nástroje `file_size_check` a `directory_size_check` jsou automaticky dostupné Kodérovi a Reviewerovi.

```python
# Kontrola jednoho souboru
file_size_check("output/services/user_service.py")

# Kontrola celého adresáře
directory_size_check("output/")
```

### Jak rozdělit velký soubor

1. **Extrahujte helper funkce** do utility souborů
2. **Rozdělte UI komponenty** na menší subkomponenty
3. **Extrahujte business logiku** do service souborů
4. **Extrahujte typy** do samostatných souborů

Více v [tools/README.md](tools/README.md).

## Pravidla pro agenty

Pravidla jsou definována v `projects/<name>/rules/`:

### `general.md`
- Tech stack projektu
- Konvence pro TypeScript a Python
- Pravidla pro pojmenování
- Pravidla pro importy
- **File Size limity** (kritické)

### `do-not.md`
- Co agenti NESMÍ dělat
- **File Size Limits** (kritické)
- TypeScript/Python specifická omezení
- UI pravidla
- Supabase pravidla

## Konfigurace

### Environment proměnné

```bash
# LLM Provider
LITELLM_MODEL=anthropic/claude-sonnet-4-6
ANTHROPIC_API_KEY=your-key

# nebo
LITELLM_MODEL=gemini/gemini-2.5-flash
GOOGLE_API_KEY=your-key

# Telegram notifikace (volitelné)
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_CHAT_ID=your-chat-id
```

### Modely pro agenty

Konfigurovatelné v `models.py`:

```python
AGENT_MODELS = {
    "architect": "anthropic/claude-sonnet-4-6",
    "coder": "anthropic/claude-sonnet-4-6",
    "reviewer": "anthropic/claude-sonnet-4-6",
    "integrator": "anthropic/claude-haiku-4-5",
}
```

## Vytvoření nového projektu

1. Vytvořte adresář `projects/<project_name>/`
2. Přidejte `SPECS.md` s přehledem projektu
3. Přidejte `PROGRESS.md` se seznamem tasků
4. Vytvořte `rules/general.md` a `rules/do-not.md`
5. Přidejte detailní specifikace do `specs/`

```bash
mkdir -p projects/my-project/rules
mkdir -p projects/my-project/specs
touch projects/my-project/SPECS.md
touch projects/my-project/PROGRESS.md
touch projects/my-project/rules/general.md
touch projects/my-project/rules/do-not.md
```

## Monitoring

### Telegram notifikace

Supervisor posílá notifikace o:
- Začátku tasku
- Úspěšném dokončení tasku
- Chybách a selháních
- Dokončení celého projektu

### Usage tracking

Token usage a náklady se ukládají do `logs/usage.json`:

```json
{
  "Architekt": {
    "model": "anthropic/claude-sonnet-4-6",
    "input_tokens": 15000,
    "output_tokens": 3000,
    "cost_total": 0.09
  },
  "_total": {
    "input_tokens": 50000,
    "output_tokens": 10000,
    "cost_usd": 0.30
  }
}
```

## Architektura agentů

### Architekt
- **Role**: Plánování a dekompozice tasků
- **Model**: Claude Sonnet 4.6
- **Výstup**: Technický plán v `output/plan.md`

### Kodér
- **Role**: Implementace kódu
- **Model**: Claude Sonnet 4.6
- **Nástroje**: file_reader, file_writer, file_size_check, list_dir, search_content, image_generator
- **Max iterací**: 30

### Reviewer
- **Role**: Kontrola implementace
- **Model**: Claude Sonnet 4.6
- **Nástroje**: file_reader, list_dir, find_files, search_content, lint_check, file_size_check, directory_size_check
- **Max iterací**: 15

### Integrátor
- **Role**: Finalizace a konzistence
- **Model**: Claude Haiku 4.5 (levnější pro jednodušší úkoly)
- **Nástroje**: file_reader, file_writer, list_dir, search_content

## Troubleshooting

### Supervisor už běží

```bash
# Zkontrolujte běžící proces
cat /tmp/multiagent_supervisor.lock

# Ukončete předchozí instanci
kill <PID>
```

### Task selhal po 5 pokusech

Supervisor se zastaví a vyžaduje manuální intervenci:
1. Zkontrolujte `output/` adresář
2. Přečtěte chybovou zprávu od Reviewera
3. Opravte problémy manuálně nebo upravte specifikace
4. Spusťte supervisor znovu

### Soubory překračují limity

Reviewer odmítne PASS, pokud soubory překračují limity:
1. Zkontrolujte `rules/general.md` pro pokyny
2. Rozdělte soubory podle best practices
3. Spusťte retry

## Dokumentace

- [WORKFLOW.md](docs/WORKFLOW.md) - Detailní popis workflow a změn
- [tools/README.md](tools/README.md) - Dokumentace nástrojů

## Licence

MIT