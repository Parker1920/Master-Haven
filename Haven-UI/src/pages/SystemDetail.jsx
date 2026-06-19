/**
 * SystemDetail — Level 5 of the Systems Tab v2.0.
 *
 * Route: /systems/:id
 * Auth: Public (data restrictions enforced by backend)
 *
 * Layout (spec section 8.1):
 *   ┌──────────────────┬───────────┐
 *   │ Hero card +      │ Community │
 *   │ stat row +       │ Coords    │
 *   │ description      │ Contribs  │
 *   │                  │ Actions   │
 *   │                  │ Activity  │
 *   ├──────────────────┴───────────┤
 *   │     Planets grid             │
 *   ├──────────────────────────────┤
 *   │     Photos grid              │
 *   └──────────────────────────────┘
 *
 * Edit Mode (spec section 8.4):
 *   - Toggle button at top right
 *   - Editable fields: name, description
 *   - Save submits to /api/submit_system with `id` set → pending_systems
 *     row with edit_system_id, enters the normal approval queue. NO direct
 *     PATCH on the live `systems` row.
 *   - Discard re-fetches and reverts
 *
 * Photo lightbox: gathers system-level photos plus planet-level photos
 * into a single ordered list, lazy-renders only when opened.
 */

import React, { useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import axios from 'axios'
import { AuthContext } from '../utils/AuthContext'
import { getThumbnailUrl, getPhotoUrl } from '../utils/api'
import { getFaunaColor, getFloraColor, getSentinelColor } from '../utils/adjectiveColors'
import Lightbox from '../components/Lightbox'
import { formatCoords } from '../components/LatLngInput'
import FromMapBanner from '../components/FromMapBanner'
import ActivityFeed from '../components/ActivityFeed'
import PlanetSphere from '../components/shared/PlanetSphere'
import { GRADE_BADGE_STYLE } from '../utils/gradeColors'

const STAR_HEX = {
  Yellow: '#facc15', Blue: '#3b82f6', Red: '#ef4444', Green: '#10b981', Purple: '#a855f7',
  // Legacy / fallback colors so old rows with Unknown / White / NULL don't all coerce to yellow
  White: '#e5e7eb', Unknown: '#94a3b8',
}
const STAR_TEXT = { Yellow: '#422006' } // contrast on Yellow only; others use white
// Grade badge styling is single-sourced from gradeColors.js (S+ / S / A / B / C).
const GRADE_STYLE = GRADE_BADGE_STYLE
const GAME_MODE_COLOR = {
  Normal: { bg: 'rgba(148,163,184,0.2)', text: '#cbd5e1' },
  Survival: { bg: 'rgba(249,115,22,0.2)', text: '#fb923c' },
  Permadeath: { bg: 'rgba(239,68,68,0.2)', text: '#f87171' },
  Creative: { bg: 'rgba(6,182,212,0.2)', text: '#22d3ee' },
  Relaxed: { bg: 'rgba(34,197,94,0.2)', text: '#4ade80' },
  Custom: { bg: 'rgba(168,85,247,0.2)', text: '#c084fc' },
}
const COMPLETENESS_CATEGORIES = [
  ['system_core', 'System Core', 35],
  ['system_extra', 'System Extra', 10],
  ['planet_coverage', 'Planet Coverage', 10],
  ['planet_environment', 'Planet Environment', 25],
  ['planet_life', 'Planet Life', 15],
  ['space_station', 'Space Station', 5],
]
const BIOME_TINT = {
  Lush: '#10b981', Frozen: '#60a5fa', Scorched: '#f97316',
  Barren: '#a8a29e', Toxic: '#84cc16', Exotic: '#a855f7',
  Radioactive: '#a3e635', Marsh: '#06b6d4', Volcanic: '#ef4444',
  Infested: '#84cc16', Desolate: '#a8a29e', Airless: '#94a3b8',
  'Gas Giant': '#fbbf24',
}

function gatherPhotos(system) {
  if (!system) return []
  const out = []
  function addPhotos(field, ownerLabel) {
    if (!field) return
    let list = field
    if (typeof list === 'string') {
      try { list = JSON.parse(list) } catch { return }
    }
    if (!Array.isArray(list)) return
    for (const p of list) {
      if (!p) continue
      const url = typeof p === 'string' ? p : (p.url || p.filename || p.path)
      if (!url) continue
      out.push({
        url: getPhotoUrl(url),
        thumbnailUrl: getThumbnailUrl(url),
        caption: typeof p === 'object' ? (p.caption || '') : '',
        uploadedBy: typeof p === 'object' ? (p.uploaded_by || p.uploader || '') : '',
        uploadedAt: typeof p === 'object' ? (p.uploaded_at || '') : '',
        owner: ownerLabel,
      })
    }
  }
  addPhotos(system.photos, 'system')
  for (const p of system.planets || []) {
    addPhotos(p.photos, p.name)
    for (const m of p.moons || []) addPhotos(m.photos, `${m.name} (moon of ${p.name})`)
  }
  return out
}

export default function SystemDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [searchParams] = useSearchParams()
  const [system, setSystem] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editMode, setEditMode] = useState(false)
  const [draft, setDraft] = useState({ name: '', description: '' })
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)
  const [lightboxIdx, setLightboxIdx] = useState(null)

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      const r = await axios.get(`/api/systems/${encodeURIComponent(id)}`)
      setSystem(r.data)
      setDraft({ name: r.data?.name || '', description: r.data?.description || '' })
      setError(null)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to load system')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { reload() }, [reload])

  const photos = useMemo(() => gatherPhotos(system), [system])

  function showToast(message, kind = 'success') {
    setToast({ message, kind })
    setTimeout(() => setToast(null), 2500)
  }

  function startEdit() {
    setDraft({ name: system?.name || '', description: system?.description || '' })
    setEditMode(true)
  }

  function discardEdits() {
    setEditMode(false)
    setDraft({ name: system?.name || '', description: system?.description || '' })
  }

  async function saveEdits() {
    if (!system) return
    const trimmedName = (draft.name || '').trim()
    if (!trimmedName) {
      showToast('Name cannot be empty', 'error')
      return
    }
    setSaving(true)
    try {
      // Per Parker's call (Phase 3 Q5): inline edits submit to pending_systems
      // with edit_system_id, NOT a direct PATCH on the live row. The existing
      // /api/submit_system endpoint reads the `id` field as edit_system_id
      // and queues the row for normal approval review.
      //
      // M-S2: send ONLY the fields the user actually edited (plus the
      // identity fields the approval handler needs to locate the row).
      // Spreading the full `system` object previously dragged joined
      // fields (region_name, completeness_breakdown, etc.) and nested
      // arrays (planets, moons) into the pending row, where they either
      // got stomped on approval or bloated the JSON blob unnecessarily.
      const editPayload = {
        id: system.id,
        name: trimmedName,
        description: draft.description,
        // Identity fields the approval flow uses to locate the original
        // system and route the pending row to the right civ scope.
        glyph_code: system.glyph_code,
        reality: system.reality,
        galaxy: system.galaxy,
        discord_tag: system.discord_tag,
        region_x: system.region_x,
        region_y: system.region_y,
        region_z: system.region_z,
      }
      await axios.post('/api/submit_system', editPayload)
      setEditMode(false)
      showToast('Edits submitted for approval')
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Save failed'
      showToast(detail, 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="skeleton-card h-48" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="skeleton-card h-64 lg:col-span-2" />
          <div className="skeleton-card h-64" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="haven-card p-8 text-center">
        <h2 className="text-lg font-semibold mb-2">{error}</h2>
        <button onClick={() => navigate('/systems')} className="haven-btn-ghost px-3 py-2 rounded text-sm">
          Back to Systems
        </button>
      </div>
    )
  }

  if (!system) return null

  const starHex = STAR_HEX[system.star_type] || '#facc15'
  const starTextColor = STAR_TEXT[system.star_type] || 'white'
  const grade = system.completeness_grade
  const fromMap = searchParams.get('from_map') === '1'

  return (
    <div className="space-y-4">
      {fromMap && <FromMapBanner subject={system.name} />}

      {/* Stub banner — yellow notice when system was created as a placeholder
          for a discovery and still needs full data filled in. */}
      {system.is_stub && (
        <div
          className="flex items-start gap-3 px-4 py-3 rounded-lg"
          style={{
            background: 'rgba(250,204,21,0.10)',
            border: '1px solid rgba(250,204,21,0.45)',
          }}
        >
          <span className="text-lg" aria-hidden="true">⚠️</span>
          <div className="text-sm" style={{ color: 'rgba(255,255,255,0.9)' }}>
            <div className="font-semibold" style={{ color: '#facc15' }}>Stub System — Needs Update</div>
            <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
              This system was created as a placeholder so a discovery could link to it. Please use the Wizard to fill in the full system data.
            </div>
          </div>
        </div>
      )}

      {editMode && (
        <div
          className="flex items-center justify-between gap-3 px-4 py-2.5 rounded-lg"
          style={{
            background: 'rgba(255, 180, 76, 0.1)',
            border: '1px solid rgba(255, 180, 76, 0.4)',
          }}
        >
          <div className="flex items-center gap-2 text-sm">
            <svg className="w-4 h-4" style={{ color: 'var(--app-accent-amber)' }} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            <span>
              <span className="font-medium" style={{ color: 'var(--app-accent-amber)' }}>Edit Mode</span>
              {' '}<span style={{ color: 'var(--muted)' }}>— changes submit for admin approval; click "Save changes" to send, or "Discard" to cancel</span>
            </span>
          </div>
          <button onClick={discardEdits} className="haven-btn-ghost px-2.5 py-1 rounded text-xs">
            Discard
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* LEFT: hero card */}
        <div className="lg:col-span-2 haven-card overflow-hidden p-0">
          <div
            className="relative h-48 overflow-hidden"
            style={{
              background: `radial-gradient(circle at 30% 50%, ${starHex}40 0%, transparent 60%), linear-gradient(135deg, #0f1538, var(--app-bg))`,
            }}
          >
            <div className="absolute inset-0 flex items-center justify-center">
              <div
                className="w-32 h-32 rounded-full"
                style={{ background: `radial-gradient(circle, ${starHex} 0%, ${starHex}80 30%, transparent 70%)`, filter: 'blur(12px)' }}
              />
              <div
                className="absolute w-16 h-16 rounded-full"
                style={{ background: starHex, boxShadow: `0 0 40px ${starHex}` }}
              />
            </div>
            <div className="absolute top-3 left-3 flex items-center gap-1.5 flex-wrap">
              {system.star_type && (
                <span className="pill" style={{ background: starHex, color: starTextColor, fontWeight: 700 }}>
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="10" r="6" /></svg>
                  {system.star_type}
                </span>
              )}
              {system.economy_type && (
                <span className="pill pill-muted backdrop-blur" style={{ background: 'rgba(0,0,0,0.6)' }}>
                  {system.economy_type}{system.economy_level ? ` ${system.economy_level}` : ''}
                </span>
              )}
              {system.game_mode && system.game_mode !== 'Normal' && (
                <span
                  className="pill backdrop-blur font-semibold"
                  style={{
                    background: (GAME_MODE_COLOR[system.game_mode] || GAME_MODE_COLOR.Normal).bg,
                    color: (GAME_MODE_COLOR[system.game_mode] || GAME_MODE_COLOR.Normal).text,
                  }}
                  title={`Game mode: ${system.game_mode}`}
                >
                  {system.game_mode}
                </span>
              )}
            </div>
            <div className="absolute top-3 right-3 flex items-center gap-1.5">
              {system.is_stub && (
                <span
                  className="pill text-[10px] font-bold"
                  style={{ background: 'rgba(250,204,21,0.25)', color: '#facc15', border: '1px solid rgba(250,204,21,0.5)' }}
                  title="Placeholder system created for a discovery — needs full data"
                >
                  STUB
                </span>
              )}
              {grade && (
                <span className="w-8 h-8 rounded-md flex items-center justify-center text-sm font-bold mono" style={GRADE_STYLE[grade] || GRADE_STYLE.C}>
                  {grade}
                </span>
              )}
            </div>
          </div>

          <div className="p-5 space-y-4">
            <div>
              <div className="flex items-center justify-between gap-3 flex-wrap">
                {editMode ? (
                  <input
                    value={draft.name}
                    onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
                    className="haven-input text-2xl font-semibold px-2 py-1 flex-1 min-w-0"
                    style={{ borderColor: 'var(--app-primary)' }}
                    aria-label="System name"
                  />
                ) : (
                  <h2 className="text-2xl font-semibold flex-1 min-w-0 truncate">{system.name}</h2>
                )}
                <div className="flex items-center gap-2">
                  <ShowOnMapButton system={system} variant="ghost" />
                  {!editMode && (
                    <button onClick={startEdit} className="haven-btn-ghost px-2.5 py-1.5 rounded-lg text-xs flex items-center gap-1.5">
                      <PencilIcon /> Edit
                    </button>
                  )}
                  {editMode && (
                    <button
                      onClick={saveEdits}
                      disabled={saving}
                      className="haven-btn-primary px-2.5 py-1.5 rounded-lg text-xs flex items-center gap-1.5 disabled:opacity-40"
                    >
                      {saving ? 'Submitting…' : 'Save changes'}
                    </button>
                  )}
                </div>
              </div>
              <p className="mono text-xs mt-1" style={{ color: 'var(--muted)' }}>
                {system.glyph_code || '—'}
                {system.stellar_classification ? ` · ${system.stellar_classification}` : ''}
                {system.discovered_by || system.personal_discord_username ? ` · discovered by ${system.discovered_by || system.personal_discord_username}` : ''}
              </p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Stat label="Planets" value={(system.planets || []).filter((p) => !p.is_moon).length} secondary={`+ ${(system.planets || []).reduce((acc, p) => acc + (p.moons?.length || 0), 0)} moons`} />
              <Stat
                label="Conflict"
                value={system.conflict_level || '—'}
                secondary={system.dominant_lifeform ? `${system.dominant_lifeform} dominant` : null}
                valueClass={
                  system.conflict_level === 'Low' ? 'grade-a'
                  : system.conflict_level === 'High' ? 'text-red-400'
                  : 'grade-s'
                }
              />
              <Stat
                label="Economy"
                value={system.economy_level || '—'}
                secondary={system.economy_type || null}
              />
              <Stat
                label="Complete"
                value={system.completeness_score != null ? `${system.completeness_score}%` : '—'}
                secondary={
                  system.completeness_score == null ? null
                  : grade === 'S+' ? 'grade S+'
                  : system.completeness_score >= 85 ? 'grade S'
                  : system.completeness_score >= 65 ? 'grade A'
                  : system.completeness_score >= 40 ? 'grade B' : 'grade C'
                }
                valueClass={
                  grade === 'S+' ? 'grade-splus'
                  : system.completeness_score >= 85 ? 'grade-s'
                  : system.completeness_score >= 65 ? 'grade-a'
                  : system.completeness_score >= 40 ? 'grade-b' : 'grade-c'
                }
              />
            </div>

            <div>
              <div className="text-[10px] uppercase tracking-wider font-semibold mb-1.5" style={{ color: 'var(--muted)' }}>Description</div>
              {editMode ? (
                <textarea
                  value={draft.description}
                  onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))}
                  rows={4}
                  className="haven-input w-full text-sm p-2"
                />
              ) : (
                <p className="text-sm" style={{ color: 'rgba(255,255,255,0.85)' }}>
                  {system.description || <span style={{ color: 'var(--muted)' }}>No description yet.</span>}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT: meta column */}
        <div className="space-y-4">
          <div className="haven-card p-4">
            <div className="text-[10px] uppercase tracking-wider mb-2 font-semibold" style={{ color: 'var(--muted)' }}>Community</div>
            {system.discord_tag && system.discord_tag !== 'personal' ? (
              <div className="flex items-center gap-2">
                <span className="pill pill-purple">{system.discord_tag}</span>
              </div>
            ) : (
              <div className="text-sm" style={{ color: 'var(--muted)' }}>Personal submission</div>
            )}
          </div>

          <div className="haven-card p-4">
            <div className="text-[10px] uppercase tracking-wider mb-2 font-semibold" style={{ color: 'var(--muted)' }}>Coordinates</div>
            <div className="space-y-1.5 text-xs">
              <Row label="Galaxy" value={system.galaxy || 'Euclid'} />
              <Row label="Reality" value={system.reality || 'Normal'} />
              <Row label="Region" value={`${system.region_x} · ${system.region_y} · ${system.region_z}`} mono />
              {system.region_name && <Row label="Name" value={system.region_name} />}
              {system.glyph_code && <Row label="Glyph" value={system.glyph_code} mono />}
            </div>
            {system.glyph_code && (
              <button
                onClick={() => navigator.clipboard?.writeText(system.glyph_code).then(() => showToast('Glyph copied'))}
                className="haven-btn-ghost w-full px-2 py-1.5 rounded text-xs mt-3"
              >
                Copy glyph
              </button>
            )}
          </div>

          <div className="haven-card p-4 space-y-2">
            <div className="text-[10px] uppercase tracking-wider mb-1 font-semibold" style={{ color: 'var(--muted)' }}>Actions</div>
            <ShowOnMapButton system={system} variant="block" />
            <Link
              to={`/wizard?edit=${encodeURIComponent(system.id)}`}
              className="haven-btn-ghost w-full px-3 py-2 rounded-lg text-sm flex items-center justify-center gap-2"
            >
              <PencilIcon /> Full edit (Wizard)
            </Link>
          </div>

          <div className="haven-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--muted)' }}>Recent Activity</div>
            </div>
            <ActivityFeed systemId={system.id} system={system} />
          </div>
        </div>
      </div>

      {/* PLANETS */}
      {(system.planets || []).length > 0 && (
        <div className="haven-card p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-semibold">Planets &amp; Moons ({system.planets.length})</h3>
          </div>
          {/* 2-up on lg+, gives each expandable card enough horizontal room
              for sphere + name + 3 stats + expanded detail rows. */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-3" style={{ alignItems: 'start' }}>
            {(system.planets || []).map((p, i) => <PlanetCard key={p.id || i} p={p} index={i + 1} />)}
          </div>
        </div>
      )}

      {/* SPACE STATION */}
      {system.space_station && <SpaceStationCard station={system.space_station} />}

      {/* DISCOVERIES (linked to this system) */}
      {(system.discoveries || []).length > 0 && (
        <SystemDiscoveriesList discoveries={system.discoveries} />
      )}

      {/* COMPLETENESS BREAKDOWN */}
      {system.completeness_breakdown && (
        <CompletenessBreakdown
          breakdown={system.completeness_breakdown}
          score={system.completeness_score}
          grade={grade}
        />
      )}

      {/* PHOTOS */}
      {photos.length > 0 && (
        <div className="haven-card p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-semibold">Photos ({photos.length})</h3>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
            {photos.map((p, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setLightboxIdx(i)}
                className="aspect-square rounded-lg overflow-hidden cursor-pointer hover:opacity-80 transition-opacity"
                style={{ background: '#0f1538' }}
                title={p.caption || `Photo ${i + 1}`}
              >
                <img
                  src={p.thumbnailUrl || p.url}
                  alt=""
                  className="w-full h-full object-cover"
                  onError={(e) => { e.currentTarget.src = p.url }}
                />
              </button>
            ))}
          </div>
        </div>
      )}

      {lightboxIdx != null && (
        <Lightbox
          photos={photos}
          index={lightboxIdx}
          onChange={setLightboxIdx}
          onClose={() => setLightboxIdx(null)}
        />
      )}

      {toast && (
        <div
          className="fixed bottom-6 left-1/2 z-[80]"
          style={{
            transform: 'translateX(-50%)',
            background: 'var(--app-card)',
            border: `1px solid ${toast.kind === 'error' ? '#ef4444' : 'var(--app-primary)'}`,
            borderRadius: 8,
            padding: '0.625rem 1rem',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
            animation: 'slideDown 200ms',
          }}
        >
          <div className="flex items-center gap-2 text-sm">
            {toast.kind === 'error'
              ? <span style={{ color: '#fca5a5' }}>✕</span>
              : <span style={{ color: 'var(--app-primary)' }}>✓</span>}
            {toast.message}
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, secondary, valueClass }) {
  return (
    <div className="p-3 rounded-lg" style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-soft)' }}>
      <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--muted)' }}>{label}</div>
      <div className={`text-xl font-bold ${valueClass || ''}`}>{value}</div>
      {secondary && <div className="text-[10px]" style={{ color: 'var(--muted)' }}>{secondary}</div>}
    </div>
  )
}

