// Render-ready signal for headless screenshot tools.
//
// Every poster component MUST call markPosterReady() in both success and
// error paths after first paint settles. The Playwright-based renderer in
// services/poster_service.py polls window.__POSTER_READY === true before
// taking a screenshot. If a poster errors before setting this, Playwright
// hangs until the 12s timeout.

export function markPosterReady() {
  if (typeof window === 'undefined') return
  // Defer one RAF so layout/paint commits before screenshot
  if (typeof window.requestAnimationFrame === 'function') {
    window.requestAnimationFrame(() => {
      window.__POSTER_READY = true
    })
  } else {
    window.__POSTER_READY = true
  }
}

// Reset the flag (used between page navigations in dev / SPA hot reload).
export function clearPosterReady() {
  if (typeof window === 'undefined') return
  window.__POSTER_READY = false
}
