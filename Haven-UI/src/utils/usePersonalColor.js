import { useState, useEffect } from 'react'

// Default personal color (fuchsia)
const DEFAULT_PERSONAL_COLOR = '#c026d3'

// Module-level cache to avoid multiple fetches
let cachedColor = null
let fetchPromise = null

export function usePersonalColor() {
  const [personalColor, setPersonalColor] = useState(cachedColor || DEFAULT_PERSONAL_COLOR)
  const [loading, setLoading] = useState(!cachedColor)

  useEffect(() => {
    // If we already have a cached color, use it
    if (cachedColor) {
      setPersonalColor(cachedColor)
      setLoading(false)
      return
    }

    // If a fetch is already in progress, wait for it
    if (fetchPromise) {
      fetchPromise.then(color => {
        setPersonalColor(color)
        setLoading(false)
      })
      return
    }

    // Start a new fetch
    fetchPromise = fetch('/api/settings', { credentials: 'include' })
      .then(r => r.json())
      .then(settings => {
        const color = settings?.personal_color || DEFAULT_PERSONAL_COLOR
        cachedColor = color
        return color
      })
      .catch(() => DEFAULT_PERSONAL_COLOR)

    fetchPromise.then(color => {
      setPersonalColor(color)
      setLoading(false)
    })
  }, [])

  return { personalColor, loading }
}

// Utility to clear cache (useful when color is updated)
export function clearPersonalColorCache() {
  cachedColor = null
  fetchPromise = null
}

export default usePersonalColor
