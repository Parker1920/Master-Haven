/**
 * SystemsList — Level 4 of the Systems v2.0 hierarchy.
 *
 * Fetches /api/systems with the active filters + region scope, renders either
 * a 3:2 poster card grid or a virtual-scroll table (react-window, dep already
 * present in package.json).
 *
 * Grade letter overlay in the top-right of each card comes from the
 * `completeness_grade` field the backend computes on every system. Star
 * color pill in the top-left uses .pill-star-{color}.
 *
 * Per spec section 5.3, the table is virtual-scrolled — useful once a region
 * has hundreds of systems. We render up to `MAX_TABLE_ROWS` (1000) before
 * paginating cards-view to avoid drowning the user in cards.
 */

import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import { FixedSizeList } from 'react-window'
import { useSystems } from '../contexts/SystemsContext'
import useFilters from '../hooks/useFilters'
import LoadingSkeleton from './LoadingSkeleton'
import EmptyState from './EmptyState'
import CompareToggleButton from './CompareToggleButton'
import { cardStateClass, hasOutdatedDot, hasConflictDot, stateBadge } from '../utils/dataStates'
import { GRADE_BADGE_STYLE } from '../utils/gradeColors'

const CARDS_PAGE_SIZE = 24
const TABLE_ROW_HEIGHT = 44

const SORTS = {
  'recent-desc': { label: 'Recently added ↓', param: { sort: 'recent', dir: 'desc' } },
  'grade-desc': { label: 'Grade ↓', param: { sort: 'completeness', dir: 'desc' } },
  'name-asc': { label: 'Name A-Z', param: { sort: 'name', dir: 'asc' } },
}

// Grade badge styling is single-sourced from gradeColors.js (S+ / S / A / B / C).
const GRADE_OVERLAY_STYLE = GRADE_BADGE_STYLE

