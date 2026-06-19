// Single source of truth for the completeness grade scale, used by BOTH the
// grade pills and the discovery class chips (starship / multi-tool class).
// Keep these in lockstep with:
//   - the .grade-* / .bar-* rules in src/styles/index.css
//   - the inline copies in the map HTML (public/VH-System-View.html,
//     public/VH-Cartographer.html) which can't import JS modules.
//
// In-game scheme (per Parker): S = Gold, A = Purple, B = Blue, C = Green.
// S+ ("fully charted") is a checklist tier that sits ON TOP of S — a system
// that scores S AND has a discovery on every body, wonder notes on every
// planet, a documented base, and a recorded station. It renders Diamond Cyan.

export const TIER_COLORS = {
  'S+': '#22d3ee', // diamond cyan (fully charted)
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

// Solid grade-chip styling: a background hue + a readable dark foreground per
// grade. THIS is the single source for every grade badge/tile across the app
// (system cards, detail header, posters, wizard preview). `{ bg, fg }` shape
// matches the poster StatTile convention; GRADE_BADGE_STYLE below mirrors it
// in CSS `{ background, color }` form for JSX inline-style consumers.
export const GRADE_BADGE = {
  'S+': { bg: '#22d3ee', fg: '#083344' }, // diamond cyan on deep cyan
  S: { bg: '#ffd700', fg: '#422006' }, // gold
  A: { bg: '#c084fc', fg: '#2e1065' }, // purple
  B: { bg: '#60a5fa', fg: '#082f49' }, // blue
  C: { bg: '#4ade80', fg: '#052e16' }, // green
}

// Same colors, CSS-style keys, for `style={GRADE_BADGE_STYLE[grade]}` badges.
export const GRADE_BADGE_STYLE = Object.fromEntries(
  Object.entries(GRADE_BADGE).map(([g, { bg, fg }]) => [g, { background: bg, color: fg }]),
)

/** C/B/A/S(/S+) letter -> hue (used for both class chips and grade pills). */
export function classColor(value) {
  if (value == null) return null
  return TIER_COLORS[String(value).trim().toUpperCase()] || null
}

// Grade pills use the exact same scale as item class.
export const gradeColor = classColor

/** Grade letter -> solid {bg, fg} tile, falling back to C. */
export function gradeBadge(grade) {
  if (grade == null) return GRADE_BADGE.C
  return GRADE_BADGE[String(grade).trim().toUpperCase()] || GRADE_BADGE.C
}

/** Common / Rare / Extraordinary -> color. */
export function richnessColor(value) {
  if (value == null) return null
  return RICHNESS_COLORS[String(value).trim().toLowerCase()] || null
}
