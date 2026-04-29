import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import PosterFrame, { POSTER_COLORS, POSTER_FONTS } from './_shared/PosterFrame'
import CompassMark from './_shared/CompassMark'
import Watermark from './_shared/Watermark'
import { markPosterReady } from './_shared/ready'
import { fetchTagColorsForPoster, getTagColorFromAPI, LIFEFORM_COLORS } from './_shared/colors'
import { normalizeUsernameForUrl } from './_shared/identity'

// ============================================================================
// Voyager Poster — 680×1040 personal "galaxy fingerprint" card.
// Self-fetches /api/public/voyager-fingerprint?username=X.
// Mounts at /voyager/:user (friendly) AND /poster/voyager/:key (renderer).
// ============================================================================

const POSTER_W = 680
const POSTER_H = 1040

export default function VoyagerPoster({ routeKey }) {
  const params = useParams()
  const username = routeKey || params.username
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setData(null)
    setError(null)
    // Pre-fetch tag colors so faction badges render colored on first paint.
    Promise.all([
      fetchTagColorsForPoster(),
      fetch(`/api/public/voyager-fingerprint?username=${encodeURIComponent(username)}`)
        .then(async r => {
          if (!r.ok) throw new Error(await r.text())
          return r.json()
        }),
    ])
      .then(([_, j]) => {
        if (cancelled) return
        setData(j)
        markPosterReady()
      })
      .catch(e => {
        if (cancelled) return
        setError(e.message || 'Failed to load')
        markPosterReady()
      })
    return () => { cancelled = true }
  }, [username])

  if (error) {
    return (
      <PosterFrame width={POSTER_W} height={POSTER_H}>
        <CenteredMessage title="No card available" subtitle={error} hint="Username may not have any approved contributions yet." />
      </PosterFrame>
    )
  }

  if (!data) {
    return (
      <PosterFrame width={POSTER_W} height={POSTER_H}>
        <CenteredMessage title="Loading…" />
      </PosterFrame>
    )
  }

  if (!data.poster_public) {
    return (
      <PosterFrame width={POSTER_W} height={POSTER_H}>
        <CenteredMessage title={data.username} subtitle="This voyager has chosen privacy." />
      </PosterFrame>
    )
  }

  return (
    <PosterFrame width={POSTER_W} height={POSTER_H}>
      <Body data={data} />
    </PosterFrame>
  )
}

// ----- Body -----

