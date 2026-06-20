// Single source of truth for system URLs.
//
// Goal: pretty + unique + shareable. NMS procgen system names repeat, so a bare
// `/systems/<name>` is ambiguous for duplicates. We disambiguate with the
// system's portal glyph code (its unique NMS address) — but only when needed:
//   unique name   -> /systems/Gelt
//   duplicate name -> /systems/Mabaya-111D0193CFA8
//
// `systemSlug` is for NAVIGATION (link clicks): the caller doesn't know yet
// whether a name is unique, so it always includes the glyph when available
// (which resolves to exactly one system). SystemDetail then rewrites the address
// bar down to the canonical form via `canonicalSystemSlug` once the backend has
// told it whether the name is unique.

function looksLikeGlyph(s) {
  return typeof s === 'string' && /^[0-9A-Fa-f]{12}$/.test(s.trim())
}

// Navigation slug: name + glyph (exact, never hits the disambiguation picker);
// falls back to id when no glyph is available, then to the bare name.
export function systemSlug(sys) {
  if (!sys) return ''
  const name = (sys.name || '').toString()
  const glyph = (sys.glyph_code || '').toString().trim()
  if (name && looksLikeGlyph(glyph)) return `${encodeURIComponent(name)}-${glyph}`
  if (sys.id) return encodeURIComponent(String(sys.id))
  return encodeURIComponent(name)
}

// Canonical address-bar slug: bare name when the name is unique, name + glyph
// when it collides, id only as a last resort (duplicate name with no glyph).
export function canonicalSystemSlug(sys) {
  if (!sys) return ''
  const name = (sys.name || '').toString()
  if (sys.name_unique && name) return encodeURIComponent(name)
  const glyph = (sys.glyph_code || '').toString().trim()
  if (name && looksLikeGlyph(glyph)) return `${encodeURIComponent(name)}-${glyph}`
  if (sys.id) return encodeURIComponent(String(sys.id))
  return encodeURIComponent(name)
}

export function systemPath(sys) {
  return `/systems/${systemSlug(sys)}`
}
