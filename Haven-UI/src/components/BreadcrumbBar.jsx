/**
 * BreadcrumbBar — back/forward arrows + clickable breadcrumb chain + level
 * indicator pill ("Level 2/4").
 *
 * History stack lives in SystemsContext; arrows respect Alt+←/→ shortcuts.
 * Buttons render disabled (low opacity) at the history extremes per spec
 * section 4.2.
 */

import React from 'react'
import { useSystems } from '../contexts/SystemsContext'

const LEVEL_INDEX = { reality: 1, galaxy: 2, region: 3, system: 4 }
const LEVEL_TOTAL = 4

export default function BreadcrumbBar() {
  const {
    reality, galaxy, region, level,
    goToLevel, selectGalaxy, selectRegion,
    canGoBack, canGoForward, navBack, navForward,
  } = useSystems()

  // Bottom-of-chain (i.e. lowest deepest selection) drives the level indicator
  const indicator = LEVEL_INDEX[level] || 1

  const regionName = region
    ? (region.display_name || `(${region.region_x}, ${region.region_y}, ${region.region_z})`)
    : null

  return (
    <nav className="flex items-center gap-1 text-sm flex-wrap" aria-label="Breadcrumb">
      <div className="flex items-center gap-0.5 mr-1.5">
        <button
          type="button"
          onClick={navBack}
          disabled={!canGoBack}
          className="p-1.5 rounded hover:bg-white/5 transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
          title="Back (Alt + ←)"
          style={{ color: 'var(--muted)' }}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
        </button>
        <button
          type="button"
          onClick={navForward}
          disabled={!canGoForward}
          className="p-1.5 rounded hover:bg-white/5 transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
          title="Forward (Alt + →)"
          style={{ color: 'var(--muted)' }}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
          </svg>
        </button>
      </div>
      <span className="w-px h-5 mr-1.5" style={{ background: 'var(--border-soft)' }} />

      <Crumb label="Systems" onClick={() => goToLevel('root')} active={!reality} icon="home" />
      {reality && (
        <>
          <Sep />
          <Crumb label={reality} onClick={() => goToLevel('reality')} active={!galaxy} />
        </>
      )}
      {galaxy && (
        <>
          <Sep />
          <Crumb label={galaxy} onClick={() => goToLevel('galaxy')} active={!region} />
        </>
      )}
      {region && (
        <>
          <Sep />
          <Crumb label={regionName} onClick={() => selectRegion(region)} active />
        </>
      )}

      <span
        className="ml-auto text-[11px] mono px-2 py-1"
        style={{ color: 'var(--muted)' }}
      >
        Level {indicator}
        <span style={{ opacity: 0.5 }}>/{LEVEL_TOTAL}</span>
      </span>
    </nav>
  )
}

function Sep() {
  return <span style={{ color: 'var(--muted)' }}>/</span>
}

function Crumb({ label, onClick, active, icon }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-2 py-1 rounded hover:bg-white/5 transition-colors flex items-center gap-1.5"
      style={{ color: active ? 'var(--app-text)' : 'var(--muted)' }}
    >
      {icon === 'home' && (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
          />
        </svg>
      )}
      {label}
    </button>
  )
}
