import React from 'react'
import CompassMark from './CompassMark'
import { POSTER_COLORS } from './PosterFrame'

// Standard footer used at the bottom of every poster.
// - Left: brand mark + "VOYAGER'S HAVEN · EST 2025"
// - Right: havenmap.online url + "drawn from live data" tagline
//
// Pass `url` to override the right-side URL (default: havenmap.online).

export default function Watermark({ url = 'havenmap.online', tagline = 'drawn from live data · every star a system named' }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-end',
      paddingTop: 16,
      borderTop: `1px solid ${POSTER_COLORS.border}`,
      fontFamily: '"JetBrains Mono", "SF Mono", "Consolas", monospace',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <CompassMark size={16} />
        <div>
          <div style={{ fontSize: 11, color: POSTER_COLORS.text, letterSpacing: 2 }}>VOYAGER'S HAVEN</div>
          <div style={{ fontSize: 9, color: POSTER_COLORS.dim, letterSpacing: 1, marginTop: 2 }}>EST · 2025</div>
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontSize: 11, color: POSTER_COLORS.accent, letterSpacing: 1 }}>{url}</div>
        <div style={{ fontSize: 9, color: POSTER_COLORS.dim, fontStyle: 'italic', marginTop: 2 }}>{tagline}</div>
      </div>
    </div>
  )
}
