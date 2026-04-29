import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import PosterFrame, { POSTER_COLORS, POSTER_FONTS } from './_shared/PosterFrame'
import CompassMark from './_shared/CompassMark'
import { markPosterReady } from './_shared/ready'
import { fetchTagColorsForPoster, getTagColorFromAPI, getDisplayTagName } from './_shared/colors'

// ============================================================================
// Community OG Card — 1200×630 per-community preview for /community-stats/:tag.
// ============================================================================

const W = 1200
const H = 630

export default function OGCommunityCard({ routeKey }) {
  const params = useParams()
  const tag = routeKey || params.tag || 'Haven'
  const [overview, setOverview] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      fetchTagColorsForPoster(),
      fetch('/api/public/community-overview')
        .then(r => r.ok ? r.json() : null),
    ]).then(([_, j]) => {
      if (cancelled) return
      const list = j?.communities || []
      const match = list.find(c => (c.tag || '').toLowerCase() === tag.toLowerCase())
      setOverview(match || null)
      markPosterReady()
    }).catch(() => { if (!cancelled) markPosterReady() })
    return () => { cancelled = true }
  }, [tag])

  const tagColor = getTagColorFromAPI(tag) || POSTER_COLORS.primary
  const display = getDisplayTagName(tag)

  return (
    <PosterFrame width={W} height={H}>
      <div style={s.row}>
        <div style={s.leftCol}>
          <div style={s.brandRow}>
            <CompassMark size={20} />
            <div style={s.brandText}>VOYAGER'S HAVEN · COMMUNITY</div>
          </div>
          <div>
            <div style={{ ...s.heroName, color: tagColor }}>{display}</div>
            <div style={s.subline}>a charting community of No Man's Sky</div>
          </div>
          <div style={s.url}>havenmap.online/community-stats/{tag}</div>
        </div>
        <div style={s.rightCol}>
          <Stat label="STAR SYSTEMS" value={overview?.systems?.toLocaleString() || '—'} accent={tagColor} />
          <Stat label="DISCOVERIES" value={overview?.discoveries?.toLocaleString() || '—'} />
          <Stat label="MEMBERS" value={overview?.contributors?.toLocaleString() || '—'} />
          <Stat label="MANUAL / EXTRACTOR" value={`${overview?.manual ?? '—'} / ${overview?.extractor ?? '—'}`} />
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
  row: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, height: '100%' },
  leftCol: { display: 'flex', flexDirection: 'column', justifyContent: 'space-between' },
  brandRow: { display: 'flex', alignItems: 'center', gap: 12 },
  brandText: { fontSize: 13, letterSpacing: 2.5, color: POSTER_COLORS.text },
  heroName: {
    fontFamily: POSTER_FONTS.serif, fontSize: 92, fontStyle: 'italic',
    lineHeight: 1, fontWeight: 500,
  },
  subline: { fontSize: 18, color: POSTER_COLORS.accent, marginTop: 8, fontStyle: 'italic' },
  url: { fontSize: 13, color: POSTER_COLORS.accent, letterSpacing: 1 },
  rightCol: {
    display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignContent: 'center',
  },
  stat: {
    background: POSTER_COLORS.surface,
    border: `1px solid ${POSTER_COLORS.border}`,
    borderRadius: 12, padding: 18,
  },
  statLabel: { fontSize: 10, color: POSTER_COLORS.dim, letterSpacing: 2, marginBottom: 8 },
  statValue: { fontSize: 36, fontWeight: 300, lineHeight: 1, fontFamily: POSTER_FONTS.mono },
}
