# Visual Style Guide — Procedural Textures

## References
- Related: specs/ui-scenes.md — which scenes use which sprites
- Related: specs/data-model.md — TEXTURE_KEYS, ANIM_KEYS constants
- Related: src/constants.js — COLORS object with all hex values

---

## Rendering Rules
- All textures generated in BootScene via:
  `const g = this.make.graphics({x:0,y:0,add:false})`
  → draw shapes → `g.generateTexture(key, w, h)` → `g.destroy()`
- Pixel art: hard edges, no anti-aliasing, no gradients
- Base grid: 8px — all shapes snap to 8px multiples
- Phaser config must have `pixelArt: true`

---

## Color Palette (mirrors COLORS in constants.js)

| Constant | Hex | Used For |
|----------|-----|----------|
| `NEON_CYAN` | `#00f5ff` | Player outline, primary neon, normal level |
| `NEON_MAGENTA` | `#ff00ff` | Accent, booster glow, reset_weapon |
| `NEON_GREEN` | `#00ff88` | Earnings HUD, good_client booster |
| `NEON_YELLOW` | `#ffff00` | Coffee booster, new_skill, rust level |
| `NEON_RED` | `#ff3333` | Danger obstacles, krize level, adobe_crash |
| `NEON_ORANGE` | `#ff8800` | Safari, ppt_presentation, sunrise bg |
| `DARK_BG` | `#0a0a0f` | Canvas background |
| `DARK_BODY` | `#1a1a2e` | Player body fill |
| `DARK_MID` | `#16213e` | Building fills |
| `GROUND_BLUE` | `#0f3460` | Ground tile base |
| `WHITE` | `#ffffff` | Pixel highlights, eyes |

---

## Player Sprite

- Texture key: `player`
- Frame size: 32×48px
- Spritesheet layout: 4 columns × 4 rows = 128×192px total canvas

| Row | Anim Key | Frame Count | Drawing Instructions |
|-----|----------|-------------|----------------------|
| 0 | `player_idle` | 2 | Body: DARK_BODY fillRect(6,16,20,32). Head: DARK_BODY fillRect(8,0,16,16). Outline: NEON_CYAN strokeRect 2px around both. Eyes: WHITE 2×2px at (11,5) and (17,5). Frame 1: body at y+1 (subtle bob). |
| 1 | `player_run` | 4 | Same body+head. Left leg: DARK_BODY fillRect(6,40,6,16). Right leg: DARK_BODY fillRect(20,40,6,16). Per frame: legs offset alternately ±4px vertical, ±2px horizontal. NEON_CYAN outline. |
| 2 | `player_jump` | 2 | Same body+head. Legs tucked: both leg rects moved up to y=36, compressed to 8px tall. Arms: NEON_CYAN fillRect(2,16,4,8) left, fillRect(26,16,4,8) right, raised position. |
| 3 | `player_dead` | 2 | Same body, rotated appearance: draw body tilted (use pixel offset). X eyes: two NEON_RED 2×2 crosses at eye positions. Frame 2: body lower by 4px. |

- postFX after creation: `player.postFX.addGlow(0x00f5ff, 2, 1)`

---

## Ground Tile

- Texture key: `ground`
- Size: 64×32px (TileSprite — will repeat horizontally)
- Fill: GROUND_BLUE fillRect(0,0,64,32)
- Top edge: NEON_CYAN fillRect(0,0,64,2)
- Dashed center line: WHITE 4×1px rects every 16px along y=16
- Bottom strip: DARK_BG fillRect(0,28,64,4)

---

## Background Layers

Each level has 3 TileSprite layers. Generate all 9 textures in BootScene.

### Layer specs

| Layer | Key suffix | Canvas Size | Scroll Speed Multiplier |
|-------|-----------|-------------|------------------------|
| Far buildings | `_far` | 512×160px | 0.2× game speed |
| Near buildings | `_near` | 512×200px | 0.5× game speed |
| Ground decor | `_decor` | 256×48px | 0.8× game speed |

### bg_city (normal)
- `bg_city_far`: DARK_BG fill. Draw 6–8 building rects, widths 32–64px, heights 80–140px, fill DARK_MID, spaced across 512px. Add 4×4px window dots: NEON_CYAN and NEON_MAGENTA alternating, grid pattern on each building.
- `bg_city_near`: DARK_BG fill. Draw 4–5 taller buildings, widths 48–80px, heights 120–180px, fill `#0d0d1a`. Window rows: NEON_CYAN 4×4px dots every 12px.
- `bg_city_decor`: GROUND_BLUE fill. Draw 2–3 small sign rects (24×12px, NEON_CYAN outline). Draw ladder pattern (vertical lines + horizontal rungs, WHITE 1px) on one building edge.

### bg_city_storm (krize)
- Same structure as bg_city but:
- `bg_city_storm_far`: Add dark red overlay: NEON_RED fillRect at alpha 0.15 over full canvas (draw semi-transparent rect). Windows alternate NEON_RED instead of CYAN. Add rain: 8–10 vertical WHITE lines, 1×4px, scattered x positions.
- `bg_city_storm_near`: Same red tint. Windows NEON_RED. Add 4–5 more rain lines.
- `bg_city_storm_decor`: Same as bg_city_decor but signs in NEON_RED.

