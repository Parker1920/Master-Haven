import React from 'react'

// Shared stat tile primitive — used by:
//   - src/posters/SystemThumb.jsx       (system_thumb cached PNG poster)
//   - src/components/wizard/WizardAdvancedPreview.jsx
//
// Mono label on top, bold value middle, optional sub-line beneath.
// `tile` prop turns the cell into a solid-color "grade tile" — pass an
// object {bg, fg} (see GRADE_BG below).

export default function StatTile({ label, value, sub, valueColor, tile, truncate }) {
  const isTile = !!tile
  return (
    <div style={{
      padding: '7px 9px',
      borderRadius: 4,
      background: isTile ? tile.bg : 'rgba(0,0,0,0.30)',
      border: `1px solid ${isTile ? 'transparent' : 'rgba(255,255,255,0.10)'}`,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      minHeight: 50,
      overflow: 'hidden',
    }}>
      <div style={{
        fontFamily: '"JetBrains Mono", "SF Mono", "Consolas", monospace',
        fontSize: 8,
        letterSpacing: 1.5,
        color: isTile ? tile.fg : 'rgba(255,255,255,0.55)',
        opacity: isTile ? 0.85 : 1,
        textTransform: 'uppercase',
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: '"JetBrains Mono", "SF Mono", "Consolas", monospace',
        fontSize: 13,
        color: valueColor || (isTile ? tile.fg : '#ffffff'),
        fontWeight: 700,
        whiteSpace: truncate ? 'nowrap' : undefined,
        overflow: truncate ? 'hidden' : undefined,
        textOverflow: truncate ? 'ellipsis' : undefined,
      }}>
        {value}
      </div>
      {sub && (
        <div style={{
          fontFamily: '"JetBrains Mono", "SF Mono", "Consolas", monospace',
          fontSize: 9,
          color: isTile ? tile.fg : 'rgba(255,255,255,0.55)',
          opacity: isTile ? 0.75 : 1,
        }}>
          {sub}
        </div>
      )}
    </div>
  )
}

// Grade-tile color tokens — shared between poster + wizard preview so the
// S/A/B/C visual stays consistent.
export const GRADE_BG = {
  S: { bg: '#ffb44c', fg: '#422006' },          // amber
  A: { bg: '#34d399', fg: '#022c22' },          // emerald
  B: { bg: '#60a5fa', fg: '#082f49' },          // blue
  C: { bg: 'rgba(255,255,255,0.20)', fg: 'rgba(255,255,255,0.95)' },
}

export function gradeFromScore(score) {
  if (score == null) return '—'
  if (score >= 85) return 'S'
  if (score >= 65) return 'A'
  if (score >= 40) return 'B'
  return 'C'
}