function Row({ label, value, mono }) {
  return (
    <div className="flex justify-between gap-2">
      <span style={{ color: 'var(--muted)' }}>{label}</span>
      <span className={mono ? 'mono text-right' : 'text-right'}>{value}</span>
    </div>
  )
}

function PencilIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
    </svg>
  )
}

function ShowOnMapButton({ system, variant = 'ghost' }) {
  // v1.68.2 — sister buttons that drop a sticky tracking pin. Every button
  // sets focus=system:<id> on the URL, so clicking any of the three buttons
  // pins the same system across all 3 map layers — the chip appears on
  // every page, and the user removes the pin with ✕ when done.
  const sysId = encodeURIComponent(system.id)
  const focusParam = `focus=system:${sysId}`
  const rx = system.region_x, ry = system.region_y, rz = system.region_z
  const hasRegion = rx != null && ry != null && rz != null
  const buttons = [
    {
      label: 'System Map',
      icon: '⭐',
      href: `/map/system/${sysId}?${focusParam}`,
      title: 'Open this system in the planetary 3D viewer',
    },
  ]
  if (hasRegion) {
    buttons.push({
      label: 'Region Map',
      icon: '📍',
      href: `/map/region?rx=${rx}&ry=${ry}&rz=${rz}&${focusParam}`,
      title: 'View this system in its region',
    })
    buttons.push({
      label: 'Galaxy Map',
      icon: '🌌',
      href: `/map/latest?${focusParam}`,
      title: 'See where this system sits in the galaxy',
    })
  }
  if (variant === 'block') {
    return (
      <div className="w-full grid grid-cols-1 sm:grid-cols-3 gap-2">
        {buttons.map((b) => (
          <a
            key={b.label}
            href={b.href}
            title={b.title}
            className="haven-btn-ghost px-3 py-2 rounded-lg text-sm flex items-center justify-center gap-2"
          >
            <span style={{ color: 'var(--app-primary)' }}>{b.icon}</span>
            {b.label}
          </a>
        ))}
      </div>
    )
  }
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {buttons.map((b) => (
        <a
          key={b.label}
          href={b.href}
          title={b.title}
          className="haven-btn-ghost px-2.5 py-1.5 rounded-lg text-xs flex items-center gap-1.5"
        >
          <span style={{ color: 'var(--app-primary)' }}>{b.icon}</span>
          {b.label}
        </a>
      ))}
    </div>
  )
}

