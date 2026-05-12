/**
 * URLBar — top-of-page address-bar display for the Systems Tab v2.0.
 *
 * Shows what the URL "would" look like with the Phase 5 path-based routing
 * landed (e.g., `havenmap.online/systems/normal/euclid/sea-of-gidzenuf`).
 * Today, real navigation still uses `/systems?reality=...&galaxy=...&rx=...`
 * — see SystemsContext.jsx for why the migration is deferred.
 *
 * Copy button copies the pretty path joined to the production origin (so
 * sharing works even from a localhost dev session). "From Map" simulates
 * an inbound deep-link from the Map tab; in production this is wired by
 * the FromMapBanner / `?from_map=1` flow added in Phase 5.
 */

import React, { useState } from 'react'
import { useSystems } from '../contexts/SystemsContext'

const PRODUCTION_ORIGIN = 'havenmap.online'

export default function URLBar() {
  const { prettyPath } = useSystems()
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    const fullUrl = `https://${PRODUCTION_ORIGIN}${prettyPath}`
    try {
      await navigator.clipboard.writeText(fullUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // navigator.clipboard fails on non-HTTPS contexts (some dev / preview
      // setups). Fall back to a prompt so the user can copy manually.
      window.prompt('Copy this URL:', fullUrl)
    }
  }

  function handleFromMap() {
    // Stub for Phase 3. Phase 5's FromMapBanner consumes ?from_map=1 in the
    // URL and shows a "back to Map" affordance. For now just append the
    // marker so the wiring becomes visible once the banner lands.
    const params = new URLSearchParams(window.location.search)
    params.set('from_map', '1')
    window.history.replaceState(null, '', `${window.location.pathname}?${params}`)
  }

  return (
    <div
      style={{ background: 'rgba(0,0,0,0.4)', borderBottom: '1px solid var(--border-soft)' }}
      className="-mx-6 px-6 py-2"
    >
      <div className="max-w-[1100px] mx-auto flex items-center gap-2">
        <span
          className="text-[10px] mono uppercase tracking-wider"
          style={{ color: 'var(--muted)' }}
        >
          URL
        </span>
        <div
          className="flex-1 flex items-center gap-1.5 px-3 py-1.5 rounded mono text-xs overflow-x-auto scrollbar-thin"
          style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid var(--border-soft)' }}
        >
          <svg
            className="w-3 h-3 shrink-0"
            style={{ color: '#34d399' }}
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 11c0-1.1-.9-2-2-2s-2 .9-2 2 .9 2 2 2 2-.9 2-2zm0 0V7m0 4v4m6-4a6 6 0 11-12 0 6 6 0 0112 0z"
            />
          </svg>
          <span style={{ color: 'var(--muted)' }}>{PRODUCTION_ORIGIN}</span>
          <span style={{ color: 'white' }}>{prettyPath}</span>
        </div>
        <button
          onClick={handleCopy}
          className="haven-btn-ghost px-2 py-1.5 rounded text-[10px] flex items-center gap-1.5"
          title="Copy shareable URL"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
          <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
        </button>
        <button
          onClick={handleFromMap}
          className="haven-btn-ghost px-2 py-1.5 rounded text-[10px] flex items-center gap-1.5"
          title="Simulate inbound deep-link from the Map tab"
        >
          <svg
            className="w-3 h-3"
            style={{ color: 'var(--app-primary)' }}
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
            />
          </svg>
          <span className="hidden sm:inline">From Map</span>
        </button>
      </div>
    </div>
  )
}
