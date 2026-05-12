/**
 * RegionBrowser — Level 3 of the Systems v2.0 hierarchy.
 *
 * Hits /api/regions/grouped?include_systems=false (the cheap fast path
 * added in Master Haven 1.43.0) with the active filters. Renders a 2:1
 * stub-poster card grid by default, or a virtual-scroll-style table.
 *
 * Pagination: 6 cards per page per spec section 5.3 with prev/next + page
 * number row. Table view uses the same scroll-only treatment as L4 since
 * region counts cap around ~1,500.
 *
 * Region rows from the backend don't yet carry `is_stub`, `pending_approval`,
 * `is_restricted`, or `last_verified_at` — they're region rollups, not
 * direct rows. Data-state classes are computed on the props but won't fire
 * until the backend lights them up; the slots are wired so that drop is
 * frontend-free.
 */

import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { useSystems } from '../contexts/SystemsContext'
import useFilters from '../hooks/useFilters'
import LoadingSkeleton from './LoadingSkeleton'
import EmptyState from './EmptyState'
import CompareToggleButton from './CompareToggleButton'
import { cardStateClass, hasOutdatedDot, hasConflictDot, stateBadge } from '../utils/dataStates'

const PAGE_SIZE = 6
const SORTS = {
  'systems-desc': { label: 'System count ↓', fn: (a, b) => (b.system_count || 0) - (a.system_count || 0) },
  'name-asc': { label: 'Name A-Z', fn: (a, b) => (a.display_name || '').localeCompare(b.display_name || '') },
  'named-first': {
    label: 'Named first',
    fn: (a, b) => {
      const ax = a.custom_name ? 0 : 1
      const bx = b.custom_name ? 0 : 1
      return ax - bx || (b.system_count || 0) - (a.system_count || 0)
    },
  },
}

// M-S3: include reality + galaxy in the key. Since v1.49.0 the `regions`
// table UNIQUE is (reality, galaxy, rx, ry, rz), so the same coord triple
// in Euclid and Hilbert is two real rows. Keying only on rx/ry/rz let
// Compare collapse them into one column.
function regionKey(r, reality, galaxy) {
  return `${reality || 'Normal'}|${galaxy || 'Euclid'}|${r.region_x},${r.region_y},${r.region_z}`
}

export default function RegionBrowser() {
  const { reality, galaxy, selectRegion, pushRecentlyViewed, clearFilters, compareMode, pinsByLevel, togglePin } = useSystems()
  const { apiParams, activeFilterCount } = useFilters()
  const pinning = compareMode === 'region'
  const pinnedKeys = new Set((pinsByLevel.region || []).map((p) => p.id))
  const [rows, setRows] = useState([])
  const [totalRegions, setTotalRegions] = useState(0)
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState('cards')
  const [sort, setSort] = useState('named-first')
  const [page, setPage] = useState(1)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    axios.get('/api/regions/grouped', {
      params: { include_systems: false, reality, galaxy, ...apiParams },
    })
      .then((r) => {
        if (cancelled) return
        setRows(r.data.regions || [])
        setTotalRegions(r.data.total_regions || (r.data.regions || []).length)
      })
      .catch(() => { if (!cancelled) { setRows([]); setTotalRegions(0) } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [reality, galaxy, JSON.stringify(apiParams)])

  // Reset to page 1 on filter / sort / data change
  useEffect(() => { setPage(1) }, [reality, galaxy, sort, JSON.stringify(apiParams)])

  const sorted = useMemo(() => {
    const fn = SORTS[sort]?.fn || SORTS['named-first'].fn
    return [...rows].sort(fn)
  }, [rows, sort])

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))
  const paged = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return sorted.slice(start, start + PAGE_SIZE)
  }, [sorted, page])

  function handleClick(region) {
    if (pinning) {
      const k = regionKey(region, reality, galaxy)
      togglePin('region', {
        id: k,
        key: k,
        label: region.display_name,
        payload: region,
      })
      return
    }
    pushRecentlyViewed({
      type: 'region',
      name: region.display_name,
      href: `/systems?reality=${encodeURIComponent(reality)}&galaxy=${encodeURIComponent(galaxy)}&rx=${region.region_x}&ry=${region.region_y}&rz=${region.region_z}`,
    })
    selectRegion(region)
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-semibold">Regions in {galaxy}</h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
            {totalRegions.toLocaleString()} regions · <span style={{ color: 'var(--app-primary)' }}>{sorted.length} shown</span>
            {totalPages > 1 && ` · Page ${page} of ${totalPages}`}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs flex-wrap">
          <CompareToggleButton targetLevel="region" />
          <span style={{ color: 'var(--muted)' }}>View:</span>
          <button
            type="button"
            onClick={() => setView('cards')}
            className={view === 'cards' ? 'px-2.5 py-1 rounded text-xs font-medium' : 'px-2.5 py-1 rounded text-xs haven-btn-ghost'}
            style={view === 'cards' ? { background: 'var(--app-primary-dim)', color: 'var(--app-primary)', border: '1px solid rgba(0, 194, 179, 0.3)' } : undefined}
          >
            Cards
          </button>
          <button
            type="button"
            onClick={() => setView('table')}
            className={view === 'table' ? 'px-2.5 py-1 rounded text-xs font-medium' : 'px-2.5 py-1 rounded text-xs haven-btn-ghost'}
            style={view === 'table' ? { background: 'var(--app-primary-dim)', color: 'var(--app-primary)', border: '1px solid rgba(0, 194, 179, 0.3)' } : undefined}
          >
            Table
          </button>
          <span style={{ color: 'var(--muted)' }} className="ml-2">Sort:</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)} className="haven-input text-xs py-1 px-2">
            {Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </div>
      </div>

      {loading ? (
        <LoadingSkeleton variant="region" count={6} />
      ) : sorted.length === 0 ? (
        <EmptyState
          variant="region"
          title="No regions match these filters"
          message="Filters may be too narrow for this galaxy. Adjust filters or expand scope."
          actionLabel={activeFilterCount > 0 ? 'Clear all filters' : undefined}
          onAction={activeFilterCount > 0 ? clearFilters : undefined}
        />
      ) : view === 'cards' ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {paged.map((r) => {
              const k = regionKey(r, reality, galaxy)
              return <RegionCard key={k} r={r} onClick={() => handleClick(r)} pinned={pinnedKeys.has(k)} pinning={pinning} reality={reality} galaxy={galaxy} />
            })}
          </div>
          {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPage={setPage} />}
        </>
      ) : (
        <RegionTable rows={sorted} onSelect={handleClick} />
      )}
    </section>
  )
}