export default function SystemsList() {
  const { reality, galaxy, region, q, pushRecentlyViewed, clearFilters, compareMode, pinsByLevel, togglePin } = useSystems()
  const { apiParams, activeFilterCount } = useFilters()
  const pinning = compareMode === 'system'
  const pinnedIds = new Set((pinsByLevel.system || []).map((p) => p.id))
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState('cards')
  const [sort, setSort] = useState('recent-desc')
  const [page, setPage] = useState(1)
  // Track the backend's pagination.total so the header shows the real region
  // size even when we hit the fetch cap below.
  const [serverTotal, setServerTotal] = useState(null)
  const navigate = useNavigate()

  // M-S1: bumped from 500 → 2000 since some Euclid regions in production
  // approach the old cap and silently truncated. 2000 covers the densest
  // region we've seen with comfortable headroom. If we hit it, we surface
  // a truncation banner using `serverTotal` so users know there's more.
  const FETCH_CAP = 2000

  // When q is set, the grid uses /api/systems/search (which OR-spans name +
  // glyph + region + community + contributor + co-authors AND ANDs the
  // active filters) so filter+search compose. When q is empty, the grid
  // uses the regular paginated /api/systems endpoint as before.
  const trimmedQ = (q || '').trim()
  const useSearchMode = trimmedQ.length >= 2

  useEffect(() => {
    if (!region) return
    let cancelled = false
    setLoading(true)
    setServerTotal(null)

    if (useSearchMode) {
      // /api/systems/search response is `{results, total, ...}`. The grid
      // expects a `systems` field, so we normalize the shape on read.
      const params = {
        q: trimmedQ,
        reality, galaxy,
        rx: region.region_x, ry: region.region_y, rz: region.region_z,
        ...apiParams,
        limit: 50,
        page,
      }
      axios.get('/api/systems/search', { params })
        .then((r) => {
          if (cancelled) return
          const data = r.data || {}
          setRows(data.results || [])
          setServerTotal(typeof data.total === 'number' ? data.total : null)
        })
        .catch(() => { if (!cancelled) { setRows([]); setServerTotal(null) } })
        .finally(() => { if (!cancelled) setLoading(false) })
    } else {
      axios.get('/api/systems', {
        params: {
          reality, galaxy,
          region_x: region.region_x, region_y: region.region_y, region_z: region.region_z,
          ...apiParams,
          limit: FETCH_CAP,
        },
      })
        .then((r) => {
          if (cancelled) return
          const data = r.data || {}
          setRows(data.systems || data || [])
          const t = data?.pagination?.total
          setServerTotal(typeof t === 'number' ? t : null)
        })
        .catch(() => { if (!cancelled) { setRows([]); setServerTotal(null) } })
        .finally(() => { if (!cancelled) setLoading(false) })
    }
    return () => { cancelled = true }
  }, [reality, galaxy, region?.region_x, region?.region_y, region?.region_z, useSearchMode, trimmedQ, page, JSON.stringify(apiParams)])

  useEffect(() => { setPage(1) }, [region, sort, view, trimmedQ, JSON.stringify(apiParams)])

  const sorted = useMemo(() => {
    const list = [...rows]
    if (sort === 'name-asc') list.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
    else if (sort === 'grade-desc') list.sort((a, b) => (b.completeness_score || 0) - (a.completeness_score || 0))
    else list.sort((a, b) => (new Date(b.created_at || 0)) - (new Date(a.created_at || 0)))
    return list
  }, [rows, sort])

  function handleClick(sys) {
    if (pinning) {
      togglePin('system', {
        id: sys.id,
        key: String(sys.id),
        label: sys.name,
        payload: sys,
      })
      return
    }
    // Navigate by id, not name — names repeat across systems, so a name URL
    // would re-trigger the disambiguation picker on a card the user already picked.
    pushRecentlyViewed({ type: 'system', name: sys.name, href: `/systems/${encodeURIComponent(sys.id)}` })
    navigate(`/systems/${encodeURIComponent(sys.id)}`)
  }

  const total = sorted.length
  const totalPages = Math.max(1, Math.ceil(total / CARDS_PAGE_SIZE))
  const paged = useMemo(() => {
    const start = (page - 1) * CARDS_PAGE_SIZE
    return sorted.slice(start, start + CARDS_PAGE_SIZE)
  }, [sorted, page])

  const regionName = region?.display_name || `(${region?.region_x ?? '?'}, ${region?.region_y ?? '?'}, ${region?.region_z ?? '?'})`

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-semibold">Systems in {regionName}</h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
            {/* Prefer server-side total — when we truncated, `total` (the
                local sorted length) is less than the real count.  */}
            {(serverTotal ?? total).toLocaleString()} systems
            {serverTotal != null && serverTotal > rows.length && (
              <span style={{ color: 'var(--app-accent-amber)' }}>
                {' '}(showing first {rows.length.toLocaleString()}; refine filters to see more)
              </span>
            )}
            {activeFilterCount > 0 && <span style={{ color: 'var(--app-primary)' }}> · filtered</span>}
            {view === 'cards' && totalPages > 1 && ` · Page ${page} of ${totalPages}`}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs flex-wrap">
          <CompareToggleButton targetLevel="system" />
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
        <LoadingSkeleton variant="system" count={8} />
      ) : sorted.length === 0 ? (
        <EmptyState
          variant="system"
          title="No systems match these filters"
          message="No system in this region matches your criteria. Try widening filters or jump up to galaxy scope."
          actionLabel={activeFilterCount > 0 ? 'Clear all filters' : undefined}
          onAction={activeFilterCount > 0 ? clearFilters : undefined}
        />
      ) : view === 'cards' ? (
        <>
          {/* Grid caps at 3 columns on PC (was xl:grid-cols-4). Parker
              2026-05-11: at 4-up the system_thumb poster squashed to
              ~250 px wide which made the 6 stat tiles unreadable.
              Mobile breakpoints unchanged. */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {paged.map((s) => <SystemCard key={s.id} s={s} onClick={() => handleClick(s)} pinned={pinnedIds.has(s.id)} pinning={pinning} />)}
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-1 pt-2">
              <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1} className="px-3 py-1.5 rounded haven-btn-ghost text-sm disabled:opacity-40">←</button>
              <span className="text-xs mono px-3" style={{ color: 'var(--muted)' }}>{page} / {totalPages}</span>
              <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages} className="px-3 py-1.5 rounded haven-btn-ghost text-sm disabled:opacity-40">→</button>
            </div>
          )}
        </>
      ) : (
        <SystemTable rows={sorted} onSelect={handleClick} />
      )}
    </section>
  )
}

// Whitelist of star type values that have a corresponding `.pill-star-*` CSS
// class. Legacy DB rows have `Unknown(N)` / `White` / NULL etc. which would
// generate invalid CSS class names like `pill-star-unknown(7)`; map those to
// a neutral fallback.
const KNOWN_STAR_PILLS = new Set(['yellow', 'red', 'green', 'blue', 'purple'])

