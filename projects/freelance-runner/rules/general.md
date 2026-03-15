# General Coding Conventions

## Tech Stack
Phaser 3 (CDN), JavaScript ES6+, single HTML entry point,
Host Grotesk via Google Fonts, LocalStorage for highscore.
No build tools, no npm, no TypeScript.

## JavaScript
- ES6+ only: const/let, arrow functions, destructuring, template literals
- No external dependencies beyond Phaser 3 CDN
- No global variables — all state on `this.game` or passed via constructor

## Naming
- Classes: PascalCase (`GameScene`, `ObstacleManager`)
- Functions/variables: camelCase (`spawnObstacle`, `earningsMultiplier`)
- Constants: UPPER_SNAKE_CASE (`BASE_SCROLL_SPEED`, `MAX_HAPPINESS`)
- Files: kebab-case (`game-scene.js`, `obstacle-manager.js`)
- Phaser texture keys: snake_case strings (`'bg_city_far'`, `'obs_basic'`)

## File Structure
- Entry point: `index.html` (loads Phaser CDN + all JS modules via script type="module")
- Each Phaser Scene in its own file: `src/scenes/`
- Game logic managers in: `src/managers/`
- Constants in: `src/constants.js`
- Utils in: `src/utils/`
- No inline scripts in index.html beyond Phaser game config init

## File Size
- Max 150 lines per file — split into managers if larger
- Scenes handle only Phaser lifecycle (create/update/destroy)
- Business logic goes in manager classes, not scenes

## Imports
- Use ES6 modules (`type="module"` on all script tags)
- Import order: Phaser → constants → managers → utils
- No circular dependencies

## DRY
- Search existing managers before writing new utility functions
- All numeric values must live in constants.js — never inline
