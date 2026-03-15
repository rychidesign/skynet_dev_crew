# Detailní technický plán pro Task 1.1: Project scaffold + constants

## 1. Dekompozice tasku (Subtasky)

Tento úkol buduje fundamentální základ celého projektu. Abychom splnili požadavek nulového počtu chyb v prohlížeči (zero console errors) a projekt se úspěšně spustil v `index.html`, je **nezbytné** už v tomto kroku vytvořit tzv. zástupné scény (stubs). Konfigurace Phaseru totiž vyžaduje zavedení definovaných modulů a jejich nenalezení by vedlo ke kritické chybě 404 (modul nenalezen).

**Subtask 1.1: Inicializace adresářové struktury a zástupných scén (Stubs)**
- Založení složek `src` a `src/scenes` ve složce `output`.
- Vytvoření 6 prázdných Phaser scén (odvozených z `Phaser.Scene`) se správnými klíči v konstruktoru (např. `BootScene`, `MenuScene`, atd.).

**Subtask 1.2: Vytvoření konfiguračního souboru `constants.js`**
- Přepis veškerých statických čísel, konfigurací levelů, hexadecimálních barev, rychlostí a pravděpodobností z markdown specifikací (`levels.md`, `mechanics.md`, `visual-style.md`, `data-model.md`).
- Výsledkem bude čistě deklarativní JavaScriptový modul plný konstant (`export const`), na kterém budou závislé všechny další systémy.

**Subtask 1.3: Vytvoření vstupního HTML dokumentu (`index.html`)**
- Deklarace HTML5 hlavičky s přednačtením Google fontu Host Grotesk.
- Zahrnutí Phaseru 3 z definovaného CDN jsDelivr.
- Vytvoření ES modulu (`<script type="module">`), který naimportuje zástupné scény a inicializuje objekt `Phaser.Game(config)` podle definované architektury.

---

## 2. Soubory k vytvoření a jejich obsah

*(Všechny cesty jsou uváděny relativně k `projects/freelance-runner/output/`)*

### 2.1 Zástupné scény (Scaffold)
Vytvořte 6 následujících souborů ve složce `src/scenes/`:
- `BootScene.js`
- `MenuScene.js`
- `GameScene.js`
- `HUDScene.js`
- `LevelTransitionScene.js`
- `GameOverScene.js`

*Každý z nich bude obsahovat základní kostru. Příklad pro `BootScene.js`:*
```javascript
export class BootScene extends Phaser.Scene {
    constructor() {
        super({ key: 'BootScene' });
    }
}
```

### 2.2 `src/constants.js`
Centrální úložiště herních dat. Bude obsahovat:
- **`COLORS`**: Hexadecimální barvy jako čísla: `NEON_CYAN: 0x00f5ff`, `NEON_MAGENTA: 0xff00ff`, `NEON_GREEN: 0x00ff88`, `NEON_YELLOW: 0xffff00`, `NEON_RED: 0xff3333`, `NEON_ORANGE: 0xff8800`, `DARK_BG: 0x0a0a0f`, `DARK_BODY: 0x1a1a2e`, `DARK_MID: 0x16213e`, `GROUND_BLUE: 0x0f3460`, `WHITE: 0xffffff`.
- **`TEXTURE_KEYS`**: Klíče textur: `PLAYER: 'player'`, `GROUND: 'ground'`, překážky `OBS_BASIC: 'obs_basic'`, atd., boostery `BST_PASSIVE: 'bst_passive'`, atd., a prefixy pro pozadí (např. `BG_CITY_FAR: 'bg_city_far'`).
- **`ANIM_KEYS`**: Klíče animací (`PLAYER_IDLE: 'player_idle'`, `PLAYER_RUN: 'player_run'`, `PLAYER_JUMP: 'player_jump'`, `PLAYER_DEAD: 'player_dead'`).
- **`HAPPINESS_TIERS`**: Definice hranic a názvů (Burnout, Stressed, OK, Flow State).
- **`OBSTACLE_TYPES` a `BOOSTER_TYPES`**: Unikátní řetězcové konstanty (např. `'nonpaying_client'`, `'coffee'`).
- **`PHYSICS`**: Gravitace (`GRAVITY: 900`).
- **`JUMP_VELOCITIES`**: Skokové rychlosti pro tier (`BURNOUT: -380`, `STRESSED: -430`, `OK: -480`, `FLOW_STATE: -520`, `DOUBLE_JUMP: -420`).
- **`MECHANICS`**: Pravidla hry jako `EARNINGS_RATIO_PX: 10` (1 výdělek za 10px), `HAPPINESS_DECAY_AMOUNT: 1`, `HAPPINESS_DECAY_MS: 3000`, `WEAPON_COOLDOWN_MS: 3000`, `MIN_SCROLL_SPEED: 150`, `SPEED_RAMP_PX: 5`, `SPEED_RAMP_INTERVAL_MS: 15000`.
- **`LEVEL_CONFIGS` a `SPAWN_WEIGHTS`**: Podrobné přepsání tabulek ze specifikace `levels.md`.