function RegionCard({ r, onClick, pinned, pinning, reality, galaxy }) {
  const stateCls = cardStateClass(r)
  const badge = stateBadge(r)
  const named = !!r.custom_name
  // Live region_thumb poster — see Haven-UI/src/posters/RegionThumb.jsx.
  // Cache key is `rx_ry_rz`; galaxy + reality go in the query string so the
  // SPA poster route can render with the right scope. Threshold-based
  // invalidation handles refresh on growth (10+ new systems).
  const posterKey = `${r.region_x}_${r.region_y}_${r.region_z}`
  const posterUrl = `/api/posters/region_thumb/${posterKey}.png?galaxy=${encodeURIComponent(galaxy || 'Euclid')}&reality=${encodeURIComponent(reality || 'Normal')}`
  return (
    <button
      type="button"
      onClick={onClick}
      className={`haven-card haven-card-hover overflow-hidden p-0 text-left relative ${stateCls}`.trim()}
      style={pinned ? { outline: '2px solid var(--app-primary)', outlineOffset: '-2px' } : undefined}
      aria-pressed={pinning ? pinned : undefined}
    >
      {hasOutdatedDot(r) && <span className="outdated-dot" />}
      {hasConflictDot(r) && <span className="conflict-dot" />}
      {badge && <span className={`state-badge ${badge.kind}`}>{badge.label}</span>}
      {pinning && pinned && (
        <span className="absolute top-2 left-2 z-20 pill-teal-solid text-[10px] mono px-1.5 py-0.5 rounded">PINNED</span>
      )}

      <div className="aspect-[2/1] relative overflow-hidden" style={{ background: 'linear-gradient(135deg, #0f1538, var(--app-bg))' }}>
        <img
          src={posterUrl}
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
          loading="lazy"
          onError={(e) => { e.currentTarget.style.display = 'none' }}
        />
        <div className="absolute inset-0" style={{ background: 'linear-gradient(135deg, rgba(157, 78, 221, 0.10), transparent)' }} />
        <div className="absolute top-3 left-3 z-10">
          <span
            className={`pill backdrop-blur ${named ? 'pill-purple' : 'pill-muted'}`}
            style={named ? { background: 'rgba(157, 78, 221, 0.4)', color: 'white' } : undefined}
          >
            {named ? 'Named' : 'Unnamed'}
          </span>
        </div>
      </div>
      <div className="p-4">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold truncate" style={!named ? { color: 'var(--muted)' } : undefined}>
              {r.display_name}
            </h3>
            <p className="mono text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>
              {r.region_x} · {r.region_y} · {r.region_z}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 pt-3" style={{ borderTop: '1px solid var(--border-soft)' }}>
          <Stat value={r.system_count} label="systems" />
          <Stat value={r.grade_s_count} label="grade S" emphasis="grade-s" />
          <Stat value={r.contributor_count} label="contributors" emphasis="primary" />
        </div>
      </div>
    </button>
  )
}

