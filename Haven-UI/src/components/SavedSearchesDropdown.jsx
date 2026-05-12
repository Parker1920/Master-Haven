/**
 * SavedSearchesDropdown — server-backed named filter sets (Phase 2 endpoints).
 *
 * Server is the source of truth for tier 1–4 users (password-set members
 * and above). localStorage acts as:
 *   1. Warm cache — the dropdown renders instantly from cache, then
 *      reconciles when the server response arrives.
 *   2. Standalone storage for anonymous / tier-5 readonly users, who get a
 *      403 from the server endpoint. In that mode we display a "Set a
 *      password to sync across devices" hint at the bottom.
 *
 * Apply path: clicking a row mirrors the saved `filters` snapshot into
 * SystemsContext.filters and `scope` into context scope. Region/galaxy
 * pinning in saved searches is intentionally NOT applied (a saved filter
 * shouldn't yank the user out of their current scope) — only the
 * filter/scope fields are restored.
 */

import React, { useContext, useEffect, useState } from 'react'
import { AuthContext } from '../utils/AuthContext'
import { useSystems } from '../contexts/SystemsContext'
import { listSavedSearches, createSavedSearch, deleteSavedSearch } from '../utils/api'

const LOCAL_KEY = 'haven.systemsv2.savedSearches.cache'

function readCache() {
  try {
    const raw = localStorage.getItem(LOCAL_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeCache(rows) {
  try { localStorage.setItem(LOCAL_KEY, JSON.stringify(rows)) } catch {}
}

export default function SavedSearchesDropdown() {
  const auth = useContext(AuthContext)
  const { filters, setFilters, scope, setScope, openDropdown, toggleDropdown, closeDropdowns, activeFilterCount } = useSystems()
  const isOpen = openDropdown === 'saved'

  // tier <= 4 can sync to server. anon + tier 5 stay local-only.
  const canSync = !!auth?.user && (auth.user.tier == null || auth.user.tier <= 4) && !auth.isReadOnly

  const [rows, setRows] = useState(() => readCache())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!canSync) return
    setLoading(true)
    listSavedSearches()
      .then((data) => {
        setRows(data)
        writeCache(data)
        setError(null)
      })
      .catch((e) => {
        // 401/403 just means we should stay on local cache silently.
        const msg = String(e?.message || e)
        if (!/401|403/.test(msg)) setError('Could not load saved searches.')
      })
      .finally(() => setLoading(false))
  }, [canSync])

  function applyRow(row) {
    const snap = row.filters || {}
    if (snap.__filters) {
      setFilters(snap.__filters)
    } else {
      setFilters(snap)
    }
    if (snap.__scope) setScope(snap.__scope)
    closeDropdowns()
  }

  async function saveCurrent() {
    const name = window.prompt('Name this saved search:')
    if (!name) return
    const snapshot = { __filters: filters, __scope: scope }
    setBusy(true)
    try {
      if (canSync) {
        const created = await createSavedSearch(name.trim(), snapshot)
        const next = [created, ...rows]
        setRows(next)
        writeCache(next)
      } else {
        const localRow = {
          id: `local-${Date.now()}`,
          name: name.trim(),
          filters: snapshot,
          created_at: new Date().toISOString(),
          _local: true,
        }
        const next = [localRow, ...rows]
        setRows(next)
        writeCache(next)
      }
      setError(null)
    } catch (e) {
      const msg = String(e?.message || '')
      if (msg.includes('limit')) setError('You\'ve hit the 50-saved-search cap. Delete one first.')
      else setError('Save failed. Try again.')
    } finally {
      setBusy(false)
    }
  }

  async function removeRow(row) {
    setBusy(true)
    try {
      if (canSync && !row._local) {
        await deleteSavedSearch(row.id)
      }
      const next = rows.filter((r) => r.id !== row.id)
      setRows(next)
      writeCache(next)
    } catch {
      setError('Delete failed. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => toggleDropdown('saved')}
        className="haven-btn-ghost w-full lg:w-auto px-3 py-2.5 rounded-lg text-sm flex items-center justify-center gap-2"
        title="Saved searches"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
          />
        </svg>
        Saved
        {rows.length > 0 && (
          <span className="pill-teal-solid mono text-[10px] px-1.5 py-0.5 rounded-full">{rows.length}</span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-80 haven-card overflow-hidden z-30 p-0">
          <div className="px-3 py-2 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-soft)' }}>
            <span className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--muted)' }}>
              Your saved searches
            </span>
            <button
              type="button"
              onClick={saveCurrent}
              disabled={busy || activeFilterCount === 0}
              className="text-xs font-medium disabled:opacity-40"
              style={{ color: 'var(--app-primary)' }}
              title={activeFilterCount === 0 ? 'Apply some filters first' : 'Save current filters'}
            >
              + Save current
            </button>
          </div>

          <div className="max-h-72 overflow-y-auto scrollbar-thin">
            {loading && rows.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs" style={{ color: 'var(--muted)' }}>Loading…</div>
            ) : rows.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs" style={{ color: 'var(--muted)' }}>
                No saved searches yet — apply some filters, then click "Save current"
              </div>
            ) : (
              rows.map((row) => (
                <div key={row.id} className="saved-row flex items-center justify-between gap-2 px-3 py-2">
                  <button
                    type="button"
                    onClick={() => applyRow(row)}
                    className="flex-1 min-w-0 text-left"
                  >
                    <div className="text-sm truncate">{row.name}</div>
                    <div className="text-[10px] mono truncate" style={{ color: 'var(--muted)' }}>
                      {row._local ? 'local' : 'synced'}
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => removeRow(row)}
                    className="opacity-50 hover:opacity-100"
                    title="Delete"
                    aria-label="Delete saved search"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))
            )}
          </div>

          <div
            className="px-3 py-2 text-[10px]"
            style={{ color: 'var(--muted)', borderTop: '1px solid var(--border-soft)', background: 'rgba(0,0,0,0.2)' }}
          >
            {error
              ? <span style={{ color: '#fca5a5' }}>{error}</span>
              : canSync
                ? 'Synced to your profile · available on every device'
                : 'Local-only · set a password on your profile to sync across devices'}
          </div>
        </div>
      )}
    </div>
  )
}
