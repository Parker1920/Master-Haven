// Canonical star-type tint hex — mirrors the .pill-star-* tokens in
// src/styles/index.css (the single source of truth per the 2.0 design
// conventions). Previews, posters, and SVG/canvas renderers can't use the CSS
// classes, so the hex values are mirrored here ONCE instead of being
// re-hardcoded (and drifting) in each component. If the .pill-star-* values
// ever change in index.css, update these to match.
export const STAR_HEX = {
  Yellow: '#facc15',
  Red: '#ef4444',
  Blue: '#3b82f6',
  Green: '#10b981',
  Purple: '#a855f7',
}

/**
 * Resolve a star type to its canonical hex tint.
 * @param {string} starType - e.g. "Yellow", "Blue"
 * @param {string} [fallback] - color when the type is unknown/empty
 * @returns {string} hex color
 */
export function starHex(starType, fallback = '#64748b') {
  if (!starType) return fallback
  return STAR_HEX[String(starType).trim()] || fallback
}
