/**
 * RecentlyViewedDropdown — 8-item rolling history of galaxies, regions, and
 * systems the user has clicked through to. Device-local (localStorage), not
 * profile-backed per spec section 4.4.
 *
 * Phase 3 surfaces the dropdown shell + clear action. Items are populated
 * via SystemsContext.pushRecentlyViewed from level click handlers (Phase 4
 * will wire those into GalaxyGrid / RegionBrowser / SystemsList; for Phase
 * 3 the only producer is SearchOverlay clicking through to a system).
 */

import React from 'react'
import { Link } from 'react-router-dom'
import { useSystems } from '../contexts/SystemsContext'

function relativeTime(iso) {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  const diff = Date.now() - then
  if (diff < 60_000) return 'just now'
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

const TYPE_ICON = {
  galaxy: (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="9" />
      <path d="M3.6 9h16.8M3.6 15h16.8M11.5 3a17 17 0 000 18M12.5 3a17 17 0 010 18" />
    </svg>
  ),
  region: (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
      <circle cx="12" cy="11" r="3" />
    </svg>
  ),
  system: (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="4" />
      <path d="M3 12h2m14 0h2M12 3v2m0 14v2M5.6 5.6l1.4 1.4m10 10l1.4 1.4M5.6 18.4l1.4-1.4m10-10l1.4-1.4" />
    </svg>
  ),
}

export default function RecentlyViewedDropdown() {
  const { recentlyViewed, clearRecentlyViewed, openDropdown, toggleDropdown, closeDropdowns } = useSystems()
  const isOpen = openDropdown === 'recent'

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => toggleDropdown('recent')}
        className="haven-btn-ghost w-full lg:w-auto px-3 py-2.5 rounded-lg text-sm flex items-center justify-center gap-2"
        title="Recently viewed"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span className="hidden md:inline">Recent</span>
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-72 haven-card overflow-hidden z-30 p-0">
          <div className="px-3 py-2 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-soft)' }}>
            <span className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--muted)' }}>
              Recently viewed
            </span>
            {recentlyViewed.length > 0 && (
              <button onClick={clearRecentlyViewed} className="text-[10px]" style={{ color: 'var(--muted)' }}>
                Clear
              </button>
            )}
          </div>
          <div className="max-h-72 overflow-y-auto scrollbar-thin">
            {recentlyViewed.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs" style={{ color: 'var(--muted)' }}>
                No history yet — start browsing
              </div>
            ) : (
              recentlyViewed.map((entry) => (
                <Link
                  key={`${entry.type}:${entry.name}:${entry.at}`}
                  to={entry.href || '#'}
                  onClick={closeDropdowns}
                  className="saved-row flex items-center gap-2 px-3 py-2"
                >
                  <span style={{ color: 'var(--muted)' }}>{TYPE_ICON[entry.type] || TYPE_ICON.system}</span>
                  <span className="text-sm flex-1 truncate">{entry.name}</span>
                  <span className="text-[10px] mono shrink-0" style={{ color: 'var(--muted)' }}>
                    {relativeTime(entry.at)}
                  </span>
                </Link>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
