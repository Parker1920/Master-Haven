/**
 * EmptyState — used when a level grid renders zero matches.
 *
 * Variant icons distinguish the four levels visually so the user can tell at
 * a glance whether the empty grid is galaxies / regions / systems / search.
 * The CTA copy + handler is owned by the caller so we can show
 * "Clear all filters" when filters are active vs a softer message when not.
 */

import React from 'react'

const ICONS = {
  reality: (
    <svg className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" />
      <path d="M2 12h20M12 2a15 15 0 010 20M12 2a15 15 0 000 20" />
    </svg>
  ),
  galaxy: (
    <svg className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="9" />
      <path d="M3.6 9h16.8M3.6 15h16.8M11.5 3a17 17 0 000 18M12.5 3a17 17 0 010 18" />
    </svg>
  ),
  region: (
    <svg className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
      <circle cx="12" cy="11" r="3" />
    </svg>
  ),
  system: (
    <svg className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="6" />
      <path strokeLinecap="round" d="M12 2v2M12 20v2M2 12h2M20 12h2" />
    </svg>
  ),
}

export default function EmptyState({
  variant = 'system',
  title = 'No matches',
  message = 'Try widening your filters or expanding scope.',
  actionLabel,
  onAction,
}) {
  return (
    <div className="haven-card p-8 text-center dot-grid">
      {ICONS[variant] || ICONS.system}
      <h3 className="text-base font-semibold mb-1">{title}</h3>
      <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>{message}</p>
      {actionLabel && onAction && (
        <button type="button" onClick={onAction} className="haven-btn-primary px-4 py-2 rounded-lg text-sm">
          {actionLabel}
        </button>
      )}
    </div>
  )
}
