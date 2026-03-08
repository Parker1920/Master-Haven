// Colors are loaded from /api/discord_tag_colors on startup.
// Hardcoded values are fallbacks only. Default teal (#00C2B3) is
// used for partners who have not yet set a custom color.

// --- API-driven color cache (populated by ThemeProvider on startup) ---
let _apiColors = {} // { tag: { color: '#hex', name: 'display' } }

/**
 * Called from ThemeProvider after fetching /api/discord_tag_colors.
 * Populates the module-level cache used by all color functions below.
 */
export function setApiTagColors(colors) {
  _apiColors = colors || {}
}

// --- Hardcoded fallbacks (used before API responds or if fetch fails) ---

// Tailwind class format (used by DiscordTagBadge, SystemsList, LeaderboardTable)
export const tagColors = {
  'Haven': 'bg-cyan-500 text-white',
  'IEA': 'bg-green-500 text-white',
  'B.E.S': 'bg-orange-500 text-white',
  'ARCH': 'bg-purple-500 text-white',
  'TBH': 'bg-yellow-500 text-black',
  'EVRN': 'bg-pink-500 text-white',
  'Personal': 'bg-gray-500 text-white',
}

// Tailwind bg-only classes (used by LeaderboardTable pill badges)
export const tagBgColors = {
  'Haven': 'bg-cyan-500',
  'IEA': 'bg-green-500',
  'B.E.S': 'bg-orange-500',
  'ARCH': 'bg-purple-500',
  'TBH': 'bg-yellow-500',
  'EVRN': 'bg-pink-500',
  'Personal': 'bg-gray-500',
}

// Hardcoded hex colors matching the Tailwind classes above
const tagHexColors = {
  'Haven': '#06b6d4',
  'IEA': '#22c55e',
  'B.E.S': '#f97316',
  'ARCH': '#a855f7',
  'TBH': '#eab308',
  'EVRN': '#ec4899',
  'Personal': '#6b7280',
}

// RGBA style object format (used by CommunityStats, CommunityDetail charts/cards)
export const tagColorStyles = {
  'Haven': { bg: 'rgba(6, 182, 212, 0.15)', border: 'rgba(6, 182, 212, 0.3)', text: '#06b6d4' },
  'IEA': { bg: 'rgba(34, 197, 94, 0.15)', border: 'rgba(34, 197, 94, 0.3)', text: '#22c55e' },
  'B.E.S': { bg: 'rgba(249, 115, 22, 0.15)', border: 'rgba(249, 115, 22, 0.3)', text: '#f97316' },
  'ARCH': { bg: 'rgba(168, 85, 247, 0.15)', border: 'rgba(168, 85, 247, 0.3)', text: '#a855f7' },
  'TBH': { bg: 'rgba(234, 179, 8, 0.15)', border: 'rgba(234, 179, 8, 0.3)', text: '#eab308' },
  'EVRN': { bg: 'rgba(236, 72, 153, 0.15)', border: 'rgba(236, 72, 153, 0.3)', text: '#ec4899' },
  'Personal': { bg: 'rgba(107, 114, 128, 0.15)', border: 'rgba(107, 114, 128, 0.3)', text: '#6b7280' },
}

export const defaultTagColorStyle = { bg: 'rgba(20, 184, 166, 0.15)', border: 'rgba(20, 184, 166, 0.3)', text: '#14b8a6' }

// Hash-based fallback palette for unknown tags (Tailwind bg classes)
const hashColorPalette = ['bg-indigo-500', 'bg-violet-500', 'bg-rose-500', 'bg-emerald-500', 'bg-amber-500', 'bg-sky-500']
const hashHexPalette = ['#6366f1', '#8b5cf6', '#f43f5e', '#10b981', '#f59e0b', '#0ea5e9']
const tagColorCache = new Map()

function hashTag(tag) {
  let hash = 0
  for (let i = 0; i < (tag || '').length; i++) {
    hash = tag.charCodeAt(i) + ((hash << 5) - hash)
  }
  return Math.abs(hash)
}

/**
 * Get hex color for a tag. Checks API cache first, then hardcoded, then hash-based.
 * This is the primary function consumers should use for API-driven colors.
 */
export function getTagColorFromAPI(tag) {
  // API-driven color (authoritative)
  if (_apiColors[tag]?.color) return _apiColors[tag].color
  // Hardcoded fallback
  if (tagHexColors[tag]) return tagHexColors[tag]
  // Hash-based fallback
  return hashHexPalette[hashTag(tag) % hashHexPalette.length]
}

/**
 * Convert a hex color to the {bg, border, text} style object format.
 */
export function hexToTagStyle(hex) {
  // Parse hex to r,g,b
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return {
    bg: `rgba(${r}, ${g}, ${b}, 0.15)`,
    border: `rgba(${r}, ${g}, ${b}, 0.3)`,
    text: hex,
  }
}

/**
 * Get Tailwind bg class for a tag. Returns cached hash-based color for unknown tags.
 * Kept for backward compatibility — prefer getTagColorFromAPI() for new code.
 */
export function getTagColor(tag) {
  if (tagBgColors[tag]) return tagBgColors[tag]
  if (tagColorCache.has(tag)) return tagColorCache.get(tag)
  const color = hashColorPalette[hashTag(tag) % hashColorPalette.length]
  tagColorCache.set(tag, color)
  return color
}

/**
 * Get RGBA style object for a tag. Checks API cache first, then hardcoded, then default teal.
 */
export function getTagColorStyle(tag) {
  // API-driven: convert hex to style
  if (_apiColors[tag]?.color) return hexToTagStyle(_apiColors[tag].color)
  // Hardcoded fallback
  return tagColorStyles[tag] || defaultTagColorStyle
}
