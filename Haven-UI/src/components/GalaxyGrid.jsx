/**
 * GalaxyGrid — Level 2 of the Systems v2.0 hierarchy.
 *
 * Square-aspect poster card with real /api/posters/atlas_thumb/{name}.png
 * poster overlaid on a fallback gradient. Bottom of the card shows system /
 * region counts plus the grade-distribution stripe driven by the
 * grade_s/_a/_b/_c columns the backend already returns from
 * /api/galaxies/summary.
 *
 * Sort options: canonical galaxy number, system count, avg grade score,
 * alphabetical name. The backend doesn't expose a sort param, so we sort
 * the response in-memory — fine for the 158-galaxy worst case.
 */

import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { useSystems } from '../contexts/SystemsContext'
import useFilters from '../hooks/useFilters'
import LoadingSkeleton from './LoadingSkeleton'
import EmptyState from './EmptyState'
import CompareToggleButton from './CompareToggleButton'
import { cardStateClass, hasOutdatedDot, hasConflictDot, stateBadge } from '../utils/dataStates'

// Sort by canonical NMS galaxy index (1=Euclid, 2=Hilbert, …, 256=Iousongola).
// galaxy_index is attached client-side from /api/galaxies — see GalaxyGrid.
const SORTS = {
  'num-asc': { label: 'Canonical # ↑', fn: (a, b) => (a.galaxy_index || 999999) - (b.galaxy_index || 999999) },
  'systems-desc': { label: 'System count ↓', fn: (a, b) => (b.system_count || 0) - (a.system_count || 0) },
  'avg-desc': { label: 'Avg score ↓', fn: (a, b) => (b.avg_score || 0) - (a.avg_score || 0) },
  'name-asc': { label: 'Name A-Z', fn: (a, b) => (a.galaxy || '').localeCompare(b.galaxy || '') },
}

