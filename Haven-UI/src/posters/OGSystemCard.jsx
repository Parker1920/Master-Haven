import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import PosterFrame, { POSTER_COLORS, POSTER_FONTS } from './_shared/PosterFrame'
import CompassMark from './_shared/CompassMark'
import { markPosterReady } from './_shared/ready'
import { fetchTagColorsForPoster, getTagColorFromAPI, getDisplayTagName } from './_shared/colors'

// ============================================================================
// System OG Card — 1200×630 per-system preview for /systems/:id share embeds.
// ============================================================================

const W = 1200
const H = 630

export default function OGSystemCard({ routeKey }) {
  const params = useParams()
  const systemId = routeKey || params.id
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      fetchTagColorsForPoster(),
      fetch(`/api/systems/${encodeURIComponent(systemId)}`)
        .then(async r => r.ok ? r.json() : Promise.reject(await r.text())),
    ]).then(([_, j]) => {
      if (cancelled) return
      setData(j); markPosterReady()
    }).catch(e => {
      if (cancelled) return
      setError(typeof e === 'string' ? e : 'Failed to load'); markPosterReady()
    })
    return () => { cancelled = true }
  }, [systemId])

  if (error || !data) {
    return (
      <PosterFrame width={W} height={H}>
        <Center>{error ? `System unavailable` : 'Loading…'}</Center>
      </PosterFrame>
    )
  }

  const sys = data.system || data
  const tag = sys.discord_tag || 'Personal'
  const tagColor = getTagColorFromAPI(tag) || POSTER_COLORS.primary
  const grade = sys.completeness_grade || gradeFromScore(sys.is_complete)

  return (
    <PosterFrame width={W} height={H}>
      <div style={s.row}>
        <div style={s.leftCol}>
          <div style={s.brandRow}>
            <CompassMark size={20} />
            <div style={s.brandText}>VOYAGER'S HAVEN · STAR SYSTEM</div>
          </div>
          <div>
            <div style={s.heroName}>{sys.name || 'Unknown System'}</div>
            <div style={s.subline}>
              {sys.galaxy || 'Euclid'} · {sys.glyph_code || '——'}
            </div>
          </div>
          <div style={s.url}>havenmap.online/systems/{systemId}</div>
        </div>
        <div style={s.rightCol}>
          <Stat label="STAR TYPE" value={sys.star_type || '—'} />
          <Stat label="ECONOMY" value={sys.economy_type || '—'} />
          <Stat label="COMMUNITY" value={getDisplayTagName(tag)} accent={tagColor} />
          <Stat label="GRADE" value={grade} accent={POSTER_COLORS.primary} />
        </div>
      </div>
    </PosterFrame>
  )
}

function gradeFromScore(score) {
  if (score == null) return '—'
  if (score >= 85) return 'S'
  if (score >= 65) return 'A'
  if (score >= 40) return 'B'
  return 'C'
}

function Stat({ label, value, accent }) {
  return (
    <div style={s.stat}>
      <div style={s.statLabel}>{label}</div>
      <div style={{ ...s.statValue, color: accent || POSTER_COLORS.text }}>{value}</div>
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
  brandRow: { display: 'flex', alignItems: 'center', gap: 12 },
  brandText: { fontSize: 13, letterSpacing: 2.5, color: POSTER_COLORS.text },
  heroName: {
    fontFamily: POSTER_FONTS.serif, fontSize: 76, fontStyle: 'italic',
    color: POSTER_COLORS.amber, lineHeight: 1, fontWeight: 500,
  },
  subline: { fontSize: 18, color: POSTER_COLORS.accent, marginTop: 8, letterSpacing: 1 },
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
  statValue: { fontSize: 32, fontWeight: 300, lineHeight: 1, fontFamily: POSTER_FONTS.mono },
}
