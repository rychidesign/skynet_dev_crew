# Testing Conventions

## Approach
Manual browser testing — no automated test framework.
Open `output/index.html` directly in browser (no server needed for static files).

## Required Checks per Task
- Open in Chrome and Firefox — zero console errors or warnings
- Verify feature works end-to-end in a full gameplay run
- Check no Phaser texture warnings ("Texture not found")
- Check no physics body errors on scene restart

## Gameplay Test Cases

### Obstacles
- `basic`: game over triggered (no weapon), OR weapon consumed + cooldown starts
- `nonpaying_client`: earnings decrease by 500, never below 0
- `unpaid_invoice`: earnings decrease by 50
- `ppt_presentation`: happiness -20, scroll speed visibly slower for 5s
- `adobe_crash`: earnings stop incrementing for 6s, then resume
- `reset_weapon`: weapon icon grays out immediately
- `safari_browser`: controls invert for 4s (left/right or up behavior changes)

### Boosters
- `passive_income`: earnings increment visibly faster for 8s
- `coffee`: scroll speed visibly increases for 5s
- `good_client`: earnings +500, happiness +20
- `new_skill`: happiness +15, earnings rate increases

### Mechanics
- Happiness tiers: jump height visibly changes crossing 25/50/75 boundaries
- Double jump: only available above 75 happiness — verify blocked below
- Earnings freeze + multiplier do not conflict (freeze wins)
- Level transition: overlay appears, game pauses, background changes, resumes correctly
- No two consecutive identical levels
- Speed ramp: scroll speed increases after each 15s interval

### Persistence
- Highscore saves to LocalStorage key `freelance_runner_highscore` on game over
- Highscore loads and displays correctly on MenuScene after page refresh
- "NEW BEST!" shows only when new highscore achieved

## Console Checks
- No `undefined` on gameState fields during update loop
- No "Cannot read properties of null" errors
- No Phaser deprecation warnings