function Stat({ value, label, emphasis }) {
  const cls = emphasis === 'grade-s' ? 'text-base font-bold grade-s' : 'text-base font-bold'
  const style = emphasis === 'primary' ? { color: 'var(--app-primary)' } : undefined
  return (
    <div>
      <div className={cls} style={style}>{value != null ? value : '—'}</div>
      <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>{label}</div>
    </div>
  )
}

function RegionTable({ rows, onSelect }) {
  return (
    <div className="haven-card overflow-hidden p-0">
      <div className="px-3 py-1.5 flex items-center justify-between text-[10px] mono" style={{ background: 'rgba(0,0,0,0.3)', color: 'var(--muted)', borderBottom: '1px solid var(--border-soft)' }}>
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--app-primary)' }} />
          Showing {rows.length} regions
        </span>
      </div>
      <div className="overflow-x-auto scrollbar-thin">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: 'rgba(0,0,0,0.25)', borderBottom: '1px solid var(--border-soft)' }}>
              <Th>Region</Th>
              <Th>Coordinates</Th>
              <Th right>Systems</Th>
              <Th>Status</Th>
              <th className="px-2 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                // OK to key on coords alone here — RegionTable always
                // renders one (reality, galaxy) context at a time, so the
                // coord triple is unique within `rows`. Adding reality/
                // galaxy here would require threading them through props.
                key={`${r.region_x},${r.region_y},${r.region_z}`}
                onClick={() => onSelect(r)}
                className="cursor-pointer hover:bg-white/5 transition-colors"
                style={{ borderBottom: '1px solid var(--border-soft)' }}
              >
                <td className="px-4 py-2.5 font-medium" style={!r.custom_name ? { color: 'var(--muted)' } : undefined}>
                  {r.display_name}
                </td>
                <td className="px-3 py-2.5 mono text-xs" style={{ color: 'var(--muted)' }}>
                  {r.region_x} · {r.region_y} · {r.region_z}
                </td>
                <td className="px-3 py-2.5 text-right font-bold">{r.system_count}</td>
                <td className="px-3 py-2.5">
                  <span className={`pill ${r.custom_name ? 'pill-purple' : 'pill-muted'} text-[10px]`}>
                    {r.custom_name ? 'Named' : 'Unnamed'}
                  </span>
                </td>
                <td className="px-2 py-2.5">
                  <svg className="w-4 h-4" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Th({ children, right }) {
  return (
    <th
      className={`${right ? 'text-right' : 'text-left'} px-3 py-2.5 text-[10px] uppercase tracking-wider font-semibold`}
      style={{ color: 'var(--muted)' }}
    >
      {children}
    </th>
  )
}

function Pagination({ page, totalPages, onPage }) {
  const buttons = useMemo(() => {
    // Show 1, …, current-1, current, current+1, …, totalPages — capped reasonably
    const out = new Set([1, totalPages, page - 1, page, page + 1])
    const arr = [...out].filter((p) => p >= 1 && p <= totalPages).sort((a, b) => a - b)
    return arr
  }, [page, totalPages])

  return (
    <div className="flex items-center justify-center gap-1 pt-2">
      <button onClick={() => onPage(Math.max(1, page - 1))} disabled={page <= 1} className="px-3 py-1.5 rounded haven-btn-ghost text-sm disabled:opacity-40">←</button>
      {buttons.map((p, i) => (
        <React.Fragment key={p}>
          {i > 0 && buttons[i - 1] !== p - 1 && <span className="px-1 text-xs" style={{ color: 'var(--muted)' }}>…</span>}
          <button
            onClick={() => onPage(p)}
            className={`px-3 py-1.5 rounded text-sm ${p === page ? 'haven-btn-primary' : 'haven-btn-ghost'}`}
          >
            {p}
          </button>
        </React.Fragment>
      ))}
      <button onClick={() => onPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages} className="px-3 py-1.5 rounded haven-btn-ghost text-sm disabled:opacity-40">→</button>
    </div>
  )
}
