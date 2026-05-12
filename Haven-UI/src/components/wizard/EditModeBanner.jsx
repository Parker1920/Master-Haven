import React, { useState } from 'react'

// Wizard v1 edit-mode banner (mockup #v11-edit-banner 6160).
// Shown when ?edit=<id> resolves a system. Surfaces:
//   - Original submitter
//   - Edit count (n prior edits)
//   - Inline list of prior edits (from system.prior_edits[])
//
// Per Parker's Phase 0 answer #6: surface BOTH the prior edits and the count.
export default function EditModeBanner({ system }) {
  const [expanded, setExpanded] = useState(false)
  if (!system) return null

  const editCount = system.edit_count || 0
  const original = system.original_submitter || system.discovered_by || 'Unknown'
  const prior = system.prior_edits || []

  return (
    <div
      className="rounded-lg p-3 mb-4 flex flex-wrap items-center gap-3"
      style={{ backgroundColor: 'rgba(255, 180, 76, 0.12)', border: '1px solid var(--app-accent-amber)' }}
    >
      <span className="text-xl">✎</span>
      <div className="flex-1 min-w-0 text-sm">
        <span className="font-semibold">Editing {system.name}</span>
        <span className="opacity-70"> · originally submitted by </span>
        <span className="font-semibold">{original}</span>
        <span className="opacity-70"> · </span>
        <span className="font-semibold">{editCount} prior edit{editCount !== 1 ? 's' : ''}</span>
        <span className="opacity-70"> · changed fields highlighted in amber</span>
      </div>
      {prior.length > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-xs px-2 py-1 rounded"
          style={{ backgroundColor: 'var(--app-accent-amber)', color: '#1a1a1a' }}
        >
          {expanded ? 'Hide history' : 'Show history'}
        </button>
      )}
      {expanded && prior.length > 0 && (
        <ul className="w-full mt-2 text-xs space-y-1 pl-7 list-disc opacity-90">
          {prior.map((p, i) => (
            <li key={i}>
              <span className="font-semibold">{p.name || 'Unknown'}</span>
              <span className="opacity-70"> on {p.date ? new Date(p.date).toLocaleDateString() : 'unknown date'}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
