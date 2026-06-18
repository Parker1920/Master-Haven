// Single source of truth for the in-game C/B/A/S color scale, used by BOTH the
// completeness grade pills and the discovery class chips (starship / multi-tool
// class). Keep these in lockstep with:
//   - the .grade-* / .bar-* rules in src/styles/index.css
//   - the inline copies in the map HTML (public/VH-System-View.html,
//     public/VH-Cartographer.html) which can't import JS modules.
//
// In-game scheme (per Parker): S = Gold, A = Purple, B = Blue, C = Green.

export const TIER_COLORS = {
  S: '#ffd700', // gold
  A: '#c084fc', // purple
  B: '#60a5fa', // blue
  C: '#4ade80', // green
}

// Mineral deposit richness reuses the top of the same scale (3 tiers).
export const RICHNESS_COLORS = {
  extraordinary: '#ffd700', // gold
  rare: '#c084fc', // purple
  common: '#4ade80', // green
}

/** C/B/A/S letter -> color (used for both class chips and grade pills). */
export function classColor(value) {
  if (value == null) return null
  return TIER_COLORS[String(value).trim().toUpperCase()] || null
}

// Grade pills use the exact same scale as item class.
export const gradeColor = classColor

/** Common / Rare / Extraordinary -> color. */
export function richnessColor(value) {
  if (value == null) return null
  return RICHNESS_COLORS[String(value).trim().toLowerCase()] || null
}
