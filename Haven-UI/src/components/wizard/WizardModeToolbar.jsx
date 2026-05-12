import React from 'react'

// Wizard v1 toolbar (mockup 6134). Holds:
//   - Flow toggle: Basic | Advanced
//   - Required-only checkbox
//   - Edit-mode badge (when editing)
//   - Help button (toggles slide-in panel)
//   - Autosave indicator
//
// NOT sticky by itself anymore — the parent in Wizard.jsx wraps this
// component AND the mobile section pill nav in one sticky container so
// the two read as one continuous surface with zero gap.
export default function WizardModeToolbar({
  flow,
  onFlowChange,
  requiredOnly,
  onRequiredOnlyChange,
  isEditMode,
  helpOpen,
  onToggleHelp,
  lastSavedAt,
}) {
  const savedLabel = lastSavedAt
    ? `Auto-saved ${new Date(lastSavedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
    : 'Draft will save automatically'

  return (
    // No sticky/positioning here — the parent sticky container in
    // Wizard.jsx handles pinning AND provides the border + rounding
    // (so the bordered box always closes even when the pill nav isn't
    // rendered below — e.g. Basic flow on mobile, or any flow on desktop).
    <div
      className="flex flex-wrap items-center gap-3 px-3 py-2"
      style={{ backgroundColor: 'var(--app-card)' }}
    >
      {/* Flow toggle */}
      <div className="flex rounded overflow-hidden text-xs font-semibold" style={{ border: '1px solid var(--app-accent-3)' }}>
        {['easy', 'advanced'].map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => onFlowChange(opt)}
            className="px-3 py-1.5 transition-colors"
            style={{
              backgroundColor: flow === opt ? 'var(--app-primary)' : 'transparent',
              color: flow === opt ? '#fff' : 'inherit',
            }}
          >
            {opt === 'easy' ? 'Basic' : 'Advanced'}
          </button>
        ))}
      </div>

      {/* Required-only toggle (Advanced only) */}
      {flow === 'advanced' && (
        <label className="flex items-center gap-1.5 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={!!requiredOnly}
            onChange={(e) => onRequiredOnlyChange(e.target.checked)}
            className="w-3.5 h-3.5"
          />
          Required only
        </label>
      )}

      {/* Edit mode badge */}
      {isEditMode && (
        <span
          className="text-xs px-2 py-1 rounded font-semibold"
          style={{ backgroundColor: 'var(--app-accent-amber)', color: '#1a1a1a' }}
        >
          ✎ Edit Mode
        </span>
      )}

      {/* Spacer */}
      <span className="flex-1" />

      {/* Autosave indicator */}
      <span className="text-xs opacity-70 hidden sm:inline" aria-live="polite">
        {savedLabel}
      </span>

      {/* Help button — hidden on mobile since the floating Help FAB
          (HelpFab.jsx, lg:hidden) already covers that need. Keeping both
          visible on mobile made the toolbar wrap to two rows. */}
      <button
        type="button"
        onClick={onToggleHelp}
        className="hidden sm:inline-block px-3 py-1.5 rounded text-xs font-semibold transition-colors"
        style={{
          backgroundColor: helpOpen ? 'var(--app-primary)' : 'var(--app-accent-3)',
          color: helpOpen ? '#fff' : 'inherit',
        }}
      >
        ? Help
      </button>
    </div>
  )
}
