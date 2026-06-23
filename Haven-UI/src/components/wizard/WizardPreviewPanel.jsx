import React from 'react'
import { TIER_COLORS } from '../../utils/gradeColors'
import { biomeTintHex } from '../../data/biomeCategoryMappings'
import { STAR_HEX } from '../../utils/starColors'

// Wizard v1 live preview panel (mockup aside#preview-panel 6005-6110).
// Sticky right column on desktop. Shows the system as a "system disk":
// glowing star at center, planets in concentric orbit positions, optional
// space-station marker. Below that, a compact stat-card grid.
//
// All visual updates are pure functions of the `system` prop — no animation,
// no data fetching. Renders fine even when the system is half-filled.
export default function WizardPreviewPanel({ system, gradeInfo }) {
  const planets = system?.planets || []
  const planetCount = planets.length
  const moonCount = planets.reduce((acc, p) => acc + (p.moons?.length || 0), 0)
  const hasStation = !!system?.space_station
  const coauthorCount = (system?.coauthors || []).length
  const starColor = STAR_HEX[system?.star_type] || '#64748b'
  const grade = gradeInfo?.grade || '—'
  const percent = gradeInfo?.percent ?? null

  return (
    <aside className="lg:sticky lg:top-4 lg:w-72 flex-shrink-0 lg:self-start">
      <div
        className="rounded-lg p-4"
        style={{
          backgroundColor: 'var(--app-card)',
          border: '1px solid var(--app-accent-3)',
        }}
      >
        <div className="text-xs font-semibold uppercase tracking-wider opacity-70 mb-3">
          System Preview
        </div>

        {/* System disk SVG — star at center, planets on concentric orbits, station as ◆ */}
        <SystemDiskSVG
          starColor={starColor}
          planets={planets}
          hasStation={hasStation}
          stationRadius={system?.space_station?.orbitalRadius}
        />

        {/* Name + galaxy underneath the disk */}
        <div className="mt-3 mb-4 text-center">
          <div className="font-semibold truncate">{system?.name || <span className="opacity-60">Unnamed System</span>}</div>
          <div className="text-xs opacity-70 truncate">
            {system?.galaxy || 'Galaxy?'} · {system?.reality || 'Reality?'}
          </div>
        </div>

        {/* Compact stats */}
        <div className="grid grid-cols-2 gap-2 text-sm">
          <Stat label="Glyphs" value={system?.glyph_code ? `${system.glyph_code.length}/12` : '0/12'} />
          <Stat label="Planets" value={planetCount} />
          <Stat label="Moons" value={moonCount} />
          <Stat label="Station" value={hasStation ? 'Yes' : 'No'} />
          <Stat label="Co-authors" value={coauthorCount} />
          <Stat
            label="Grade"
            value={grade}
            valueColor={TIER_COLORS[grade]}
            sub={percent != null ? `${percent}%` : null}
          />
        </div>

        {/* Region info */}
        {system?.region_x != null && (
          <div className="mt-4 pt-4 border-t text-xs opacity-70" style={{ borderColor: 'var(--app-accent-3)' }}>
            Region [{system.region_x}, {system.region_y}, {system.region_z}]
          </div>
        )}
      </div>
    </aside>
  )
}

