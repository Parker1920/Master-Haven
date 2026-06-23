/**
 * Systems Tab v2.0 — shared state container.
 *
 * Owns the hierarchy/scope/filter/history state for the redesigned Systems
 * browser. Lives in a context so the new chrome components (URLBar,
 * SearchOverlay, FilterPillsRow, BreadcrumbBar, dropdowns) can read and
 * write without prop-drilling through Systems.jsx.
 *
 * State is INTENTIONALLY kept in a single provider rather than split across
 * smaller contexts — every chrome component reads several pieces of state
 * (e.g., FilterPillsRow needs filters + scope + reality/galaxy), so splitting
 * would just multiply consumer subscriptions without reducing re-renders.
 *
 * URL sync (Phase 3 scope):
 *   - Hierarchy (reality/galaxy/region) is mirrored to the URL query string
 *     via react-router's useSearchParams, matching the existing pattern in
 *     pages/Systems.jsx (legacy).
 *   - The "pretty path-style" URL the user sees in URLBar is a display layer
 *     formatted from this state — not actual navigation. Migrating
 *     window.location.pathname to the production-style form
 *     (`/systems/normal/euclid/sea-of-gidzenuf`) is a Phase 5 polish item
 *     bundled with the SystemDetail rewrite, since it requires reshuffling
 *     `/systems/:id` to avoid a route collision.
 *   - Hash is left untouched (kept clear for future scratch state like
 *     compare-mode pins).
 */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

const SystemsContext = createContext(null)

const SCOPES = ['all', 'galaxy', 'region']

const RECENTLY_VIEWED_KEY = 'haven.systemsv2.recentlyViewed'
const RECENTLY_VIEWED_CAP = 8

// Keys that should be parsed back as arrays from the URL (OR-logic multi).
const FILTER_MULTI_KEYS = ['star_type', 'economy_level', 'conflict_level', 'is_complete', 'resource']
// Keys that are scalar. tri-state has_moons stored as 'true'/'false'.
const FILTER_SCALAR_KEYS = [
  'economy_type', 'dominant_lifeform', 'biome', 'weather', 'sentinel_level',
  'stellar_classification', 'has_moons', 'min_planets', 'max_planets',
]
// Hierarchy keys we must NOT treat as filters.
const HIERARCHY_KEYS = new Set(['reality', 'galaxy', 'rx', 'ry', 'rz', 'rname'])
// Non-filter, non-hierarchy URL keys (currently just the search query).
const RESERVED_KEYS = new Set(['q'])

/**
 * Resolve which level view to render from the current selection state.
 * Returns the grid to show next, not which entity was last clicked.
 *
 *   nothing  → 'reality' (RealitySelector)
 *   reality  → 'galaxy'  (GalaxyGrid filtered to that reality)
 *   galaxy   → 'region'  (RegionBrowser inside that galaxy)
 *   region   → 'system'  (SystemsList inside that region)
 */
function deriveLevel({ reality, galaxy, region }) {
  if (region) return 'system'
  if (galaxy) return 'region'
  if (reality) return 'galaxy'
  return 'reality'
}

/**
 * Format a region tuple as a URL-safe slug for the displayed pretty URL.
 * Prefers the display name (with spaces → dashes) and falls back to the
 * `rx,ry,rz` triple. Pure presentation — does not affect navigation.
 */
function formatRegionSlug(region) {
  if (!region) return null
  if (region.display_name) {
    return region.display_name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
  }
  return `${region.region_x},${region.region_y},${region.region_z}`
}

