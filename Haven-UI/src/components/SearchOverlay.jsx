/**
 * SearchOverlay — unified search input + scope chips + live results popover.
 *
 * Phase 3 wires the input + scope chips + popover shell. The result list is
 * intentionally minimal (top 8 + "View all" link); Phase 4's filter engine
 * is what scopes results across the four levels. The input is debounced
 * 300ms before hitting /api/systems/search, mirroring the legacy Systems
 * page behavior.
 *
 * Keyboard shortcuts:
 *   - `/` anywhere on the page focuses the input
 *   - Esc closes the popover (delegated through SystemsContext.openDropdown)
 *
 * Out of scope for Phase 3: keyboard arrow nav inside the result list, full
 * "View all results" page. Both land in Phase 4.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import useDebounce from '../hooks/useDebounce'
import { useSystems } from '../contexts/SystemsContext'

const SCOPE_LABELS = {
  all: 'All Realities',
  galaxy: 'This Galaxy',
  region: 'This Region',
}

export default function SearchOverlay() {
  const navigate = useNavigate()
  const { scope, setScope, reality, galaxy, region, openDropdown, toggleDropdown, closeDropdowns, pushRecentlyViewed } = useSystems()
  const [q, setQ] = useState('')
  const debouncedQ = useDebounce(q, 300)
  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [isSearching, setIsSearching] = useState(false)
  const inputRef = useRef(null)

  const isOpen = openDropdown === 'search'

  // Focus the input on `/`
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

  // Run search whenever the debounced query changes. Scope is applied as the
  // appropriate filter param so the backend can narrow without us paginating.
  useEffect(() => {
    const trimmed = debouncedQ.trim()
    if (trimmed.length < 2) {
      setResults([])
      setTotal(0)
      return
    }
    setIsSearching(true)
    const params = { q: trimmed, page: 1, limit: 8 }
    if (scope === 'galaxy' && galaxy) params.galaxy = galaxy
    if (scope === 'region' && region) {
      params.rx = region.region_x
      params.ry = region.region_y
      params.rz = region.region_z
    }
    if (reality) params.reality = reality
    axios.get('/api/systems/search', { params })
      .then((r) => {
        setResults(r.data.results || [])
        setTotal(r.data.total || 0)
      })
      .catch(() => {
        setResults([])
        setTotal(0)
      })
      .finally(() => setIsSearching(false))
  }, [debouncedQ, scope, reality, galaxy, region])

  const showPopover = isOpen && q.trim().length >= 2

  function handleFocus() {
    if (q.trim().length >= 2 && openDropdown !== 'search') toggleDropdown('search')
  }

  function handleChange(e) {
    setQ(e.target.value)
    if (e.target.value.trim().length >= 2 && openDropdown !== 'search') toggleDropdown('search')
    else if (e.target.value.trim().length < 2 && openDropdown === 'search') closeDropdowns()
  }

  function handleResultClick(system) {
    pushRecentlyViewed({
      type: 'system',
      name: system.name,
      href: `/systems/${system.id}`,
    })
    closeDropdowns()
    setQ('')
    navigate(`/systems/${encodeURIComponent(system.id)}`)
  }

  const galaxyScopeDisabled = !galaxy
  const regionScopeDisabled = !region

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
            placeholder="Search by name, glyph code, contributor, or community..."
            className="haven-input w-full pl-9 pr-9 py-2.5 text-sm"
            value={q}
            onChange={handleChange}
            onFocus={handleFocus}
          />
          <kbd
            className="hidden lg:block absolute right-3 top-1/2 -translate-y-1/2 mono text-[10px] px-1.5 py-0.5 rounded"
            style={{ border: '1px solid var(--border-soft)', color: 'var(--muted)' }}
          >
            /
          </kbd>

          {showPopover && (
            <div
              className="absolute left-0 right-0 top-full mt-2 haven-card overflow-hidden z-30 p-0"
              role="listbox"
            >
              <div
                className="px-3 py-2 flex items-center justify-between"
                style={{ borderBottom: '1px solid var(--border-soft)' }}
              >
                <span className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--muted)' }}>
                  {total} results · scope: <span style={{ color: 'var(--app-primary)' }}>{SCOPE_LABELS[scope]}</span>
                </span>
                <button onClick={closeDropdowns} className="text-[10px]" style={{ color: 'var(--muted)' }}>Esc</button>
              </div>
              <div className="max-h-80 overflow-y-auto scrollbar-thin">
                {isSearching && results.length === 0 ? (
                  <div className="px-3 py-6 text-center text-xs" style={{ color: 'var(--muted)' }}>Searching…</div>
                ) : results.length === 0 ? (
                  <div className="px-3 py-6 text-center text-xs" style={{ color: 'var(--muted)' }}>
                    No matches in scope
                  </div>
                ) : (
                  results.map((sys) => (
                    <button
                      key={sys.id}
                      onClick={() => handleResultClick(sys)}
                      className="w-full text-left px-3 py-2 saved-row flex items-center justify-between gap-3"
                      style={{ borderBottom: '1px solid var(--border-soft)' }}
                    >
                      <div className="min-w-0">
                        <div className="text-sm truncate">{sys.name}</div>
                        <div className="text-[11px] mono truncate" style={{ color: 'var(--muted)' }}>
                          {sys.glyph_code ? sys.glyph_code : `(${sys.region_x}, ${sys.region_y}, ${sys.region_z})`}
                          {sys.galaxy ? ` · ${sys.galaxy}` : ''}
                        </div>
                      </div>
                      {sys.star_type && (
                        <span className={`pill pill-star-${(sys.star_type || '').toLowerCase()} text-[10px] shrink-0`}>
                          {sys.star_type}
                        </span>
                      )}
                    </button>
                  ))
                )}
              </div>
              <div
                className="px-3 py-2 text-[10px] flex items-center justify-between"
                style={{ color: 'var(--muted)', borderTop: '1px solid var(--border-soft)', background: 'rgba(0,0,0,0.2)' }}
              >
                <span>↵ open · Esc close</span>
                {total > results.length && (
                  <span className="font-medium" style={{ color: 'var(--app-primary)' }}>
                    {total - results.length} more — refine search
                  </span>
                )}
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

function ScopeChip({ label, active, disabled, onClick }) {
  const cls = `pill pill-clickable ${active ? 'pill-teal' : 'pill-muted'} ${disabled ? 'disabled' : ''}`
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={cls}>
      {label}
    </button>
  )
}
