import React, { useState } from 'react'

// Wizard v1 left sidebar (Advanced flow). Mockup #adv-sidebar (5340-5374).
//
// On lg+ the entire <aside> sticks to the side column. Inside, the grade
// panel and the section nav flow as a single column.
//
// On <lg the section nav is NOT in this component — it lives in the unified
// sticky container in Wizard.jsx alongside the toolbar so they read as one
// continuous surface with guaranteed-zero gap. The aside still renders on
// mobile, but only the grade panel is visible (the desktop nav is `lg:block`
// only). The aside is non-sticky on mobile and scrolls away normally.
//
// Each section shows a status icon: ○ empty / ◐ partial / ✓ complete.
//
// Props:
//   sections: [{ id, label, status: 'empty'|'partial'|'complete' }]
//   activeId
//   onJump(id)
//   gradeInfo: { grade, percent, breakdown, gaps } (from useCompletenessScore)
const NEXT_GRADE_THRESHOLDS = { C: { name: 'B', need: 40 }, B: { name: 'A', need: 65 }, A: { name: 'S', need: 85 }, S: null }

export default function WizardSidebar({ sections, activeId, onJump, gradeInfo }) {
  const [tooltipOpen, setTooltipOpen] = useState(false)
  const grade = gradeInfo?.grade || 'C'
  const percent = gradeInfo?.percent || 0
  const gradeColor = {
    S: 'var(--app-accent-amber)',
    A: '#22c55e',
    B: '#3b82f6',
    C: '#94a3b8',
  }[grade]
  const next = NEXT_GRADE_THRESHOLDS[grade]

  return (
    <aside className="lg:sticky lg:top-4 lg:w-64 flex-shrink-0 lg:self-start">
      <div
        className="rounded-lg p-3 lg:p-4 shadow-md mb-2"
        style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
      >
        {/* Live grade tracker */}
        {gradeInfo && (
          <div className="mb-4 pb-4 border-b relative" style={{ borderColor: 'var(--app-accent-3)' }}>
            <div className="text-xs font-semibold uppercase tracking-wider opacity-70 mb-1">Completeness</div>
            <div className="flex items-baseline gap-2">
              {/* Why-this-grade tooltip on hover/click */}
              <button
                type="button"
                onMouseEnter={() => setTooltipOpen(true)}
                onMouseLeave={() => setTooltipOpen(false)}
                onFocus={() => setTooltipOpen(true)}
                onBlur={() => setTooltipOpen(false)}
                onClick={() => setTooltipOpen((v) => !v)}
                className="text-3xl font-bold cursor-help focus:outline-none"
                style={{ color: gradeColor }}
                aria-label={`Grade ${grade} — show breakdown`}
              >
                {grade}
              </button>
              <span className="text-sm opacity-70">{percent}%</span>
            </div>
            <div className="h-2 rounded-full mt-2 overflow-hidden" style={{ backgroundColor: 'var(--app-bg)' }}>
              <div
                className="h-full transition-all duration-300"
                style={{ width: `${percent}%`, backgroundColor: gradeColor }}
              />
            </div>

            {/* Grade tooltip — per-category score + next-grade threshold */}
            {tooltipOpen && gradeInfo.breakdown && (
              <div
                className="absolute left-0 right-0 top-full mt-2 z-30 rounded-lg p-3 shadow-xl text-xs"
                style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
              >
                <div className="font-semibold mb-2" style={{ color: gradeColor }}>Grade {grade} · {percent}%</div>
                <div className="space-y-1">
                  {gradeInfo.breakdown.map((b) => (
                    <div key={b.name} className="flex justify-between gap-2">
                      <span className="opacity-80 truncate">{b.name}</span>
                      <span className="font-mono opacity-90 flex-shrink-0">{b.score}/{b.max}</span>
                    </div>
                  ))}
                </div>
                {next && (
                  <div className="mt-2 pt-2 border-t" style={{ borderColor: 'var(--app-accent-3)' }}>
                    <span className="opacity-70">Next grade:</span>{' '}
                    <span className="font-semibold">{next.name}</span>
                    <span className="opacity-70"> needs {next.need}+ ({Math.max(0, next.need - percent)} more).</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Grade guidance — top-4 deltas of "+N Add X" suggestions (mockup v11RenderGradeGuidance 9681) */}
        {gradeInfo?.gaps && gradeInfo.gaps.length > 0 && (
          <div className="mb-4 pb-4 border-b" style={{ borderColor: 'var(--app-accent-3)' }}>
            <div className="text-xs font-semibold uppercase tracking-wider opacity-70 mb-2">Boost your grade</div>
            <ul className="space-y-1.5 text-xs">
              {gradeInfo.gaps.map((g, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span
                    className="font-mono font-bold flex-shrink-0 px-1.5 rounded"
                    style={{ backgroundColor: 'var(--app-accent-amber)', color: '#1a1a1a' }}
                  >
                    +{g.delta}
                  </span>
                  <span className="opacity-90">{g.text}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Section nav — desktop only. Mobile uses the unified sticky
            container in Wizard.jsx so the toolbar + nav stack with zero gap. */}
        <nav className="hidden lg:flex lg:flex-col gap-1">
          {sections.map((s) => {
            const active = s.id === activeId
            const icon = s.status === 'complete' ? '✓' : s.status === 'partial' ? '◐' : '○'
            const iconColor = s.status === 'complete' ? '#22c55e' : s.status === 'partial' ? 'var(--app-accent-amber)' : 'var(--app-accent-3)'
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => onJump(s.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded text-sm whitespace-nowrap transition-colors ${
                  active ? 'font-semibold' : 'opacity-70 hover:opacity-100'
                }`}
                style={{
                  backgroundColor: active ? 'var(--app-primary)' : 'transparent',
                  color: active ? '#fff' : 'inherit',
                }}
              >
                <span style={{ color: active ? '#fff' : iconColor }}>{icon}</span>
                <span>{s.label}</span>
              </button>
            )
          })}
        </nav>
      </div>
    </aside>
  )
}
