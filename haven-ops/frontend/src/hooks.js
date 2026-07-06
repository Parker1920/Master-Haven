import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

// Fetch-on-mount with manual reload — screens refetch after any mutation.
export function useFetch(path) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let alive = true
    api.get(path)
      .then((d) => { if (alive) { setData(d); setError(null) } })
      .catch((e) => { if (alive) setError(e) })
    return () => { alive = false }
  }, [path, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, reload }
}
