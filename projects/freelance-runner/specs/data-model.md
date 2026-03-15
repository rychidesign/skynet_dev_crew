# Data Model

## References
- Related: specs/mechanics.md — formulas using these values
- Related: specs/levels.md — level config shape
- Related: specs/ui-scenes.md — HUD reads from GameState

---

## GameState (runtime object)

| Field | Type | Description |
|-------|------|-------------|
| scene | string | Active Phaser scene key |
| level | LevelConfig | Current level config |
| score | ScoreState | Earnings + happiness |
| run | RunState | Distance, timer, speed |
| player | PlayerState | Player runtime state |
| highscore | number | Loaded from LocalStorage |

---

## ScoreState

| Field | Type | Description |
|-------|------|-------------|
| earnings | number | Main score (auto-increments) |
| happiness | number | 0–100, affects jump height |
| earningsMultiplier | number | Default 1.0; boosted by passive income |
| earningsFrozen | boolean | True during Adobe Crash |
| earningsFreezeTimer | number | ms remaining for freeze |

---

## PlayerState

| Field | Type | Description |
|-------|------|-------------|
| x | number | Fixed horizontal position |
| y | number | Vertical position |
| velocityY | number | Current vertical velocity |
| isGrounded | boolean | On ground |
| jumpCount | number | 0/1/2 — tracks double jump |
| hasWeapon | boolean | Weapon available |
| state | PlayerStateEnum | idle/running/jumping/dead |
| activeEffects | Effect[] | Currently applied timed effects |

## PlayerStateEnum
`idle` | `running` | `jumping` | `falling` | `dead`

---

## Obstacle

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique instance id |
| type | ObstacleType | See below |
| x | number | Spawn x position |
| y | number | Spawn y position |
| width | number | Hitbox width |
| height | number | Hitbox height |
| effect | ObstacleEffect | Applied on collision |

## ObstacleType
| Type | Effect |
|------|--------|
| `basic` | Game over |
| `nonpaying_client` | earnings -= 500 |
| `unpaid_invoice` | earnings -= 50 |
| `ppt_presentation` | happiness -= 20, scroll speed -= 20% for 5s |
| `adobe_crash` | earningsFrozen = true for 6s |
| `reset_weapon` | hasWeapon = false |
| `safari_browser` | controls invert for 4s |

---

## Booster

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique instance id |
| type | BoosterType | See below |
| x | number | Spawn x |
| y | number | Spawn y |

## BoosterType
| Type | Effect |
|------|--------|
| `passive_income` | earningsMultiplier = 2.0 for 8s |
| `coffee` | scroll speed +30% for 5s |
| `good_client` | earnings += 500, happiness += 20 |
| `new_skill` | earningsRate *= 1.2 (max 2.0x), happiness += 15 |

---

## LevelConfig

| Field | Type | Description |
|-------|------|-------------|
| id | string | `normal` / `krize` / `rust` |
| label | string | Display name |
| background | string | Phaser texture key prefix |
| obstacleRate | number | Spawns per second |
| boosterRate | number | Spawns per second |
| scrollSpeed | number | Base px/s |
| duration | number | ms before next level |

---

## Effect (timed active effect)

| Field | Type | Description |
|-------|------|-------------|
| type | string | Effect identifier |
| remainingMs | number | Time left |
| payload | object | Effect-specific data |

---

## LocalStorage Schema

| Key | Value |
|-----|-------|
| `freelance_runner_highscore` | number (earnings) |
