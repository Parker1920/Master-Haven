import React from 'react'

// Wizard v1 location-type picker (mockup #adv-discoveries 5794-5815).
// Three-button segmented control: Planet | Moon | Space. Reusable across the
// inline wizard discoveries section and the existing DiscoverySubmitModal.
//
// Props:
//   value: 'planet' | 'moon' | 'space'
//   onChange(value)
//   compact: bool — slimmer styling for inline cards
const OPTIONS = [
  { value: 'planet', label: 'Planet' },
  { value: 'moon', label: 'Moon' },
  { value: 'space', label: 'Space' },
]

export default function LocationTypePicker({ value = 'planet', onChange, compact = false }) {
  return (
    <div
      className="flex rounded overflow-hidden"
      style={{ border: '1px solid var(--app-accent-3)' }}
    >
      {OPTIONS.map((opt, i) => {
        const active = value === opt.value
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`flex-1 text-sm font-medium transition-colors ${compact ? 'py-1 px-2 text-xs' : 'py-2 px-3'}`}
            style={{
              backgroundColor: active ? 'var(--app-primary)' : 'transparent',
              color: active ? '#fff' : 'inherit',
              borderRight: i < OPTIONS.length - 1 ? '1px solid var(--app-accent-3)' : 'none',
            }}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
