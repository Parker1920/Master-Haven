import React, { useMemo } from 'react'
import OrbitalDiagram from '../shared/OrbitalDiagram'
import StatTile, { GRADE_BG, gradeFromScore } from '../shared/StatTile'

// Wizard advanced-flow live preview. Replaces the portrait sticky panel in
// the advanced flow with a full landscape banner.
//
// Per Parker's spec (2026-05-11):
//   - Landscape, ~800×420, sticky to top of advanced form
//   - Glyphs rendered as the 12 actual icon images (not a "12/12" tile)
//   - Co-authors shown as named list (not a count)
//   - Stat grid expanded to economy / conflict / lifeform / planets / moons
//   - Stellar class + game version + expedition shown as supporting meta
//   - Planet biome thumbnail strip + special-feature badge row at bottom

// Same glyph map as the cached poster. /haven-ui-photos/* serves them.
const GLYPH_FILE = {
  '0': 'IMG_9202.webp', '1': 'IMG_9203.webp', '2': 'IMG_9204.webp', '3': 'IMG_9205.webp',
  '4': 'IMG_9206.webp', '5': 'IMG_9207.webp', '6': 'IMG_9208.webp', '7': 'IMG_9209.webp',
  '8': 'IMG_9210.webp', '9': 'IMG_9211.webp', 'A': 'IMG_9212.webp', 'B': 'IMG_9213.webp',
  'C': 'IMG_9214.webp', 'D': 'IMG_9215.webp', 'E': 'IMG_9216.webp', 'F': 'IMG_9217.webp',
}

const BIOME_TINTS = {
  Lush: '#34d399', Frozen: '#60a5fa', Scorched: '#f97316', Barren: '#a8a29e',
  Toxic: '#84cc16', Radioactive: '#a3e635', Exotic: '#a855f7', Marsh: '#06b6d4',
  Volcanic: '#ef4444', Infested: '#84cc16', Desolate: '#a8a29e', Airless: '#94a3b8',
  Dead: '#6b7280', 'Gas Giant': '#fbbf24',
}

// Aggregate per-planet boolean flags into a deduped list of badge labels.
const FEATURE_FLAGS = [
  ['vile_brood', 'Vile Brood'],
  ['ancient_bones', 'Ancient Bones'],
  ['storm_crystals', 'Storm Crystals'],
  ['gravitino_balls', 'Gravitino Balls'],
  ['salvageable_scrap', 'Salvageable Scrap'],
  ['is_dissonant', 'Dissonant'],
  ['is_infested', 'Infested'],
  ['water_world', 'Water World'],
  ['is_bubble', 'Bubble Planet'],
  ['is_floating_islands', 'Floating Islands'],
]

const STAR_TEXT_FG = { Yellow: '#422006' }
const STAR_HEX = { Yellow: '#facc15', Blue: '#60a5fa', Red: '#ef4444', Green: '#34d399', Purple: '#a855f7' }

