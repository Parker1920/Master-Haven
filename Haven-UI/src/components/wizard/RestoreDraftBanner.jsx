import React from 'react'

// Wizard v1 restore-draft banner (mockup #v11-restore-banner 6150).
// Shown at mount when readDraft() returns a saved snapshot. Two actions:
// Restore (rehydrate state) or Dismiss (clearDraft).
function timeAgo(iso) {
  if (!iso) return 'a moment ago'
  const ms = Date.now() - new Date(iso).getTime()
  if (ms < 60_000) return 'just now'
  const mins = Math.round(ms / 60_000)
  if (mins < 60) return `${mins} minute${mins !== 1 ? 's' : ''} ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs !== 1 ? 's' : ''} ago`
  const days = Math.round(hrs / 24)
  return `${days} day${days !== 1 ? 's' : ''} ago`
}

export default function RestoreDraftBanner({ savedAt, onRestore, onDismiss }) {
  return (
    <div
      className="rounded-lg p-3 mb-4 flex flex-wrap items-center gap-3"
      style={{ backgroundColor: 'rgba(34, 197, 94, 0.12)', border: '1px solid #22c55e' }}
    >
      <span className="text-xl">📝</span>
      <div className="flex-1 text-sm">
        <span className="font-semibold">You have a draft from {timeAgo(savedAt)}</span>
        <span className="opacity-70"> — restore it?</span>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onRestore}
          className="px-3 py-1.5 rounded text-xs font-semibold"
          style={{ backgroundColor: '#22c55e', color: '#fff' }}
        >
          Restore
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="px-3 py-1.5 rounded text-xs"
          style={{ backgroundColor: 'var(--app-accent-3)' }}
        >
          Dismiss
        </button>
      </div>
    </div>
  )
}