### 2.3 `index.html`
Základní konfigurační a spouštěcí soubor.
- **`<head>`:** 
  - Standardní `meta charset`, `<title>`.
  - Import Google Fontu "Host Grotesk" přes `<link>` tag.
  - Vlastní tag `<style>` pro minimalizaci okrajů a vycentrování plátna na tmavém pozadí (`body { margin: 0; background-color: #0a0a0f; display: flex; justify-content: center; align-items: center; height: 100vh; }`).
- **`<body>`:**
  - Zahrnutí CDN pro Phaser 3 (`https://cdn.jsdelivr.net/npm/phaser@3/dist/phaser.min.js`).
  - `<script type="module">`: Zde se naimportuje 6 scén z lokálních souborů. Dále se definuje `const config` podle předepsané architektury (`width: 800, height: 400, pixelArt: true`, arcade physics gravitace 900, pole `scene`). Následně se instancuje `new Phaser.Game(config)`.

---

## 3. Interfaces a Datové struktury (Shape konstant)

V projektu používáme vanilkový ES6 JavaScript. I tak ale musí složitější objekty v `constants.js` zachovat strukturu, aby na ni mohly pozdější systémy bezpečně spoléhat:

```javascript
export const LEVEL_CONFIGS = {
    normal: { id: 'normal', label: 'Normální den', bgPrefix: 'bg_city', obstacleRate: 1.2, boosterRate: 0.8, baseSpeed: 300, duration: 30000 },
    krize: { id: 'krize', label: 'Krize', bgPrefix: 'bg_city_storm', obstacleRate: 2.2, boosterRate: 0.4, baseSpeed: 360, duration: 25000 },
    rust: { id: 'rust', label: 'Růst', bgPrefix: 'bg_city_sunrise', obstacleRate: 0.6, boosterRate: 1.4, baseSpeed: 280, duration: 35000 }
};

export const SPAWN_WEIGHTS = {
    normal: {
        obstacles: { basic: 0.30, nonpaying_client: 0.15, unpaid_invoice: 0.20, ppt_presentation: 0.15, adobe_crash: 0.10, reset_weapon: 0.05, safari_browser: 0.05 },
        boosters: { passive_income: 0.25, coffee: 0.30, good_client: 0.25, new_skill: 0.20 }
    },
    krize: {
        obstacles: { basic: 0.35, nonpaying_client: 0.20, unpaid_invoice: 0.20, ppt_presentation: 0.15, adobe_crash: 0.05, reset_weapon: 0.03, safari_browser: 0.02 },
        boosters: { passive_income: 0.20, coffee: 0.35, good_client: 0.30, new_skill: 0.15 }
    },
    rust: {
        obstacles: { basic: 0.20, nonpaying_client: 0.10, unpaid_invoice: 0.15, ppt_presentation: 0.20, adobe_crash: 0.15, reset_weapon: 0.10, safari_browser: 0.10 },
        boosters: { passive_income: 0.30, coffee: 0.25, good_client: 0.20, new_skill: 0.25 }
    }
};

export const HAPPINESS_TIERS = {
    BURNOUT: { min: 0, max: 25, label: 'Burnout' },
    STRESSED: { min: 26, max: 50, label: 'Stressed' },
    OK: { min: 51, max: 75, label: 'OK' },
    FLOW_STATE: { min: 76, max: 100, label: 'Flow State' }
};
```

---

## 4. Závislosti mezi komponentami

- **`index.html`:** Má kritickou závislost na dostupnosti sítě (stažení Phaseru z CDN a Google fontů) a také absolutní závislost na přítomnosti zástupných `.js` modulů. Nesmí chybět žádný, jinak engine spadne na ES Module chybě. Typ scriptu musí být striktně `type="module"`.
- **`constants.js`:** Izolovaný datový konfigurační repozitář (Single Source of Truth). Nesmí importovat žádný cizí kód, všechny ostatní manažery budou výhledově importovat jej.

---

## 5. Pořadí implementace (pro Codera)

1. **Adresářová struktura:** V projektu `output` založte složku `src` a v ní podsložku `scenes`.
2. **Stubs scén:** V adresáři `scenes/` vytvořte všech 6 výše specifikovaných `.js` souborů. Do každého dejte základní ES6 třídu, která rozšiřuje `Phaser.Scene` a má funkční klíč v konstruktoru.
3. **Konstanty:** Vytvořte soubor `output/src/constants.js`. Manuálně, přehledně a pečlivě do něj z markdown specifikací přeneste barvy, klíče, fyziku, pravděpodobnosti a definice úrovní.
4. **Vstupní soubor:** Založte `output/index.html`. Nakódujte hlavičku (Google Fonts, tag style), a tělo (Phaser CDN script). Pak napište inicializační `script type="module"`, provedete v něm 6 importů scén, definujete config a spustíte hru.
5. **Verifikace úkolu:** Otevřete `index.html` v prohlížeči. Úkol je splněn pouze tehdy, když na obrazovce uvidíte černý vycentrovaný herní blok (800x400) a když stisknete F12, v konzoli se neukáže absolutně žádné varování ani chybová hláška.