import React from 'react'

// Wizard v1 help chip — small `(?)` icon next to confusing fields. Click
// opens HelpPanel scrolled to the matching FAQ anchor.
//
// Props:
//   anchor: string — FAQ anchor in HelpPanel (e.g. 'spectral-class')
//   onOpen(anchor): void — wizard's helpAnchor setter that opens the panel
//   label: string — accessible label for screen readers
export default function HelpChip({ anchor, onOpen, label }) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        onOpen?.(anchor)
      }}
      className="inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold leading-none cursor-help align-middle ml-1 transition-colors"
      style={{
        backgroundColor: 'var(--app-accent-3)',
        color: 'inherit',
        opacity: 0.7,
      }}
      onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
      onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.7' }}
      aria-label={label || `Help: ${anchor}`}
      title="Click for help"
    >
      ?
    </button>
  )
}
