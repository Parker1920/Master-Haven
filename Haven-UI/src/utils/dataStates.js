/**
 * dataStates — derives state-modifier classes + overlay flags for cards.
 *
 * Per Parker's clarification on the Phase 4 spec:
 *   - is_stub: existing column on `systems` (added in v1.33.0)
 *   - pending_approval: derived from a pending_systems row referencing this
 *     system_id (NOT wired yet — backend doesn't expose this on
 *     /api/systems list responses; flagged for Phase 4.x follow-up)
 *   - is_restricted: derived from the data_restrictions pipeline (NOT wired
 *     yet — same)
 *   - last_verified_at: most recent approval/edit timestamp (NOT wired yet)
 *   - conflict: manual flag, no schema work in v2.0
 *
 * For Phase 4 the function shape supports all five fields so consumers
 * don't need to change when the backend lights them up. Today only
 * `is_stub` actually causes a visible state change.
 */

const SIX_MONTHS_MS = 1000 * 60 * 60 * 24 * 30 * 6

export function cardStateClass(row) {
  if (!row) return ''
  const classes = []
  if (row.is_stub) classes.push('state-stub')
  if (row.pending_approval) classes.push('state-pending')
  if (row.is_restricted) classes.push('state-restricted')
  return classes.join(' ')
}

export function hasOutdatedDot(row) {
  if (!row || !row.last_verified_at) return false
  const ts = Date.parse(row.last_verified_at)
  if (Number.isNaN(ts)) return false
  return Date.now() - ts > SIX_MONTHS_MS
}

export function hasConflictDot(row) {
  return !!(row && row.has_conflict)
}

export function stateBadge(row) {
  if (!row) return null
  if (row.is_restricted) return { kind: 'restricted', label: 'Locked' }
  if (row.pending_approval) return { kind: 'pending', label: 'Pending' }
  if (row.is_stub) return { kind: 'stub', label: 'Stub' }
  return null
}