function SystemCard({ s, onClick, pinned, pinning }) {
  const stateCls = cardStateClass(s)
  const badge = stateBadge(s)
  const gradeStyle = GRADE_OVERLAY_STYLE[s.completeness_grade] || GRADE_OVERLAY_STYLE.C
  const rawStar = (s.star_type || 'yellow').toLowerCase()
  const starCls = KNOWN_STAR_PILLS.has(rawStar) ? `pill-star-${rawStar}` : 'pill-muted'
  const planetCount = s.planet_count ?? 0
  const moonCount = s.moon_count ?? 0

  return (
    <button
      type="button"
      onClick={onClick}
      className={`haven-card haven-card-hover overflow-hidden p-0 text-left relative ${stateCls}`.trim()}
      style={pinned ? { outline: '2px solid var(--app-primary)', outlineOffset: '-2px' } : undefined}
      aria-pressed={pinning ? pinned : undefined}
    >
      {hasOutdatedDot(s) && <span className="outdated-dot" />}
      {hasConflictDot(s) && <span className="conflict-dot" />}
      {badge && <span className={`state-badge ${badge.kind}`}>{badge.label}</span>}
      {pinning && pinned && (
        <span className="absolute top-2 left-2 z-20 pill-teal-solid text-[10px] mono px-1.5 py-0.5 rounded">PINNED</span>
      )}

      <div className="aspect-[3/2] relative overflow-hidden" style={{ background: 'linear-gradient(135deg, #0f1538, var(--app-bg))' }}>
        {/* Live-rendered system_thumb poster — first view triggers headless
            render (lazy). New systems get pre-rendered on approval, so the
            common path is instant. Errors fall back to the stub gradient. */}
        <img
          src={`/api/posters/system_thumb/${encodeURIComponent(s.id)}.png`}
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
          loading="lazy"
          onError={(e) => { e.currentTarget.style.display = 'none' }}
        />
        <div className="absolute inset-0" style={{ background: 'linear-gradient(135deg, rgba(0, 194, 179, 0.06), transparent)' }} />
        <div className="absolute top-3 left-3 z-10">
          {s.star_type && (
            <span className={`pill ${starCls}`}>
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="10" r="6"/></svg>
              {s.star_type}
            </span>
          )}
        </div>
        <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5">
          {s.is_stub && (
            <span
              className="pill text-[10px] font-bold"
              style={{ background: 'rgba(250,204,21,0.25)', color: '#facc15', border: '1px solid rgba(250,204,21,0.5)' }}
              title="Placeholder system — needs full data"
            >
              STUB
            </span>
          )}
          {s.completeness_grade && (
            <span className="w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold mono" style={gradeStyle}>
              {s.completeness_grade}
            </span>
          )}
        </div>
        {s.glyph_code && (
          <div className="absolute bottom-3 left-3 right-3 z-10">
            <span className="mono text-[10px] px-2 py-1 rounded backdrop-blur" style={{ background: 'rgba(0,0,0,0.6)', color: 'rgba(255,255,255,0.85)' }}>
              {s.glyph_code}
            </span>
          </div>
        )}
      </div>

      {/* Card text section — bumped contrast and font sizes per Parker
          (2026-05-11) since the cards felt cramped under the poster. Labels
          stay subtly muted; values are bright white for legibility. */}
      <div className="p-4">
        <div className="flex items-start justify-between mb-3 gap-2">
          <h3 className="text-lg font-semibold truncate flex-1 min-w-0" style={{ color: 'var(--app-text)' }}>{s.name}</h3>
          {s.discord_tag && s.discord_tag !== 'personal' && (
            <span className="pill pill-purple shrink-0 text-[11px]">{s.discord_tag}</span>
          )}
        </div>
        <div className="space-y-2 text-sm mb-3">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" style={{ color: 'rgba(255,255,255,0.5)' }} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 8v8m-4-4h8M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <span style={{ color: 'rgba(255,255,255,0.92)' }}>
              {s.economy_type || '—'}{s.economy_level ? ` / ${s.economy_level}` : ''}
            </span>
            <span className="ml-auto" style={{ color: 'rgba(255,255,255,0.78)' }}>
              {s.conflict_level || '—'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" style={{ color: 'rgba(255,255,255,0.5)' }} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg>
            <span style={{ color: 'rgba(255,255,255,0.92)' }}>
              {planetCount} planet{planetCount === 1 ? '' : 's'}{moonCount ? ` · ${moonCount} moon${moonCount === 1 ? '' : 's'}` : ''}
            </span>
            <span className="ml-auto" style={{ color: 'rgba(255,255,255,0.78)' }}>
              {s.dominant_lifeform || '—'}
            </span>
          </div>
        </div>
        <div className="pt-3 flex items-center justify-between text-[11px]" style={{ borderTop: '1px solid var(--border-soft)', color: 'rgba(255,255,255,0.7)' }}>
          <span className="mono">{s.completeness_score != null ? `${s.completeness_score}% complete` : '—'}</span>
          <span className="truncate ml-2">{s.discovered_by || s.personal_discord_username || '—'}</span>
        </div>
      </div>
    </button>
  )
}

function SystemTable({ rows, onSelect }) {
  const tooBigForCards = rows.length > 200
  return (
    <div className="haven-card overflow-hidden p-0">
      <div className="px-3 py-1.5 flex items-center justify-between text-[10px] mono" style={{ background: 'rgba(0,0,0,0.3)', color: 'var(--muted)', borderBottom: '1px solid var(--border-soft)' }}>
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--app-primary)' }} />
          {tooBigForCards ? 'Virtual scroll enabled — only visible rows render' : `Showing ${rows.length} systems`}
        </span>
      </div>
      <div className="overflow-x-auto scrollbar-thin">
        <table className="w-full text-sm" style={{ minWidth: 720 }}>
          <thead>
            <tr style={{ background: 'rgba(0,0,0,0.25)', borderBottom: '1px solid var(--border-soft)' }}>
              <Th>System</Th>
              <Th>Glyph</Th>
              <Th>Star</Th>
              <Th>Economy</Th>
              <Th>Lifeform</Th>
              <Th right>Planets</Th>
              <Th center>Grade</Th>
              <Th>Discoverer</Th>
              <Th>Tag</Th>
              <th className="px-2 py-2.5" />
            </tr>
          </thead>
        </table>
      </div>
      {tooBigForCards ? (
        <FixedSizeList
          height={Math.min(rows.length * TABLE_ROW_HEIGHT, 600)}
          width="100%"
          itemSize={TABLE_ROW_HEIGHT}
          itemCount={rows.length}
        >
          {({ index, style }) => (
            <div style={style}>
              <SystemRow s={rows[index]} onSelect={onSelect} />
            </div>
          )}
        </FixedSizeList>
      ) : (
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full text-sm" style={{ minWidth: 720 }}>
            <tbody>
              {rows.map((s) => (
                <SystemRow key={s.id} s={s} onSelect={onSelect} asRow />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function SystemRow({ s, onSelect, asRow }) {
  const grade = s.completeness_grade
  const cells = (
    <>
      <td className="px-4 py-2.5 font-medium truncate">{s.name}</td>
      <td className="px-3 py-2.5 mono text-xs" style={{ color: 'var(--muted)' }}>{s.glyph_code || '—'}</td>
      <td className="px-3 py-2.5">
        {s.star_type ? <span className={`pill pill-star-${s.star_type.toLowerCase()} text-[10px] px-2 py-0.5`}>{s.star_type}</span> : '—'}
      </td>
      <td className="px-3 py-2.5"><span>{s.economy_type || '—'}</span>{s.economy_level && <span className="mono text-[10px] ml-1" style={{ color: 'var(--muted)' }}>{s.economy_level}</span>}</td>
      <td className="px-3 py-2.5">{s.dominant_lifeform || '—'}</td>
      <td className="px-3 py-2.5 text-right mono">{s.planet_count ?? 0}{s.moon_count ? ` / ${s.moon_count}m` : ''}</td>
      <td className="px-3 py-2.5 text-center">
        {grade && (
          <span className="w-6 h-6 rounded-md inline-flex items-center justify-center text-xs font-bold mono" style={GRADE_OVERLAY_STYLE[grade] || GRADE_OVERLAY_STYLE.C}>{grade}</span>
        )}
      </td>
      <td className="px-3 py-2.5 text-xs truncate" style={{ color: 'var(--muted)' }}>{s.discovered_by || s.personal_discord_username || '—'}</td>
      <td className="px-3 py-2.5">{s.discord_tag && s.discord_tag !== 'personal' ? <span className="pill pill-purple text-[10px]">{s.discord_tag}</span> : '—'}</td>
      <td className="px-2 py-2.5">
        <svg className="w-4 h-4" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </td>
    </>
  )
  if (asRow) {
    return (
      <tr
        onClick={() => onSelect(s)}
        className="cursor-pointer hover:bg-white/5 transition-colors"
        style={{ borderBottom: '1px solid var(--border-soft)' }}
      >
        {cells}
      </tr>
    )
  }
  // Virtual-scroll path: render as a positioned table row inside an absolutely
  // sized container. react-window expects a flat div, so we wrap as a table.
  return (
    <table className="w-full text-sm" style={{ minWidth: 720, height: TABLE_ROW_HEIGHT }}>
      <tbody>
        <tr
          onClick={() => onSelect(s)}
          className="cursor-pointer hover:bg-white/5 transition-colors"
          style={{ borderBottom: '1px solid var(--border-soft)' }}
        >
          {cells}
        </tr>
      </tbody>
    </table>
  )
}

function Th({ children, right, center }) {
  const align = right ? 'text-right' : center ? 'text-center' : 'text-left'
  return (
    <th className={`${align} px-3 py-2.5 text-[10px] uppercase tracking-wider font-semibold`} style={{ color: 'var(--muted)' }}>
      {children}
    </th>
  )
}