export default function GalaxyGrid() {
  const { reality, selectGalaxy, pushRecentlyViewed, clearFilters, compareMode, pinsByLevel, togglePin } = useSystems()
  const { apiParams, activeFilterCount } = useFilters()
  const pinning = compareMode === 'galaxy'
  const pinnedIds = new Set((pinsByLevel.galaxy || []).map((p) => p.id))
  const [rows, setRows] = useState([])
  const [galaxyIndex, setGalaxyIndex] = useState({}) // name → canonical NMS index
  const [loading, setLoading] = useState(true)
  const [sort, setSort] = useState('num-asc')

  // Canonical NMS galaxy list (1=Euclid through 256). Cached for the lifetime
  // of the session — it never changes between releases.
  useEffect(() => {
    let cancelled = false
    axios.get('/api/galaxies').then((r) => {
      if (cancelled) return
      const map = {}
      for (const g of r.data?.galaxies || []) map[g.name] = g.index
      setGalaxyIndex(map)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    axios.get('/api/galaxies/summary', { params: { reality, ...apiParams } })
      .then((r) => { if (!cancelled) setRows(r.data.galaxies || []) })
      .catch(() => { if (!cancelled) setRows([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [reality, JSON.stringify(apiParams)])

  // Attach galaxy_index to every row so the sort fn + card badge can read it
  // off the row directly.
  const decorated = useMemo(
    () => rows.map((r) => ({ ...r, galaxy_index: galaxyIndex[r.galaxy] })),
    [rows, galaxyIndex]
  )

  const sorted = useMemo(() => {
    const fn = SORTS[sort]?.fn || SORTS['num-asc'].fn
    return [...decorated].sort(fn)
  }, [decorated, sort])

  function handleClick(galaxyRow) {
    if (pinning) {
      togglePin('galaxy', {
        id: galaxyRow.galaxy,
        key: galaxyRow.galaxy,
        label: galaxyRow.galaxy,
        payload: galaxyRow,
      })
      return
    }
    pushRecentlyViewed({ type: 'galaxy', name: galaxyRow.galaxy, href: `/systems?reality=${encodeURIComponent(reality)}&galaxy=${encodeURIComponent(galaxyRow.galaxy)}` })
    selectGalaxy(galaxyRow.galaxy)
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-semibold">Galaxies in {reality}</h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
            <span>{rows.length}</span> galaxies with data
            {activeFilterCount > 0 && <span style={{ color: 'var(--app-primary)' }}> · filtered</span>}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <CompareToggleButton targetLevel="galaxy" />
          <span style={{ color: 'var(--muted)' }}>Sort:</span>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="haven-input text-xs py-1 px-2"
          >
            {Object.entries(SORTS).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <LoadingSkeleton variant="galaxy" count={8} />
      ) : sorted.length === 0 ? (
        <EmptyState
          variant="galaxy"
          title="No galaxies match these filters"
          message="Try removing a filter, or expand your scope to find more results."
          actionLabel={activeFilterCount > 0 ? 'Clear all filters' : undefined}
          onAction={activeFilterCount > 0 ? clearFilters : undefined}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {sorted.map((g) => <GalaxyCard key={g.galaxy} g={g} onClick={() => handleClick(g)} pinned={pinnedIds.has(g.galaxy)} pinning={pinning} />)}
        </div>
      )}
    </section>
  )
}

function GalaxyCard({ g, onClick, pinned, pinning }) {
  const total = g.system_count || 0
  // S+ ("fully charted") is its own segment; grade_s is S-but-not-S+ from the
  // backend so the buckets are mutually exclusive and sum to the total.
  const segments = [
    { cls: 'bar-splus', gcls: 'grade-splus', label: 'S+', count: g.grade_splus || 0 },
    { cls: 'bar-s', gcls: 'grade-s', label: 'S', count: g.grade_s || 0 },
    { cls: 'bar-a', gcls: 'grade-a', label: 'A', count: g.grade_a || 0 },
    { cls: 'bar-b', gcls: 'grade-b', label: 'B', count: g.grade_b || 0 },
    { cls: 'bar-c', gcls: 'grade-c', label: 'C', count: g.grade_c || 0 },
  ]
  const stateCls = cardStateClass(g)
  const badge = stateBadge(g)
  const avgGradeCls =
    g.avg_score >= 85 ? 'grade-s' :
    g.avg_score >= 65 ? 'grade-a' :
    g.avg_score >= 40 ? 'grade-b' : 'grade-c'

  return (
    <button
      type="button"
      onClick={onClick}
      className={`haven-card haven-card-hover overflow-hidden p-0 text-left relative ${stateCls}`.trim()}
      style={pinned ? { outline: '2px solid var(--app-primary)', outlineOffset: '-2px' } : undefined}
      aria-pressed={pinning ? pinned : undefined}
    >
      {hasOutdatedDot(g) && <span className="outdated-dot" title="Outdated — last verified > 6 months ago" />}
      {hasConflictDot(g) && <span className="conflict-dot" title="Data conflict" />}
      {badge && <span className={`state-badge ${badge.kind}`}>{badge.label}</span>}
      {pinning && pinned && (
        <span className="absolute top-2 left-2 z-20 pill-teal-solid text-[10px] mono px-1.5 py-0.5 rounded">PINNED</span>
      )}

      <div className="aspect-square relative overflow-hidden" style={{ background: 'linear-gradient(135deg, #0f1538, var(--app-bg))' }}>
        <img
          src={`/api/posters/atlas_thumb/${encodeURIComponent(g.galaxy)}.png`}
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-70 mix-blend-screen"
          loading="lazy"
          onError={(e) => { e.currentTarget.style.display = 'none' }}
        />
        <div className="absolute inset-0" style={{ background: 'linear-gradient(to top, var(--app-card) 5%, transparent 50%)' }} />
        <div className="absolute top-3 left-3 flex items-center gap-1.5 z-10">
          {g.galaxy_index != null && (
            <span
              className="w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold mono backdrop-blur"
              style={{ background: 'rgba(0,0,0,0.6)', color: 'white' }}
              title={`Canonical NMS galaxy #${g.galaxy_index}`}
            >
              {g.galaxy_index}
            </span>
          )}
          <span className="pill pill-teal backdrop-blur" style={{ background: 'rgba(0, 194, 179, 0.4)', color: 'white' }}>
            {g.reality || 'Normal'}
          </span>
        </div>
      </div>

      <div className="p-4">
        <h3 className="text-base font-semibold truncate">{g.galaxy}</h3>
        <p className="text-xs mt-0.5 mb-3" style={{ color: 'var(--muted)' }}>
          {g.galaxy === 'Euclid'
            ? 'Starting galaxy — most explored'
            : g.galaxy_index != null
              ? `Galaxy #${g.galaxy_index}`
              : `Galaxy in ${g.reality || 'Normal'}`}
        </p>
        <div className="grid grid-cols-2 gap-2 pb-3" style={{ borderBottom: '1px solid var(--border-soft)' }}>
          <div>
            <div className="text-lg font-bold">{total.toLocaleString()}</div>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>systems</div>
          </div>
          <div>
            <div className="text-lg font-bold">{(g.region_count || 0).toLocaleString()}</div>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>regions</div>
          </div>
        </div>
        <div className="pt-3">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>data grades</span>
            {g.avg_score != null && (
              <span className={`mono text-[10px] ${avgGradeCls}`}>avg {g.avg_score}</span>
            )}
          </div>
          <div className="flex items-center gap-1.5 text-[10px] font-bold mb-1">
            {segments.filter((s) => s.count > 0).map((s, i) => (
              <span key={i} className={s.gcls}>
                {s.count}<span className="opacity-60">{s.label}</span>
              </span>
            ))}
          </div>
          <div className="flex h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(0,0,0,0.4)' }}>
            {segments.map((s, i) => total > 0 && s.count > 0 ? (
              <div key={i} className={s.cls} style={{ width: `${(s.count / total) * 100}%` }} />
            ) : null)}
          </div>
        </div>
      </div>
    </button>
  )
}
