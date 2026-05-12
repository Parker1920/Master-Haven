/**
 * FromMapBanner — transient "Opened from Map" banner shown when the URL
 * carries `?from_map=1`. Auto-dismisses after 8 seconds (spec section 9.2).
 *
 * The "Back to Map" button is provided as a navigation affordance; in
 * production it goes to /map/latest (the actual map route, matching what
 * the landing page uses). Manual dismiss via the X button removes the
 * banner and strips the param from the URL.
 */

import React, { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

export default function FromMapBanner({ subject }) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const present = searchParams.get('from_map') === '1'
  const [visible, setVisible] = useState(present)

  // Auto-dismiss after 8 seconds
  useEffect(() => {
    if (!visible) return
    const t = setTimeout(() => dismiss(), 8000)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible])

  // Re-show if the URL param flips back (e.g., user navigates with ?from_map=1)
  useEffect(() => {
    if (present) setVisible(true)
  }, [present])

  function dismiss() {
    setVisible(false)
    setSearchParams((prev) => {
      const out = new URLSearchParams(prev)
      out.delete('from_map')
      return out
    }, { replace: true })
  }

  if (!visible) return null

  return (
    <div
      className="haven-card flex items-center gap-3 px-4 py-2.5"
      style={{
        borderColor: 'rgba(0, 194, 179, 0.4)',
        animation: 'slideDown 220ms cubic-bezier(0.16, 1, 0.3, 1)',
      }}
      role="status"
    >
      <svg className="w-4 h-4 shrink-0" style={{ color: 'var(--app-primary)' }} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
      <div className="text-sm flex-1 min-w-0">
        <span style={{ color: 'var(--muted)' }}>Opened from Map</span>
        {subject ? <span> → <span className="font-medium">{subject}</span></span> : null}
      </div>
      <button
        type="button"
        onClick={() => navigate('/map/latest')}
        className="haven-btn-ghost px-2.5 py-1 rounded text-xs"
      >
        Back to Map
      </button>
      <button
        type="button"
        onClick={dismiss}
        className="opacity-60 hover:opacity-100"
        aria-label="Dismiss"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
