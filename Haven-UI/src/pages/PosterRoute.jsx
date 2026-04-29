import React, { Suspense, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getPosterEntry } from '../posters/registry'
import { fetchTagColorsForPoster } from '../posters/_shared/colors'
import { markPosterReady, clearPosterReady } from '../posters/_shared/ready'

// Single registry-driven route at /poster/:type/:key.
// Looks up which poster component to mount and forwards :key to it via params.
//
// This is the URL the headless Playwright renderer opens. Real users typically
// reach posters via friendly URLs like /voyager/:user or /atlas/:galaxy which
// alias to the same components but bypass the registry indirection.

export default function PosterRoute() {
  const { type, key } = useParams()
  const entry = getPosterEntry(type)

  useEffect(() => {
    clearPosterReady()
    // Pre-warm the discord_tag_colors cache before posters render so they
    // don't flash uncolored/dim on first paint.
    fetchTagColorsForPoster()
  }, [type, key])

  if (!entry) {
    // Unknown type — mark ready so the headless renderer doesn't time out
    useEffect(() => { markPosterReady() }, [])
    return (
      <div style={{ padding: 40, color: '#7a85b5', fontFamily: 'monospace', background: '#02041a', minHeight: '100vh' }}>
        Unknown poster type: {type}
      </div>
    )
  }

  const Component = entry.component
  return (
    <Suspense fallback={<PosterFallback />}>
      <Component routeKey={key} />
    </Suspense>
  )
}

function PosterFallback() {
  // Minimal background while the lazy-loaded component arrives. Doesn't set
  // POSTER_READY — we want Playwright to wait for the actual component.
  return (
    <div style={{ minHeight: '100vh', background: '#02041a' }} aria-hidden="true" />
  )
}
