import React, { useMemo } from 'react'
import productsData from '../data/changelog/products.json'
import timelineData from '../data/changelog/timeline.json'
import roadmapData from '../data/changelog/roadmap.json'

/**
 * Changelog — Route: /changelog
 * Auth: Public (no login required).
 *
 * The Voyager's Haven story page. Three sections read from static JSON files
 * committed alongside the component:
 *   - products.json   — "What We've Built" cards
 *   - timeline.json   — "Recent Witnessing" feed (grouped by month, newest first)
 *   - roadmap.json    — "What's Still Being Made" horizons
 *
 * "Last updated" is computed from the most recent timeline entry, not hardcoded.
 *
 * Color system uses three accents from the global theme:
 *   --app-primary       teal   (live status, dates, CTA)
 *   --app-accent-2      violet (section titles, month labels, identity tags)
 *   --app-accent-amber  amber  (in-development status pills)
 */

const HORIZON_COLORS = {
  soon:  { var: 'var(--app-primary)',      rgba: 'rgba(0,194,179,0.4)' },
  next:  { var: 'var(--app-accent-amber)', rgba: 'rgba(255,180,76,0.4)' },
  later: { var: 'var(--app-accent-2)',     rgba: 'rgba(157,78,221,0.4)' },
}

export default function Changelog() {
  // Most recent date in the timeline drives the "Last updated" label.
  const lastUpdated = useMemo(() => {
    const entries = timelineData.entries || []
    if (!entries.length) return null
    const latest = entries.reduce((max, e) => (e.date > max ? e.date : max), entries[0].date)
    const d = new Date(latest + 'T00:00:00')
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  }, [])

  // Reverse-chronological grouping by year-month. File stores oldest-first
  // so it's natural to append; we reverse and group at render time.
  const grouped = useMemo(() => {
    const entries = [...(timelineData.entries || [])].reverse()
    const groups = []
    let current = null
    for (const entry of entries) {
      const d = new Date(entry.date + 'T00:00:00')
      const key = `${d.getFullYear()}-${d.getMonth()}`
      const label = d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
      if (!current || current.key !== key) {
        current = { key, label, items: [] }
        groups.push(current)
      }
      current.items.push(entry)
    }
    return groups
  }, [])

  return (
    <div className="max-w-6xl mx-auto" style={{ color: 'var(--app-text)' }}>
      {/* Status banner sits flush with the navbar — same status indicator the rest of the platform has. */}
      <div className="flex items-center justify-end pb-6 border-b" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
        <span
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium"
          style={{
            border: '1px solid var(--app-primary)',
            background: 'rgba(0,194,179,0.1)',
            color: 'var(--app-primary)',
          }}
        >
          <span
            className="w-2 h-2 rounded-full"
            style={{ background: 'var(--app-primary)', boxShadow: '0 0 10px var(--app-primary)' }}
          />
          All Systems Online
        </span>
      </div>

      {/* HERO */}
      <section className="text-center py-16 md:py-20">
        <div
          className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-6 font-mono text-[11px] uppercase"
          style={{
            border: '1px solid rgba(255,255,255,0.12)',
            background: 'rgba(255,255,255,0.02)',
            color: 'var(--app-accent-2)',
            letterSpacing: '0.18em',
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: 'var(--app-accent-2)', boxShadow: '0 0 8px var(--app-accent-2)' }}
          />
          A Record of Witness
        </div>

        <h1 className="text-5xl md:text-6xl font-bold mb-3 leading-tight tracking-tight">
          Voyager's{' '}
          <span
            style={{
              background: 'linear-gradient(120deg, var(--app-primary), var(--app-accent-2))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Haven
          </span>
        </h1>

        <div className="text-sm mb-10 md:mb-12" style={{ color: 'var(--muted)' }}>
          What we've built · what we're shipping · what's coming next
        </div>

        {/* Tagline — single line, italic, with vertical gradient rules left/right. */}
        <div className="relative max-w-3xl mx-auto px-6 md:px-10 py-8 md:py-10">
          <div
            className="absolute top-0 left-0 w-px h-full hidden md:block"
            style={{ background: 'linear-gradient(to bottom, transparent, rgba(255,255,255,0.18), transparent)' }}
          />
          <div
            className="absolute top-0 right-0 w-px h-full hidden md:block"
            style={{ background: 'linear-gradient(to bottom, transparent, rgba(255,255,255,0.18), transparent)' }}
          />
          <p className="italic font-light text-xl md:text-3xl leading-relaxed">
            To witness is to remember, we are only one light among countless stars.
          </p>
        </div>

        {lastUpdated && (
          <div
            className="mt-12 md:mt-14 inline-flex items-center gap-3 font-mono text-[11px] uppercase"
            style={{ color: 'var(--muted)', letterSpacing: '0.15em' }}
          >
            <span>Last updated</span>
            <span className="w-1 h-1 rounded-full opacity-60" style={{ background: 'var(--muted)' }} />
            <span style={{ color: 'var(--app-primary)' }}>{lastUpdated}</span>
          </div>
        )}
      </section>

      {/* WHAT WE'VE BUILT */}
      <Section
        icon="🛰️"
        title="What We've Built"
        blurb="The tools that members use today — real, running, and shaped by the community."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {productsData.products.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      </Section>

      {/* RECENT WITNESSING */}
      <Section
        icon="📜"
        title="Recent Witnessing"
        blurb="What's been added, fixed, refined, and shipped — in the order it happened."
      >
        <div className="max-w-3xl mx-auto">
          {grouped.map((group, idx) => (
            <div key={group.key} className={idx > 0 ? 'mt-12' : ''}>
              <div
                className="inline-flex items-center gap-3 mb-5 px-4 py-1.5 rounded-md font-semibold text-xs uppercase"
                style={{
                  background: 'rgba(157,78,221,0.1)',
                  border: '1px solid rgba(157,78,221,0.4)',
                  color: 'var(--app-accent-2)',
                  letterSpacing: '0.18em',
                }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ background: 'var(--app-accent-2)', boxShadow: '0 0 8px var(--app-accent-2)' }}
                />
                {group.label}
              </div>
              <div className="space-y-2.5">
                {group.items.map((entry, i) => (
                  <TimelineEntry key={`${group.key}-${i}`} entry={entry} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* WHAT'S STILL BEING MADE */}
      <Section
        icon="🧭"
        title="What's Still Being Made"
        blurb="We don't promise dates. The work ships when it's ready — but here's what's on the horizon."
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {roadmapData.horizons.map((h) => (
            <HorizonCard key={h.id} horizon={h} />
          ))}
        </div>
      </Section>

      {/* FOOTER */}
      <footer
        className="text-center pt-16 pb-12 mt-8 border-t"
        style={{ borderColor: 'rgba(255,255,255,0.08)' }}
      >
        <p className="max-w-xl mx-auto mb-8 text-sm md:text-base leading-relaxed" style={{ color: 'var(--muted)' }}>
          Voyager's Haven is built by a small group of people who care, for a community of Travelers who do the same.
        </p>

        <a
          href="https://discord.gg/2PbhNPdDQ"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 px-7 py-3 rounded-full font-semibold text-sm transition-transform hover:-translate-y-0.5"
          style={{
            background: 'var(--app-primary)',
            color: 'var(--app-bg)',
            boxShadow: '0 0 30px rgba(0,194,179,0.25)',
          }}
        >
          Join the Discord →
        </a>

        <div
          className="mt-10 font-mono text-[11px] uppercase leading-relaxed"
          style={{ color: 'rgba(255,255,255,0.3)', letterSpacing: '0.15em' }}
        >
          Voyager's Haven · A No Man's Sky community<br />
          No Man's Sky is a trademark of Hello Games. We are a community, not affiliated.
        </div>
      </footer>
    </div>
  )
}

// ============================================================================
// Section header + wrapper. Title in violet, blurb on the right (right-aligned
// on desktop, left-aligned on mobile per the mockup).
// ============================================================================
function Section({ icon, title, blurb, children }) {
  return (
    <section className="py-14 md:py-16 border-t" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
      <div
        className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-9 pb-4 border-b"
        style={{ borderColor: 'rgba(255,255,255,0.08)' }}
      >
        <div className="flex items-center gap-3.5">
          <span className="text-2xl" aria-hidden="true">{icon}</span>
          <h2
            className="text-2xl md:text-[28px] font-semibold tracking-tight"
            style={{ color: 'var(--app-accent-2)' }}
          >
            {title}
          </h2>
        </div>
        <p
          className="text-sm max-w-md md:text-right leading-snug"
          style={{ color: 'var(--muted)' }}
        >
          {blurb}
        </p>
      </div>
      {children}
    </section>
  )
}

// ============================================================================
// Product card — Live (teal) or In Development (amber) status pill.
// ============================================================================
function ProductCard({ product }) {
  const isLive = product.status === 'live'
  const accent = isLive ? 'var(--app-primary)' : 'var(--app-accent-amber)'
  const pillBg = isLive ? 'rgba(0,194,179,0.1)' : 'rgba(255,180,76,0.1)'
  const pillBorder = isLive ? 'rgba(0,194,179,0.4)' : 'rgba(232,154,50,0.5)'
  const label = isLive ? 'Live' : 'In Development'

  return (
    <article
      className="rounded-xl p-6 transition-all hover:-translate-y-0.5"
      style={{
        background: 'linear-gradient(180deg, var(--app-card), rgba(255,255,255,0.01))',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.18)' }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)' }}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2.5">
          <span className="text-xl" aria-hidden="true">{product.icon}</span>
          <h3 className="text-lg md:text-xl font-semibold tracking-tight" style={{ color: 'var(--app-text)' }}>
            {product.name}
          </h3>
        </div>
        <span
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full font-mono text-[10px] uppercase font-medium shrink-0 mt-0.5"
          style={{
            color: accent,
            background: pillBg,
            border: `1px solid ${pillBorder}`,
            letterSpacing: '0.15em',
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: accent, boxShadow: `0 0 8px ${accent}` }}
          />
          {label}
        </span>
      </div>

      <p className="text-sm leading-relaxed mb-4" style={{ color: 'rgba(255,255,255,0.78)' }}>
        {product.description}
      </p>

      <div
        className="flex justify-between items-center pt-3 font-mono text-[11px] border-t"
        style={{ borderColor: 'rgba(255,255,255,0.08)', color: 'var(--muted)' }}
      >
        <span>{product.footerLeft}</span>
        {product.footerRight && (
          product.footerRight.link ? (
            <a
              href={product.footerRight.link}
              target="_blank"
              rel="noreferrer"
              style={{ color: 'var(--app-primary)' }}
              className="hover:underline"
            >
              {product.footerRight.text}
            </a>
          ) : (
            <span>{product.footerRight.text}</span>
          )
        )}
      </div>
    </article>
  )
}

// ============================================================================
// Timeline entry — date column on desktop, stacked on mobile.
// ============================================================================
function TimelineEntry({ entry }) {
  const d = new Date(entry.date + 'T00:00:00')
  const dateStrong = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  const weekday = d.toLocaleDateString('en-US', { weekday: 'long' })

  return (
    <div
      className="grid grid-cols-1 md:grid-cols-[96px_1fr] gap-2 md:gap-6 px-5 py-4 rounded-xl transition-colors"
      style={{
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.16)' }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)' }}
    >
      <div
        className="font-mono text-[11px] uppercase"
        style={{ color: 'var(--muted)', letterSpacing: '0.1em' }}
      >
        <span className="block font-medium text-[13px]" style={{ color: 'var(--app-primary)' }}>
          {dateStrong}
        </span>
        {weekday}
      </div>

      <div>
        <div
          className="inline-block font-mono text-[10px] uppercase mb-1.5 font-medium"
          style={{ color: 'var(--app-accent-2)', letterSpacing: '0.18em' }}
        >
          {entry.tag}
        </div>
        <h4 className="text-base md:text-[17px] font-semibold leading-snug mb-1.5" style={{ color: 'var(--app-text)' }}>
          {entry.title}
        </h4>
        <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.78)' }}>
          {entry.body}
        </p>
      </div>
    </div>
  )
}

// ============================================================================
// Horizon card — Soon (teal), Next (amber), Later (violet).
// ============================================================================
function HorizonCard({ horizon }) {
  const colors = HORIZON_COLORS[horizon.id] || HORIZON_COLORS.soon
  return (
    <article
      className="rounded-xl p-6"
      style={{
        background: 'linear-gradient(180deg, var(--app-card), rgba(255,255,255,0.01))',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      <div className="flex items-center gap-2.5 mb-1.5">
        <span
          className="font-mono text-[11px] uppercase font-medium px-2.5 py-1 rounded-md"
          style={{
            color: colors.var,
            border: `1px solid ${colors.rgba}`,
            background: 'rgba(0,0,0,0.25)',
            letterSpacing: '0.2em',
          }}
        >
          {horizon.label}
        </span>
      </div>
      <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
        {horizon.title}
      </h3>
      <ul className="list-none p-0 m-0">
        {horizon.items.map((item, i) => (
          <li
            key={i}
            className={`py-3.5 text-sm leading-relaxed ${i === 0 ? '' : 'border-t'}`}
            style={{
              color: 'rgba(255,255,255,0.78)',
              borderColor: 'rgba(255,255,255,0.08)',
            }}
          >
            <strong className="block text-[15px] font-semibold mb-1" style={{ color: 'var(--app-text)' }}>
              {item.title}
            </strong>
            {item.body}
          </li>
        ))}
      </ul>
    </article>
  )
}