export function SystemsProvider({ children }) {
  const [searchParams, setSearchParams] = useSearchParams()

  // ---- Hierarchy state, mirrored to ?reality=&galaxy=&rx=&ry=&rz=&rname= ----
  const reality = searchParams.get('reality') || null
  const galaxy = searchParams.get('galaxy') || null
  const region = useMemo(() => {
    const rx = searchParams.get('rx')
    const ry = searchParams.get('ry')
    const rz = searchParams.get('rz')
    if (rx == null || ry == null || rz == null) return null
    return {
      region_x: parseInt(rx, 10),
      region_y: parseInt(ry, 10),
      region_z: parseInt(rz, 10),
      display_name: searchParams.get('rname') || null,
    }
  }, [searchParams])

  const level = deriveLevel({ reality, galaxy, region })

  // ---- Scope chip selection ---------------------------------------------------
  // 'all' = search every reality; 'galaxy' = scope to current galaxy;
  // 'region' = scope to current region. Default follows the deepest selection
  // unless the user has explicitly chosen a different scope this session.
  const [scope, setScopeState] = useState('all')
  const userPickedScope = useRef(false)
  useEffect(() => {
    if (userPickedScope.current) return
    if (region) setScopeState('region')
    else if (galaxy) setScopeState('galaxy')
    else setScopeState('all')
  }, [galaxy, region])

  const setScope = useCallback((next) => {
    if (!SCOPES.includes(next)) return
    userPickedScope.current = true
    setScopeState(next)
  }, [])

  // ---- Search query state (URL-synced via ?q=...) ---------------------------
  // Single source of truth: the URL. Components that need to react to query
  // changes read `q` from this context; the SearchOverlay's local input state
  // is debounced before being committed back here.
  const q = searchParams.get('q') || ''
  const setQ = useCallback((next) => {
    setSearchParams((prev) => {
      const out = new URLSearchParams(prev)
      const trimmed = (next || '').trim()
      if (trimmed) out.set('q', trimmed)
      else out.delete('q')
      return out
    }, { replace: true })
  }, [setSearchParams])

  // ---- Filter state (mirrored to query string for refresh-safe deep links) --
  const filters = useMemo(() => {
    const out = {}
    for (const [k, v] of searchParams.entries()) {
      if (HIERARCHY_KEYS.has(k) || RESERVED_KEYS.has(k)) continue
      if (FILTER_MULTI_KEYS.includes(k)) {
        const parts = v.split(',').map((p) => p.trim()).filter(Boolean)
        if (parts.length) out[k] = parts
      } else if (FILTER_SCALAR_KEYS.includes(k)) {
        if (k === 'has_moons') out[k] = v === 'true'
        else if (k === 'min_planets' || k === 'max_planets') {
          const n = parseInt(v, 10)
          if (!Number.isNaN(n)) out[k] = n
        } else if (v !== '') {
          out[k] = v
        }
      }
    }
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const setFilters = useCallback((next) => {
    setSearchParams((prev) => {
      const out = new URLSearchParams()
      // Preserve hierarchy params + the search query untouched
      for (const k of ['reality', 'galaxy', 'rx', 'ry', 'rz', 'rname', 'q']) {
        const v = prev.get(k)
        if (v != null) out.set(k, v)
      }
      const resolved = typeof next === 'function' ? next(filters) : next
      for (const [k, v] of Object.entries(resolved || {})) {
        if (v == null) continue
        if (Array.isArray(v)) {
          if (v.length) out.set(k, v.join(','))
        } else if (typeof v === 'boolean') {
          out.set(k, v ? 'true' : 'false')
        } else if (typeof v === 'number') {
          out.set(k, String(v))
        } else {
          const s = String(v).trim()
          if (s) out.set(k, s)
        }
      }
      return out
    }, { replace: true })
  }, [setSearchParams, filters])

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter((v) => {
      if (v == null) return false
      if (Array.isArray(v)) return v.length > 0
      if (typeof v === 'object') return Object.keys(v).length > 0
      return v !== '' && v !== false
    }).length,
    [filters]
  )

  const clearFilters = useCallback(() => setFilters({}), [setFilters])
  const removeFilter = useCallback((key) => {
    setFilters((prev) => {
      if (!(key in prev)) return prev
      const next = { ...prev }
      delete next[key]
      return next
    })
  }, [setFilters])

  // ---- Navigation history (browser-style back/forward) -----------------------
  // Hierarchy snapshots only; filter state is intentionally NOT history-tracked
  // (matches typical map/explorer UX — back goes up a level, not "undo filter").
  const [history, setHistory] = useState({ stack: [], cursor: -1 })
  const pushingFromHistory = useRef(false)

  useEffect(() => {
    if (pushingFromHistory.current) {
      pushingFromHistory.current = false
      return
    }
    setHistory((prev) => {
      const snapshot = { reality, galaxy, region }
      const top = prev.stack[prev.cursor]
      if (top && JSON.stringify(top) === JSON.stringify(snapshot)) return prev
      const truncated = prev.stack.slice(0, prev.cursor + 1)
      const nextStack = [...truncated, snapshot].slice(-32) // cap to avoid unbounded growth
      return { stack: nextStack, cursor: nextStack.length - 1 }
    })
  }, [reality, galaxy, region])

  const canGoBack = history.cursor > 0
  const canGoForward = history.cursor < history.stack.length - 1

  // Helper: rebuild URL params with new hierarchy snapshot but preserve any
  // non-hierarchy params (filter state, etc.).
  const writeHierarchy = useCallback((snap, opts = {}) => {
    setSearchParams((prev) => {
      const out = new URLSearchParams()
      // Carry filter params (and search query) forward
      for (const [k, v] of prev.entries()) {
        if (!HIERARCHY_KEYS.has(k)) out.set(k, v)
      }
      if (snap.reality) out.set('reality', snap.reality)
      if (snap.galaxy) out.set('galaxy', snap.galaxy)
      if (snap.region) {
        out.set('rx', String(snap.region.region_x))
        out.set('ry', String(snap.region.region_y))
        out.set('rz', String(snap.region.region_z))
        if (snap.region.display_name) out.set('rname', snap.region.display_name)
      }
      return out
    }, opts)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setSearchParams])

  const applySnapshot = useCallback((snap) => {
    pushingFromHistory.current = true
    writeHierarchy(snap, { replace: true })
  }, [writeHierarchy])

  const navBack = useCallback(() => {
    if (!canGoBack) return
    const nextCursor = history.cursor - 1
    setHistory((prev) => ({ ...prev, cursor: nextCursor }))
    applySnapshot(history.stack[nextCursor])
  }, [canGoBack, history, applySnapshot])

  const navForward = useCallback(() => {
    if (!canGoForward) return
    const nextCursor = history.cursor + 1
    setHistory((prev) => ({ ...prev, cursor: nextCursor }))
    applySnapshot(history.stack[nextCursor])
  }, [canGoForward, history, applySnapshot])

  // Alt+Left / Alt+Right shortcuts per spec section 4.2.
  useEffect(() => {
    function onKey(e) {
      if (!e.altKey) return
      const target = e.target
      // Don't hijack history nav while typing in an input
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return
      if (e.key === 'ArrowLeft') { e.preventDefault(); navBack() }
      if (e.key === 'ArrowRight') { e.preventDefault(); navForward() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navBack, navForward])

  // ---- Hierarchy mutation helpers --------------------------------------------
  // All go through writeHierarchy so filter params survive hierarchy changes.
  const selectReality = useCallback((nextReality) => {
    writeHierarchy({ reality: nextReality, galaxy: null, region: null })
  }, [writeHierarchy])

  const selectGalaxy = useCallback((nextGalaxy) => {
    writeHierarchy({ reality, galaxy: nextGalaxy, region: null })
  }, [reality, writeHierarchy])

  const selectRegion = useCallback((nextRegion) => {
    writeHierarchy({ reality, galaxy, region: nextRegion })
  }, [reality, galaxy, writeHierarchy])

  const goToLevel = useCallback((targetLevel) => {
    if (targetLevel === 'root') {
      writeHierarchy({})
      return
    }
    if (targetLevel === 'reality') {
      writeHierarchy({ reality })
      return
    }
    if (targetLevel === 'galaxy') {
      writeHierarchy({ reality, galaxy })
    }
  }, [reality, galaxy, writeHierarchy])

  // ---- Recently viewed (localStorage, 8 cap) ---------------------------------
  // Per spec section 4.4, this is device-local, NOT profile-backed.
  const [recentlyViewed, setRecentlyViewed] = useState(() => {
    try {
      const raw = localStorage.getItem(RECENTLY_VIEWED_KEY)
      if (!raw) return []
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  })

  const pushRecentlyViewed = useCallback((entry) => {
    // entry: { type: 'galaxy'|'region'|'system', name, href, at }
    if (!entry || !entry.type || !entry.name) return
    setRecentlyViewed((prev) => {
      const key = `${entry.type}:${entry.name}`
      const filtered = prev.filter((e) => `${e.type}:${e.name}` !== key)
      const next = [{ ...entry, at: entry.at || new Date().toISOString() }, ...filtered].slice(0, RECENTLY_VIEWED_CAP)
      try { localStorage.setItem(RECENTLY_VIEWED_KEY, JSON.stringify(next)) } catch {}
      return next
    })
  }, [])

  const clearRecentlyViewed = useCallback(() => {
    setRecentlyViewed([])
    try { localStorage.removeItem(RECENTLY_VIEWED_KEY) } catch {}
  }, [])

  // ---- Compare mode (per-level pin isolation, cap 4) -------------------------
  // Per spec section 7.1, pins are isolated per level — switching levels doesn't
  // lose your pins, and you can only compare items of the same kind.
  // Pin shape: { id, key, label, payload }
  //   id    — unique within a level (galaxy name, region coord-key, system id)
  //   key   — stable React key (the same as id for galaxies/systems; "rx,ry,rz" for regions)
  //   label — what we render in the bar / panel column header
  //   payload — the raw row, so ComparePanel can render columns without re-fetching
  const COMPARE_CAP = 4
  const [compareMode, setCompareMode] = useState(null) // null | 'galaxy' | 'region' | 'system'
  const [pinsByLevel, setPinsByLevel] = useState({ galaxy: [], region: [], system: [] })

  const togglePin = useCallback((targetLevel, pin) => {
    setPinsByLevel((prev) => {
      const cur = prev[targetLevel] || []
      const idx = cur.findIndex((p) => p.id === pin.id)
      let next
      if (idx >= 0) next = cur.filter((p) => p.id !== pin.id)
      else if (cur.length >= COMPARE_CAP) next = cur // silently cap
      else next = [...cur, pin]
      return { ...prev, [targetLevel]: next }
    })
  }, [])

  const clearPins = useCallback((targetLevel) => {
    if (!targetLevel) {
      setPinsByLevel({ galaxy: [], region: [], system: [] })
    } else {
      setPinsByLevel((prev) => ({ ...prev, [targetLevel]: [] }))
    }
  }, [])

  const toggleCompareMode = useCallback((targetLevel) => {
    setCompareMode((cur) => (cur === targetLevel ? null : targetLevel))
  }, [])

  // ---- Dropdown open state (one-at-a-time) -----------------------------------
  const [openDropdown, setOpenDropdown] = useState(null) // 'saved' | 'recent' | 'search' | null
  const toggleDropdown = useCallback((name) => {
    setOpenDropdown((cur) => (cur === name ? null : name))
  }, [])
  const closeDropdowns = useCallback(() => setOpenDropdown(null), [])

  // Esc closes whichever dropdown is open
  useEffect(() => {
    if (!openDropdown) return
    function onKey(e) {
      if (e.key === 'Escape') setOpenDropdown(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openDropdown])

  // ---- Pretty URL formatter (presentation only) ------------------------------
  const prettyPath = useMemo(() => {
    const parts = ['/systems']
    if (reality) parts.push(reality.toLowerCase())
    if (galaxy) parts.push(galaxy.toLowerCase().replace(/\s+/g, '-'))
    if (region) {
      const slug = formatRegionSlug(region)
      if (slug) parts.push(slug)
    }
    return parts.join('/')
  }, [reality, galaxy, region])

  const value = useMemo(() => ({
    // hierarchy
    reality, galaxy, region, level,
    selectReality, selectGalaxy, selectRegion, goToLevel,
    // scope
    scope, setScope,
    // search query (URL-synced)
    q, setQ,
    // filters
    filters, setFilters, removeFilter, clearFilters, activeFilterCount,
    // history
    canGoBack, canGoForward, navBack, navForward,
    // recently viewed
    recentlyViewed, pushRecentlyViewed, clearRecentlyViewed,
    // dropdowns
    openDropdown, toggleDropdown, closeDropdowns,
    // compare
    compareMode, toggleCompareMode, pinsByLevel, togglePin, clearPins, COMPARE_CAP,
    // presentation
    prettyPath,
  }), [
    reality, galaxy, region, level,
    selectReality, selectGalaxy, selectRegion, goToLevel,
    scope, setScope,
    q, setQ,
    filters, removeFilter, clearFilters, activeFilterCount,
    canGoBack, canGoForward, navBack, navForward,
    recentlyViewed, pushRecentlyViewed, clearRecentlyViewed,
    openDropdown, toggleDropdown, closeDropdowns,
    compareMode, toggleCompareMode, pinsByLevel, togglePin, clearPins,
    prettyPath,
  ])

  return <SystemsContext.Provider value={value}>{children}</SystemsContext.Provider>
}

export function useSystems() {
  const ctx = useContext(SystemsContext)
  if (!ctx) throw new Error('useSystems must be used inside <SystemsProvider>')
  return ctx
}
