// Color + display-name resolution helpers for poster components.
// Centralized so every poster gets identical faction colors and labels.
//
// Backed by /api/discord_tag_colors which returns:
//   { Haven: { color: "#06b6d4", name: "Haven" }, GHUB: { color: "#5b21b6", name: "Galactic Hub" }, ... }
//
// On poster routes we self-fetch this once via fetchTagColorsForPoster().

import { getTagColorFromAPI, setApiTagColors } from '../../utils/tagColors'

// Module-level cache so multiple posters in the same render share one API call.
let _displayNameCache = {}

// Hardcoded display-name fallbacks for tags that pre-date the discord_tag_colors API.
// Lowercased keys matched case-insensitively in getDisplayTagName().
const HARDCODED_DISPLAY_NAMES = {
  'ghub': 'Galactic Hub',
  'haven': 'Haven',
  'evrn': 'Everion Empire',
  'tgc': 'Tugarv Compendium',
  'acsd': 'Atlas-CSD',
  'shdw': 'Shadow Worlds',
  'tps': 'TPS',
  'tbh': 'Mourning Amity',
  'hg': 'Hilbert Group',
  'iea': 'IEA',
  'b.e.s': 'B.E.S',
  'bes': 'B.E.S',
  'arch': 'ARCH',
  'personal': 'Personal',
}

export async function fetchTagColorsForPoster() {
  // Pull tag colors from the API and feed them into both the existing tagColors
  // module (so getTagColorFromAPI works) and our local display-name cache.
  try {
    const res = await fetch('/api/discord_tag_colors', { credentials: 'same-origin' })
    if (!res.ok) return
    const data = await res.json()
    setApiTagColors(data)
    // Build display-name cache for fast sync lookup
    _displayNameCache = {}
    for (const [tag, info] of Object.entries(data)) {
      if (info && info.name) {
        _displayNameCache[tag.toLowerCase()] = info.name
      }
    }
  } catch (e) {
    // Non-fatal — fall through to hardcoded display names + tag itself
    // eslint-disable-next-line no-console
    console.warn('Poster: failed to fetch /api/discord_tag_colors', e)
  }
}

// Resolve a tag like "GHUB" or "personal" to the display name "Galactic Hub" / "Personal".
// Lookup chain: API cache → hardcoded → titlecase the tag → "Personal".
export function getDisplayTagName(tag) {
  if (!tag) return 'Personal'
  const lower = String(tag).toLowerCase()
  if (_displayNameCache[lower]) return _displayNameCache[lower]
  if (HARDCODED_DISPLAY_NAMES[lower]) return HARDCODED_DISPLAY_NAMES[lower]
  // Titlecase fallback for unknown tags
  if (lower === tag) return tag.charAt(0).toUpperCase() + tag.slice(1).toLowerCase()
  return tag
}

// Re-export the existing color helper so posters have a single import surface
export { getTagColorFromAPI }

// Lifeform color palette — used on Voyager Card lifeform bars.
// Matches the in-game civilization colors as a visual cue.
export const LIFEFORM_COLORS = {
  Gek: '#22c55e',
  Korvax: '#a78bfa',
  "Vy'keen": '#f59e0b',
  Vykeen: '#f59e0b',
  Robots: '#ef4444',
  Atlas: '#06b6d4',
  Diplomats: '#ec4899',
}
