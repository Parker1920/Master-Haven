import React from 'react'

// Chrome-less wrapper used by every poster component.
// - Sizes the viewport to the registry-defined width/height
// - Sets the deep navy background and serif/mono font fallbacks
// - Fills the entire screen with the poster centered
//
// Children should render the actual poster content. Outermost container has
// the registry width/height locked so headless screenshot dimensions match.

// Mirror the Haven theme tokens defined in src/styles/index.css so posters
// match the live web UI. Whenever those CSS variables change, update here too.
//   --app-bg          → BG_POSTER
//   --app-card        → SURFACE
//   --app-text        → TEXT
//   --app-primary     → PRIMARY (teal)
//   --app-accent-2    → ACCENT  (rich purple)
//   --app-accent-amber→ AMBER   (warm orange)
const BG_OUTER = '#02041a'
const BG_POSTER = '#0a0e27'
const BORDER = '#2a3370'

export default function PosterFrame({ width, height, children, padded = true, style }) {
  // No outer padding/centering — inner box must sit flush at (0,0) of the
  // viewport so headless screenshot clip [0..width, 0..height] captures the
  // full card. Earlier outer 24px top-padding was shifting bottom labels
  // out of the clip region.
  // No border / borderRadius — full-bleed PNG fits cleanly into UI tiles
  // and Discord/Twitter embeds without dark rounded margins.
  return (
    <div style={{
      width,
      height,
      background: BG_POSTER,
      padding: padded ? 32 : 0,
      boxSizing: 'border-box',
      position: 'relative',
      overflow: 'hidden',
      fontFamily: '"JetBrains Mono", "SF Mono", "Consolas", monospace',
      color: '#ffffff',
      ...style,
    }}>
      {children}
    </div>
  )
}

export const POSTER_COLORS = {
  bgOuter: BG_OUTER,
  bgPoster: BG_POSTER,    // --app-bg
  surface: '#141b3d',     // --app-card
  surfaceHi: '#1f2858',   // a touch lighter than surface for stat-card highlights
  border: BORDER,
  text: '#ffffff',        // --app-text
  dim: '#8a93b8',         // dimmed text / labels
  accent: '#9d4edd',      // --app-accent-2 (rich purple)
  primary: '#00C2B3',     // --app-primary (teal)
  amber: '#ffb44c',       // --app-accent-amber (warm orange)
}

export const POSTER_FONTS = {
  mono: '"JetBrains Mono", "SF Mono", "Consolas", monospace',
  serif: '"Cormorant Garamond", "Georgia", serif',
}