function Body({ data }) {
  const primaryColor = getTagColorFromAPI(data.primary_community.name) || POSTER_COLORS.primary
  const charted = data.first_charted
  const daysSinceFirst = charted?.charted_at ? daysBetween(charted.charted_at, new Date()) : null
  const slug = normalizeUsernameForUrl(data.username)

  return (
    <>
      {/* Header */}
      <div style={s.header}>
        <div style={s.brandRow}>
          <CompassMark size={18} />
          <div style={s.brandStack}>
            <div style={s.brandTitle}>VOYAGER'S HAVEN</div>
            <div style={s.brandSub}>galaxy fingerprint · 2026</div>
          </div>
        </div>
        {data.primary_community.rank && (
          <div style={s.rankBadge}>
            <div style={s.rankStar}>★</div>
            <div style={s.rankText}>RANK #{data.primary_community.rank}</div>
            <div style={s.rankCommunity}>in {data.primary_community.name}</div>
          </div>
        )}
      </div>

      <div style={s.divider} />

      {/* Title */}
      <div style={s.titleBlock}>
        <div style={s.heroName}>{data.username}</div>
        <div style={s.heroSub}>CONTRIBUTING SINCE · {fmtDate(data.first_submission)}</div>
      </div>

      {/* Stats row */}
      <div style={s.statRow}>
        <StatCard
          eyebrow={`SYSTEMS · ${data.primary_community.name.toUpperCase()}`}
          value={data.primary_community.systems.toLocaleString()}
          valueColor={primaryColor}
          footer={`${data.primary_community.pct_of_community}% of ${data.primary_community.name} · ${methodSplit(data.primary_community)}`}
        />
        <StatCard
          eyebrow="SYSTEMS · ALL COMMUNITIES"
          value={data.totals.systems.toLocaleString()}
          footer={`across ${data.totals.communities} ${data.totals.communities === 1 ? 'community' : 'communities'}${data.totals.global_rank ? ` · global #${data.totals.global_rank}` : ''}`}
        />
      </div>

      {/* Reach + Lifeforms */}
      <div style={s.twoCol}>
        <Section title={`REACH · ${data.galaxy_reach.length} GALAXIES`}>
          <ReachBars items={data.galaxy_reach.slice(0, 5)} max={data.galaxy_reach[0]?.systems || 1} />
          {data.galaxy_reach.length > 5 && (
            <div style={s.moreNote}>+ {data.galaxy_reach.length - 5} more galaxies</div>
          )}
        </Section>
        <Section title="LIFEFORMS">
          <LifeformBars lifeforms={data.lifeforms.slice(0, 3)} />
          {data.lifeforms.length >= 3 && data.lifeforms[2].pct >= 25 && (
            <div style={s.lifeFooter}>a near-perfect<br />three-faction balance</div>
          )}
        </Section>
      </div>

      {/* Top regions */}
      <div style={s.regionsBlock}>
        <div style={s.sectionLabel}>TOP REGIONS · {data.named_regions} NAMED</div>
        <div style={s.regionsCard}>
          {data.top_regions.length === 0 ? (
            <div style={s.emptyHint}>No named regions yet.</div>
          ) : (
            data.top_regions.map((r, i) => (
              <div key={i} style={s.regionRow}>
                <span style={s.regionRank}>{String(i + 1).padStart(2, '0')}</span>
                <span style={{ ...s.regionName, color: i === 0 ? primaryColor : POSTER_COLORS.accent }}>{r.name}</span>
                <span style={s.regionCount}>{r.systems}</span>
                <div style={s.regionBar}>
                  <div style={{
                    ...s.regionBarFill,
                    width: `${(r.systems / data.top_regions[0].systems) * 100}%`,
                    background: i === 0 ? primaryColor : POSTER_COLORS.accent,
                  }} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer cards: First Charted + Completeness */}
      <div style={s.twoCol}>
        <Section title="FIRST CHARTED">
          {charted ? (
            <>
              <div style={s.firstName}>{charted.name}</div>
              <div style={s.firstSub}>{charted.region || '—'} · {charted.galaxy}</div>
              <div style={s.firstSub}>
                {fmtDate(charted.charted_at)}
                {daysSinceFirst != null && ` · ${daysSinceFirst} ${daysSinceFirst === 1 ? 'day' : 'days'} ago`}
              </div>
            </>
          ) : <div style={s.emptyHint}>no data</div>}
        </Section>
        <Section title="COMPLETENESS">
          <CompletenessBlock c={data.completeness} primaryColor={primaryColor} />
        </Section>
      </div>

      <div style={{ marginTop: 'auto' }}>
        <div style={s.footerBar}>
          <div>havenmap.online/voyager/{slug}</div>
          <div>share #havengalaxy</div>
        </div>
        <div style={s.footerBottom}>data pulled live · {fmtDate(new Date().toISOString())}</div>
      </div>
    </>
  )
}

// ----- Sub-components -----

function StatCard({ eyebrow, value, valueColor, footer }) {
  return (
    <div style={s.statCard}>
      <div style={s.statEyebrow}>{eyebrow}</div>
      <div style={{ ...s.statValue, color: valueColor || POSTER_COLORS.text }}>{value}</div>
      <div style={s.statFooter}>{footer}</div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div style={s.section}>
      <div style={s.sectionLabel}>{title}</div>
      <div>{children}</div>
    </div>
  )
}

function ReachBars({ items, max }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {items.map((g, i) => (
        <div key={g.galaxy}>
          <div style={s.reachRow}>
            <span style={s.reachName}>{g.galaxy.toUpperCase()}</span>
            <span style={s.reachCount}>{g.systems}</span>
          </div>
          <div style={s.reachBar}>
            <div style={{
              ...s.reachBarFill,
              width: `${(g.systems / max) * 100}%`,
              background: i === 0 ? POSTER_COLORS.primary : POSTER_COLORS.accent,
            }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function LifeformBars({ lifeforms }) {
  if (!lifeforms.length) return <div style={s.emptyHint}>no inhabited systems yet</div>
  const max = lifeforms[0].systems || 1
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {lifeforms.map(l => (
        <div key={l.name}>
          <div style={s.reachRow}>
            <span style={s.reachName}>{l.name.toUpperCase()}</span>
            <span style={s.reachCount}>{l.systems}</span>
          </div>
          <div style={s.reachBar}>
            <div style={{
              ...s.reachBarFill,
              width: `${(l.systems / max) * 100}%`,
              background: LIFEFORM_COLORS[l.name] || '#94a3b8',
            }} />
          </div>
          <div style={s.lifePct}>{l.pct}% of inhabited systems</div>
        </div>
      ))}
    </div>
  )
}

function CompletenessBlock({ c, primaryColor }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      <div style={{ flex: 1 }}>
        <div>
          <span style={s.bigScore}>{c.avg_score}</span>
          <span style={s.scoreOutOf}>/ 100</span>
        </div>
        <div style={s.gradeBreakdown}>{c.grade_s} S · {c.grade_a} A · {c.grade_b} B</div>
      </div>
      <div style={{ ...s.gradePill, background: primaryColor }}>{c.grade}</div>
    </div>
  )
}

function CenteredMessage({ title, subtitle, hint }) {
  return (
    <div style={s.errorBox}>
      <div style={s.errorTitle}>{title}</div>
      {subtitle && <div style={s.errorMsg}>{subtitle}</div>}
      {hint && <div style={s.errorHint}>{hint}</div>}
    </div>
  )
}

// ----- helpers -----

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return '—'
    return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())}`
  } catch { return '—' }
}
function pad(n) { return String(n).padStart(2, '0') }
function daysBetween(iso, now) {
  try { return Math.floor((now.getTime() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24)) } catch { return null }
}
function methodSplit(c) {
  const total = (c.manual || 0) + (c.extractor || 0)
  if (total === 0) return ''
  if (c.manual && !c.extractor) return 'all manual'
  if (c.extractor && !c.manual) return 'all extractor'
  return `${c.manual} manual · ${c.extractor} extractor`
}

// ----- styles -----

const s = {
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  brandRow: { display: 'flex', alignItems: 'center', gap: 10 },
  brandStack: { display: 'flex', flexDirection: 'column', lineHeight: 1.1 },
  brandTitle: { fontSize: 13, letterSpacing: 2.5, color: POSTER_COLORS.text, fontWeight: 600 },
  brandSub: { fontSize: 11, color: POSTER_COLORS.dim, letterSpacing: 1.5, marginTop: 2 },
  rankBadge: {
    background: POSTER_COLORS.amber,
    color: '#1a1a1a',
    padding: '8px 16px',
    borderRadius: 999,
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    minWidth: 110,
  },
  rankStar: { fontSize: 11, marginBottom: -2 },
  rankText: { fontSize: 13, fontWeight: 700, letterSpacing: 1 },
  rankCommunity: { fontSize: 9, color: POSTER_COLORS.dim, marginTop: 2, letterSpacing: 1 },
  divider: { height: 1, background: `linear-gradient(90deg, transparent, ${POSTER_COLORS.border}, transparent)`, margin: '20px 0 8px' },
  titleBlock: { padding: '24px 0 16px' },
  heroName: { fontFamily: POSTER_FONTS.serif, fontSize: 64, fontStyle: 'italic', fontWeight: 500, color: POSTER_COLORS.text, lineHeight: 1 },
  heroSub: { fontSize: 11, color: POSTER_COLORS.dim, letterSpacing: 2, marginTop: 12 },
  statRow: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 },
  statCard: { background: POSTER_COLORS.surface, border: `1px solid ${POSTER_COLORS.border}`, borderRadius: 12, padding: 18 },
  statEyebrow: { fontSize: 10, color: POSTER_COLORS.dim, letterSpacing: 2, marginBottom: 8 },
  statValue: { fontSize: 48, fontWeight: 300, lineHeight: 1, marginBottom: 8 },
  statFooter: { fontSize: 10, color: POSTER_COLORS.dim, letterSpacing: 1 },
  twoCol: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 },
  section: { background: POSTER_COLORS.surface, border: `1px solid ${POSTER_COLORS.border}`, borderRadius: 12, padding: 18 },
  sectionLabel: { fontSize: 10, color: POSTER_COLORS.dim, letterSpacing: 2, marginBottom: 12 },
  reachRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 },
  reachName: { fontSize: 11, color: POSTER_COLORS.text, letterSpacing: 1 },
  reachCount: { fontSize: 13, color: POSTER_COLORS.text, fontWeight: 500 },
  reachBar: { height: 4, background: 'rgba(167,139,250,0.15)', borderRadius: 2, overflow: 'hidden' },
  reachBarFill: { height: '100%', borderRadius: 2 },
  moreNote: { fontSize: 10, color: POSTER_COLORS.dim, marginTop: 12, fontStyle: 'italic' },
  lifePct: { fontSize: 9, color: POSTER_COLORS.dim, marginTop: 4 },
  lifeFooter: { fontSize: 11, color: POSTER_COLORS.accent, fontStyle: 'italic', textAlign: 'center', marginTop: 14 },
  regionsBlock: { marginBottom: 16 },
  regionsCard: { background: POSTER_COLORS.surface, border: `1px solid ${POSTER_COLORS.border}`, borderRadius: 12, padding: 16 },
  regionRow: {
    display: 'grid', gridTemplateColumns: '32px 1fr auto',
    alignItems: 'baseline', columnGap: 12, rowGap: 4, marginBottom: 10,
  },
  regionRank: { fontSize: 10, color: POSTER_COLORS.dim, letterSpacing: 1 },
  regionName: { fontSize: 14, fontWeight: 500 },
  regionCount: { fontSize: 13, color: POSTER_COLORS.text },
  regionBar: { gridColumn: '2 / span 2', height: 3, background: 'rgba(167,139,250,0.15)', borderRadius: 2, overflow: 'hidden' },
  regionBarFill: { height: '100%', borderRadius: 2 },
  firstName: { fontFamily: POSTER_FONTS.serif, fontSize: 22, fontStyle: 'italic', color: POSTER_COLORS.text, marginBottom: 6 },
  firstSub: { fontSize: 11, color: POSTER_COLORS.dim, marginBottom: 2 },
  bigScore: { fontSize: 44, fontWeight: 300, color: POSTER_COLORS.text },
  scoreOutOf: { fontSize: 18, color: POSTER_COLORS.dim, marginLeft: 6 },
  gradeBreakdown: { fontSize: 10, color: POSTER_COLORS.dim, marginTop: 6, letterSpacing: 1 },
  gradePill: {
    width: 56, height: 32, borderRadius: 999,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: POSTER_COLORS.bgOuter, fontWeight: 700, fontSize: 16,
  },
  emptyHint: { fontSize: 11, color: POSTER_COLORS.dim, fontStyle: 'italic' },
  footerBar: {
    display: 'flex', justifyContent: 'space-between',
    fontSize: 10, color: POSTER_COLORS.dim, letterSpacing: 1,
    paddingTop: 16, borderTop: `1px solid ${POSTER_COLORS.border}`, marginTop: 8,
  },
  footerBottom: { fontSize: 9, color: POSTER_COLORS.dim, textAlign: 'center', letterSpacing: 1, marginTop: 8 },
  errorBox: {
    minHeight: '80%',
    display: 'flex', flexDirection: 'column',
    justifyContent: 'center', alignItems: 'center',
    color: POSTER_COLORS.text, fontFamily: POSTER_FONTS.mono,
  },
  errorTitle: { fontFamily: POSTER_FONTS.serif, fontSize: 32, fontStyle: 'italic', marginBottom: 8 },
  errorMsg: { fontSize: 13, color: POSTER_COLORS.dim, marginBottom: 12 },
  errorHint: { fontSize: 11, color: POSTER_COLORS.dim, fontStyle: 'italic' },
}
