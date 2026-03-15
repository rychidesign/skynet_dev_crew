# Architecture Rules

## Folder Structure
```
output/
├── index.html                       ← Phaser CDN, Google Fonts, scene registration
└── src/
    ├── constants.js                 ← ALL magic numbers, keys, configs
    ├── Player.js                    ← Player sprite + physics + state
    ├── scenes/
    │   ├── BootScene.js             ← procedural texture generation, anims
    │   ├── MenuScene.js             ← main menu
    │   ├── GameScene.js             ← main game loop
    │   ├── HUDScene.js              ← parallel overlay HUD
    │   ├── LevelTransitionScene.js  ← level name overlay
    │   └── GameOverScene.js         ← end screen
    ├── managers/
    │   ├── ScoreManager.js          ← earnings, happiness, multipliers, LocalStorage
    │   ├── LevelManager.js          ← level cycling, duration timer
    │   ├── EffectManager.js         ← timed effects, tick, emit events
    │   ├── ObstacleManager.js       ← pool, spawn, collision
    │   ├── BoosterManager.js        ← pool, spawn, collision
    │   └── BackgroundManager.js     ← parallax TileSprites, level swap
    └── utils/
        └── format.js                ← formatEarnings(), formatTime()
```

## Separation of Concerns
- **Scenes**: Phaser lifecycle only (create, update, shutdown) — no game logic
- **Managers**: all game logic, state mutations, spawn timers, collision handling
- **Player.js**: player sprite, physics, jump logic, animation state — no score logic
- **constants.js**: every numeric value, string key, and config object
- **HUDScene**: event-driven only — never polls GameScene directly
- **GameScene → HUDScene**: communicate via `this.game.events.emit()`

## State Management
- Single `gameState` object initialized on `this.game` in GameScene.create()
- All managers receive `gameState` reference in constructor
- Managers mutate `gameState` directly — no return values for state changes
- HUDScene reads state only from events, never from `this.game.gameState` directly

## Phaser Config (in index.html)
```javascript
{
  type: Phaser.AUTO,
  width: 800,
  height: 400,
  pixelArt: true,
  physics: { default: 'arcade', arcade: { gravity: { y: 900 }, debug: false } },
  scene: [BootScene, MenuScene, GameScene, HUDScene, LevelTransitionScene, GameOverScene]
}
```

## Scene Communication
- GameScene → HUDScene: `this.game.events.emit('scoreUpdate', payload)`
- GameScene → LevelTransitionScene: `this.scene.launch('LevelTransitionScene', data)`
- GameScene → GameOverScene: `this.scene.start('GameOverScene', { earnings, highscore })`
- HUDScene launched in parallel: `this.scene.launch('HUDScene')` from GameScene.create()
