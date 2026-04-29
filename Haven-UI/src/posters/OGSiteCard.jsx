import React, { useEffect, useState } from 'react'

import PosterFrame, { POSTER_COLORS, POSTER_FONTS } from './_shared/PosterFrame'
import CompassMark from './_shared/CompassMark'
import { markPosterReady } from './_shared/ready'

// ============================================================================
// Site OG Card — 1200×630 global Haven preview that replaces the static
// haven-preview.png. Auto-refreshed weekly via /schedule cron.
// ============================================================================

const W = 1200
const H = 630

export default function OGSiteCard() {
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

  const sysCount = stats?.total_systems ?? stats?.systems ?? '—'
  const planetCount = stats?.total_planets ?? stats?.planets ?? '—'
  const regionCount = stats?.total_regions ?? stats?.regions ?? '—'
  const galaxies = stats?.unique_galaxies ?? '—'

  const fmt = v => typeof v === 'number' ? v.toLocaleString() : v

  return (
    <PosterFrame width={W} height={H}>
      <div style={s.row}>
        <div style={s.leftCol}>
          <div style={s.brandRow}>
            <CompassMark size={22} />
            <div style={s.brandText}>VOYAGER'S HAVEN · CONTROL ROOM</div>
          </div>
          <div>
            <div style={s.title}>HAVEN</div>
            <div style={s.subtitle}>a community atlas of No Man's Sky</div>
          </div>
          <div style={s.url}>havenmap.online</div>
        </div>
        <div style={s.rightCol}>
          <Stat label="STAR SYSTEMS" value={fmt(sysCount)} accent={POSTER_COLORS.primary} />
          <Stat label="PLANETS" value={fmt(planetCount)} />
          <Stat label="NAMED REGIONS" value={fmt(regionCount)} />
          <Stat label="GALAXIES EXPLORED" value={fmt(galaxies)} accent={POSTER_COLORS.amber} />
        </div>
      </div>
    </PosterFrame>
  )
}

function Stat({ label, value, accent }) {
  return (
    <div style={s.stat}>
      <div style={s.statLabel}>{label}</div>
      <div style={{ ...s.statValue, color: accent || POSTER_COLORS.text }}>{value}</div>
    </div>
  )
}

const s = {
  row: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 40, height: '100%' },
  leftCol: { display: 'flex', flexDirection: 'column', justifyContent: 'space-between' },
  brandRow: { display: 'flex', alignItems: 'center', gap: 12 },
  brandText: { fontSize: 14, letterSpacing: 2.5, color: POSTER_COLORS.text, fontWeight: 600 },
  title: {
    fontFamily: POSTER_FONTS.serif, fontSize: 156, fontStyle: 'italic',
    fontWeight: 500, color: POSTER_COLORS.amber, lineHeight: 1,
  },
  subtitle: {
    fontFamily: POSTER_FONTS.serif, fontSize: 22, fontStyle: 'italic',
    color: POSTER_COLORS.accent, marginTop: 8,
  },
  url: { fontSize: 14, color: POSTER_COLORS.accent, letterSpacing: 2 },
  rightCol: {
    display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16,
    alignContent: 'center',
  },
  stat: {
    background: POSTER_COLORS.surface,
    border: `1px solid ${POSTER_COLORS.border}`,
    borderRadius: 16, padding: 22,
  },
  statLabel: { fontSize: 11, color: POSTER_COLORS.dim, letterSpacing: 2, marginBottom: 10 },
  statValue: { fontSize: 56, fontWeight: 300, lineHeight: 1, fontFamily: POSTER_FONTS.mono },
}
