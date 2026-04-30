import React, { useEffect, useState } from 'react'

import PosterFrame from './_shared/PosterFrame'
import { markPosterReady } from './_shared/ready'

// ============================================================================
// Landing-page OG card — 1200×630 embed shown on Discord/Twitter when someone
// shares havenmap.online itself. Mirrors the public landing page aesthetic
// (cosmic-compass mark, Cinzel wordmark, dark-navy radial gradient, teal
// accents) — distinct from OGSiteCard.jsx which is the older dashboard-era
// site card. Re-rendered weekly via the existing poster cron (ttl_hours=168).
// ============================================================================

const W = 1200
const H = 630

// Colors lifted from landing/index.html so this card and the page itself
// read as one identity. Don't pull from POSTER_COLORS — those track the
// dashboard theme, not the landing-page theme.
const C = {
  bgInner: '#1a1f3a',
  bgMid:   '#0A0E1A',
  bgOuter: '#05060d',
  text:    '#E8ECF7',
  textDim: 'rgba(232, 236, 247, 0.6)',
  teal:    '#5EE7DF',
  purple:  '#A78BFA',
  border:  'rgba(255, 255, 255, 0.08)',
}

export default function LandingOG() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetch('/api/db_stats')
      .then(r => r.ok ? r.json() : null)
      .then(j => {
        if (cancelled) return
        setStats(j?.stats || null)
        markPosterReady()
      })
      .catch(() => { if (!cancelled) markPosterReady() })
    return () => { cancelled = true }
  }, [])

  const sysCount    = stats?.total_systems    ?? stats?.systems  ?? '—'
  const regionCount = stats?.total_regions    ?? stats?.regions  ?? '—'
  const galaxies    = stats?.unique_galaxies                     ?? '—'
  const fmt = v => typeof v === 'number' ? v.toLocaleString() : v

  return (
    <PosterFrame width={W} height={H} padded={false} style={{ background: 'transparent' }}>
      {/* Pull Cinzel + Inter from Google Fonts so the rendered PNG matches the
          landing page typography. Playwright waits for the fonts before
          screenshotting via markPosterReady() at the bottom of useEffect. */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600&family=Inter:wght@400;500;600&display=swap');
      `}</style>

      {/* Background: radial-gradient base + a sparse static starfield painted
          on top with multiple radial-gradient stops. Cheap, deterministic,
          no JS needed for the stars. */}
      <div style={s.bg} />
      <div style={s.starsTeal} />
      <div style={s.starsPurple} />
      <div style={s.starsWhite} />

      {/* HERO ROW — logo + wordmark, centered vertically in the top ~62% */}
      <div style={s.hero}>
        <div style={s.logoWrap}>
          <img
            src="/assets/haven-logo-hero.webp"
            alt=""
            width={280}
            height={280}
            style={s.logo}
            // If the asset 404s in dev, the alt is empty so nothing visual
            // remains — better than alt-text leaking into the screenshot.
            onError={(e) => { e.currentTarget.style.display = 'none' }}
          />
        </div>
        <div style={s.wordmarkCol}>
          <div style={s.wordmark}>VOYAGER&apos;S HAVEN</div>
          <div style={s.divider} />
          <div style={s.tagline}>To witness is to remember,<br />We are only one light among countless stars</div>
        </div>
      </div>

      {/* STATS STRIP — three live counts, bottom band */}
      <div style={s.statsStrip}>
        <Stat value={fmt(sysCount)}    label="STAR SYSTEMS"  accent={C.teal} />
        <Stat value={fmt(regionCount)} label="NAMED REGIONS" accent={C.text} />
        <Stat value={fmt(galaxies)}    label="GALAXIES EXPLORED" accent={C.purple} />
      </div>

      {/* URL FOOTER */}
      <div style={s.urlBar}>
        <span style={s.urlDot} />
        havenmap.online
      </div>
    </PosterFrame>
  )
}

function Stat({ value, label, accent }) {
  return (
    <div style={s.stat}>
      <div style={{ ...s.statValue, color: accent }}>{value}</div>
      <div style={s.statLabel}>{label}</div>
    </div>
  )
}

const s = {
  bg: {
    position: 'absolute', inset: 0,
    background: `radial-gradient(ellipse at 50% 40%, ${C.bgInner} 0%, ${C.bgMid} 55%, ${C.bgOuter} 100%)`,
  },
  // Three layered starfields — teal/purple tint sparingly, white dominant.
  // Each gradient is one star; positions hand-chosen for visual balance.
  starsTeal: {
    position: 'absolute', inset: 0, opacity: 0.7,
    background: `
      radial-gradient(1px 1px at 8% 12%,  ${C.teal}, transparent 50%),
      radial-gradient(1px 1px at 73% 22%, ${C.teal}, transparent 50%),
      radial-gradient(1.5px 1.5px at 22% 88%, ${C.teal}, transparent 50%),
      radial-gradient(1px 1px at 91% 71%, ${C.teal}, transparent 50%)
    `,
  },
  starsPurple: {
    position: 'absolute', inset: 0, opacity: 0.6,
    background: `
      radial-gradient(1px 1px at 58% 8%,  ${C.purple}, transparent 50%),
      radial-gradient(1.5px 1.5px at 12% 64%, ${C.purple}, transparent 50%),
      radial-gradient(1px 1px at 84% 41%, ${C.purple}, transparent 50%)
    `,
  },
  starsWhite: {
    position: 'absolute', inset: 0, opacity: 0.55,
    background: `
      radial-gradient(0.8px 0.8px at 18% 32%, #fff, transparent 50%),
      radial-gradient(1px 1px   at 32% 9%,   #fff, transparent 50%),
      radial-gradient(0.8px 0.8px at 47% 18%, #fff, transparent 50%),
      radial-gradient(1.2px 1.2px at 64% 36%, #fff, transparent 50%),
      radial-gradient(0.8px 0.8px at 81% 14%, #fff, transparent 50%),
      radial-gradient(1px 1px   at 96% 28%, #fff, transparent 50%),
      radial-gradient(0.8px 0.8px at 6% 47%,  #fff, transparent 50%),
      radial-gradient(1px 1px   at 28% 56%, #fff, transparent 50%),
      radial-gradient(0.8px 0.8px at 41% 78%, #fff, transparent 50%),
      radial-gradient(1px 1px   at 67% 84%, #fff, transparent 50%),
      radial-gradient(0.8px 0.8px at 88% 92%, #fff, transparent 50%),
      radial-gradient(1px 1px   at 53% 94%, #fff, transparent 50%)
    `,
  },
  hero: {
    position: 'absolute', top: 60, left: 60, right: 60, height: 320,
    display: 'flex', alignItems: 'center', gap: 56,
    zIndex: 1,
  },
  logoWrap: {
    width: 280, height: 280,
    flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    filter: 'drop-shadow(0 0 18px rgba(94, 231, 223, 0.25))',
  },
  logo: {
    width: '100%', height: '100%', objectFit: 'contain',
  },
  wordmarkCol: {
    flex: 1,
    display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 12,
  },
  wordmark: {
    fontFamily: '"Cinzel", "Cormorant Garamond", serif',
    fontSize: 64, fontWeight: 600, letterSpacing: '0.18em',
    color: C.text, lineHeight: 1,
  },
  divider: {
    width: 120, height: 2,
    background: `linear-gradient(90deg, ${C.teal}, ${C.purple})`,
    opacity: 0.7,
  },
  tagline: {
    fontFamily: '"Inter", system-ui, sans-serif',
    fontSize: 19, fontWeight: 400, fontStyle: 'italic',
    letterSpacing: '0.04em',
    lineHeight: 1.45,
    color: C.textDim,
  },
  statsStrip: {
    position: 'absolute', left: 60, right: 60, bottom: 80, height: 110,
    display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18,
    zIndex: 1,
  },
  stat: {
    background: 'linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%)',
    border: `1px solid ${C.border}`,
    borderRadius: 12,
    padding: '18px 24px',
    display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 6,
  },
  statValue: {
    fontFamily: '"Inter", system-ui, sans-serif',
    fontSize: 44, fontWeight: 600, lineHeight: 1,
  },
  statLabel: {
    fontFamily: '"Inter", system-ui, sans-serif',
    fontSize: 11, fontWeight: 500,
    letterSpacing: '0.2em', textTransform: 'uppercase',
    color: C.textDim,
  },
  urlBar: {
    position: 'absolute', left: 60, bottom: 36,
    fontFamily: '"Inter", system-ui, sans-serif',
    fontSize: 13, fontWeight: 500,
    letterSpacing: '0.18em', textTransform: 'uppercase',
    color: C.teal,
    display: 'flex', alignItems: 'center', gap: 10,
    zIndex: 1,
  },
  urlDot: {
    width: 6, height: 6, borderRadius: '50%',
    background: C.teal,
    boxShadow: `0 0 8px ${C.teal}`,
  },
}
