import React from 'react'

// Shared orbital-system diagram. Consumed by:
//   - src/posters/SystemThumb.jsx       (system_thumb cached PNG poster)
//   - src/components/wizard/WizardAdvancedPreview.jsx (live in-wizard preview)
//
// Center star colored by star_type with glow + solid core. Up to 6 planet
// orbits, evenly angular-spaced, biome-tinted dot per planet. Moons render
// as smaller dots near the parent. Space station appears as an outside
// diamond marker.
//
// All visuals are pure functions of props — no fetch, no animation. Render
// at whatever pixel size the parent gives via the `size` prop.

const STAR_COLORS = {
  Yellow: '#facc15',
  Blue: '#60a5fa',
  Red: '#ef4444',
  Green: '#34d399',
  Purple: '#a855f7',
}

const BIOME_TINTS = {
  Lush: '#34d399',
  Frozen: '#60a5fa',
  Scorched: '#f97316',
  Barren: '#a8a29e',
  Toxic: '#84cc16',
  Radioactive: '#a3e635',
  Exotic: '#a855f7',
  Marsh: '#06b6d4',
  Volcanic: '#ef4444',
  Infested: '#84cc16',
  Desolate: '#a8a29e',
  Airless: '#94a3b8',
  Dead: '#6b7280',
  'Gas Giant': '#fbbf24',
}

export default function OrbitalDiagram({
  size = 240,
  starType,
  planets = [],
  hasStation = false,
  // Accent token names so callers can stay theme-consistent. Defaults match
  // the poster palette (--app-accent-purple-ish via inline value).
  stationStroke = '#9d4edd',
}) {
  const cx = size / 2
  const cy = size / 2
  const star = STAR_COLORS[starType] || '#64748b'

  // Only count planets (not moons) for the orbit count.
  const planetRows = planets.filter((p) => !p.is_moon)
  const N = Math.max(1, Math.min(planetRows.length, 6))
  const innerR = size * 0.16
  const outerR = size * 0.42
  const orbitR = (i) => (N === 1 ? (innerR + outerR) / 2 : innerR + (outerR - innerR) * (i / (N - 1)))

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <defs>
        <radialGradient id={`star-glow-${star.replace('#', '')}`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={star} stopOpacity="0.9" />
          <stop offset="40%" stopColor={star} stopOpacity="0.35" />
          <stop offset="100%" stopColor={star} stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Orbit rings */}
      {planetRows.map((_, i) => (
        <circle key={`ring-${i}`} cx={cx} cy={cy} r={orbitR(i)} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth={0.6} />
      ))}

      {/* Star glow + core */}
      <circle cx={cx} cy={cy} r={size * 0.21} fill={`url(#star-glow-${star.replace('#', '')})`} />
      <circle cx={cx} cy={cy} r={size * 0.075} fill={star} />

      {/* Planet dots */}
      {planetRows.map((p, i) => {
        const angle = (i / Math.max(1, planetRows.length)) * Math.PI * 2 - Math.PI / 2
        const r = orbitR(i)
        const px = cx + r * Math.cos(angle)
        const py = cy + r * Math.sin(angle)
        const tint = BIOME_TINTS[p.biome] || '#00C2B3'
        const planetSize = size * 0.025
        // Moons live on the planet row itself
        const moons = p.moons || []
        return (
          <g key={`p-${i}`}>
            <circle cx={px} cy={py} r={planetSize} fill={tint} opacity="0.95" />
            {/* Ring overlay if planet has rings */}
            {p.has_rings ? (
              <ellipse cx={px} cy={py} rx={planetSize + 2.5} ry={1.2} fill="none" stroke={tint} strokeWidth="0.8" opacity="0.7" />
            ) : null}
            {/* Moons — up to 3, offset around the planet */}
            {moons.slice(0, 3).map((m, mi) => {
              const ma = mi * (Math.PI * 2 / 3) + angle
              const mr = size * 0.046
              const mx = px + mr * Math.cos(ma)
              const my = py + mr * Math.sin(ma)
              return <circle key={`m-${i}-${mi}`} cx={mx} cy={my} r={size * 0.008} fill={tint} opacity="0.7" />
            })}
          </g>
        )
      })}

      {/* Space station — outside diamond marker */}
      {hasStation && (
        <g transform={`translate(${cx}, ${cy - outerR - size * 0.07}) rotate(45)`}>
          <rect x={-size * 0.022} y={-size * 0.022} width={size * 0.043} height={size * 0.043}
            fill="none" stroke={stationStroke} strokeWidth={size * 0.008} />
        </g>
      )}
    </svg>
  )
}

export { STAR_COLORS, BIOME_TINTS }
