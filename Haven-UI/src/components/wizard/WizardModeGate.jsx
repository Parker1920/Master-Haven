import React from 'react'

// Wizard v1 mode chooser. Two-card hero matches mockup #mode-gate (5009-5046).
// Easy = 4-step linear flow. Advanced = single-page sidebar nav with full controls.
export default function WizardModeGate({ onChoose }) {
  const cards = [
    {
      key: 'easy',
      title: 'First Charting',
      tag: 'EASY · 4 STEPS',
      desc: 'Get a system into Haven fast. Glyphs, name, community, planets. Perfect for your first submission.',
      accent: 'var(--app-primary)',
      icon: '⛵',
    },
    {
      key: 'advanced',
      title: 'Full Logbook',
      tag: 'ADVANCED · ONE PAGE',
      desc: 'Map every detail — system attributes, every planet, station trade goods, discoveries, co-authors, expedition tagging. The full cartographer experience.',
      accent: 'var(--app-accent-2)',
      icon: '🗺️',
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl mx-auto">
      {cards.map((c) => (
        <button
          key={c.key}
          type="button"
          onClick={() => onChoose(c.key)}
          className="text-left p-6 rounded-xl border-2 transition-all hover:scale-[1.01] hover:shadow-lg"
          style={{
            borderColor: c.accent,
            backgroundColor: 'var(--app-card)',
          }}
        >
          <div className="text-4xl mb-3">{c.icon}</div>
          <div className="text-xs font-bold tracking-wider mb-1" style={{ color: c.accent }}>
            {c.tag}
          </div>
          <div className="text-2xl font-semibold mb-2">{c.title}</div>
          <div className="text-sm opacity-80">{c.desc}</div>
        </button>
      ))}
    </div>
  )
}