### bg_city_sunrise (rust)
- `bg_city_sunrise_far`: Sky bands: DARK_BG top 60px, `#1a0a1a` mid 60px, `#2d1b00` bottom 40px (3 fillRect strips). Buildings same shapes, windows NEON_YELLOW and NEON_ORANGE. Add sun rays: 3–4 diagonal 1px NEON_ORANGE lines from top-right corner.
- `bg_city_sunrise_near`: Same sky bands visible behind buildings. Windows NEON_YELLOW. Buildings fill `#0d0d0a`.
- `bg_city_sunrise_decor`: Same as bg_city_decor, signs in NEON_YELLOW.

---

## Obstacle Sprites

Hitbox = 80% of sprite size (set in ObstacleManager, not in texture).

| Type | Key | Size | Drawing Instructions |
|------|-----|------|----------------------|
| `basic` | `obs_basic` | 48×48px | NEON_RED fillRect(4,8,40,40). Top spikes: 4 pixel triangles 8×8px using fillTriangle at x=4,12,20,28 along top edge. WHITE 2×2px highlight at (6,10). |
| `nonpaying_client` | `obs_nonpaying` | 32×48px | Body silhouette: DARK_MID fillRect(6,16,20,32). Head: DARK_MID fillRect(8,4,16,16). Tie: NEON_RED fillRect(13,20,6,14). Wallet above head: WHITE strokeRect(10,0,12,8), small NEON_RED X inside (2 diagonal lines). |
| `unpaid_invoice` | `obs_invoice` | 48×48px | Paper: WHITE fillRect(4,4,40,40). Corner fold: NEON_RED triangle at top-right (fillTriangle). Text lines: `#aaaaaa` fillRect lines at y=16,22,28,34, width 28px. OVERDUE: NEON_RED diagonal cross (2 lines, 2px wide) over paper center. |
| `ppt_presentation` | `obs_ppt` | 48×48px | Monitor: DARK_MID fillRect(4,4,40,36). NEON_ORANGE strokeRect(4,4,40,36) 2px. Stand: DARK_MID fillRect(20,40,8,8). Bar chart on screen: 3 rects inside monitor, heights 8/16/12px, width 6px each, NEON_ORANGE fill, spaced 4px apart. |
| `adobe_crash` | `obs_adobe` | 48×48px | NEON_RED fillRect(4,4,40,40). WHITE strokeRect(4,4,40,40) 1px. Exclamation: WHITE fillRect(21,10,6,20) + fillRect(21,34,6,6). Cracks: 4 diagonal WHITE 1px lines radiating from center (22,22) to corners. |
| `safari_browser` | `obs_safari` | 48×48px | Window: DARK_MID fillRect(4,4,40,40). Title bar: NEON_ORANGE fillRect(4,4,40,10). Compass circle: WHITE strokeRect(14,18,20,20). Cardinal dots: NEON_ORANGE 2×2px at N/S/E/W positions inside circle. |
| `reset_weapon` | `obs_reset` | 48×48px | Horseshoe magnet: two NEON_MAGENTA fillRect(10,8,10,32) and fillRect(28,8,10,32), connected by fillRect(10,8,28,10) at top. Tips: NEON_RED fillRect(10,36,10,6) and fillRect(28,36,10,6). Lightning bolt: WHITE pixel zigzag centered, 1px lines. |

---

## Booster Sprites

| Type | Key | Size | Drawing Instructions |
|------|-----|------|----------------------|
| `passive_income` | `bst_passive` | 32×32px | 3 coin ellipses stacked: bottom NEON_GREEN fillRect(4,20,24,8), mid fillRect(4,13,24,8), top fillRect(4,6,24,8). WHITE 2px arc highlight on top coin top-left. DARK_BG gap lines between coins. |
| `coffee` | `bst_coffee` | 32×32px | Cup body: WHITE fillRect(6,14,20,16). Saucer: WHITE fillRect(4,28,24,4). Coffee fill: `#4a2800` fillRect(8,14,16,4). Handle: WHITE strokeRect(26,16,6,8) 1px. Steam: NEON_YELLOW 1px vertical wavy lines at x=10,16,22 above cup (y=4 to y=12, zigzag). |
| `good_client` | `bst_good_client` | 32×32px | Face circle: NEON_GREEN strokeRect(4,4,24,24) 2px (approximate circle with rect). Eyes: WHITE fillRect(9,10,4,4) and fillRect(19,10,4,4). Smile: WHITE 1px arc approximated as fillRect(9,20,14,2) + corner pixels. Star above: NEON_YELLOW 5-point pixel star at (16,0), 8×8px. |
| `new_skill` | `bst_skill` | 32×32px | Lightning bolt: NEON_YELLOW filled polygon — top point (20,0), right (28,14), mid-right (20,14), bottom (12,32), left (4,18), mid-left (12,18), back to top. WHITE 1px outline around bolt. |

- All boosters postFX: `booster.postFX.addGlow(0xff00ff, 3, 1)`
- All boosters tween: `scene.tweens.add({ targets: booster, y: '+=6', duration: 800, yoyo: true, repeat: -1 })`

---

## HUD Icons (text objects, not textures)

| Element | Value | Font Size | Color |
|---------|-------|-----------|-------|
| Happiness filled | `😊` | 20px | — |
| Happiness empty | `🖤` | 20px | — |
| Weapon available | `🔫` | 20px | alpha 1.0 |
| Weapon unavailable | `🔫` | 20px | alpha 0.3 |
