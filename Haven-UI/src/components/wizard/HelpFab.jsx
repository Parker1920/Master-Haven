import React from 'react'

// Wizard v1 mobile help FAB (Layer C). Always-visible floating "?" button
// at the bottom-right while scrolling. Mirrors the mockup's FAB pattern
// (mockup line 6119 — phone-only "view chart" FAB). Hidden on lg+ screens
// where the toolbar's Help button is reliably in view.
//
// Props:
//   onClick(): void
//   isOpen: bool — visually flips when the panel is open
export default function HelpFab({ onClick, isOpen }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={isOpen ? 'Close help' : 'Open help'}
      className="fixed bottom-4 right-4 z-30 lg:hidden w-12 h-12 rounded-full font-bold text-lg shadow-2xl transition-all flex items-center justify-center"
      style={{
        backgroundColor: isOpen ? 'var(--app-accent-3)' : 'var(--app-primary)',
        color: '#fff',
        // Subtle ring on mobile so the button stands out against any background
        boxShadow: '0 4px 14px rgba(0,0,0,0.4), 0 0 0 2px rgba(255,255,255,0.08)',
      }}
    >
      {isOpen ? '×' : '?'}
    </button>
  )
}
