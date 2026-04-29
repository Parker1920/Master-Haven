import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getTagColorFromAPI } from '../utils/tagColors'

// ============================================================================
// Voyager Poster — 680×1040 personal "galaxy fingerprint" card.
// Chrome-less. Mounted at /voyager/:username and at /poster/voyager/:username
// (the latter for headless screenshot capture once Playwright pipeline lands).
// Self-fetches /api/public/voyager-fingerprint?username=X.
// ============================================================================

const POSTER_W = 680
const POSTER_H = 1040

// Mirror Haven theme tokens from src/styles/index.css. Hoisted to the top
// because the module-level LIFEFORM_COLORS dict reads ACCENT before the
// styles block is evaluated — defining these later triggers a TDZ error.
const BG = '#0a0e27'           // --app-bg
const SURFACE = '#141b3d'      // --app-card
const SURFACE_HI = '#1f2858'
const BORDER = '#2a3370'
const TEXT = '#ffffff'         // --app-text
const DIM = '#8a93b8'
const ACCENT = '#9d4edd'       // --app-accent-2 (rich purple)
const AMBER = '#ffb44c'        // --app-accent-amber (warm orange)

export default function VoyagerPoster({ routeKey }) {
  const params = useParams()
  const username = routeKey || params.username
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setData(null)
    setError(null)
    fetch(`/api/public/voyager-fingerprint?username=${encodeURIComponent(username)}`)
      .then(async r => {
        if (!r.ok) {
          const err = await r.text()
          throw new Error(err || `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then(j => {
        if (cancelled) return
        setData(j)
        // Mark ready for headless screenshot tools to detect render-complete
        if (typeof window !== 'undefined') window.__POSTER_READY = true
      })
      .catch(e => {
        if (cancelled) return
        setError(e.message || 'Failed to load')
        if (typeof window !== 'undefined') window.__POSTER_READY = true
      })
    return () => { cancelled = true }
  }, [username])

  if (error) {
    return (
      <PosterFrame>
        <div style={styles.errorBox}>
          <div style={styles.errorTitle}>No card available</div>
          <div style={styles.errorMsg}>{error}</div>
          <div style={styles.errorHint}>Username may not have any approved contributions yet.</div>
        </div>
      </PosterFrame>
    )
  }

  if (!data) {
    return (
      <PosterFrame>
        <div style={styles.errorBox}>
          <div style={styles.errorTitle}>Loading…</div>
        </div>
      </PosterFrame>
    )
  }

  if (!data.poster_public) {
    return (
      <PosterFrame>
        <div style={styles.errorBox}>
          <div style={styles.errorTitle}>{data.username}</div>
          <div style={styles.errorMsg}>This voyager has chosen privacy.</div>
        </div>
      </PosterFrame>
    )
  }

  return <PosterFrame><VoyagerCardBody data={data} /></PosterFrame>
}

function PosterFrame({ children }) {
  return (
    <div style={styles.fullscreen}>
      <div style={styles.poster}>{children}</div>
    </div>
  )
}

function VoyagerCardBody({ data }) {
  const primaryColor = getTagColorFromAPI(data.primary_community.name) || '#00C2B3'
  const daysSinceFirst = data.first_charted?.charted_at ? daysBetween(data.first_charted.charted_at, new Date()) : null

  return (
    <>
      {/* Header row */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.brandRow}>
            <CompassMark size={18} color="#00C2B3" />
            <div style={styles.brandStack}>
              <div style={styles.brandTitle}>VOYAGER'S HAVEN</div>
              <div style={styles.brandSub}>galaxy fingerprint · 2026</div>
            </div>
          </div>
        </div>
        {data.primary_community.rank && (
          <div style={styles.rankBadge}>
            <div style={styles.rankStar}>★</div>
            <div style={styles.rankText}>RANK #{data.primary_community.rank}</div>
            <div style={styles.rankCommunity}>in {data.primary_community.name}</div>
          </div>
        )}
      </div>

      <div style={styles.divider} />

      {/* Title block */}
      <div style={styles.titleBlock}>
        <div style={styles.heroName}>{data.username}</div>
        <div style={styles.heroSub}>
          CONTRIBUTING SINCE · {fmtDate(data.first_submission)}
        </div>
      </div>

      {/* Stat cards */}
      <div style={styles.statRow}>
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
      <div style={styles.twoCol}>
        <Section title={`REACH · ${data.galaxy_reach.length} GALAXIES`}>
          <ReachBars items={data.galaxy_reach.slice(0, 5)} max={data.galaxy_reach[0]?.systems || 1} />
          {data.galaxy_reach.length > 5 && (
            <div style={styles.moreNote}>+ {data.galaxy_reach.length - 5} more galaxies</div>
          )}
        </Section>
        <Section title="LIFEFORMS">
          <LifeformBars lifeforms={data.lifeforms.slice(0, 3)} />
          {data.lifeforms.length >= 3 && data.lifeforms[2].pct >= 25 && (
            <div style={styles.lifeFooter}>
              a near-perfect<br />three-faction balance
            </div>
          )}
        </Section>
      </div>

      {/* Top regions */}
      <div style={styles.regionsBlock}>
        <div style={styles.sectionLabel}>TOP REGIONS · {data.named_regions} NAMED</div>
        <div style={styles.regionsCard}>
          {data.top_regions.length === 0 ? (
            <div style={styles.emptyHint}>No named regions yet.</div>
          ) : (
            data.top_regions.map((r, i) => (
              <div key={i} style={styles.regionRow}>
                <span style={styles.regionRank}>{String(i + 1).padStart(2, '0')}</span>
                <span style={{ ...styles.regionName, color: i === 0 ? primaryColor : ACCENT }}>{r.name}</span>
                <span style={styles.regionCount}>{r.systems}</span>
                <div style={styles.regionBar}>
                  <div style={{
                    ...styles.regionBarFill,
                    width: `${(r.systems / data.top_regions[0].systems) * 100}%`,
                    background: i === 0 ? primaryColor : ACCENT,
                  }} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer cards: First Charted + Completeness */}
      <div style={styles.twoCol}>
        <Section title="FIRST CHARTED" tone="dim">
          {data.first_charted ? (
            <>
              <div style={styles.firstName}>{data.first_charted.name}</div>
              <div style={styles.firstSub}>{data.first_charted.region} · {data.first_charted.galaxy}</div>
              <div style={styles.firstSub}>
                {fmtDate(data.first_charted.charted_at)}
                {daysSinceFirst != null && ` · ${daysSinceFirst} ${daysSinceFirst === 1 ? 'day' : 'days'} ago`}
              </div>
            </>
          ) : <div style={styles.emptyHint}>no data</div>}
        </Section>
        <Section title="COMPLETENESS" tone="dim">
          <CompletenessBlock c={data.completeness} primaryColor={primaryColor} />
        </Section>
      </div>

      <div style={styles.footerBar}>
        <div style={styles.footerLeft}>havenmap.online/voyager/{(data.username || '').toLowerCase()}</div>
        <div style={styles.footerRight}>share #havengalaxy</div>
      </div>
      <div style={styles.footerBottom}>data pulled live · {fmtDate(new Date().toISOString())}</div>
    </>
  )
}

// ----- Sub-components -----

function StatCard({ eyebrow, value, valueColor, footer }) {
  return (
    <div style={styles.statCard}>
      <div style={styles.statEyebrow}>{eyebrow}</div>
      <div style={{ ...styles.statValue, color: valueColor || '#fff' }}>{value}</div>
      <div style={styles.statFooter}>{footer}</div>
    </div>
  )
}

function Section({ title, children, tone }) {
  return (
    <div style={tone === 'dim' ? styles.sectionDim : styles.section}>
      <div style={styles.sectionLabel}>{title}</div>
      <div style={styles.sectionBody}>{children}</div>
    </div>
  )
}

function ReachBars({ items, max }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {items.map((g, i) => (
        <div key={g.galaxy}>
          <div style={styles.reachRow}>
            <span style={styles.reachName}>{g.galaxy.toUpperCase()}</span>
            <span style={styles.reachCount}>{g.systems}</span>
          </div>
          <div style={styles.reachBar}>
            <div style={{
              ...styles.reachBarFill,
              width: `${(g.systems / max) * 100}%`,
              background: i === 0 ? '#00C2B3' : ACCENT,
            }} />
          </div>
        </div>
      ))}
    </div>
  )
}

const LIFEFORM_COLORS = {
  'Gek': '#22c55e',
  'Korvax': ACCENT,
  'Vy\'keen': '#f59e0b',
  'Vykeen': '#f59e0b',
  'Robots': '#ef4444',
  'Atlas': '#06b6d4',
  'Diplomats': '#ec4899',
}

function LifeformBars({ lifeforms }) {
  if (!lifeforms.length) return <div style={styles.emptyHint}>no inhabited systems yet</div>
  const max = lifeforms[0].systems || 1
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {lifeforms.map(l => (
        <div key={l.name}>
          <div style={styles.reachRow}>
            <span style={styles.reachName}>{l.name.toUpperCase()}</span>
            <span style={styles.reachCount}>{l.systems}</span>
          </div>
          <div style={styles.reachBar}>
            <div style={{
              ...styles.reachBarFill,
              width: `${(l.systems / max) * 100}%`,
              background: LIFEFORM_COLORS[l.name] || '#94a3b8',
            }} />
          </div>
          <div style={styles.lifePct}>{l.pct}% of inhabited systems</div>
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
          <span style={styles.bigScore}>{c.avg_score}</span>
          <span style={styles.scoreOutOf}>/ 100</span>
        </div>
        <div style={styles.gradeBreakdown}>
          {c.grade_s} S · {c.grade_a} A · {c.grade_b} B
        </div>
      </div>
      <div style={{ ...styles.gradePill, background: primaryColor }}>{c.grade}</div>
    </div>
  )
}

function CompassMark({ size = 24, color = '#00C2B3' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" stroke={color} strokeWidth="1.5" fill="none" />
      <circle cx="12" cy="12" r="2" fill={color} />
    </svg>
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
  try {
    const d = new Date(iso)
    return Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24))
  } catch { return null }
}

function methodSplit(c) {
  const total = (c.manual || 0) + (c.extractor || 0)
  if (total === 0) return ''
  if (c.manual && !c.extractor) return 'all manual'
  if (c.extractor && !c.manual) return 'all extractor'
  return `${c.manual} manual · ${c.extractor} extractor`
}

// ----- styles -----

const monoFont = '"JetBrains Mono", "SF Mono", "Consolas", monospace'
const serifFont = '"Cormorant Garamond", "Georgia", serif'

const styles = {
  fullscreen: {
    minHeight: '100vh',
    background: '#02041a',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    padding: '40px 20px',
    fontFamily: monoFont,
    color: TEXT,
  },
  poster: {
    width: POSTER_W,
    minHeight: POSTER_H,
    background: BG,
    border: `1px solid ${BORDER}`,
    borderRadius: 24,
    padding: 32,
    boxShadow: '0 25px 80px rgba(0,0,0,0.6)',
    boxSizing: 'border-box',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  headerLeft: { display: 'flex', alignItems: 'center' },
  brandRow: { display: 'flex', alignItems: 'center', gap: 10 },
  brandStack: { display: 'flex', flexDirection: 'column', lineHeight: 1.1 },
  brandTitle: { fontSize: 13, letterSpacing: 2.5, color: TEXT, fontWeight: 600 },
  brandSub: { fontSize: 11, color: DIM, letterSpacing: 1.5, marginTop: 2 },
  rankBadge: {
    background: AMBER,
    color: '#1a1a1a',
    padding: '8px 16px',
    borderRadius: 999,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    minWidth: 110,
  },
  rankStar: { fontSize: 11, marginBottom: -2 },
  rankText: { fontSize: 13, fontWeight: 700, letterSpacing: 1 },
  rankCommunity: { fontSize: 9, color: DIM, marginTop: 2, letterSpacing: 1 },
  divider: {
    height: 1,
    background: `linear-gradient(90deg, transparent, ${BORDER}, transparent)`,
    margin: '20px 0 8px',
  },
  titleBlock: { padding: '24px 0 16px' },
  heroName: {
    fontFamily: serifFont,
    fontSize: 64,
    fontStyle: 'italic',
    fontWeight: 500,
    color: TEXT,
    lineHeight: 1,
  },
  heroSub: {
    fontSize: 11,
    color: DIM,
    letterSpacing: 2,
    marginTop: 12,
  },
  statRow: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 },
  statCard: {
    background: SURFACE,
    border: `1px solid ${BORDER}`,
    borderRadius: 12,
    padding: 18,
  },
  statEyebrow: { fontSize: 10, color: DIM, letterSpacing: 2, marginBottom: 8 },
  statValue: { fontSize: 48, fontWeight: 300, lineHeight: 1, marginBottom: 8 },
  statFooter: { fontSize: 10, color: DIM, letterSpacing: 1 },
  twoCol: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 },
  section: {
    background: SURFACE,
    border: `1px solid ${BORDER}`,
    borderRadius: 12,
    padding: 18,
  },
  sectionDim: {
    background: SURFACE,
    border: `1px solid ${BORDER}`,
    borderRadius: 12,
    padding: 18,
    opacity: 0.95,
  },
  sectionLabel: {
    fontSize: 10,
    color: DIM,
    letterSpacing: 2,
    marginBottom: 12,
  },
  sectionBody: {},
  reachRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 },
  reachName: { fontSize: 11, color: TEXT, letterSpacing: 1 },
  reachCount: { fontSize: 13, color: TEXT, fontWeight: 500 },
  reachBar: { height: 4, background: 'rgba(167,139,250,0.15)', borderRadius: 2, overflow: 'hidden' },
  reachBarFill: { height: '100%', borderRadius: 2 },
  moreNote: { fontSize: 10, color: DIM, marginTop: 12, fontStyle: 'italic' },
  lifePct: { fontSize: 9, color: DIM, marginTop: 4 },
  lifeFooter: { fontSize: 11, color: ACCENT, fontStyle: 'italic', textAlign: 'center', marginTop: 14 },
  regionsBlock: { marginBottom: 16 },
  regionsCard: {
    background: SURFACE,
    border: `1px solid ${BORDER}`,
    borderRadius: 12,
    padding: 16,
  },
  regionRow: {
    display: 'grid',
    gridTemplateColumns: '32px 1fr auto',
    alignItems: 'baseline',
    columnGap: 12,
    rowGap: 4,
    marginBottom: 10,
  },
  regionRank: { fontSize: 10, color: DIM, letterSpacing: 1 },
  regionName: { fontSize: 14, fontWeight: 500 },
  regionCount: { fontSize: 13, color: TEXT },
  regionBar: {
    gridColumn: '2 / span 2',
    height: 3,
    background: 'rgba(167,139,250,0.15)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  regionBarFill: { height: '100%', borderRadius: 2 },
  firstName: { fontFamily: serifFont, fontSize: 22, fontStyle: 'italic', color: TEXT, marginBottom: 6 },
  firstSub: { fontSize: 11, color: DIM, marginBottom: 2 },
  bigScore: { fontSize: 44, fontWeight: 300, color: TEXT },
  scoreOutOf: { fontSize: 18, color: DIM, marginLeft: 6 },
  gradeBreakdown: { fontSize: 10, color: DIM, marginTop: 6, letterSpacing: 1 },
  gradePill: {
    width: 56, height: 32,
    borderRadius: 999,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#02041a',
    fontWeight: 700,
    fontSize: 16,
  },
  emptyHint: { fontSize: 11, color: DIM, fontStyle: 'italic' },
  footerBar: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 10,
    color: DIM,
    letterSpacing: 1,
    paddingTop: 16,
    borderTop: `1px solid ${BORDER}`,
    marginTop: 8,
  },
  footerLeft: {},
  footerRight: {},
  footerBottom: { fontSize: 9, color: DIM, textAlign: 'center', letterSpacing: 1, marginTop: 8 },
  errorBox: {
    minHeight: POSTER_H - 100,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    color: TEXT,
    fontFamily: monoFont,
  },
  errorTitle: { fontFamily: serifFont, fontSize: 32, fontStyle: 'italic', marginBottom: 8 },
  errorMsg: { fontSize: 13, color: DIM, marginBottom: 12 },
  errorHint: { fontSize: 11, color: DIM, fontStyle: 'italic' },
}