// Wonders Page Notes (migration v1.76.0 — wizard rebuild). Renders only when
// at least one field is populated so old systems show no extra chrome.
function WondersNotes({ row }) {
  if (!row) return null
  const fields = [
    ['Estimated Age', row.estimated_age],
    ['Core Element', row.core_element],
    ['Root Structure', row.root_structure],
    ['Nutrient Source', row.nutrient_source],
  ].filter(([, v]) => v != null && v !== '')
  if (fields.length === 0 && !row.lore_notes) return null
  return (
    <div
      className="mt-2 p-2 rounded text-[10px] space-y-0.5"
      style={{
        background: 'rgba(255, 180, 76, 0.07)',
        border: '1px solid rgba(255, 180, 76, 0.30)',
      }}
    >
      <div className="font-semibold uppercase tracking-wider flex items-center gap-1" style={{ color: 'var(--app-accent-amber)' }}>
        ★ Wonders Notes
      </div>
      {fields.map(([label, v]) => (
        <div key={label}><span style={{ color: 'var(--muted)' }}>{label}: </span><span>{v}</span></div>
      ))}
      {row.lore_notes && (
        <div className="italic whitespace-pre-line mt-1" style={{ color: 'rgba(255,255,255,0.85)' }}>
          {row.lore_notes}
        </div>
      )}
    </div>
  )
}

