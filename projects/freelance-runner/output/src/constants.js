export const COLORS = {
  PRIMARY_BACKGROUND: 0x1a1a2e,
  ACCENT_GLOW: 0x00f5ff,
  DANGER_GLOW: 0xff0044,
  BOOSTER_GLOW: 0xff00ff,
  HUD_HIGHLIGHT: 0x00ff88,
  MENU_TEXT: 0xf2f2f2,
  GROUND: 0x0f0f17
};

export const TEXTURE_KEYS = {
  PLAYER: 'player',
  GROUND: 'ground',
  BACKGROUND_CITY_FAR: 'bg_city_far',
  BACKGROUND_CITY_NEAR: 'bg_city_near',
  BACKGROUND_CITY_DECOR: 'bg_city_decor',
  BACKGROUND_STORM_FAR: 'bg_city_storm_far',
  BACKGROUND_STORM_NEAR: 'bg_city_storm_near',
  BACKGROUND_STORM_DECOR: 'bg_city_storm_decor',
  BACKGROUND_SUNRISE_FAR: 'bg_city_sunrise_far',
  BACKGROUND_SUNRISE_NEAR: 'bg_city_sunrise_near',
  BACKGROUND_SUNRISE_DECOR: 'bg_city_sunrise_decor',
  OBSTACLE_BASIC: 'obs_basic',
  OBSTACLE_NONPAYING_CLIENT: 'obs_nonpaying_client',
  OBSTACLE_UNPAID_INVOICE: 'obs_unpaid_invoice',
  OBSTACLE_PPT_PRESENTATION: 'obs_ppt_presentation',
  OBSTACLE_ADOBE_CRASH: 'obs_adobe_crash',
  OBSTACLE_RESET_WEAPON: 'obs_reset_weapon',
  OBSTACLE_SAFARI_BROWSER: 'obs_safari_browser',
  BOOSTER_PASSIVE_INCOME: 'boost_passive_income',
  BOOSTER_COFFEE: 'boost_coffee',
  BOOSTER_GOOD_CLIENT: 'boost_good_client',
  BOOSTER_NEW_SKILL: 'boost_new_skill'
};

export const ANIM_KEYS = {
  PLAYER_IDLE: 'player_idle',
  PLAYER_RUN: 'player_run',
  PLAYER_JUMP: 'player_jump',
  PLAYER_DEAD: 'player_dead'
};

export const HAPPINESS_TIERS = {
  BURNOUT: { label: 'Burnout', min: 0, max: 25 },
  STRESSED: { label: 'Stressed', min: 26, max: 50 },
  OK: { label: 'OK', min: 51, max: 75 },
  FLOW: { label: 'Flow State', min: 76, max: 100 }
};

export const OBSTACLE_TYPES = [
  'basic',
  'nonpaying_client',
  'unpaid_invoice',
  'ppt_presentation',
  'adobe_crash',
  'reset_weapon',
  'safari_browser'
];

export const BOOSTER_TYPES = [
  'passive_income',
  'coffee',
  'good_client',
  'new_skill'
];

export const PHYSICS = {
  GRAVITY: 900
};

export const JUMP_VELOCITIES = {
  BURNOUT: -380,
  STRESSED: -430,
  OK: -480,
  FLOW: -520,
  DOUBLE: -420
};

export const MECHANICS = {
  BASE_EARNINGS_PER_PIXEL: 0.1,
  HAPPINESS_DECAY_AMOUNT: 1,
  HAPPINESS_DECAY_INTERVAL_MS: 3000,
  MIN_SCROLL_SPEED: 150,
  SCROLL_SPEED_RAMP_INTERVAL_MS: 15000,
  SCROLL_SPEED_RAMP_INCREMENT: 5,
  COFFEE_SCROLL_BOOST: 0.3,
  COFFEE_DURATION_MS: 5000,
  PPT_SCROLL_REDUCTION: 0.2,
  PPT_DURATION_MS: 5000,
  ADOBE_CRASH_DURATION_MS: 6000,
  PASSIVE_INCOME_DURATION_MS: 8000,
  NEW_SKILL_MULTIPLIER_STEP: 1.2,
  NEW_SKILL_MULTIPLIER_MAX: 2.0,
  HAPPINESS_MIN: 0,
  HAPPINESS_MAX: 100,
  DOUBLE_JUMP_THRESHOLD: 76,
  WEAPON_COOLDOWN_MS: 3000,
  DISTANCE_PER_EARNING: 10
};

export const LEVEL_CONFIGS = {
  normal: {
    id: 'normal',
    label: 'Normální den',
    backgroundPrefix: 'bg_city',
    obstacleRate: 1.2,
    boosterRate: 0.8,
    baseScrollSpeed: 300,
    durationMs: 30000
  },
  krize: {
    id: 'krize',
    label: 'Krize',
    backgroundPrefix: 'bg_neon',
    obstacleRate: 1.6,
    boosterRate: 0.5,
    baseScrollSpeed: 260,
    durationMs: 22000
  },
  rust: {
    id: 'rust',
    label: 'Růst',
    backgroundPrefix: 'bg_rust',
    obstacleRate: 0.9,
    boosterRate: 1.1,
    baseScrollSpeed: 340,
    durationMs: 28000
  }
};

export const SPAWN_WEIGHTS = {
  normal: {
    obstacles: {
      basic: 0.3,
      nonpaying_client: 0.15,
      unpaid_invoice: 0.2,
      ppt_presentation: 0.1,
      adobe_crash: 0.1,
      reset_weapon: 0.07,
      safari_browser: 0.08
    },
    boosters: {
      passive_income: 0.25,
      coffee: 0.3,
      good_client: 0.2,
      new_skill: 0.25
    }
  },
  krize: {
    obstacles: {
      basic: 0.35,
      nonpaying_client: 0.2,
      unpaid_invoice: 0.05,
      ppt_presentation: 0.15,
      adobe_crash: 0.05,
      reset_weapon: 0.03,
      safari_browser: 0.02
    },
    boosters: {
      passive_income: 0.2,
      coffee: 0.2,
      good_client: 0.3,
      new_skill: 0.3
    }
  },
  rust: {
    obstacles: {
      basic: 0.2,
      nonpaying_client: 0.1,
      unpaid_invoice: 0.15,
      ppt_presentation: 0.1,
      adobe_crash: 0.05,
      reset_weapon: 0.05,
      safari_browser: 0.05
    },
    boosters: {
      passive_income: 0.3,
      coffee: 0.2,
      good_client: 0.3,
      new_skill: 0.2
    }
  }
};

export const STORAGE_KEYS = {
  HIGHSCORE: 'freelance_runner_highscore'
};

export const FONT_FAMILY = 'Host Grotesk';
