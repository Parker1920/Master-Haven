import React from 'react'
import { TIER_COLORS } from '../../utils/gradeColors'

// Wizard v1 top progress bar (mockup .v11-progress-bar at 6130).
// Width = completeness percent. Color shifts toward gold as you climb to S.
export default function WizardProgressBar({ percent = 0, grade = 'C' }) {
  const color = TIER_COLORS[grade] || TIER_COLORS.C

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
