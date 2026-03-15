# Game Mechanics

## References
- Related: specs/data-model.md — PlayerState, ScoreState, Effect shapes
- Related: specs/levels.md — base scroll speeds, level durations

---

## Earnings System

- Earnings auto-increment every frame based on distance traveled
- Base rate: `1 earnings per 10px traveled`
- Modified by:
  - `earningsMultiplier` (passive income booster): multiplies final increment
  - `new_skill` booster: `earningsRate *= 1.2` (stacks, max 2.0x)
  - `earningsFrozen`: increments paused entirely during Adobe Crash
- Earnings never go below 0
- Displayed as currency: `$1,234`

---

## Happiness System

| Range | Label | Effect |
|-------|-------|--------|
| 0–25 | Burnout | Jump height -40%, no double jump |
| 26–50 | Stressed | Jump height -15%, no double jump |
| 51–75 | OK | Normal jump height |
| 76–100 | Flow State | Jump height +20%, double jump enabled |

- Happiness decays: -1 per 3s passively
- Capped 0–100
- Displayed as icon bar (5 icons, each = 20pts)

---

## Jump Physics

- Single jump: applies upward velocity based on happiness tier
- Double jump: available only in Flow State (happiness 76–100), resets on grounding
- Jump velocities (px/s):

| Tier | Single Jump | Double Jump |
|------|-------------|-------------|
| Burnout | -380 | — |
| Stressed | -430 | — |
| OK | -480 | — |
| Flow State | -520 | -420 |

- Gravity: 900 px/s²
- Player x position: fixed at 15% of canvas width

---

## Weapon System

- Player starts with weapon: `hasWeapon = true`
- Weapon allows destroying one `basic` obstacle (instead of game over)
- Weapon cooldown after use: 3s (cannot pick up another during cooldown)
- `reset_weapon` obstacle sets `hasWeapon = false` immediately
- Visual: small icon on HUD; grayed out when unavailable

---

## Scroll Speed

- Base speed defined per level (see levels.md)
- Modified by:
  - `coffee` booster: +30% for 5s
  - `ppt_presentation` obstacle: -20% for 5s
  - Global speed ramp: +5 px/s every 15s of total run time (difficulty curve)
- Effects stack additively on top of base speed
- Minimum scroll speed: 150 px/s (never slower)

---

## Collision Detection

- Phaser Arcade Physics, rectangular hitboxes
- Obstacle hitbox: 80% of sprite size (forgiving hit detection)
- Booster hitbox: same as sprite size
- On obstacle collision: apply effect, destroy obstacle sprite
- On `basic` obstacle:
  - If `hasWeapon = true`: destroy obstacle, start weapon cooldown
  - If `hasWeapon = false`: trigger game over
