import React, { useState } from 'react'
import DiscoverySubmitModal from '../DiscoverySubmitModal'
import Button from '../Button'

// Wizard v1 inline discovery list (mockup #adv-discoveries 5794-5815).
//
// Phase 2 scope: scaffold the section per the mockup and defer to the
// existing DiscoverySubmitModal for actual entry. This works because:
//   - For admin direct save (system_id is known after submit): we open the
//     existing modal pre-pointed at the new system.
//   - For public pending submit (no system_id yet): the user is informed
//     they can add discoveries from the system page once approved.
// A future iteration can replace the modal-launch UX with the full inline
// list from the mockup (with type chips, photos, evidence URLs, ★ record).
//
// Props:
//   systemId: number | null   — only set when the wizard has a real id (admin direct or edit mode)
//   isPending: bool           — true for public-submit flow (no id yet)
//   defaultDiscordTag: string
export default function WizardDiscoveryList({ systemId, isPending = false, defaultDiscordTag }) {
  const [modalOpen, setModalOpen] = useState(false)
  const [count, setCount] = useState(0)

  if (isPending && !systemId) {
    return (
      <div
        className="rounded p-3 text-sm"
        style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
      >
        <p className="opacity-80">
          Discoveries (creatures, ancient ruins, ships, multi-tools, etc.) can be added once your system has been approved by an admin.
          You'll see a "Submit Discovery" button on the system page.
        </p>
        <p className="text-xs opacity-60 mt-2">
          Bundled discovery submission is on the v2 roadmap.
        </p>
      </div>
    )
  }

  if (!systemId) {
    return (
      <div
        className="rounded p-3 text-sm opacity-70"
        style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
      >
        Save the system first to attach discoveries.
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm opacity-80">
          {count > 0
            ? `${count} discover${count === 1 ? 'y' : 'ies'} added during this session.`
            : 'Add fauna, flora, ships, multi-tools, or any other discovery.'}
        </p>
        <Button onClick={() => setModalOpen(true)}>+ Add Discovery</Button>
      </div>
      <DiscoverySubmitModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={() => {
          setCount((c) => c + 1)
          setModalOpen(false)
        }}
      />
    </div>
  )
}
