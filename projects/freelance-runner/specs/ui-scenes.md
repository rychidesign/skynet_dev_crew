# UI & Scenes

## References
- Related: specs/data-model.md — GameState, ScoreState
- Related: specs/mechanics.md — happiness tiers, earnings display
- Related: specs/visual-style.md — colors, font, neon glow rules

---

## Phaser Scene List

| Scene Key | Purpose |
|-----------|---------|
| `BootScene` | Preload assets, generate procedural textures, define animations |
| `MenuScene` | Main menu, highscore display, start button |
| `GameScene` | Main gameplay loop |
| `HUDScene` | Overlay HUD (runs parallel to GameScene via scene.launch) |
| `LevelTransitionScene` | Level name overlay between levels |
| `GameOverScene` | Final score, highscore, restart |

---

## MenuScene Layout

```
┌─────────────────────────────────┐
│  [FREELANCE RUNNER]  (neon title)│
│                                 │
│   Highest Earnings: $12,450     │
│                                 │
│      [ START ]  (neon button)   │
│                                 │
│   pixel art character idle anim │
└─────────────────────────────────┘
```

---

## HUD Layout (GameScene overlay)

```
┌─────────────────────────────────┐
│ 😊😊😊😀😀   $4,230   [🔫]   │  ← top bar
│ LEVEL: Krize                    │
│ [☕ +30% speed 3s] [effect pill] │
└─────────────────────────────────┘
```

- Happiness: 5 emoji icons (filled/empty based on value, each icon = 20pts)
- Earnings: right-aligned, `$X,XXX` format, NEON_GREEN color
- Weapon icon: grayed (alpha 0.3) when unavailable
- Level name: small label top-left, color-coded (normal=cyan, krize=red, rust=yellow)
- Active effects: small pill text objects below top bar, created/destroyed dynamically
- HUD background: semi-transparent dark strip, height 48px

---

## GameOverScene Layout

```
┌─────────────────────────────────┐
│        GAME OVER                │
│                                 │
│   Earnings: $6,780              │
│   Best:     $12,450             │
│   NEW BEST! (if applicable)     │
│                                 │
│   [ RESTART ]   [ MENU ]        │
└─────────────────────────────────┘
```

---

## LevelTransition Overlay

- Semi-transparent dark overlay (`#000000`, alpha 0.7) over GameScene
- Level name in large neon font (48px), centered
- Level type label below (24px, color-coded)
- Fade in 0.3s → hold 1.5s → fade out 0.3s
- GameScene paused during transition (`scene.pause('GameScene')`)
- Resume GameScene after transition complete

---

## Visual Style Rules

- Font: Host Grotesk (all UI text, loaded via Google Fonts in index.html head)
- Colors (use COLORS constants from constants.js):
  - Canvas background: `#0a0a0f`
  - Neon primary: `#00f5ff` (cyan)
  - Neon accent: `#ff00ff` (magenta)
  - Earnings text: `#00ff88` (green)
  - Danger/obstacle: `#ff3333` (red)
  - Booster: `#ffff00` (yellow)
- Phaser config: `pixelArt: true`
- Neon glow on key elements: `sprite.postFX.addGlow(color, outerStrength, innerStrength)`
- Canvas size: 800×400px
