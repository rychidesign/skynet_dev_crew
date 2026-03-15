# Levels

## References
- Related: specs/data-model.md — LevelConfig shape
- Related: specs/mechanics.md — scroll speed formulas
- Related: specs/visual-style.md — background texture descriptions

---

## Level Types

| ID | Label | Obstacle Rate | Booster Rate | Base Scroll Speed | Duration |
|----|-------|--------------|--------------|-------------------|----------|
| `normal` | Normální den | 1.2/s | 0.8/s | 300 px/s | 30s |
| `krize` | Krize | 2.2/s | 0.4/s | 360 px/s | 25s |
| `rust` | Růst | 0.6/s | 1.4/s | 280 px/s | 35s |

## Level Cycling
- Levels cycle in random order, no two same levels in a row
- On level transition: show level name overlay for 2s, then fade in new background
- Scroll speed resets to base value of new level on transition
- Active effects (freeze, invert, etc.) persist across level transitions

---

## Backgrounds

| Level | Texture Key Prefix | Description |
|-------|--------------------|-------------|
| `normal` | `bg_city` | City skyline, neon signs, night purple sky |
| `krize` | `bg_city_storm` | Same city, red tint, rain overlay, flickering neons |
| `rust` | `bg_city_sunrise` | City at sunrise, warm neon + orange gradient |

- Each background uses 3-layer parallax (far/near/decor)
- Full texture keys: `{prefix}_far`, `{prefix}_near`, `{prefix}_decor`
- Ground layer: separate `ground` TileSprite, same across all levels
- Background textures generated procedurally in BootScene (see specs/visual-style.md)

---

## Obstacle Spawn Weights per Level

| Obstacle | Normal | Krize | Růst |
|----------|--------|-------|------|
| `basic` | 30% | 35% | 20% |
| `nonpaying_client` | 15% | 20% | 10% |
| `unpaid_invoice` | 20% | 20% | 15% |
| `ppt_presentation` | 15% | 15% | 20% |
| `adobe_crash` | 10% | 5% | 15% |
| `reset_weapon` | 5% | 3% | 10% |
| `safari_browser` | 5% | 2% | 10% |

## Booster Spawn Weights per Level

| Booster | Normal | Krize | Růst |
|---------|--------|-------|------|
| `passive_income` | 25% | 20% | 30% |
| `coffee` | 30% | 35% | 25% |
| `good_client` | 25% | 30% | 20% |
| `new_skill` | 20% | 15% | 25% |