export default function WizardAdvancedPreview({ system, gradeInfo }) {
  const planets = (system?.planets || []).filter((p) => !p.is_moon)
  const moonCount = (system?.planets || []).reduce((acc, p) => acc + (p.moons?.length || 0), 0)
  const coauthors = system?.coauthors || []
  const hasStation = !!system?.space_station
  const grade = gradeInfo?.grade || gradeFromScore(system?.is_complete)
  const score = gradeInfo?.percent ?? system?.completeness_score ?? system?.is_complete

  const glyphChars = useMemo(() => {
    const g = (system?.glyph_code || '').trim().toUpperCase().replace(/[-\s]/g, '')
    return g.length === 12 ? g.split('') : []
  }, [system?.glyph_code])

  const features = useMemo(() => {
    const set = new Set()
    for (const p of system?.planets || []) {
      for (const [key, label] of FEATURE_FLAGS) {
        if (p[key]) set.add(label)
      }
    }
    return [...set]
  }, [system?.planets])

  const starHex = STAR_HEX[system?.star_type] || '#64748b'

  return (
    <aside
      // Top-banner mount in the advanced wizard flow — full content width,
      // sticky to viewport top on scroll so the live preview tracks the
      // user's edits as they scroll the form below.
      className="w-full mb-4"
      style={{
        position: 'sticky',
        top: 16,
        zIndex: 10,
      }}
    >
      <div
        className="rounded-lg overflow-hidden relative"
        style={{
          background: `radial-gradient(60% 60% at 22% 50%, ${starHex}22 0%, transparent 65%), linear-gradient(135deg, #0f1538 0%, var(--app-bg) 100%)`,
          border: '1px solid var(--app-accent-3)',
        }}
      >
        {/* Eyebrow */}
        <div
          className="px-5 py-2 flex items-center justify-between text-[10px] mono uppercase tracking-widest"
          style={{ color: 'rgba(255,255,255,0.55)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}
        >
          <span>System Preview · Live</span>
          <span className="flex items-center gap-2">
            {hasStation && <span style={{ color: 'var(--app-primary)' }}>◆ STATION</span>}
            {grade && grade !== '—' && (
              <span
                className="px-2 py-0.5 rounded font-bold"
                style={{ background: (GRADE_BG[grade] || GRADE_BG.C).bg, color: (GRADE_BG[grade] || GRADE_BG.C).fg }}
              >
                {grade}{score != null ? ` · ${Math.round(score)}%` : ''}
              </span>
            )}
          </span>
        </div>

        {/* Hero row */}
        <div className="px-5 py-4 grid gap-4" style={{ gridTemplateColumns: '220px 1fr' }}>
          {/* Orbital diagram */}
          <div className="flex items-center justify-center" style={{ minHeight: 220 }}>
            <OrbitalDiagram
              size={220}
              starType={system?.star_type}
              planets={system?.planets || []}
              hasStation={hasStation}
              stationStroke="var(--app-accent-2)"
            />
          </div>

          {/* Right column */}
          <div className="flex flex-col gap-3 min-w-0">
            <div>
              <div className="text-2xl font-semibold truncate" style={{ fontFamily: '"Cormorant Garamond", "Georgia", serif', fontStyle: 'italic' }}>
                {system?.name || <span className="opacity-60">Unnamed System</span>}
              </div>
              <div className="text-xs opacity-70 truncate mono">
                {(system?.galaxy || 'Galaxy?')} · {(system?.reality || 'Reality?')}
                {system?.game_version ? ` · ${system.game_version}` : ''}
                {system?.stellar_classification ? ` · ${system.stellar_classification}` : ''}
              </div>
            </div>

            <div className="grid grid-cols-5 gap-2">
              <StatTile label="Economy" value={system?.economy_type || '—'} sub={system?.economy_level || null} />
              <StatTile label="Conflict" value={system?.conflict_level || '—'} />
              <StatTile label="Lifeform" value={system?.dominant_lifeform || '—'} truncate />
              <StatTile label="Planets" value={planets.length} />
              <StatTile label="Moons" value={moonCount} />
            </div>

            {/* Co-authors row — names spelled out (Parker spec) */}
            <div className="text-xs flex items-baseline gap-2 flex-wrap">
              <span className="opacity-60 mono uppercase tracking-wider text-[10px]">Co-authors</span>
              {coauthors.length === 0 ? (
                <span className="opacity-60">solo submission</span>
              ) : (
                <span className="opacity-90">
                  {coauthors.map((c, i) => (
                    <React.Fragment key={i}>
                      {i > 0 ? ' · ' : ''}
                      {typeof c === 'string' ? c : (c.username || c.name || '?')}
                    </React.Fragment>
                  ))}
                </span>
              )}
            </div>

            {system?.expedition_id != null && (
              <div className="text-xs flex items-baseline gap-2">
                <span className="opacity-60 mono uppercase tracking-wider text-[10px]">Expedition</span>
                <span className="opacity-90">#{system.expedition_id}</span>
              </div>
            )}
          </div>
        </div>

        {/* Detail strip — planet biome thumbnails + feature badges + glyph row */}
        <div className="px-5 py-3 space-y-2" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          {planets.length > 0 && (
            <div className="flex items-center gap-2 text-xs">
              <span className="opacity-60 mono uppercase tracking-wider text-[10px] shrink-0" style={{ width: 70 }}>Planets</span>
              <div className="flex items-center gap-1.5 flex-wrap">
                {planets.map((p, i) => (
                  <div
                    key={i}
                    title={`${p.name || `P${i + 1}`}${p.biome ? ' · ' + p.biome : ''}`}
                    className="w-6 h-6 rounded-md flex items-center justify-center text-[9px] font-bold"
                    style={{
                      background: BIOME_TINTS[p.biome] || 'rgba(255,255,255,0.10)',
                      color: '#0a0e27',
                    }}
                  >
                    {i + 1}
                  </div>
                ))}
              </div>
            </div>
          )}

          {features.length > 0 && (
            <div className="flex items-center gap-2 text-xs">
              <span className="opacity-60 mono uppercase tracking-wider text-[10px] shrink-0" style={{ width: 70 }}>Features</span>
              <div className="flex flex-wrap gap-1">
                {features.map((f) => (
                  <span key={f} className="pill pill-amber text-[10px]">★ {f}</span>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center gap-2 text-xs">
            <span className="opacity-60 mono uppercase tracking-wider text-[10px] shrink-0" style={{ width: 70 }}>Glyphs</span>
            <div className="flex items-center gap-1 flex-wrap">
              {Array.from({ length: 12 }).map((_, i) => {
                const c = glyphChars[i]
                const file = c && GLYPH_FILE[c]
                return (
                  <div
                    key={i}
                    className="w-6 h-6 rounded flex items-center justify-center"
                    style={{
                      background: 'rgba(0,0,0,0.35)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      opacity: c ? 1 : 0.3,
                    }}
                    title={c || 'pending'}
                  >
                    {file ? (
                      <img
                        src={`/haven-ui-photos/${file}`}
                        alt={c}
                        style={{ width: 22, height: 22, objectFit: 'cover', mixBlendMode: 'screen', filter: 'brightness(1.4)' }}
                      />
                    ) : (
                      <span className="mono text-[10px] opacity-50">·</span>
                    )}
                  </div>
                )
              })}
            </div>
            {system?.glyph_code && glyphChars.length === 12 && (
              <span className="mono text-[10px] opacity-50 ml-2">{system.glyph_code}</span>
            )}
          </div>
        </div>

        {/* Region footer (matches the original portrait panel) */}
        {system?.region_x != null && (
          <div
            className="px-5 py-2 text-[10px] mono uppercase tracking-wider opacity-50"
            style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
          >
            Region [{system.region_x}, {system.region_y}, {system.region_z}]
          </div>
        )}
      </div>
    </aside>
  )
}