// "System disk" SVG. Star at the center; planets sit on concentric orbits
// indexed by array position. Gas giants are tinted orange; everything else
// uses --app-primary. Station marker is a small diamond near the auto-placed
// orbit. Drawn at 240×240 user-space units; intrinsic ratio is preserved.
function SystemDiskSVG({ starColor, planets, hasStation, stationRadius }) {
  const VB = 240
  const cx = VB / 2
  const cy = VB / 2
  const innerRadius = 18
  const outerRadius = 100
  const count = Math.max(1, planets.length)
  // Spread up to 6 planets across orbits; if more, additional planets share
  // the outermost orbit at staggered angles.
  const orbitFor = (i) => {
    const ringIndex = Math.min(i, 5)
    const t = (ringIndex + 1) / 6
    return innerRadius + 6 + t * (outerRadius - innerRadius - 6)
  }
  // Spread planets evenly around the orbit, offset by a small phase per index.
  const angleFor = (i) => {
    const phase = (i * 137.5) % 360
    return (phase * Math.PI) / 180
  }

  const stationOrbit = (() => {
    if (!hasStation) return null
    if (stationRadius && Number.isFinite(stationRadius)) {
      // Map station's reported orbital radius to our SVG range.
      // generateStationPosition uses ~5–8 game units; scale linearly.
      return Math.min(outerRadius - 4, innerRadius + 12 + (stationRadius - 4) * 8)
    }
    return outerRadius - 12
  })()

  return (
    <div className="w-full flex items-center justify-center" aria-hidden="true">
      <svg viewBox={`0 0 ${VB} ${VB}`} width="100%" style={{ maxWidth: 220, aspectRatio: '1 / 1' }}>
        <defs>
          <radialGradient id="starGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={starColor} stopOpacity="0.85" />
            <stop offset="60%" stopColor={starColor} stopOpacity="0.18" />
            <stop offset="100%" stopColor={starColor} stopOpacity="0" />
          </radialGradient>
        </defs>
        {/* Backdrop: faint starfield via a few jittered dots */}
        {Array.from({ length: 28 }).map((_, i) => {
          const x = (i * 911 + 17) % VB
          const y = (i * 619 + 53) % VB
          const r = 0.4 + ((i * 7) % 5) * 0.18
          return <circle key={i} cx={x} cy={y} r={r} fill="rgba(255,255,255,0.18)" />
        })}
        {/* Orbit rings */}
        {Array.from({ length: Math.min(6, planets.length || 1) }).map((_, i) => (
          <circle
            key={`orbit-${i}`}
            cx={cx}
            cy={cy}
            r={orbitFor(i)}
            fill="none"
            stroke="rgba(255,255,255,0.07)"
            strokeWidth="1"
          />
        ))}
        {/* Star glow + core */}
        <circle cx={cx} cy={cy} r={outerRadius + 12} fill="url(#starGlow)" />
        <circle cx={cx} cy={cy} r={innerRadius} fill={starColor} />
        {/* Planets */}
        {planets.map((p, i) => {
          const r = orbitFor(i)
          const a = angleFor(i)
          const px = cx + Math.cos(a) * r
          const py = cy + Math.sin(a) * r
          const planetColor = p.is_gas_giant ? '#fb923c' : (p.is_bubble ? '#a855f7' : (biomeTintHex(p.biome) || 'var(--app-primary)'))
          const size = p.is_gas_giant ? 5.5 : 4
          return (
            <g key={i}>
              <circle cx={px} cy={py} r={size} fill={planetColor} />
              {p.has_rings ? (
                <ellipse cx={px} cy={py} rx={size + 2.5} ry={1.2} fill="none" stroke={planetColor} strokeWidth="0.8" opacity="0.7" />
              ) : null}
              {(p.moons || []).slice(0, 3).map((m, mi) => {
                const ma = a + 0.35 + mi * 0.25
                const mr = size + 4 + mi * 1.5
                return (
                  <circle
                    key={mi}
                    cx={px + Math.cos(ma) * mr}
                    cy={py + Math.sin(ma) * mr}
                    r={1.1}
                    fill="rgba(255,255,255,0.7)"
                  />
                )
              })}
            </g>
          )
        })}
        {/* Station diamond */}
        {hasStation && stationOrbit != null && (() => {
          const a = angleFor(planets.length + 1)
          const sx = cx + Math.cos(a) * stationOrbit
          const sy = cy + Math.sin(a) * stationOrbit
          return (
            <polygon
              points={`${sx},${sy - 5} ${sx + 4},${sy} ${sx},${sy + 5} ${sx - 4},${sy}`}
              fill="none"
              stroke="var(--app-accent-2)"
              strokeWidth="1.5"
            />
          )
        })()}
      </svg>
    </div>
  )
}

function Stat({ label, value, valueColor, sub }) {
  return (
    <div
      className="rounded p-2"
      style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
    >
      <div className="text-[10px] uppercase tracking-wider opacity-60">{label}</div>
      <div className="font-semibold" style={{ color: valueColor || 'inherit' }}>
        {value}
        {sub && (
          <span className="text-xs opacity-60 ml-1">{sub}</span>
        )}
      </div>
    </div>
  )
}
