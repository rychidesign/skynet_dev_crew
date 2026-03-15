# Agent Instructions

## Project
Browser-based Phaser 3 runner game. No build tools, no npm.
All output goes to `projects/freelance-runner/output/`.

## Key Reminders
- All textures generated procedurally in BootScene — never load external image files
- All numeric constants in `src/constants.js` — never inline numbers in scenes/managers
- HUDScene communicates with GameScene via `this.game.events` only
- Single `gameState` object lives on `this.game` — passed by reference to all managers
- Test in browser after every task — check console for Phaser warnings

## Known Pitfalls
- Phaser object pools: always call `group.get()` before `group.create()` to avoid leaks
- Parallax backgrounds: use `tilePositionX` on TileSprite, not manual position updates
- ES module `type="module"` required on all script tags in index.html
- Host Grotesk must load before BootScene completes — add to HTML `<head>` as Google Fonts link
