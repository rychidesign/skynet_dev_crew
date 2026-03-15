# Component & Sprite Conventions

## Sprite Creation
- Player: `this.physics.add.sprite(x, y, 'player')` with frame index
- Obstacles/Boosters: created via Phaser Groups (object pooling)
- All textures already generated in BootScene — never call `this.load` in other scenes

## Procedural Texture Generation (BootScene only)
```javascript
// Pattern for every texture:
const g = this.make.graphics({ x: 0, y: 0, add: false });
g.fillStyle(0x1a1a2e);       // use hex from COLORS constants
g.fillRect(x, y, w, h);
g.generateTexture('texture_key', width, height);
g.destroy();
```
- Always destroy graphics object after generateTexture()
- Texture keys must match TEXTURE_KEYS constants exactly
- Draw order matters — later draws appear on top

## Animations
- All defined in BootScene after all textures generated
- Use `this.anims.create({ key: ANIM_KEYS.PLAYER_RUN, frames: [...], frameRate: 8, repeat: -1 })`
- Animation keys from ANIM_KEYS in constants.js
- Player animations: `player_idle`, `player_run`, `player_jump`, `player_dead`

## Object Pooling
- ObstacleManager: `this.group = scene.physics.add.group({ maxSize: 10 })`
- BoosterManager: `this.group = scene.physics.add.group({ maxSize: 6 })`
- Spawn: `const sprite = this.group.get(x, y, textureKey)`
- Despawn: `sprite.setActive(false).setVisible(false).body.reset(0, 0)`
- Never call `sprite.destroy()` on pooled objects — return to pool instead

## Neon Glow (postFX)
- Player: `sprite.postFX.addGlow(0x00f5ff, 2, 1)`
- Boosters: `sprite.postFX.addGlow(0xff00ff, 3, 1)`
- HUD earnings text: `text.postFX.addGlow(0x00ff88, 1, 0)`
- Use sparingly — max glow on 3–4 elements at once for performance

## Booster Bob Tween
```javascript
scene.tweens.add({
  targets: boosterSprite,
  y: '+=6',
  duration: 800,
  ease: 'Sine.easeInOut',
  yoyo: true,
  repeat: -1
});
```

## HUD Text Objects
- All created in HUDScene.create()
- Font style: `{ fontFamily: 'Host Grotesk', fontSize: '16px', color: '#00f5ff' }`
- Happiness icons: array of 5 Text objects, update character on scoreUpdate event
- Effect pills: created dynamically on effectsUpdate, destroyed when effect expires
- Depth: HUD elements at depth 100, game elements at depth 0–10
