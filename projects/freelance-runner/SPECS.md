# Freelance Runner – Overview

## What We're Building
A browser-based 2D side-scrolling platformer about a freelance graphic designer
surviving the chaos of freelance life. Single-player, no backend, no auth.
**Language:** Czech UI labels, English code

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Game Engine | Phaser 3 (CDN) |
| Language | JavaScript ES6+ |
| Font | Host Grotesk (Google Fonts) |
| Persistence | LocalStorage (highscore) |
| Deployment | Static page (GitHub Pages / Netlify) |

## Core Hierarchy

```
GameState
  └── Level (Normal / Krize / Růst)
        ├── Player (position, happiness, earnings, weapon, state)
        ├── Obstacle[] (type, effect, x/y)
        └── Booster[] (type, effect, x/y)
```

## User Roles
Single-player, no auth required.

## Key Features (MVP)
- Auto-scrolling runner with jump mechanics
- Happiness stat controls jump height; double jump unlocked above threshold
- Earnings auto-increment by distance; modified by obstacles/boosters
- 6 obstacle types with distinct effects
- 4 booster types with distinct effects
- 3 level types cycling in random order (Normal / Krize / Růst)
- Pixel neon 90s visual style, Host Grotesk font
- LocalStorage highscore persistence

## Detailed Specs

| File | Covers |
|------|--------|
| specs/data-model.md | Game entities, state shape, obstacle/booster definitions |
| specs/levels.md | Level types, spawn rates, backgrounds |
| specs/mechanics.md | Earnings formula, happiness system, jump physics |
| specs/ui-scenes.md | Phaser scenes, HUD layout, menus |
| specs/visual-style.md | Procedural texture descriptions, sprite dimensions, colors |

## Agent Workflow
1. Read SPECS.md
2. Find current task in PROGRESS.md (← CURRENT)
3. Read only spec files listed in your task
4. Read relevant rules files
5. Do ONLY your assigned task
6. End session — Supervisor handles PROGRESS.md
