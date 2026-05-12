/**
 * FilterPillsRow — removable active-filter chips + "Clear all" link.
 *
 * Reads from useFilters().pills so the shape stays decoupled from the modal
 * implementation. Pill order matches insertion order from Object.entries on
 * SystemsContext.filters.
 */

import React from 'react'
import useFilters from '../hooks/useFilters'

export default function FilterPillsRow() {
  const { pills, removeFilter, clearFilters, activeFilterCount } = useFilters()

  return (
    <div className="flex items-start gap-x-3 gap-y-2 flex-wrap">
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[10px] uppercase tracking-wider font-semibold mr-0.5" style={{ color: 'var(--muted)' }}>
          Active:
        </span>
        {pills.length === 0 ? (
          <span className="text-[11px]" style={{ color: 'var(--muted)' }}>No filters applied</span>
        ) : (
          <>
            {pills.map(({ key, label, value }) => (
              <span key={key} className="pill pill-teal">
                <span className="font-medium">{label}:</span> {value}
                <button
                  type="button"
                  onClick={() => removeFilter(key)}
                  className="ml-1 -mr-1 opacity-70 hover:opacity-100"
                  aria-label={`Remove ${label} filter`}
                  title={`Remove ${label} filter`}
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </span>
            ))}
            {activeFilterCount > 1 && (
              <button
                type="button"
                onClick={clearFilters}
                className="text-[11px] font-medium ml-1"
                style={{ color: 'var(--app-primary)' }}
              >
                Clear all
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}
