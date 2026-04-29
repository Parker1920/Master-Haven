// Username normalization for poster URLs.
//
// The backend's normalize_username_for_dedup (in services/auth_service.py)
// strips '#', strips trailing 4-digit Discord discriminators, and lowercases.
// This helper reproduces that exactly so client-built share links match the
// backend's lookup keys.
//
// Test cases:
//   'TurpitZz#9999' → 'turpitzz'
//   'Parker1920'    → 'parker'   (4-digit suffix stripped)
//   'X1234567'      → 'x1234567' (suffix not stripped — char before is a digit)
//   'Ace#1234'      → 'ace'

export function normalizeUsernameForUrl(name) {
  if (!name) return ''
  let clean = String(name).replace(/#/g, '').trim()
  // Strip trailing 4-digit Discord discriminator iff:
  //   - clean is longer than 4 chars (so we don't eat short names like '1234')
  //   - last 4 chars are all digits
  //   - the char before them is NOT a digit (so we don't eat midname digits)
  if (
    clean.length > 4 &&
    /^\d{4}$/.test(clean.slice(-4)) &&
    !/^\d$/.test(clean.charAt(clean.length - 5))
  ) {
    clean = clean.slice(0, -4)
  }
  return clean.toLowerCase().trim()
}

// Build the canonical share URL for a voyager card given a raw username.
export function voyagerCardUrl(rawUsername, base = '') {
  const slug = normalizeUsernameForUrl(rawUsername)
  if (!slug) return ''
  return `${base}/voyager/${slug}`
}

// Build the canonical share URL for a galaxy atlas given a raw galaxy name.
// Galaxies aren't usually slugified — most are unique words like "Euclid",
// "Eissentam", etc. We lowercase for URL hygiene but preserve the rest.
export function atlasUrl(galaxyName, base = '') {
  if (!galaxyName) return `${base}/atlas/Euclid`
  // Encode in case of spaces (e.g. 'Hilbert Dimension')
  return `${base}/atlas/${encodeURIComponent(galaxyName)}`
}
