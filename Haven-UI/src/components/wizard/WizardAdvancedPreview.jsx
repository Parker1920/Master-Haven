import React, { useMemo } from 'react'
import OrbitalDiagram from '../shared/OrbitalDiagram'
import StatTile, { GRADE_BG, gradeFromScore } from '../shared/StatTile'
import { glyphImageSrc } from '../../utils/glyphAssets'
import { biomeTintHex } from '../../data/biomeCategoryMappings'
import { STAR_HEX } from '../../utils/starColors'

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
      // sticky to viewport top on scroll (desktop only) so the live preview
      // tracks the user's edits as they scroll the form below. On mobile
      // (<lg) it scrolls away with the form: combined with the sticky
      // toolbar+pill nav above, sticky-on-mobile ate >50% of the viewport.
      className="w-full mb-4 lg:sticky lg:top-4 lg:z-10"
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
          className="px-3 sm:px-5 py-2 flex items-center justify-between text-[10px] mono uppercase tracking-widest"
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

        {/* Hero row — stacked on mobile (orbit on top, content below),
            two-column at lg+ matching the original landscape layout. */}
        <div className="px-3 sm:px-5 py-4 flex flex-col lg:grid lg:gap-4 gap-3 lg:[grid-template-columns:220px_1fr]">
          {/* Orbital diagram — 140px on mobile, 220px on desktop */}
          <div className="flex items-center justify-center lg:[min-height:220px]">
            <div className="lg:hidden">
              <OrbitalDiagram
                size={140}
                starType={system?.star_type}
                planets={system?.planets || []}
                hasStation={hasStation}
                stationStroke="var(--app-accent-2)"
              />
            </div>
            <div className="hidden lg:block">
              <OrbitalDiagram
                size={220}
                starType={system?.star_type}
                planets={system?.planets || []}
                hasStation={hasStation}
                stationStroke="var(--app-accent-2)"
              />
            </div>
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

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
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
        <div className="px-3 sm:px-5 py-3 space-y-2" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          {planets.length > 0 && (
            <div className="flex items-center gap-2 text-xs">
              <span className="opacity-60 mono uppercase tracking-wider text-[10px] shrink-0 w-12 lg:w-[70px]">Planets</span>
              <div className="flex items-center gap-1 sm:gap-1.5 flex-wrap">
                {planets.map((p, i) => (
                  <div
                    key={i}
                    title={`${p.name || `P${i + 1}`}${p.biome ? ' · ' + p.biome : ''}`}
                    className="w-5 h-5 lg:w-6 lg:h-6 rounded-md flex items-center justify-center text-[9px] font-bold"
                    style={{
                      background: biomeTintHex(p.biome) || 'rgba(255,255,255,0.10)',
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
              <span className="opacity-60 mono uppercase tracking-wider text-[10px] shrink-0 w-12 lg:w-[70px]">Features</span>
              <div className="flex flex-wrap gap-1">
                {features.map((f) => (
                  <span key={f} className="pill pill-amber text-[10px]">★ {f}</span>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center gap-2 text-xs">
            <span className="opacity-60 mono uppercase tracking-wider text-[10px] shrink-0 w-12 lg:w-[70px]">Glyphs</span>
            <div className="flex items-center gap-1 flex-wrap">
              {Array.from({ length: 12 }).map((_, i) => {
                const c = glyphChars[i]
                const src = c ? glyphImageSrc(c) : null
                return (
                  <div
                    key={i}
                    className="w-5 h-5 lg:w-6 lg:h-6 rounded flex items-center justify-center"
                    style={{
                      background: 'rgba(0,0,0,0.35)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      opacity: c ? 1 : 0.3,
                    }}
                    title={c || 'pending'}
                  >
                    {src ? (
                      <img
                        src={src}
                        alt={c}
                        className="w-[18px] h-[18px] lg:w-[22px] lg:h-[22px]"
                        style={{ objectFit: 'contain' }}
                      />
                    ) : (
                      <span className="mono text-[10px] opacity-50">·</span>
                    )}
                  </div>
                )
              })}
            </div>
            {system?.glyph_code && glyphChars.length === 12 && (
              <span className="mono text-[10px] opacity-50 ml-2 hidden sm:inline">{system.glyph_code}</span>
            )}
          </div>
        </div>

        {/* Region footer (matches the original portrait panel) */}
        {system?.region_x != null && (
          <div
            className="px-3 sm:px-5 py-2 text-[10px] mono uppercase tracking-wider opacity-50"
            style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
          >
            Region [{system.region_x}, {system.region_y}, {system.region_z}]
          </div>
        )}
      </div>
    </aside>
  )
}
