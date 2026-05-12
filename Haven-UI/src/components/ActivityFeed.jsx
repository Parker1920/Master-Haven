/**
 * ActivityFeed — read-only stream of recent activity on a system.
 *
 * Per spec section 8.3, this is read-only — no comments, no replies.
 *
 * Phase 5: tries /api/systems/{id}/activity first; if 404 or empty, falls
 * back to deriving activity rows from the system's contributors list (the
 * existing system payload always includes `submitter_history` /
 * `contributors` / similar). The mockup shows 5 entries with avatar +
 * actor + action + relative timestamp.
 */

import React, { useEffect, useState } from 'react'
import axios from 'axios'

const AVATAR_BG = [
  { bg: 'var(--app-primary)', fg: '#042422' },
  { bg: 'var(--app-accent-purple)', fg: 'white' },
  { bg: 'rgba(255, 180, 76, 0.3)', fg: 'var(--app-accent-amber)' },
  { bg: 'rgba(255,255,255,0.1)', fg: 'white' },
]

function avatarFor(name, index) {
  const palette = AVATAR_BG[index % AVATAR_BG.length]
  return { letter: (name || '?').charAt(0).toUpperCase(), ...palette }
}

function relativeTime(iso) {
  if (!iso) return ''
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return ''
  const diff = Date.now() - ts
  if (diff < 60_000) return 'just now'
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

export default function ActivityFeed({ systemId, system }) {
  const [rows, setRows] = useState(null) // null = loading; [] = nothing
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    if (!systemId) return
    let cancelled = false
    axios.get(`/api/systems/${encodeURIComponent(systemId)}/activity`)
      .then((r) => { if (!cancelled) setRows(r.data?.activity || r.data || []) })
      .catch(() => {
        // No endpoint yet — derive from system payload.
        if (cancelled) return
        const fallback = []
        const submittedBy = system?.discovered_by || system?.personal_discord_username
        if (submittedBy && system?.created_at) {
          fallback.push({
            actor: submittedBy,
            action: 'discovered the system',
            timestamp: system.created_at,
          })
        }
        if (system?.last_edited_at && system.last_edited_at !== system.created_at) {
          fallback.push({
            actor: system.last_editor || submittedBy || 'Editor',
            action: 'updated data',
            timestamp: system.last_edited_at,
          })
        }
        setRows(fallback)
      })
    return () => { cancelled = true }
  }, [systemId, system?.created_at])

  if (rows == null) {
    return (
      <div className="text-xs" style={{ color: 'var(--muted)' }}>Loading activity…</div>
    )
  }

  if (rows.length === 0) {
    return (
      <div className="text-xs" style={{ color: 'var(--muted)' }}>No activity recorded yet.</div>
    )
  }

  const visible = showAll ? rows : rows.slice(0, 5)
  return (
    <div className="text-xs">
      {visible.map((row, i) => {
        const av = avatarFor(row.actor, i)
        return (
          <div key={i} className="activity-entry">
            <div className="activity-avatar" style={{ background: av.bg, color: av.fg }}>{av.letter}</div>
            <div className="flex-1 min-w-0">
              <div>
                <span className="font-medium">{row.actor || 'Someone'}</span>{' '}
                <span style={{ color: 'var(--muted)' }}>{row.action}</span>
                {row.target && <> <span style={{ color: 'var(--app-accent-purple)' }}>{row.target}</span></>}
              </div>
              <div className="text-[10px] mt-0.5" style={{ color: 'var(--muted)' }}>{relativeTime(row.timestamp)}</div>
            </div>
          </div>
        )
      })}
      {rows.length > 5 && (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="mt-2 text-[10px]"
          style={{ color: 'var(--app-primary)' }}
        >
          {showAll ? 'Show fewer' : `View all (${rows.length})`}
        </button>
      )}
    </div>
  )
}
