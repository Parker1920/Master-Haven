/**
 * SearchOverlay — Systems Tab v2.0 unified search.
 *
 * v1.66.0 rebuild: hits the new /api/search categorized endpoint and renders
 * four sections (Communities, Regions, Contributors, Systems) instead of a
 * flat systems-only popover. Active filters from SystemsContext are passed
 * through so filter+search compose (AND) — searching "indium" inside a
 * biome=Lush filter only surfaces Lush+indium results.
 *
 * The query string is URL-synced via `SystemsContext.q`, so refresh / share
 * / Back button all work. Local `input` state is debounced 300ms before being
 * committed to the URL to avoid spamming history entries during typing.
 *
 * Keyboard:
 *   - `/` anywhere focuses the input
 *   - `↑` / `↓` walk through results across all categories
 *   - `Enter` activates the highlighted row (or first row if none)
 *   - `Esc` closes the popover
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import useDebounce from '../hooks/useDebounce'
import { useSystems } from '../contexts/SystemsContext'
import useFilters from '../hooks/useFilters'

const SCOPE_LABELS = {
  all: 'All Realities',
  galaxy: 'This Galaxy',
  region: 'This Region',
}

const POPOVER_PER_CATEGORY = 6

export default function SearchOverlay() {
  const navigate = useNavigate()
  const {
    scope, setScope, reality, galaxy, region,
    q, setQ,
    openDropdown, toggleDropdown, closeDropdowns,
    pushRecentlyViewed, selectGalaxy, selectRegion, selectReality,
  } = useSystems()
  const { apiParams } = useFilters()

  // Local input mirrors URL `q`; user typing updates local immediately, then
  // a 300ms debounce commits back to URL state. Reading URL → local on mount
  // means a shared/refreshed link with ?q=... pre-fills the input.
  const [input, setInput] = useState(q)
  useEffect(() => { setInput(q) }, [q])
  const debouncedInput = useDebounce(input, 300)
  useEffect(() => {
    if (debouncedInput !== q) setQ(debouncedInput)
  }, [debouncedInput, q, setQ])

  const [data, setData] = useState(null)
  const [isSearching, setIsSearching] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef(null)
  const popoverRef = useRef(null)

  const isOpen = openDropdown === 'search'

  // Focus input on `/`
  useEffect(() => {
    function onKey(e) {
      if (e.key !== '/') return
      const t = e.target
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      e.preventDefault()
      inputRef.current?.focus()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Fire the categorized search whenever the debounced query, scope, or
  // active filters change. Filters compose via ...apiParams so the popover
  // results always respect the same constraints the level grid is showing.
  useEffect(() => {
    const trimmed = (input || '').trim()
    if (trimmed.length < 2) {
      setData(null)
      return
    }
    setIsSearching(true)
    const params = { q: trimmed, limit: POPOVER_PER_CATEGORY }
    if (scope === 'galaxy' && galaxy) params.galaxy = galaxy
    if (scope === 'region' && region) {
      params.rx = region.region_x
      params.ry = region.region_y
      params.rz = region.region_z
    }
    if (reality) params.reality = reality
    // Compose filters into the search request
    Object.assign(params, apiParams)
    axios.get('/api/search', { params })
      .then((r) => setData(r.data || null))
      .catch(() => setData(null))
      .finally(() => setIsSearching(false))
  }, [input, scope, reality, galaxy, region, JSON.stringify(apiParams)])

  const showPopover = isOpen && (input || '').trim().length >= 2

  // Flatten results across categories into a single ordered list for
  // keyboard nav. Order matches visual order in the popover.
  const flatRows = useMemo(() => {
    if (!data) return []
    const out = []
    for (const c of data.communities || []) out.push({ kind: 'community', row: c })
    for (const r of data.regions || []) out.push({ kind: 'region', row: r })
    for (const c of data.contributors || []) out.push({ kind: 'contributor', row: c })
    for (const s of data.systems || []) out.push({ kind: 'system', row: s })
    return out
  }, [data])

  useEffect(() => { setActiveIndex(0) }, [input, data])

  function activateRow(entry) {
    if (!entry) return
    const { kind, row } = entry
    closeDropdowns()
    if (kind === 'community') {
      pushRecentlyViewed({ type: 'community', name: row.display_name, href: `/community-stats/${encodeURIComponent(row.tag)}` })
      navigate(`/community-stats/${encodeURIComponent(row.tag)}`)
      return
    }
    if (kind === 'region') {
      // Switching reality/galaxy here keeps the breadcrumb truthful; otherwise
      // a region in Hilbert clicked from Euclid scope would look mis-placed.
      if (row.reality && row.reality !== reality) selectReality(row.reality)
      if (row.galaxy && row.galaxy !== galaxy) selectGalaxy(row.galaxy)
      selectRegion({
        region_x: row.region_x,
        region_y: row.region_y,
        region_z: row.region_z,
        display_name: row.custom_name,
      })
      pushRecentlyViewed({ type: 'region', name: row.custom_name, href: window.location.pathname + window.location.search })
      return
    }
    if (kind === 'contributor') {
      // No dedicated /profile/<username> route exists for arbitrary users
      // (only /profile for the logged-in user) — route to the contributor
      // search-results page filtered to their username.
      const name = row.username || ''
      pushRecentlyViewed({ type: 'contributor', name, href: `/search?q=${encodeURIComponent(name)}` })
      navigate(`/search?q=${encodeURIComponent(name)}`)
      return
    }
    if (kind === 'system') {
      // Navigate by id, not name — NMS system names repeat, and a name URL would
      // hit the 300 disambiguation picker even though the user picked one row.
      pushRecentlyViewed({ type: 'system', name: row.name, href: `/systems/${encodeURIComponent(row.id)}` })
      navigate(`/systems/${encodeURIComponent(row.id)}`)
    }
  }

  function handleFocus() {
    if ((input || '').trim().length >= 2 && openDropdown !== 'search') toggleDropdown('search')
  }

  function handleChange(e) {
    const v = e.target.value
    setInput(v)
    if (v.trim().length >= 2 && openDropdown !== 'search') toggleDropdown('search')
    else if (v.trim().length < 2 && openDropdown === 'search') closeDropdowns()
  }

  function handleClear() {
    setInput('')
    setQ('')
    closeDropdowns()
    inputRef.current?.focus()
  }

  function handleKeyDown(e) {
    if (!showPopover) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(flatRows.length - 1, i + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(0, i - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      activateRow(flatRows[activeIndex] || flatRows[0])
    } else if (e.key === 'Escape') {
      closeDropdowns()
    }
  }

  const galaxyScopeDisabled = !galaxy
  const regionScopeDisabled = !region
  const totals = data?.totals || {}
  const grandTotal = (totals.communities || 0) + (totals.regions || 0) + (totals.contributors || 0) + (totals.systems || 0)
  const parsedKind = data?.parsed_kind

  return (
    <div className="space-y-3">
      {/* Search input row */}
      <div className="flex flex-col lg:flex-row lg:items-center gap-2">
        <div className="flex-1 relative">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
            style={{ color: 'var(--muted)' }}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            placeholder="Search systems, communities, members, regions, or paste a glyph code..."
            className="haven-input w-full pl-9 pr-16 py-2.5 text-sm"
            value={input}
            onChange={handleChange}
            onFocus={handleFocus}
            onKeyDown={handleKeyDown}
          />
          {input && (
            <button
              type="button"
              onClick={handleClear}
              className="absolute right-9 top-1/2 -translate-y-1/2 opacity-60 hover:opacity-100"
              title="Clear search"
              aria-label="Clear search"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
          <kbd
            className="hidden lg:block absolute right-3 top-1/2 -translate-y-1/2 mono text-[10px] px-1.5 py-0.5 rounded"
            style={{ border: '1px solid var(--border-soft)', color: 'var(--muted)' }}
          >
            /
          </kbd>

          {showPopover && (
            <div
              ref={popoverRef}
              className="absolute left-0 right-0 top-full mt-2 haven-card overflow-hidden z-30 p-0"
              role="listbox"
            >
              <div
                className="px-3 py-2 flex items-center justify-between"
                style={{ borderBottom: '1px solid var(--border-soft)' }}
              >
                <span className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--muted)' }}>
                  {grandTotal} results · scope: <span style={{ color: 'var(--app-primary)' }}>{SCOPE_LABELS[scope]}</span>
                  {parsedKind && parsedKind !== 'free' && (
                    <span className="ml-1.5 mono text-[9px] px-1 py-0.5 rounded" style={{ color: 'var(--app-accent-2)', border: '1px solid var(--border-soft)' }}>
                      {parsedKind === 'nmsportal' ? 'NMSPortals link' : parsedKind === 'glyph_full' ? 'glyph' : 'glyph suffix'}
                    </span>
                  )}
                </span>
                <button onClick={closeDropdowns} className="text-[10px]" style={{ color: 'var(--muted)' }}>Esc</button>
              </div>
              <div className="max-h-[480px] overflow-y-auto scrollbar-thin">
                {isSearching && !data ? (
                  <div className="px-3 py-6 text-center text-xs" style={{ color: 'var(--muted)' }}>Searching…</div>
                ) : grandTotal === 0 ? (
                  <div className="px-3 py-6 text-center text-xs" style={{ color: 'var(--muted)' }}>
                    No matches in scope
                  </div>
                ) : (
                  <CategorizedResults
                    data={data}
                    flatRows={flatRows}
                    activeIndex={activeIndex}
                    onActivate={activateRow}
                    onHoverIndex={setActiveIndex}
                  />
                )}
              </div>
              <div
                className="px-3 py-2 text-[10px] flex items-center justify-between"
                style={{ color: 'var(--muted)', borderTop: '1px solid var(--border-soft)', background: 'rgba(0,0,0,0.2)' }}
              >
                <span>↑↓ navigate · ↵ open · Esc close</span>
                {grandTotal > flatRows.length || (totals.systems || 0) > POPOVER_PER_CATEGORY ? (
                  <button
                    type="button"
                    onClick={() => { closeDropdowns(); navigate(`/search?q=${encodeURIComponent(input.trim())}`) }}
                    className="font-medium"
                    style={{ color: 'var(--app-primary)' }}
                  >
                    View all results →
                  </button>
                ) : null}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Scope chips */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[10px] uppercase tracking-wider font-semibold mr-0.5" style={{ color: 'var(--muted)' }}>
          Scope:
        </span>
        <ScopeChip label="All Realities" active={scope === 'all'} onClick={() => setScope('all')} />
        <ScopeChip
          label="This Galaxy"
          active={scope === 'galaxy'}
          disabled={galaxyScopeDisabled}
          onClick={() => !galaxyScopeDisabled && setScope('galaxy')}
        />
        <ScopeChip
          label="This Region"
          active={scope === 'region'}
          disabled={regionScopeDisabled}
          onClick={() => !regionScopeDisabled && setScope('region')}
        />
      </div>
    </div>
  )
}

// v1.68.0 — derive the matching map URL per search result. Mirrors the
// row click destinations but routes to the static map pages instead of
// the React Systems/Profile pages. Each carries a ?focus= that the
// corresponding map page reads to auto-pan + pulse the entity.
function buildMapHref(kind, row) {
  if (kind === 'system') {
    return `/map/system/${encodeURIComponent(row.id)}?focus=system:${encodeURIComponent(row.id)}`
  }
  if (kind === 'region') {
    return `/map/region?rx=${row.region_x}&ry=${row.region_y}&rz=${row.region_z}`
  }
  if (kind === 'community') {
    return `/map/latest?focus=civ:${encodeURIComponent(row.tag)}`
  }
  if (kind === 'contributor') {
    return `/map/latest?focus=user:${encodeURIComponent(row.username || '')}`
  }
  return null
}

function CategorizedResults({ data, flatRows, activeIndex, onActivate, onHoverIndex }) {
  // Walks the same ordering used in flatRows so activeIndex aligns with what
  // gets highlighted. Each section header is non-interactive — only result
  // rows participate in keyboard nav.
  let cursor = 0
  const sections = []

  function pushSection(kind, label, rows, renderRow) {
    if (!rows || rows.length === 0) return
    const startIdx = cursor
    cursor += rows.length
    sections.push(
      <Section key={kind} label={label} count={rows.length}>
        {rows.map((row, i) => {
          const idx = startIdx + i
          return (
            <SearchRow
              key={`${kind}-${i}`}
              active={idx === activeIndex}
              onClick={() => onActivate({ kind, row })}
              onMouseEnter={() => onHoverIndex(idx)}
              mapHref={buildMapHref(kind, row)}
            >
              {renderRow(row)}
            </SearchRow>
          )
        })}
      </Section>
    )
  }

  pushSection('community', '🌐 Communities', data.communities, (c) => (
    <>
      <div className="min-w-0">
        <div className="text-sm truncate">{c.display_name}</div>
        <div className="text-[11px] mono truncate" style={{ color: 'var(--muted)' }}>
          {c.tag}{c.unregistered ? ' · unregistered' : ''}
        </div>
      </div>
      <span className="text-[11px] mono shrink-0" style={{ color: 'var(--muted)' }}>{c.system_count || 0} systems</span>
    </>
  ))
  pushSection('region', '🗺️ Regions', data.regions, (r) => (
    <>
      <div className="min-w-0">
        <div className="text-sm truncate">{r.custom_name || `(${r.region_x}, ${r.region_y}, ${r.region_z})`}</div>
        <div className="text-[11px] mono truncate" style={{ color: 'var(--muted)' }}>
          {r.galaxy || 'Euclid'} · {r.region_x},{r.region_y},{r.region_z}
        </div>
      </div>
      <span className="text-[11px] mono shrink-0" style={{ color: 'var(--muted)' }}>{r.system_count || 0} systems</span>
    </>
  ))
  pushSection('contributor', '👤 Contributors', data.contributors, (c) => (
    <>
      <div className="min-w-0">
        <div className="text-sm truncate">{c.username || '—'}</div>
        <div className="text-[11px] mono truncate" style={{ color: 'var(--muted)' }}>
          {c.source === 'anonymous' ? 'unregistered' : 'registered profile'}
        </div>
      </div>
      <span className="text-[11px] mono shrink-0" style={{ color: 'var(--muted)' }}>{c.system_count || 0} systems</span>
    </>
  ))
  pushSection('system', '⭐ Systems', data.systems, (s) => (
    <>
      <div className="min-w-0">
        <div className="text-sm truncate">{s.name}</div>
        <div className="text-[11px] mono truncate" style={{ color: 'var(--muted)' }}>
          {s.glyph_code || `(${s.region_x}, ${s.region_y}, ${s.region_z})`}
          {s.galaxy ? ` · ${s.galaxy}` : ''}
          {s.region_name ? ` · ${s.region_name}` : ''}
          {s.match_reason && s.match_reason.kind !== 'glyph' && (
            <span className="ml-1.5" style={{ color: 'var(--app-accent-2)' }}>
              · {s.match_reason.kind}: {s.match_reason.snippet}
            </span>
          )}
        </div>
      </div>
      {s.star_type && (
        <span className={`pill pill-star-${(s.star_type || '').toLowerCase()} text-[10px] shrink-0`}>
          {s.star_type}
        </span>
      )}
    </>
  ))

  return <div>{sections}</div>
}

function Section({ label, count, children }) {
  return (
    <div>
      <div
        className="px-3 py-1.5 text-[10px] uppercase tracking-wider font-semibold flex items-center justify-between"
        style={{ background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid var(--border-soft)', color: 'var(--muted)' }}
      >
        <span>{label}</span>
        <span className="mono text-[10px]" style={{ color: 'var(--app-primary)' }}>{count}</span>
      </div>
      <div>{children}</div>
    </div>
  )
}

function SearchRow({ active, onClick, onMouseEnter, mapHref, children }) {
  // v1.68.0 — refactored from a single <button> to a flex container with
  // two clickable regions: the row body (activates the React destination)
  // and a small map-icon button on the right (opens the corresponding
  // map page focused on the entity). Map button stops propagation so
  // clicking it doesn't also fire the row's onClick.
  return (
    <div
      onMouseEnter={onMouseEnter}
      className={`w-full flex items-stretch ${active ? '' : 'saved-row'}`}
      style={{
        borderBottom: '1px solid var(--border-soft)',
        background: active ? 'var(--app-primary-dim)' : undefined,
      }}
    >
      <button
        type="button"
        onClick={onClick}
        className="flex-1 text-left px-3 py-2 flex items-center justify-between gap-3 min-w-0"
        style={{ background: 'transparent' }}
      >
        {children}
      </button>
      {mapHref && (
        <a
          href={mapHref}
          onClick={(e) => e.stopPropagation()}
          title="Open on map"
          aria-label="Open on map"
          className="flex items-center justify-center px-3 shrink-0 hover:bg-white/5 transition-colors"
          style={{
            borderLeft: '1px solid var(--border-soft)',
            color: 'var(--app-primary)',
            textDecoration: 'none',
          }}
        >
          <span style={{ fontSize: '16px', lineHeight: 1 }}>🗺</span>
        </a>
      )}
    </div>
  )
}

function ScopeChip({ label, active, disabled, onClick }) {
  const cls = `pill pill-clickable ${active ? 'pill-teal' : 'pill-muted'} ${disabled ? 'disabled' : ''}`
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={cls}>
      {label}
    </button>
  )
}
