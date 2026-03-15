# Tools - Nástroje pro AI Agenty

Tento adresář obsahuje nástroje (tools) používané AI agenty v multiagentním systému. Nástroje jsou implementovány jako CrewAI BaseTool a poskytují agentům schopnost interagovat s filesystémem a dalšími službami.

## Přehled nástrojů

| Nástroj | Popis | Používá |
|---------|-------|---------|
| `file_reader.py` | Čtení souborů z filesystému | Všichni agenti |
| `file_writer.py` | Zápis souborů na filesystém | Kodér, Integrátor |
| `file_size_check.py` | Kontrola délky souborů | Kodér, Reviewer |
| `list_dir.py` | Výpis obsahu adresáře | Všichni agenti |
| `find_files.py` | Hledání souborů podle vzoru | Reviewer |
| `search_content.py` | Fulltextové vyhledávání v souborech | Všichni agenti |
| `lint_check.py` | Kontrola syntaxe kódu | Reviewer |
| `image_generator.py` | Generování obrázků | Kodér |
| `telegram_notify.py` | Notifikace přes Telegram | Supervisor |
| `ask_human.py` | Dotazování uživatele | Všichni agenti |

---

## `file_size_check.py`

Nástroj pro kontrolu limitů délky souborů. Kritický pro udržení kódu modulárního a čitelného.

### Účel

Zajišťuje, že žádný soubor nepřekračuje maximální povolený počet řádků:

- **Backend soubory**: max 200 řádků
- **Frontend soubory**: max 150 řádků

### Podporované přípony

#### Backend (200 řádků)
`.py`, `.go`, `.rs`, `.java`, `.rb`, `.php`

#### Frontend (150 řádků)
`.tsx`, `.ts`, `.jsx`, `.js`, `.vue`, `.svelte`, `.css`, `.scss`

### Dva nástroje

#### 1. `FileSizeCheckTool` (`file_size_check`)

Kontroluje jeden soubor.

**Parametry:**
- `file_path` (str): Cesta k souboru (relativní k projektu)

**Příklad použití:**
```python
from tools.file_size_check import create_file_size_check

tool = create_file_size_check("/home/project")
result = tool._run("output/services/user_service.py")
# ✅ PASS: output/services/user_service.py has 85 lines (max 200 for Backend).
```

**Výstup při překročení limitu:**
```
❌ FAIL: output/components/Dashboard.tsx has 180 lines, exceeds 150 line limit for Frontend.
   Current: 180 lines
   Maximum: 150 lines
   Exceeded by: 30 lines
   Solution: Split this file into smaller modules or extract helper functions.
```

#### 2. `DirectorySizeCheckTool` (`directory_size_check`)

Kontroluje všechny soubory v adresáři.

**Parametry:**
- `directory` (str): Adresář k kontrole (prázdný = celý projekt)

**Příklad použití:**
```python
from tools.file_size_check import create_directory_size_check

tool = create_directory_size_check("/home/project")
result = tool._run("output/")
# ✅ PASS: All 45 files are within size limits.
```

**Výstup při nalezení překročení:**
```
❌ FAIL: 3 of 45 files exceed size limits:
   - output/components/Dashboard.tsx: 180 lines (max 150 for Frontend)
   - output/services/analytics.py: 250 lines (max 200 for Backend)
   - output/lib/utils.ts: 200 lines (max 150 for Frontend)

Solution: Split large files into smaller modules or extract helper functions.
```

### Integrace s agenty

#### Kodér (`agents/coder.py`)

Kodér má k dispozici `file_size_check` a je instruován:

```python
# V backstory Kodéra:
"""
CRITICAL FILE SIZE LIMITS:
- Backend files: MAX 200 LINES
- Frontend files: MAX 150 LINES

BEFORE submitting your code, use file_size_check tool to verify each file
does not exceed the line limit. If it does, refactor immediately.
"""
```

#### Reviewer (`agents/reviewer.py`)

Reviewer má k dispozici `directory_size_check` a je instruován:

```python
# V backstory Reviewera:
"""
CRITICAL: Before issuing PASS verdict, you MUST:
1. Use directory_size_check to verify no file exceeds line limits
2. Use lint_check to verify code compiles without errors
3. Verify all files mentioned in the Architect's plan exist

If ANY file exceeds the line limit:
- Return FAIL with the specific file and line count
- Require the Coder to split the file before proceeding
"""
```

### Best Practices

#### Pro Kodéra

1. **Před zápisem**: Plánujte strukturu souboru tak, aby nepřekročil limit
2. **Po zápisu**: Vždy spusťte `file_size_check` na každý vytvořený soubor
3. **Při překročení**: Okamžitě rozdělte soubor na menší moduly

#### Pro Reviewera

1. **Vždy spusťte** `directory_size_check` před vydáním PASS verdiktu
2. **Vypište konkrétní soubory** které překračují limity
3. **Nevydejte PASS** dokud nejsou všechny soubory v limitu

### Řešení překročení limitů

Když soubor překračuje limit:

1. **Extrahujte helper funkce** do samostatných utility souborů
2. **Rozdělte UI komponenty** na menší subkomponenty
3. **Extrahujte business logiku** do service souborů
4. **Extrahujte typy** do samostatných type souborů
5. **Vytvořte moduly** pro související funkce

**Příklad:**

```python
# Před (300 řádků v jednom souboru):
agents/response_collector.py

# Po (rozděleno na zaměřené soubory):
agents/response_collector.py          # Hlavní orchestrace (~100 řádků)
agents/response_collector/cache.py    # Cache logika (~50 řádků)
agents/response_collector/api.py      # API volání (~80 řádků)
agents/response_collector/db.py       # Databázové operace (~60 řádků)
```

---

## Ostatní nástroje

### `file_reader.py`

Načítá obsah souborů. Podporuje textové soubory, obrázky (base64) a PDF.

### `file_writer.py`

Zapisuje obsah do souborů. Používá se Kodérem a Integrátorem pro vytváření/úpravu souborů.

### `list_dir.py`

Vypisuje obsah adresáře s informacemi o typech souborů.

### `find_files.py`

Hledá soubory podle názvu nebo vzoru (glob pattern).

### `search_content.py`

Vyhledává text v souborech pomocí regulárních výrazů.

### `lint_check.py`

Kontroluje syntaxi kódu pomocí jazykových linterů (Python: ruff, TypeScript: tsc).

### `image_generator.py`

Generuje obrázky pomocí DALL-E nebo jiných modelů.

### `telegram_notify.py`

Posílá notifikace o stavu tasků přes Telegram bot API.

### `ask_human.py`

Umožňuje agentům ptát se uživatele na upřesnění během práce.