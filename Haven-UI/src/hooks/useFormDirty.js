// Wizard v1 (May 2026): track form dirty state for the beforeunload guard
// and Submit Another reset preservation.
//
// Caller passes a `state` object and an optional `pristine` baseline. When
// pristine is initially null (edit-mode loader hasn't fetched yet) the hook
// stays clean until pristine resolves, then snapshots it as the baseline.
// In create mode the *current* state at mount becomes the baseline.
// Returns `{ isDirty, markClean, markDirty }`.

import { useEffect, useRef, useState, useCallback } from 'react'

export default function useFormDirty(state, pristine = null) {
  const [isDirty, setIsDirty] = useState(false)
  const baselineRef = useRef(pristine)
  const baselineSet = useRef(pristine !== null && pristine !== undefined)
  const stateRef = useRef(state)
  stateRef.current = state

  // Late-binding baseline: in edit mode the loader sets `pristine` after
  // mount. The first time pristine becomes non-null we snapshot it; further
  // pristine changes are ignored (the user's edits are what we measure).
  useEffect(() => {
    if (!baselineSet.current && pristine !== null && pristine !== undefined) {
      baselineRef.current = pristine
      baselineSet.current = true
      setIsDirty(false)
    }
  }, [pristine])

  // Whenever state changes, compare to baseline. Cheap shallow check via
  // JSON stringify is fine for the wizard's snapshot size (<10 KB).
  // While baseline is still unresolved (edit mode pre-load), stay clean.
  useEffect(() => {
    if (!baselineSet.current) {
      // Create-mode: lock the current state as the baseline on first render.
      if (pristine === null || pristine === undefined) {
        baselineRef.current = state
        baselineSet.current = true
      }
      setIsDirty(false)
      return
    }
    try {
      const a = JSON.stringify(baselineRef.current)
      const b = JSON.stringify(state)
      setIsDirty(a !== b)
    } catch {
      setIsDirty(true)
    }
  }, [state, pristine])

  // beforeunload guard — only when truly dirty
  useEffect(() => {
    function handler(e) {
      if (!isDirty) return undefined
      e.preventDefault()
      e.returnValue = ''
      return ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  const markClean = useCallback(() => {
    baselineRef.current = stateRef.current
    baselineSet.current = true
    setIsDirty(false)
  }, [])

  const markDirty = useCallback(() => setIsDirty(true), [])

  return { isDirty, markClean, markDirty }
}
