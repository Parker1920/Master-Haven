import React from 'react'

// Voyager's Haven brand mark — the teal target circle used in every poster header/footer.
// Kept as a small dedicated component so all posters render the brand identically.

export default function CompassMark({ size = 24, color = '#00C2B3', strokeWidth = 1.5 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke={color} strokeWidth={strokeWidth} fill="none" />
      <circle cx="12" cy="12" r="2.5" fill={color} />
    </svg>
  )
}

// Tiny on-map compass rose used by the Galaxy Atlas. Renders absolutely-positioned
// N/W/E/S labels around a small two-axis cross.
export function CompassRose({ size = 50, color = '#00C2B3' }) {
  return (
    <div style={{
      position: 'relative',
      width: size,
      height: size,
      color,
      fontSize: 9,
      letterSpacing: 1,
    }}>
      <span style={{ position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)' }}>N</span>
      <span style={{ position: 'absolute', top: '50%', left: 0, transform: 'translateY(-50%)' }}>W</span>
      <span style={{ position: 'absolute', top: '50%', right: 0, transform: 'translateY(-50%)' }}>E</span>
      <span style={{ position: 'absolute', bottom: 0, left: '50%', transform: 'translateX(-50%)' }}>S</span>
      <svg
        width={size * 0.7}
        height={size * 0.7}
        viewBox="0 0 32 32"
        style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}
      >
        <circle cx="16" cy="16" r="11" stroke={`${color}66`} fill="none" />
        <line x1="16" y1="5" x2="16" y2="27" stroke={`${color}99`} strokeWidth="0.8" />
        <line x1="5" y1="16" x2="27" y2="16" stroke={`${color}99`} strokeWidth="0.8" />
      </svg>
    </div>
  )
}
