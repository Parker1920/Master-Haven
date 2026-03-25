import { useState, useEffect } from 'react'

/**
 * Debounce a value by the given delay (ms).
 *
 * Usage:
 *   const debouncedSearch = useDebounce(searchQuery, 300)
 *
 * The returned value only updates after `delay` ms of inactivity,
 * preventing rapid API calls on every keystroke.
 */
export default function useDebounce(value, delay = 300) {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(handler)
  }, [value, delay])

  return debouncedValue
}
