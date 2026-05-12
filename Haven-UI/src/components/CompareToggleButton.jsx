/**
 * CompareToggleButton — small "Compare" pill placed in each level grid
 * header. Active state is owned by SystemsContext.compareMode so all three
 * grids can mount their own button without coordinating.
 */

import React from 'react'
import { useSystems } from '../contexts/SystemsContext'

export default function CompareToggleButton({ targetLevel }) {
  const { compareMode, toggleCompareMode } = useSystems()
  const active = compareMode === targetLevel
  return (
    <button
      type="button"
      onClick={() => toggleCompareMode(targetLevel)}
      className={
        active
          ? 'px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1.5'
          : 'px-2.5 py-1 rounded haven-btn-ghost text-xs flex items-center gap-1.5'
      }
      style={active ? { background: 'var(--app-primary-dim)', color: 'var(--app-primary)', border: '1px solid rgba(0, 194, 179, 0.3)' } : undefined}
      aria-pressed={active}
    >
      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12M8 12h12M8 17h12M4 7h.01M4 12h.01M4 17h.01" />
      </svg>
      Compare{active ? ' (on)' : ''}
    </button>
  )
}
