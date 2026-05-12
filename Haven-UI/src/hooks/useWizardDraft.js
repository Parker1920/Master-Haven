// Wizard v1 (May 2026): localStorage-backed draft persistence.
//
// Per Parker's Phase 1 decision: drafts are localStorage-only — no server
// endpoint. The autosave indicator on the toolbar pulls timestamps from
// here; the restore-draft banner reads the snapshot at mount.
//
// Storage key is profile-scoped when a profile is logged in, otherwise
// falls back to a single 'anonymous' bucket. One draft per scope at most.

import { useEffect, useRef, useState, useCallback } from 'react'
import useDebounce from './useDebounce'

const KEY_PREFIX = 'haven.wizard.draft.'
const ANONYMOUS_KEY = 'anon'

function storageKey(profileId) {
  return `${KEY_PREFIX}${profileId || ANONYMOUS_KEY}`
}

/** Read the most recent draft snapshot from localStorage. Returns null if absent or corrupt. */
export function readDraft(profileId) {
  try {
    const raw = localStorage.getItem(storageKey(profileId))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || !parsed.savedAt) return null
    return parsed
  } catch {
    return null
  }
}

/** Drop the draft for the given profile. */
export function clearDraft(profileId) {
  try {
    localStorage.removeItem(storageKey(profileId))
  } catch {
    /* ignore quota / private mode failures */
  }
}

/**
 * Hook: persist a wizard snapshot to localStorage on every change (debounced 1s)
 * with a 10-second interval safety net. Returns:
 *   { lastSavedAt, save, clear, restore }
 *
 * Caller passes `snapshot` as a serializable object. The hook does NOT track
 * dirty state — that lives in useFormDirty().
 *
 * Note: a previous version added a `clearedRef` flag intended to block the
 * interval from resurrecting a just-cleared draft. That flag never reset
 * during a session, which broke autosave after Submit Another. It's been
 * removed — the interval is cleaned up automatically when Wizard.jsx
 * unmounts (success screen replaces the form), so the resurrection
 * scenario can't actually occur in practice.
 */
function useWizardDraft(snapshot, profileId, { enabled = true, intervalMs = 10000 } = {}) {
  const [lastSavedAt, setLastSavedAt] = useState(null)
  const debounced = useDebounce(snapshot, 1000)
  const lastSerialized = useRef(null)

  // Live refs so the long-lived safety-net interval doesn't capture a
  // stale snapshot/enabled value at effect-creation time.
  const snapshotRef = useRef(snapshot)
  snapshotRef.current = snapshot
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled

  const writeNow = useCallback((data) => {
    try {
      const serialized = JSON.stringify({ ...data, savedAt: new Date().toISOString() })
      if (serialized === lastSerialized.current) return
      lastSerialized.current = serialized
      localStorage.setItem(storageKey(profileId), serialized)
      setLastSavedAt(new Date())
    } catch {
      /* quota error — silent */
    }
  }, [profileId])

  // Debounced save on every snapshot change
  useEffect(() => {
    if (!enabled) return
    if (!debounced) return
    writeNow(debounced)
  }, [debounced, enabled, writeNow])

  // Interval safety net — reads latest snapshot/enabled from refs so a
  // long-lived interval can never write stale data. Cleanup on unmount
  // (which happens when the wizard renders SuccessScreen post-submit)
  // is what protects against post-clear writes.
  useEffect(() => {
    const id = setInterval(() => {
      if (!enabledRef.current) return
      writeNow(snapshotRef.current)
    }, intervalMs)
    return () => clearInterval(id)
  }, [intervalMs, writeNow])

  const save = useCallback(() => writeNow(snapshotRef.current), [writeNow])
  const clear = useCallback(() => {
    clearDraft(profileId)
    setLastSavedAt(null)
    lastSerialized.current = null
  }, [profileId])
  const restore = useCallback(() => readDraft(profileId), [profileId])

  return { lastSavedAt, save, clear, restore }
}

export default useWizardDraft
