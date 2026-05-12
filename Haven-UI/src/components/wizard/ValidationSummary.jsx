import React from 'react'

// Wizard v1 validation summary (mockup #validation-summary 5902,
// computeValidation 9320, renderValidationSummary 9357).
//
// Shows up to 5 issues + "...and N more". Each issue is **clickable** —
// scrolls to the target field id and focuses the first interactive
// element inside it.
//
// Props:
//   issues: [{ id, label, fieldId?, sectionAnchor? }]
//     - fieldId: DOM id of the wrapper containing the offending field
//     - sectionAnchor: fallback anchor id (e.g. 'portal') when fieldId is
//       absent or its element isn't in the DOM (e.g. region-name input
//       only renders when an unnamed region is loaded)
//
// Implementation notes:
//   - Drops `behavior: 'smooth'` — confirmed silently no-op in Chromium
//     when called against the document scroller in this app's layout.
//     We compute the position manually and call window.scrollTo with an
//     offset that clears the sticky toolbar + section pill nav.
//   - The sticky container in Wizard.jsx is tagged with [data-wizard-sticky]
//     so we can measure its actual height (toolbar + mobile pill nav, or
//     just toolbar on desktop) rather than guessing.
//   - Wrapper divs aren't focusable. We delegate focus to the first
//     real form control inside (input/select/textarea/button).
const FALLBACK_OFFSET_PX = 120  // used when [data-wizard-sticky] isn't found yet

function stickyOffsetPx() {
  const el = typeof document !== 'undefined' ? document.querySelector('[data-wizard-sticky]') : null
  return (el?.offsetHeight || FALLBACK_OFFSET_PX) + 8  // +8 = small gap below the sticky bar
}

export default function ValidationSummary({ issues = [] }) {
  if (!issues.length) {
    return (
      <div
        className="rounded-lg p-3 mb-3"
        style={{ backgroundColor: 'rgba(34, 197, 94, 0.12)', border: '1px solid #22c55e' }}
      >
        <span className="text-sm">✓ All required fields are filled. Ready to submit.</span>
      </div>
    )
  }

  const visible = issues.slice(0, 5)
  const remaining = issues.length - visible.length

  function jumpTo(fieldId, sectionAnchor) {
    let el = fieldId ? document.getElementById(fieldId) : null
    if (!el && sectionAnchor) el = document.getElementById(sectionAnchor)
    if (!el) return
    const rect = el.getBoundingClientRect()
    const top = rect.top + window.scrollY - stickyOffsetPx()
    window.scrollTo({ top: Math.max(0, top), left: 0 })
    // Focus the first real form control inside the wrapper so the user
    // sees a cursor on the offending input.
    const focusable = el.matches('input, select, textarea, button')
      ? el
      : el.querySelector('input, select, textarea, button')
    if (focusable) {
      try { focusable.focus({ preventScroll: true }) } catch { focusable.focus() }
    }
  }

  return (
    <div
      className="rounded-lg p-3 mb-3"
      style={{ backgroundColor: 'rgba(239, 68, 68, 0.12)', border: '1px solid #ef4444' }}
    >
      <div className="text-sm font-semibold mb-2 text-red-400">
        {issues.length} issue{issues.length !== 1 ? 's' : ''} blocking submission
      </div>
      <ul className="text-sm space-y-1">
        {visible.map((iss) => (
          <li key={iss.id}>
            <button
              type="button"
              onClick={() => jumpTo(iss.fieldId, iss.sectionAnchor)}
              className="text-left underline-offset-2 hover:underline opacity-90"
            >
              • {iss.label}
            </button>
          </li>
        ))}
        {remaining > 0 && (
          <li className="opacity-70 text-xs italic">…and {remaining} more</li>
        )}
      </ul>
    </div>
  )
}
