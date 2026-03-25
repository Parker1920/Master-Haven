/**
 * Shared date formatting utilities.
 *
 * Replaces the 5+ inline formatDate() functions scattered across pages.
 * Import individual functions as needed — no hook required.
 */

/**
 * Format an ISO date string to a short readable date.
 * Example: "2026-03-18T12:00:00Z" → "Mar 18, 2026"
 */
export function formatDate(isoString) {
  if (!isoString) return 'N/A'
  try {
    const d = new Date(isoString)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return isoString
  }
}

/**
 * Format an ISO date string to a short date without year.
 * Example: "2026-03-18T12:00:00Z" → "Mar 18"
 */
export function formatDateShort(isoString) {
  if (!isoString) return 'N/A'
  try {
    const d = new Date(isoString)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } catch {
    return isoString
  }
}

/**
 * Format an ISO date string to a relative time string.
 * Example: "5 minutes ago", "2 hours ago", "3 days ago"
 */
export function formatRelativeDate(isoString) {
  if (!isoString) return 'N/A'
  try {
    const d = new Date(isoString)
    const now = new Date()
    const diffMs = now - d
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return formatDate(isoString)
  } catch {
    return isoString
  }
}

/**
 * Format an ISO date string to a full datetime.
 * Example: "2026-03-18T12:00:00Z" → "Mar 18, 2026 12:00 PM"
 */
export function formatDateTime(isoString) {
  if (!isoString) return 'N/A'
  try {
    const d = new Date(isoString)
    return d.toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit'
    })
  } catch {
    return isoString
  }
}