// Aggregate per-row boolean flags into a deduped list of badge labels.
const FEATURE_FLAGS = [
  ['vile_brood', 'Vile Brood'],
  ['ancient_bones', 'Ancient Bones'],
  ['storm_crystals', 'Storm Crystals'],
  ['gravitino_balls', 'Gravitino Balls'],
  ['salvageable_scrap', 'Salvageable Scrap'],
  ['is_dissonant', 'Dissonant'],
  ['dissonance', 'Dissonant'],
  ['is_infested', 'Infested'],
  ['infested', 'Infested'],
  ['water_world', 'Water World'],
  ['has_water', 'Water'],
  ['is_bubble', 'Bubble Planet'],
  ['is_floating_islands', 'Floating Islands'],
  ['has_rings', 'Has Rings'],
  ['is_gas_giant', 'Gas Giant'],
  ['extreme_weather', 'Extreme Weather'],
]

function featureBadges(row) {
  if (!row) return []
  const seen = new Set()
  const out = []
  for (const [key, label] of FEATURE_FLAGS) {
    if (row[key] && !seen.has(label)) { seen.add(label); out.push(label) }
  }
  return out
}

function PlanetCard({ p, index }) {
  const [expanded, setExpanded] = React.useState(false)
  const moonCount = (p.moons || []).length
  const features = featureBadges(p)
  const materials = (p.materials || '').split(',').map((s) => s.trim()).filter(Boolean)
  const resources = [
    p.common_resource && { tier: 'Common', name: p.common_resource },
    p.uncommon_resource && { tier: 'Uncommon', name: p.uncommon_resource },
    p.rare_resource && { tier: 'Rare', name: p.rare_resource },
  ].filter(Boolean)

  return (
    <div
      className="haven-card overflow-hidden"
      style={{ transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)' }}
    >
      {/* Compact header — always visible, click to expand */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left p-3 hover:bg-white/5 transition-colors"
        aria-expanded={expanded}
      >
        <div className="flex gap-3 items-start">
          {/* Parametric sphere or photo */}
          <div className="shrink-0">
            <PlanetSphere
              size={88}
              biome={p.biome}
              photo={p.photo}
              hasRings={!!p.has_rings}
              waterWorld={!!p.water_world}
              isDissonant={!!(p.is_dissonant || p.dissonance)}
              extremeWeather={!!p.extreme_weather}
              isGasGiant={!!p.is_gas_giant}
              isBubble={!!p.is_bubble}
              isFloatingIslands={!!p.is_floating_islands}
              moonCount={moonCount}
              exoticTrophy={p.exotic_trophy}
              badge={`P${index}`}
            />
          </div>
          {/* Right column: name + biome/weather + 3 stats */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="text-sm font-semibold truncate">{p.name || `Planet ${index}`}</div>
              <svg
                className="w-4 h-4 shrink-0 mt-0.5"
                style={{ color: 'var(--muted)', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 200ms' }}
                fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
            <div className="text-[11px]" style={{ color: 'var(--muted)' }}>
              {p.biome || '—'}{p.weather ? ` · ${p.weather}` : ''}
            </div>
            <div className="grid grid-cols-3 gap-1 text-[11px] mt-2">
              <div><div style={{ color: 'var(--muted)' }}>Fauna</div><div className={`font-bold truncate ${getFaunaColor(p.fauna)}`}>{p.fauna || '—'}</div></div>
              <div><div style={{ color: 'var(--muted)' }}>Flora</div><div className={`font-bold truncate ${getFloraColor(p.flora)}`}>{p.flora || '—'}</div></div>
              <div><div style={{ color: 'var(--muted)' }}>Sent.</div><div className={`font-bold truncate ${getSentinelColor(p.sentinel)}`} title={p.sentinel || ''}>{p.sentinel || '—'}</div></div>
            </div>
          </div>
        </div>
      </button>

      {/* Expanded detail block */}
      {expanded && (
        <div
          className="px-3 pb-3 pt-1 space-y-2"
          style={{ borderTop: '1px solid var(--border-soft)' }}
        >
          {features.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-2">
              {features.map((f) => <span key={f} className="pill pill-amber text-[10px]">★ {f}</span>)}
            </div>
          )}

          {materials.length > 0 && (
            <DetailRow label="Materials">
              <span className="flex flex-wrap gap-1">
                {materials.map((m, i) => <span key={i} className="pill pill-muted text-[10px]">{m}</span>)}
              </span>
            </DetailRow>
          )}

          {resources.length > 0 && (
            <DetailRow label="Resources">
              <span className="flex flex-wrap gap-1">
                {resources.map((r, i) => (
                  <span key={i} className="pill pill-blue text-[10px]">
                    <span className="opacity-60">{r.tier}:</span>&nbsp;{r.name}
                  </span>
                ))}
              </span>
            </DetailRow>
          )}

          {(p.hazard_radiation || p.hazard_temperature || p.hazard_toxicity || p.storm_frequency || p.building_density) && (
            <DetailRow label="Conditions">
              <span className="flex flex-wrap gap-x-3 gap-y-1 text-[11px]">
                {p.hazard_radiation && <span><span style={{ color: 'var(--muted)' }}>Rad:</span> {p.hazard_radiation}</span>}
                {p.hazard_temperature && <span><span style={{ color: 'var(--muted)' }}>Temp:</span> {p.hazard_temperature}</span>}
                {p.hazard_toxicity && <span><span style={{ color: 'var(--muted)' }}>Tox:</span> {p.hazard_toxicity}</span>}
                {p.storm_frequency && <span><span style={{ color: 'var(--muted)' }}>Storms:</span> {p.storm_frequency}</span>}
                {p.building_density && <span><span style={{ color: 'var(--muted)' }}>Bldgs:</span> {p.building_density}</span>}
              </span>
            </DetailRow>
          )}

          {p.exotic_trophy && (
            <DetailRow label="Exotic Trophy">
              <span style={{ color: 'var(--app-accent-amber)' }}>★ {p.exotic_trophy}</span>
            </DetailRow>
          )}

          {p.base_location && (
            <DetailRow label="Base"><span className="mono">{p.base_location}</span></DetailRow>
          )}

          {p.notes && (
            <DetailRow label="Notes">
              <span className="italic whitespace-pre-line" style={{ color: 'rgba(255,255,255,0.85)' }}>{p.notes}</span>
            </DetailRow>
          )}

          <WondersNotes row={p} />

          {/* Moons — nested expandable cards */}
          {moonCount > 0 && (
            <div className="pt-2 mt-2" style={{ borderTop: '1px solid var(--border-soft)' }}>
              <div className="text-[10px] uppercase tracking-wider mb-2 font-semibold" style={{ color: 'var(--muted)' }}>
                Moons ({moonCount})
              </div>
              <div className="space-y-2">
                {(p.moons || []).map((m, mi) => <MoonCard key={m.id || mi} m={m} index={mi + 1} />)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function MoonCard({ m, index }) {
  const [expanded, setExpanded] = React.useState(false)
  const features = featureBadges(m)
  const materials = (m.materials || '').split(',').map((s) => s.trim()).filter(Boolean)
  const resources = [
    m.common_resource && { tier: 'Common', name: m.common_resource },
    m.uncommon_resource && { tier: 'Uncommon', name: m.uncommon_resource },
    m.rare_resource && { tier: 'Rare', name: m.rare_resource },
  ].filter(Boolean)

  return (
    <div className="rounded overflow-hidden" style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-soft)' }}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left p-2 hover:bg-white/5 transition-colors"
        aria-expanded={expanded}
      >
        <div className="flex gap-2 items-center">
          <div className="shrink-0">
            <PlanetSphere
              size={48}
              biome={m.biome}
              photo={m.photo}
              waterWorld={!!m.water_world}
              isDissonant={!!(m.is_dissonant || m.dissonance)}
              extremeWeather={!!m.extreme_weather}
              isBubble={!!m.is_bubble}
              isFloatingIslands={!!m.is_floating_islands}
              isMoon
              badge={`M${index}`}
            />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{m.name || `Moon ${index}`}</div>
            <div className="text-[10px]" style={{ color: 'var(--muted)' }}>
              {m.biome || '—'}{m.weather || m.climate ? ` · ${m.weather || m.climate}` : ''}
            </div>
          </div>
          <svg
            className="w-3.5 h-3.5 shrink-0"
            style={{ color: 'var(--muted)', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 200ms' }}
            fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="px-2 pb-2 pt-1 space-y-1.5 text-[11px]" style={{ borderTop: '1px solid var(--border-soft)' }}>
          <div className="grid grid-cols-3 gap-1 pt-2">
            <div><div style={{ color: 'var(--muted)' }}>Fauna</div><div className={`font-bold truncate ${getFaunaColor(m.fauna)}`}>{m.fauna || '—'}</div></div>
            <div><div style={{ color: 'var(--muted)' }}>Flora</div><div className={`font-bold truncate ${getFloraColor(m.flora)}`}>{m.flora || '—'}</div></div>
            <div><div style={{ color: 'var(--muted)' }}>Sent.</div><div className={`font-bold truncate ${getSentinelColor(m.sentinel)}`} title={m.sentinel || ''}>{m.sentinel || '—'}</div></div>
          </div>
          {features.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {features.map((f) => <span key={f} className="pill pill-amber text-[10px]">★ {f}</span>)}
            </div>
          )}
          {materials.length > 0 && (
            <DetailRow label="Materials">
              <span className="flex flex-wrap gap-1">
                {materials.map((mat, i) => <span key={i} className="pill pill-muted text-[10px]">{mat}</span>)}
              </span>
            </DetailRow>
          )}
          {resources.length > 0 && (
            <DetailRow label="Resources">
              <span className="flex flex-wrap gap-1">
                {resources.map((r, i) => (
                  <span key={i} className="pill pill-blue text-[10px]">
                    <span className="opacity-60">{r.tier}:</span>&nbsp;{r.name}
                  </span>
                ))}
              </span>
            </DetailRow>
          )}
          {m.base_location && <DetailRow label="Base"><span className="mono">{m.base_location}</span></DetailRow>}
          {m.notes && (
            <DetailRow label="Notes">
              <span className="italic whitespace-pre-line" style={{ color: 'rgba(255,255,255,0.85)' }}>{m.notes}</span>
            </DetailRow>
          )}
          <WondersNotes row={m} />
        </div>
      )}
    </div>
  )
}

function DetailRow({ label, children }) {
  return (
    <div className="flex items-start gap-2 text-[11px]">
      <span className="shrink-0 mono uppercase tracking-wider" style={{ color: 'var(--muted)', minWidth: 70 }}>{label}</span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  )
}

// Per-field status styling for the expandable detail rows. `filled` = green
// check, `missing` = red cross, `skipped` = muted dash (dead-biome planets
// legitimately skip fauna/flora and shouldn't read as "missing").
const COMPLETENESS_STATUS = {
  filled: { mark: '✓', color: '#34d399' },
  missing: { mark: '✕', color: '#f87171' },
  skipped: { mark: '–', color: 'var(--muted)' },
}

// One field line inside an expanded category (e.g. "Star Type — Yellow").
function CompletenessField({ item }) {
  const st = COMPLETENESS_STATUS[item.status] || COMPLETENESS_STATUS.missing
  const valueText =
    item.status === 'filled' ? (item.value != null ? String(item.value) : '—')
      : item.status === 'skipped' ? 'N/A'
        : 'Missing'
  return (
    <div className="flex items-center justify-between gap-2 text-[11px] py-0.5">
      <span className="flex items-center gap-1.5 min-w-0">
        <span style={{ color: st.color, width: 9, flexShrink: 0, textAlign: 'center' }}>{st.mark}</span>
        <span className="truncate" style={{ color: 'var(--muted)' }}>{item.name}</span>
      </span>
      <span className="truncate text-right" style={{ color: st.color, maxWidth: '58%' }}>{valueText}</span>
    </div>
  )
}

// Completeness breakdown panel — per-category progress bars, each expandable
// into the backend-supplied per-field detail. Backend has returned `breakdown`
// since v1.34.0 and `breakdown.details` more recently; the frontend renders
// both now.
function CompletenessBreakdown({ breakdown, score, grade }) {
  if (!breakdown) return null
  const allDetails = breakdown.details || {}
  return (
    <div className="haven-card p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">Completeness</h3>
        <span className="text-xs" style={{ color: 'var(--muted)' }}>
          Total {score != null ? `${score}%` : '—'}{grade ? ` · grade ${grade}` : ''}
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {COMPLETENESS_CATEGORIES.map(([key, label, max]) => {
          const catScore = breakdown[key]
          if (catScore == null) return null          // null/undefined = missing, but 0 renders
          const pct = max ? Math.round((catScore / max) * 100) : 0
          // 0 = "not filled in yet" → neutral grey, not the derogatory red.
          // Red is reserved for categories that have SOME data but little (1-39%).
          const barColor = catScore === 0 ? '#6b7280' : pct >= 85 ? '#34d399' : pct >= 65 ? '#60a5fa' : pct >= 40 ? '#fbbf24' : '#f87171'
          const details = Array.isArray(allDetails[key]) ? allDetails[key] : []
          return (
            <details key={key} className="group p-2 rounded" style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-soft)' }}>
              <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <span className="flex items-center gap-1" style={{ color: 'var(--muted)' }}>
                    <span className="inline-block transition-transform group-open:rotate-90" style={{ fontSize: 8 }}>▶</span>
                    {label}
                  </span>
                  <span className="mono" style={{ color: barColor }}>{catScore}/{max}</span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${pct}%`, background: barColor }}
                  />
                </div>
              </summary>
              {details.length > 0 && (
                <div className="mt-2 pt-2 space-y-0.5" style={{ borderTop: '1px solid var(--border-soft)' }}>
                  {details.map((item, i) => (
                    Array.isArray(item.fields) ? (
                      // Planet-grouped category (planet_environment / planet_life):
                      // planet name as a sub-header, its fields indented below.
                      <div key={i} className="mt-1 first:mt-0">
                        <div className="flex items-center justify-between text-[11px] font-semibold">
                          <span className="truncate" style={{ color: 'var(--app-text)' }}>{item.name}</span>
                          <span className="mono" style={{ color: 'var(--muted)' }}>{item.filled}/{item.total}</span>
                        </div>
                        <div className="pl-2 ml-1 border-l" style={{ borderColor: 'var(--border-soft)' }}>
                          {item.fields.map((f, j) => <CompletenessField key={j} item={f} />)}
                        </div>
                      </div>
                    ) : (
                      <CompletenessField key={i} item={item} />
                    )
                  ))}
                </div>
              )}
            </details>
          )
        })}
      </div>
    </div>
  )
}

// Space station card — backend has returned `space_station` (with trade goods)
// since the v1.0 schema but SystemDetail never rendered it.
const RACE_COLOR = {
  Gek: '#10b981', "Vy'keen": '#f97316', Korvax: '#3b82f6',
  Pirate: '#a855f7', Mixed: '#94a3b8',
}
function SpaceStationCard({ station }) {
  if (!station) return null
  const race = station.race || 'Mixed'
  const raceColor = RACE_COLOR[race] || '#94a3b8'
  const tradeGoods = Array.isArray(station.trade_goods) ? station.trade_goods : []
  return (
    <div className="haven-card p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">Space Station</h3>
        <span className="pill" style={{ background: `${raceColor}30`, color: raceColor, fontWeight: 600 }}>
          {race}
        </span>
      </div>
      <div className="space-y-2">
        {station.name && (
          <div className="text-sm font-semibold">{station.name}</div>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {station.sell_percent != null && (
            <Stat label="Sell %" value={`${station.sell_percent}%`} />
          )}
          {station.buy_percent != null && (
            <Stat label="Buy %" value={`${station.buy_percent}%`} />
          )}
          {station.x != null && (
            <Stat label="Position" value={`${station.x.toFixed?.(1) ?? station.x},${station.y?.toFixed?.(1) ?? station.y}`} secondary={station.z != null ? `z ${station.z.toFixed?.(1) ?? station.z}` : null} />
          )}
        </div>
        {tradeGoods.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wider mb-1.5 font-semibold" style={{ color: 'var(--muted)' }}>
              Trade Goods ({tradeGoods.length})
            </div>
            <div className="flex flex-wrap gap-1">
              {tradeGoods.map((g, i) => (
                <span key={i} className="pill pill-muted text-[10px]">
                  {typeof g === 'string' ? g : (g?.name || JSON.stringify(g))}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// System discoveries list — discoveries linked to this system via
// planet_id / moon_id / space (no link = system-wide). Backend now returns
// these on the system detail response; previously SystemDetail had no
// awareness of linked discoveries at all even though v1.33 added the link.
function SystemDiscoveriesList({ discoveries }) {
  const grouped = useMemo(() => {
    const byTarget = { planet: {}, moon: {}, space: [], orphan: [] }
    for (const d of discoveries) {
      // An "orphan" is a discovery whose intent was to be on a planet or
      // moon (location_type says so) but whose FK link is NULL — the
      // submitter's body name didn't resolve at approval time and the
      // backend inserted with a warning. Surface these separately so they
      // don't quietly masquerade as intentional "in space" discoveries.
      const intendsBody = d.location_type === 'planet' || d.location_type === 'moon'
      const hasLink = !!(d.planet_id || d.moon_id)
      if (intendsBody && !hasLink) {
        byTarget.orphan.push(d)
      } else if (d.planet_name && !d.moon_name) {
        byTarget.planet[d.planet_name] = byTarget.planet[d.planet_name] || []
        byTarget.planet[d.planet_name].push(d)
      } else if (d.moon_name) {
        const key = `${d.planet_name || '?'}::${d.moon_name}`
        byTarget.moon[key] = byTarget.moon[key] || []
        byTarget.moon[key].push(d)
      } else {
        byTarget.space.push(d)
      }
    }
    return byTarget
  }, [discoveries])

  return (
    <div className="haven-card p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">Discoveries ({discoveries.length})</h3>
        <Link to="/discoveries" className="text-xs haven-link">Browse all →</Link>
      </div>
      <div className="space-y-3">
        {Object.entries(grouped.planet).map(([planet, list]) => (
          <DiscoveryGroup key={`p-${planet}`} label={planet} icon="🌍" items={list} />
        ))}
        {Object.entries(grouped.moon).map(([key, list]) => {
          const [planet, moon] = key.split('::')
          return (
            <DiscoveryGroup
              key={`m-${key}`}
              label={moon}
              sublabel={`moon of ${planet}`}
              icon="🌑"
              items={list}
            />
          )
        })}
        {grouped.space.length > 0 && (
          <DiscoveryGroup label="In space" icon="✨" items={grouped.space} />
        )}
        {grouped.orphan.length > 0 && (
          <div
            className="p-3 rounded"
            style={{ background: 'rgba(255,180,76,0.08)', border: '1px solid var(--app-accent-amber, #ffb44c)' }}
          >
            <div className="flex items-baseline gap-2 mb-2">
              <span aria-hidden="true">⚠</span>
              <span className="text-sm font-semibold" style={{ color: 'var(--app-accent-amber, #ffb44c)' }}>
                Unlinked ({grouped.orphan.length})
              </span>
              <span className="text-[10px]" style={{ color: 'var(--muted)' }}>
                discovery intended for a planet/moon but the body name didn't resolve at approval time
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {grouped.orphan.map((d) => (
                <Link
                  key={d.id}
                  to={`/discoveries/${d.type_slug || 'other'}`}
                  className="px-2 py-1 rounded text-xs hover:bg-white/5 transition-colors"
                  style={{ background: 'rgba(255,255,255,0.05)' }}
                  title={d.description || d.discovery_name}
                >
                  <span className="font-medium">{d.discovery_name}</span>
                  {d.discovery_type && (
                    <span className="ml-1.5 text-[10px]" style={{ color: 'var(--muted)' }}>· {d.discovery_type}</span>
                  )}
                  {formatCoords(d.latitude, d.longitude) && (
                    <span className="ml-1.5 text-[10px] font-mono" style={{ color: 'var(--muted)' }}>📍 {formatCoords(d.latitude, d.longitude)}</span>
                  )}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function DiscoveryGroup({ label, sublabel, icon, items }) {
  return (
    <div className="p-3 rounded" style={{ background: 'rgba(0,0,0,0.20)', border: '1px solid var(--border-soft)' }}>
      <div className="flex items-baseline gap-2 mb-2">
        <span aria-hidden="true">{icon}</span>
        <span className="text-sm font-semibold">{label}</span>
        {sublabel && <span className="text-[10px]" style={{ color: 'var(--muted)' }}>{sublabel}</span>}
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((d) => (
          <Link
            key={d.id}
            to={`/discoveries/${d.type_slug || 'other'}`}
            className="px-2 py-1 rounded text-xs hover:bg-white/5 transition-colors"
            style={{ background: 'rgba(255,255,255,0.05)' }}
            title={d.description || d.discovery_name}
          >
            <span className="font-medium">{d.discovery_name}</span>
            {d.discovery_type && (
              <span className="ml-1.5 text-[10px]" style={{ color: 'var(--muted)' }}>· {d.discovery_type}</span>
            )}
            {formatCoords(d.latitude, d.longitude) && (
              <span className="ml-1.5 text-[10px] font-mono" style={{ color: 'var(--muted)' }}>📍 {formatCoords(d.latitude, d.longitude)}</span>
            )}
            {d.featured && <span className="ml-1.5">★</span>}
          </Link>
        ))}
      </div>
    </div>
  )
}
