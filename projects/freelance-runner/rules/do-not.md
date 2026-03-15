# DO NOT Rules for AI Agents

## Universal
- DO NOT modify files outside the scope of your current task
- DO NOT duplicate logic — check managers before writing new functions
- DO NOT use magic numbers — every value must be in constants.js
- DO NOT write files longer than 150 lines — split into managers
- DO NOT edit PROGRESS.md — Supervisor handles this
- DO NOT call file_writer with empty content
- DO NOT truncate file content — always write complete files

## JavaScript
- DO NOT use `var` — use `const` or `let` only
- DO NOT use global variables — all state on `this.game`
- DO NOT use inline event handlers in HTML

## Asset Loading
- DO NOT load external image files — all textures generated procedurally in BootScene
- DO NOT call `this.load.image()` or `this.load.spritesheet()` in any scene
- DO NOT use external URLs for any game asset

## Phaser-Specific
- DO NOT call `scene.start()` on a scene already running — use `scene.restart()`
- DO NOT access another scene's properties directly — use `this.game.events` emitter
- DO NOT create physics bodies outside of GameScene or ObstacleManager/BoosterManager
- DO NOT add update logic to HUDScene — HUD reacts to events only
- DO NOT hardcode canvas dimensions — use `this.scale.width` / `this.scale.height`
- DO NOT call `sprite.destroy()` on pooled objects — return to pool with setActive(false)

## Architecture
- DO NOT put game logic (earnings, happiness, spawning) inside Scene files
- DO NOT skip object pooling for obstacles and boosters
- DO NOT store game state in Manager instances — use shared `gameState` on `this.game`
- DO NOT emit events from HUDScene — HUD only listens, never emits
