import React, { useState } from 'react'
import Modal from '../Modal'
import Button from '../Button'

// Wizard v1 conflict resolution modal (mockup #v11-conflict-modal 10243,
// trigger v11ShowConflictModal 9610). Triggered at submit when the existing
// system on disk has values that differ from what's been entered.
//
// Each conflicting field shows two cards:
//   "Yours" (the current form value)
//   "Existing in Haven (game v6.18)" (the existing value + game version)
// User picks one per row. Returns a map { [fieldPath]: 'mine' | 'theirs' }
// that the submit handler applies before sending.
//
// Props:
//   conflicts: [{ field, fieldLabel, mine, theirs, theirsGameVersion? }]
//   onResolve(choices) — { fieldPath: 'mine' | 'theirs' }
//   onCancel()
export default function ConflictResolutionModal({ conflicts = [], onResolve, onCancel }) {
  const [choices, setChoices] = useState({})

  function pick(field, side) {
    setChoices((prev) => ({ ...prev, [field]: side }))
  }

  const allResolved = conflicts.every((c) => choices[c.field])

  function handleApply() {
    onResolve(choices)
  }

  return (
    <Modal title="Resolve Conflicting Fields" onClose={onCancel}>
      <div className="space-y-4">
        <p className="text-sm opacity-80">
          The existing version of this system has different values for some fields. Pick which version to keep for each one.
        </p>

        {conflicts.map((c) => (
          <div key={c.field}>
            <div className="text-xs font-semibold uppercase tracking-wider opacity-70 mb-2">
              {c.fieldLabel || c.field}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Choice
                title="Yours"
                value={c.mine}
                selected={choices[c.field] === 'mine'}
                onSelect={() => pick(c.field, 'mine')}
                accent="var(--app-primary)"
              />
              <Choice
                title={`Existing in Haven${c.theirsGameVersion ? ` (game v${c.theirsGameVersion})` : ''}`}
                value={c.theirs}
                selected={choices[c.field] === 'theirs'}
                onSelect={() => pick(c.field, 'theirs')}
                accent="var(--app-accent-2)"
              />
            </div>
          </div>
        ))}

        <div className="flex gap-2 pt-3 border-t" style={{ borderColor: 'var(--app-accent-3)' }}>
          <Button onClick={handleApply} disabled={!allResolved}>
            Apply Resolutions
          </Button>
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          {!allResolved && (
            <span className="text-xs opacity-70 self-center ml-2">
              Pick a side for every field above
            </span>
          )}
        </div>
      </div>
    </Modal>
  )
}

function Choice({ title, value, selected, onSelect, accent }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="text-left p-3 rounded border-2 transition-all"
      style={{
        borderColor: selected ? accent : 'var(--app-accent-3)',
        backgroundColor: selected ? `${accent}22` : 'var(--app-bg)',
      }}
    >
      <div className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: accent }}>
        {title}
      </div>
      <div className="text-sm font-mono break-all">
        {value == null || value === '' ? <span className="opacity-50">(empty)</span> : String(value)}
      </div>
    </button>
  )
}
