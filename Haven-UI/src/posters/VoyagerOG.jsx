import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import PosterFrame, { POSTER_COLORS, POSTER_FONTS } from './_shared/PosterFrame'
import CompassMark from './_shared/CompassMark'
import { markPosterReady } from './_shared/ready'
import { fetchTagColorsForPoster, getTagColorFromAPI } from './_shared/colors'

// ============================================================================
// Voyager Card — Open Graph variant (1200×630).
// Condensed for Discord/Twitter/Slack link embeds.
// Hits the same /api/public/voyager-fingerprint endpoint as the full card.
// ============================================================================

const W = 1200
const H = 630

export default function VoyagerOG({ routeKey }) {
  const params = useParams()
  const username = routeKey || params.username
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setData(null); setError(null)
    Promise.all([
      fetchTagColorsForPoster(),
      fetch(`/api/public/voyager-fingerprint?username=${encodeURIComponent(username)}`)
        .then(async r => r.ok ? r.json() : Promise.reject(await r.text())),
    ]).then(([_, j]) => {
      if (cancelled) return
      setData(j); markPosterReady()
    }).catch(e => {
      if (cancelled) return
      setError(typeof e === 'string' ? e : 'Failed to load'); markPosterReady()
    })
    return () => { cancelled = true }
  }, [username])

  if (error || !data) {
    return (
      <PosterFrame width={W} height={H}>
        <Center>{error ? `No card · ${error}` : 'Loading…'}</Center>
      </PosterFrame>
    )
  }
  if (!data.poster_public) {
    return (
      <PosterFrame width={W} height={H}>
        <Center>{data.username} · privacy mode</Center>
      </PosterFrame>
    )
  }

  const primaryColor = getTagColorFromAPI(data.primary_community.name) || POSTER_COLORS.primary

  return (
    <PosterFrame width={W} height={H}>
      <div style={s.row}>
        {/* Left half — name + tagline */}
        <div style={s.leftCol}>
          <div style={s.brandRow}>
            <CompassMark size={18} />
            <div style={s.brandText}>VOYAGER'S HAVEN · galaxy fingerprint</div>
          </div>
          <div style={s.heroName}>{data.username}</div>
          <div style={s.tagline}>
            {data.totals.systems.toLocaleString()} systems mapped · {data.totals.communities} communities · {data.galaxy_reach.length} galaxies
          </div>
          <div style={s.url}>havenmap.online/voyager</div>
        </div>

        {/* Right half — stat trio + completeness */}
        <div style={s.rightCol}>
          {data.primary_community.rank && (
            <div style={s.rankBadge}>
              <span style={s.rankStar}>★</span>
              <span style={s.rankText}>RANK #{data.primary_community.rank}</span>
              <span style={s.rankSub}>in {data.primary_community.name}</span>
            </div>
          )}
          <div style={s.statRow}>
            <Stat eyebrow={`${data.primary_community.name.toUpperCase()}`}
              value={data.primary_community.systems.toLocaleString()}
              valueColor={primaryColor} />
            <Stat eyebrow="ALL COMMUNITIES" value={data.totals.systems.toLocaleString()} />
            <Stat eyebrow="GALAXIES" value={data.galaxy_reach.length} />
          </div>
          <div style={s.completeness}>
            <span style={s.scoreNum}>{data.completeness.avg_score}</span>
            <span style={s.scoreOf}> / 100 · {data.completeness.grade} grade</span>
            <span style={{ ...s.gradePill, background: primaryColor }}>{data.completeness.grade}</span>
          </div>
        </div>
      </div>
    </PosterFrame>
  )
}

function Stat({ eyebrow, value, valueColor }) {
  return (
    <div style={s.stat}>
      <div style={s.statEyebrow}>{eyebrow}</div>
      <div style={{ ...s.statValue, color: valueColor || POSTER_COLORS.text }}>{value}</div>
    </div>
  )
}

function Center({ children }) {
  return (
    <div style={{
      width: '100%', height: '100%',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: POSTER_FONTS.serif, fontStyle: 'italic',
      fontSize: 36, color: POSTER_COLORS.text,
    }}>{children}</div>
  )
}

const s = {
  row: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, height: '100%' },
  leftCol: { display: 'flex', flexDirection: 'column', justifyContent: 'space-between' },
  brandRow: { display: 'flex', alignItems: 'center', gap: 10 },
  brandText: { fontSize: 13, letterSpacing: 2.5, color: POSTER_COLORS.text },
  heroName: {
    fontFamily: POSTER_FONTS.serif, fontSize: 92, fontStyle: 'italic',
    color: POSTER_COLORS.text, lineHeight: 0.95,
  },
  tagline: { fontSize: 16, color: POSTER_COLORS.dim, letterSpacing: 1 },
  url: { fontSize: 13, color: POSTER_COLORS.accent, letterSpacing: 1 },
  rightCol: { display: 'flex', flexDirection: 'column', justifyContent: 'space-between' },
  rankBadge: {
    alignSelf: 'flex-end',
    background: POSTER_COLORS.amber, color: '#1a1a1a',
    padding: '10px 22px', borderRadius: 999,
    display: 'flex', alignItems: 'center', gap: 10,
  },
  rankStar: { fontSize: 14 },
  rankText: { fontSize: 16, fontWeight: 700, letterSpacing: 1 },
  rankSub: { fontSize: 12, color: '#444', letterSpacing: 1 },
  statRow: { display: 'flex', gap: 14, justifyContent: 'space-between' },
  stat: {
    flex: 1,
    background: POSTER_COLORS.surface,
    border: `1px solid ${POSTER_COLORS.border}`,
    borderRadius: 12,
    padding: 16,
  },
  statEyebrow: { fontSize: 9, color: POSTER_COLORS.dim, letterSpacing: 2, marginBottom: 6 },
  statValue: { fontSize: 36, fontWeight: 300, lineHeight: 1 },
  completeness: {
    display: 'flex', alignItems: 'center', gap: 12,
    justifyContent: 'flex-end',
  },
  scoreNum: { fontSize: 44, color: POSTER_COLORS.text, fontWeight: 300 },
  scoreOf: { fontSize: 14, color: POSTER_COLORS.dim },
  gradePill: {
    width: 48, height: 28, borderRadius: 999,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: POSTER_COLORS.bgOuter, fontWeight: 700, fontSize: 14,
    marginLeft: 8,
  },
}
