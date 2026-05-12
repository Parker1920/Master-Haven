/**
 * CompareBar — sticky bottom bar surfaced when compareMode is on at any level
 * AND at least one pin exists. Hidden otherwise so it doesn't crowd the UI.
 *
 * Per spec section 7.2, "Open Compare" is disabled until ≥ 2 pins. Clearing
 * resets the current level's pins only (per spec 7.1: per-level isolation).
 */

import React from 'react'
import { useSystems } from '../contexts/SystemsContext'

const LEVEL_LABEL = { galaxy: 'Galaxies', region: 'Regions', system: 'Systems' }

export default function CompareBar({ onOpen }) {
  const { compareMode, pinsByLevel, togglePin, clearPins, COMPARE_CAP } = useSystems()
  if (!compareMode) return null
  const pins = pinsByLevel[compareMode] || []
  if (pins.length === 0) return null

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-40"
      style={{
        background: 'var(--app-card)',
        borderTop: '1px solid rgba(0, 194, 179, 0.4)',
        boxShadow: '0 -8px 30px rgba(0,0,0,0.4)',
      }}
    >
      <div className="max-w-[1100px] mx-auto px-4 py-3 flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4" style={{ color: 'var(--app-primary)' }} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12M8 12h12M8 17h12M4 7h.01M4 12h.01M4 17h.01" />
          </svg>
          <span className="text-sm font-medium">
            Compare <span style={{ color: 'var(--app-primary)' }}>{LEVEL_LABEL[compareMode] || ''}</span>
          </span>
          <span className="pill-teal-solid mono text-[10px] px-1.5 py-0.5 rounded-full">
            {pins.length} / {COMPARE_CAP}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-wrap flex-1 min-w-0">
          {pins.map((p) => (
            <span key={p.key} className="pill pill-teal text-xs">
              {p.label}
              <button
                type="button"
                onClick={() => togglePin(compareMode, p)}
                className="ml-1 -mr-1 opacity-70 hover:opacity-100"
                aria-label={`Unpin ${p.label}`}
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </span>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => clearPins(compareMode)}
            className="haven-btn-ghost px-3 py-1.5 rounded-lg text-xs"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={onOpen}
            disabled={pins.length < 2}
            className="haven-btn-primary px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Compare
            <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 17l9.2-9.2M17 17V7H7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
