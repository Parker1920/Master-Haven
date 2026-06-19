/**
 * ComparePanel — full-screen overlay rendering pinned items side-by-side.
 *
 * Each column carries the raw payload from where it was pinned, so this
 * component is a pure renderer — no extra fetches. Three column renderers
 * pick from the payload shape:
 *   - galaxy: poster + system count + region count + grade distribution
 *   - region: coordinates + system count + grade-S count + contributors
 *   - system: star glow + economy/conflict/lifeform/biome row + planet count
 *     + completeness bar
 *
 * Clicking any column unpins it (per spec 7.3). Esc closes the panel.
 */

import React, { useEffect } from 'react'
import { useSystems } from '../contexts/SystemsContext'
import { GRADE_BADGE_STYLE } from '../utils/gradeColors'

const STAR_HEX = { Yellow: '#facc15', Blue: '#3b82f6', Red: '#ef4444', Green: '#10b981', Purple: '#a855f7' }
const LEVEL_TITLE = { galaxy: 'Galaxies', region: 'Regions', system: 'Systems' }
// Grade badge styling is single-sourced from gradeColors.js (S+ / S / A / B / C).
const GRADE_STYLE = GRADE_BADGE_STYLE

export default function ComparePanel({ open, onClose }) {
  const { compareMode, pinsByLevel, togglePin } = useSystems()

  useEffect(() => {
    if (!open) return
    function onKey(e) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open || !compareMode) return null
  const pins = pinsByLevel[compareMode] || []

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" style={{ background: 'var(--app-bg)' }}>
      <div className="max-w-[1400px] mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold">Compare {LEVEL_TITLE[compareMode] || ''}</h2>
            <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
              Side-by-side view of pinned {LEVEL_TITLE[compareMode]?.toLowerCase()}. Click any column to dismiss it.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="haven-btn-ghost px-3 py-2 rounded-lg flex items-center gap-2 text-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            Close
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {pins.map((pin) => (
            <button
              key={pin.key}
              type="button"
              onClick={() => togglePin(compareMode, pin)}
              className="haven-card haven-card-hover overflow-hidden p-0 text-left"
              title="Click to dismiss this column"
            >
              {compareMode === 'galaxy' && <GalaxyColumn g={pin.payload} />}
              {compareMode === 'region' && <RegionColumn r={pin.payload} />}
              {compareMode === 'system' && <SystemColumn s={pin.payload} />}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function GalaxyColumn({ g }) {
  if (!g) return null
  const total = g.system_count || 0
  const segments = [
    { cls: 'bar-s', count: g.grade_s || 0, letter: 'S' },
    { cls: 'bar-a', count: g.grade_a || 0, letter: 'A' },
    { cls: 'bar-b', count: g.grade_b || 0, letter: 'B' },
    { cls: 'bar-c', count: g.grade_c || 0, letter: 'C' },
  ]
  return (
    <>
      <div className="aspect-square relative overflow-hidden" style={{ background: 'linear-gradient(135deg, #0f1538, var(--app-bg))' }}>
        <img
          src={`/api/posters/atlas_thumb/${encodeURIComponent(g.galaxy)}.png`}
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-70 mix-blend-screen"
          onError={(e) => { e.currentTarget.style.display = 'none' }}
        />
        <div className="absolute inset-0" style={{ background: 'linear-gradient(to top, var(--app-card) 5%, transparent 50%)' }} />
      </div>
      <div className="p-4 space-y-3">
        <h3 className="text-base font-semibold truncate">{g.galaxy}</h3>
        <div className="grid grid-cols-2 gap-2">
          <Stat value={total.toLocaleString()} label="systems" />
          <Stat value={(g.region_count || 0).toLocaleString()} label="regions" />
        </div>
        {g.avg_score != null && (
          <div className="text-xs" style={{ color: 'var(--muted)' }}>Avg score <span className="mono" style={{ color: 'var(--app-text)' }}>{g.avg_score}</span></div>
        )}
        <div className="flex h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(0,0,0,0.4)' }}>
          {segments.map((s) => total > 0 && s.count > 0 ? <div key={s.letter} className={s.cls} style={{ width: `${(s.count / total) * 100}%` }} /> : null)}
        </div>
      </div>
    </>
  )
}

function RegionColumn({ r }) {
  if (!r) return null
  return (
    <>
      <div className="aspect-[2/1] stub-poster" />
      <div className="p-4 space-y-3">
        <div>
          <h3 className="text-base font-semibold truncate">{r.display_name}</h3>
          <div className="mono text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>
            {r.region_x} · {r.region_y} · {r.region_z}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Stat value={r.system_count} label="systems" />
          <Stat value={r.grade_s_count != null ? r.grade_s_count : '—'} label="grade S" emphasis="grade-s" />
        </div>
        <span className={`pill ${r.custom_name ? 'pill-purple' : 'pill-muted'} text-[10px]`}>
          {r.custom_name ? 'Named' : 'Unnamed'}
        </span>
      </div>
    </>
  )
}

function SystemColumn({ s }) {
  if (!s) return null
  const starHex = STAR_HEX[s.star_type] || '#facc15'
  const grade = s.completeness_grade
  return (
    <>
      <div
        className="aspect-[3/2] relative overflow-hidden"
        style={{ background: `radial-gradient(circle at 50% 50%, ${starHex}30 0%, transparent 60%), linear-gradient(135deg, #0f1538, var(--app-bg))` }}
      >
        <div className="absolute inset-0 flex items-center justify-center">
          <div
            className="w-16 h-16 rounded-full"
            style={{ background: starHex, boxShadow: `0 0 32px ${starHex}` }}
          />
        </div>
        {grade && (
          <div className="absolute top-3 right-3">
            <span className="w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold mono" style={GRADE_STYLE[grade] || GRADE_STYLE.C}>{grade}</span>
          </div>
        )}
      </div>
      <div className="p-4 space-y-3">
        <h3 className="text-base font-semibold truncate">{s.name}</h3>
        <div className="space-y-1 text-xs" style={{ color: 'var(--muted)' }}>
          <Row label="Star" value={s.star_type || '—'} />
          <Row label="Economy" value={s.economy_type ? `${s.economy_type}${s.economy_level ? ` / ${s.economy_level}` : ''}` : '—'} />
          <Row label="Conflict" value={s.conflict_level || '—'} />
          <Row label="Lifeform" value={s.dominant_lifeform || '—'} />
          <Row label="Planets" value={`${s.planet_count ?? 0}${s.moon_count ? ` (${s.moon_count} moons)` : ''}`} />
        </div>
        {s.completeness_score != null && (
          <div>
            <div className="text-[10px] mono mb-1" style={{ color: 'var(--muted)' }}>Complete · {s.completeness_score}%</div>
            <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(0,0,0,0.4)' }}>
              <div className={`bar-${(grade || 'c').toLowerCase()}`} style={{ width: `${Math.min(100, s.completeness_score)}%` }} />
            </div>
          </div>
        )}
      </div>
    </>
  )
}

function Stat({ value, label, emphasis }) {
  const cls = emphasis === 'grade-s' ? 'text-base font-bold grade-s' : 'text-base font-bold'
  return (
    <div>
      <div className={cls}>{value != null ? value : '—'}</div>
      <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>{label}</div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between">
      <span>{label}</span>
      <span style={{ color: 'var(--app-text)' }}>{value}</span>
    </div>
  )
}
