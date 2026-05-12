import React from 'react'

// Wizard v1 top progress bar (mockup .v11-progress-bar at 6130).
// Width = completeness percent. Color shifts toward gold as you climb to S.
export default function WizardProgressBar({ percent = 0, grade = 'C' }) {
  const color = {
    S: 'var(--app-accent-amber)',
    A: '#22c55e',
    B: '#3b82f6',
    C: '#94a3b8',
  }[grade] || '#94a3b8'

  return (
    <div
      className="fixed top-0 left-0 right-0 z-30 h-1 transition-all"
      style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}
    >
      <div
        className="h-full transition-all duration-300"
        style={{ width: `${Math.max(0, Math.min(100, percent))}%`, backgroundColor: color }}
      />
    </div>
  )
}
