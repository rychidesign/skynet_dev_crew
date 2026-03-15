# Phaser 3 Rules

## Setup
- Load via CDN in index.html: `https://cdn.jsdelivr.net/npm/phaser@3/dist/phaser.min.js`
- All scenes registered in Phaser config at init — no dynamic scene loading
- `pixelArt: true` in config — mandatory for crisp pixel rendering

## Scene Lifecycle
```javascript
class MyScene extends Phaser.Scene {
  constructor() { super({ key: 'MyScene' }); }
  create(data) { /* init, runs once per scene start */ }
  update(time, delta) { /* runs every frame — keep lightweight */ }
  shutdown() { /* cleanup: remove event listeners, destroy tweens */ }
}
```
- Always remove `this.game.events` listeners in shutdown() to prevent leaks
- Pass data between scenes via `this.scene.start('SceneName', { key: value })`

## Physics
- Arcade physics only — no Matter.js
- Gravity set globally in config: `{ y: 900 }`
- Player body: `setCollideWorldBounds(true)` for ground detection
- Ground: static physics group — `this.physics.add.staticGroup()`
- Collision: `this.physics.add.collider(player, ground)`
- Overlap (boosters/obstacles): `this.physics.add.overlap(player, group, callback)`

## TileSprite (backgrounds)
```javascript
const bg = this.add.tileSprite(0, 0, 800, 160, 'bg_city_far').setOrigin(0, 0);
// In update():
bg.tilePositionX += scrollSpeed * 0.2 * delta / 1000;
```
- Always use `tilePositionX` for scrolling — never move the sprite position
- Anchor at origin (0,0), positioned at top-left

## Object Groups & Pooling
```javascript
// Create pool
this.group = this.physics.add.group({ maxSize: 10, runChildUpdate: false });

// Spawn from pool
const sprite = this.group.get(x, y, 'texture_key');
if (!sprite) return; // pool exhausted — skip spawn
sprite.setActive(true).setVisible(true);
sprite.body.reset(x, y);

// Return to pool
sprite.setActive(false).setVisible(false);
sprite.body.reset(-100, -100);
```

## Text & Fonts
```javascript
this.add.text(x, y, 'text', {
  fontFamily: 'Host Grotesk',
  fontSize: '16px',
  color: '#00f5ff'
});
```
- Host Grotesk loaded via Google Fonts `<link>` in index.html `<head>` — must precede game init
- Always use hex string colors in text style objects (not 0x format)

## Tweens
- Create via `this.tweens.add({})` — Phaser manages cleanup on scene shutdown
- For looping tweens on pooled objects: store tween reference, call `tween.stop()` on despawn

## DO NOT (Phaser-specific)
- DO NOT use `setInterval` or `setTimeout` — use `this.time.addEvent()` instead
- DO NOT use `addEventListener` on window — use Phaser input system
- DO NOT mix scene.update() logic with manager logic — keep scenes thin
