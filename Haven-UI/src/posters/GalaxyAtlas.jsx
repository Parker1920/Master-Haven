import React, { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'

import PosterFrame, { POSTER_COLORS, POSTER_FONTS } from './_shared/PosterFrame'
import CompassMark, { CompassRose } from './_shared/CompassMark'
import Watermark from './_shared/Watermark'
import { markPosterReady } from './_shared/ready'
import { fetchTagColorsForPoster, getDisplayTagName, getTagColorFromAPI } from './_shared/colors'

// ============================================================================
// Galaxy Atlas Poster — 680×920 per-galaxy political map.
//
// Visual approach (from poster-system-plan.md):
//  • Project coordinates centered on (2048, 2048) — actual NMS galaxy center
//  • Apply a circular visible mask so the canvas LOOKS like a galaxy disk
//  • Tiered dot sizing: background regions tiny (1.5px), top regions ringed
//  • Legend shows faction display_names (Galactic Hub, not GHUB)
//  • Top-9 picks come from the backend's Option C picker (faction-first +
//    spatial dedup), so they're visually distributed and civ-diverse.
// ============================================================================

const POSTER_W = 680
const POSTER_H = 920
const MAP_W = 380
const MAP_H = 360

// NMS galaxy center — used as the projection origin so populated regions cluster
// in the middle of the canvas instead of being squashed against bounding-box edges.
const GALAXY_CENTER_X = 2048
const GALAXY_CENTER_Z = 2048

export default function GalaxyAtlas({ routeKey }) {
  const params = useParams()
  const galaxy = routeKey || params.galaxy || 'Euclid'
  const [search] = useSearchParams()
  const reality = search.get('reality') || 'Normal'
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setData(null)
    setError(null)
    const url = `/api/public/galaxy-atlas?galaxy=${encodeURIComponent(galaxy)}&reality=${encodeURIComponent(reality)}`
    Promise.all([
      fetchTagColorsForPoster(),
      fetch(url).then(async r => {
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
  }, [galaxy, reality])

  if (error) {
    return (
      <PosterFrame width={POSTER_W} height={POSTER_H}>
        <CenteredMsg title={galaxy} subtitle={error} />
      </PosterFrame>
    )
  }
  if (!data) {
    return (
      <PosterFrame width={POSTER_W} height={POSTER_H}>
        <CenteredMsg title="Loading…" />
      </PosterFrame>
    )
  }
  return (
    <PosterFrame width={POSTER_W} height={POSTER_H}>
      <Body data={data} />
    </PosterFrame>
  )
}

// ============================================================================
// Body
// ============================================================================

function Body({ data }) {
  const today = new Date().toISOString().slice(0, 10)

  // ============================================================================
  // DATA-DRIVEN APPROACH (per investigation report 2026-04-29):
  //
  // Plot ALL regions at their REAL galactic positions, sized by log(system_count).
  // The visual structure (clusters, bright spots, the "comet trail" feel from the
  // mockup) emerges naturally from how communities actually clustered in NMS.
  //
  // For Euclid: the GHUB super-cluster (10 regions within a 3x3 cube, 5,259
  // total systems) renders as a single bright spot — the "comet" the mockup had.
  // For sparse galaxies: a few real dots + ambient ambient stars for atmosphere.
  // ============================================================================
  const top9 = data.named_regions.slice(0, 9)
  const indexLookup = new Map(top9.map(r => [
    `${r.region_x},${r.region_y},${r.region_z}`,
    r.index_number,
  ]))

  // Plot ALL regions — every dot in the canvas is real data. No cap.
  // Capping by system_count discards the LONG TAIL of small-population
  // regions that form visible community trails (e.g. Haven's 155-region
  // diagonal trail across Euclid X=2211..2319). SVG handles 1000+ circles
  // without breaking a sweat, so there's no reason to throw signal away.
  const plotRegions = data.regions

  // Project to canvas (omits anything beyond visible disk radius)
  const projection = useMemo(() => projectGalactic(plotRegions), [plotRegions])

  // Adaptive radius scaling: log(system_count) → screen px
  // Largest cluster gets ~5-6px, single-system regions get ~0.6px
  const maxCount = Math.max(1, ...plotRegions.map(r => r.system_count))
  const dotRadius = (count) => {
    const ratio = Math.log(count + 1) / Math.log(maxCount + 1)  // 0..1
    return 0.6 + ratio * 5.2  // 0.6 → 5.8px
  }

  // Sort plottable region+point pairs by size ASC so smallest draws first
  // (biggest clusters end up on top, popping visually)
  const drawList = useMemo(() => {
    const list = []
    for (const r of plotRegions) {
      const p = projection.get(`${r.region_x},${r.region_y},${r.region_z}`)
      if (!p) continue
      list.push({ region: r, point: p, radius: dotRadius(r.system_count) })
    }
    list.sort((a, b) => a.radius - b.radius)
    return list
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plotRegions, projection, maxCount])

  // ============================================================================
  // Trail detection — find chains of same-faction adjacent regions and render
  // them as connecting polylines. THIS is what creates the visible "yellow
  // line" / "purple line" trails in the mockup. Each major faction's regions
  // are checked for spatial chains (consecutive regions within N units of
  // each other), and any chain of 4+ regions becomes a drawn trail.
  // ============================================================================
  const trails = useMemo(() => detectTrails(plotRegions, projection), [plotRegions, projection])

  return (
    <>
      {/* Header */}
      <div style={s.header}>
        <div style={s.brandRow}>
          <CompassMark size={20} />
          <div>
            <div style={s.brandTitle}>VOYAGER'S HAVEN · CONTROL ROOM</div>
            <div style={s.brandSub}>a political atlas of the {data.galaxy} Galaxy</div>
          </div>
        </div>
        <div style={s.drawnAt}>DRAWN · {today}</div>
      </div>

      {/* Title */}
      <div style={s.titleBlock}>
        <div style={s.galaxyName}>{data.galaxy.toUpperCase()}</div>
        <div style={s.subStats}>
          {data.total_systems.toLocaleString()} STARS · {data.total_regions.toLocaleString()} REGIONS · {data.total_factions} FACTIONS
        </div>
      </div>

      {/* Map + side panel */}
      <div style={s.mapRow}>
        <div style={s.mapBox}>
          <div style={s.compassWrap}><CompassRose size={48} /></div>
          <svg width={MAP_W} height={MAP_H} viewBox={`0 0 ${MAP_W} ${MAP_H}`} style={s.svg} aria-label="Galaxy map">
            <defs>
              {/* Soft elliptical disk glow — tilted galactic plane (3/4 view) */}
              <radialGradient id="diskGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="rgba(60,90,180,0.16)" />
                <stop offset="50%" stopColor="rgba(60,90,180,0.05)" />
                <stop offset="100%" stopColor="rgba(60,90,180,0)" />
              </radialGradient>
            </defs>

            {/* Sparse atmospheric ambient stars (~70 dim points for galactic feel).
                Deterministic per-galaxy. Pure decoration, NOT data. */}
            <BackgroundStarfield seed={hashGalaxyName(data.galaxy)} />

            {/* Soft elliptical glow framing the disk — barely there */}
            <ellipse cx={MAP_W / 2} cy={MAP_H / 2}
              rx={MAP_W * 0.48} ry={MAP_H * 0.34}
              fill="url(#diskGlow)" />
            {/* Faint orbital arc — minimal guide line */}
            <ellipse cx={MAP_W / 2} cy={MAP_H / 2}
              rx={MAP_W * 0.40} ry={MAP_H * 0.26}
              stroke="rgba(0,194,179,0.08)" strokeWidth="0.5" fill="none" strokeDasharray="1 5" />

            {/* TRAILS — same-faction chains rendered as connecting polylines.
                These ARE the colored "lines" in the mockup (Haven trail, EVRN
                corridor, etc). Drawn before dots so dots overlay them. */}
            {trails.map((trail, i) => {
              const color = getTagColorFromAPI(trail.tag) || '#94a3b8'
              const pathStr = trail.points.map((p, j) =>
                `${j === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`
              ).join(' ')
              // Line opacity scales with chain length (stronger = more linear)
              const op = Math.min(0.45, 0.18 + trail.chainLength * 0.012)
              return (
                <path key={`trail-${i}`} d={pathStr}
                  stroke={color} strokeWidth="0.8" fill="none"
                  opacity={op} strokeLinecap="round" strokeLinejoin="round" />
              )
            })}

            {/* REAL DATA: plot every region in the galaxy at its actual
                projected galactic position. Smallest first → biggest on top.
                A dense cluster (e.g. 10 GHUB regions in Euclid) overlaps
                naturally and forms a visible bright spot. */}
            {drawList.map(({ region, point, radius }, i) => {
              const isTop = indexLookup.has(`${region.region_x},${region.region_y},${region.region_z}`)
              if (isTop) return null  // Top-9 drawn separately on top
              const color = getTagColorFromAPI(region.dominant_tag) || '#94a3b8'
              // Bigger dots get higher opacity; tiny ones are dim
              const opacity = 0.55 + Math.min(0.4, radius * 0.07)
              return (
                <circle key={i} cx={point.x} cy={point.y} r={radius}
                  fill={color} opacity={opacity} />
              )
            })}

            {/* Top-9 numbered markers — sit ON TOP of their cluster */}
            {top9.map((nr, i) => {
              const p = projection.get(`${nr.region_x},${nr.region_y},${nr.region_z}`)
              if (!p) return null
              const color = getTagColorFromAPI(nr.dominant_tag) || '#94a3b8'
              return (
                <g key={i}>
                  {/* Inner dot (matches the data dot for that region) */}
                  <circle cx={p.x} cy={p.y} r="2.5" fill={color} opacity={1} />
                  {/* Outline ring + number */}
                  <circle cx={p.x} cy={p.y} r="9" fill="rgba(10,14,42,0.55)"
                    stroke={color} strokeWidth="1" />
                  <text x={p.x} y={p.y + 3} textAnchor="middle" fill={color}
                    fontSize="9" fontWeight="600" fontFamily="monospace">
                    {nr.index_number}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>

        {/* Index panel */}
        <div style={s.indexPanel}>
          <div style={s.panelLabel}>REGIONS · INDEX</div>
          {top9.length === 0 ? (
            <div style={s.emptyHint}>no named regions yet</div>
          ) : top9.map((r, i) => {
            const color = getTagColorFromAPI(r.dominant_tag) || '#94a3b8'
            const display = getDisplayTagName(r.dominant_tag)
            return (
              <div key={i} style={s.indexRow}>
                <div style={{ ...s.indexBadge, borderColor: color, color }}>{r.index_number}</div>
                <div style={s.indexText}>
                  <div style={s.indexName}><em>{r.region_name}</em></div>
                  <div style={s.indexSub}>{r.system_count} stars · {display}</div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Factions panel */}
      <div style={s.factionsPanel}>
        <div style={s.panelLabel}>FACTIONS</div>
        <div style={s.factionsGrid}>
          {data.factions.slice(0, 10).map((f, i) => {
            const color = getTagColorFromAPI(f.tag) || '#94a3b8'
            const display = f.display_name || getDisplayTagName(f.tag)
            return (
              <div key={i} style={s.factionRow}>
                <div style={{ ...s.factionDot, background: color }} />
                <div style={s.factionName}>{display}</div>
                <div style={s.factionCount}>{f.systems.toLocaleString()}</div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Footer */}
      <Watermark />
    </>
  )
}

// ============================================================================
// Background starfield — annular distribution around the galactic disk plus
// a bright core nucleus and a comet trail anomaly. Deterministic per-galaxy.
// ============================================================================

// Mulberry32 PRNG — deterministic, fast, uniform
function makeRng(seed) {
  let s = seed | 0
  return function () {
    s = (s + 0x6D2B79F5) | 0
    let t = Math.imul(s ^ (s >>> 15), 1 | s)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const STAR_PALETTE = [
  'rgba(220,235,255,', // pale blue-white (most common)
  'rgba(220,235,255,',
  'rgba(220,235,255,',
  'rgba(220,235,255,',
  'rgba(255,210,170,', // warm amber
  'rgba(255,180,140,', // orange
  'rgba(180,200,255,', // soft blue
  'rgba(255,180,200,', // soft magenta
  'rgba(200,255,230,', // pale teal
]

function BackgroundStarfield({ seed = 1 }) {
  // Sparse ambient stars ONLY — pure atmospheric decoration, NOT data.
  // No procedural "core" or "comet" — those come naturally from real region
  // clustering plotted by the parent component.
  const r = makeRng(seed)
  const stars = []

  const AMBIENT_COUNT = 75
  for (let i = 0; i < AMBIENT_COUNT; i++) {
    // Uniform random across the entire canvas
    const x = r() * MAP_W
    const y = r() * MAP_H

    // Tiered brightness — almost entirely dim with rare bright accents
    const b = r()
    let radius, alpha
    if (b > 0.96) { radius = 0.9 + r() * 0.5; alpha = 0.75 }       // rare bright (~4%)
    else if (b > 0.78) { radius = 0.5 + r() * 0.25; alpha = 0.45 } // medium (~18%)
    else { radius = 0.3 + r() * 0.2; alpha = 0.22 }                // dim majority (~78%)

    const color = STAR_PALETTE[Math.floor(r() * STAR_PALETTE.length)] + alpha + ')'
    stars.push(<circle key={`a${i}`} cx={x} cy={y} r={radius} fill={color} />)
  }

  return <g aria-hidden="true">{stars}</g>
}

function hashGalaxyName(name) {
  // Simple deterministic 32-bit hash (djb2 variant)
  let h = 5381
  const s = String(name || 'galaxy')
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0
  return h >>> 0 || 1
}

// ============================================================================
// Trail detection — find chains of same-faction regions arranged near-linearly
//
// For each faction, take its regions, sort by region_x, then walk through
// looking for sequences where each region is within MAX_STEP_GALACTIC units
// of the previous one. A chain of 4+ regions becomes a "trail" and is
// rendered as a connecting polyline in the SVG.
//
// This surfaces the real "exploration corridors" in the data — the long thin
// chains of small regions that communities build by exploring outward in a
// straight line. Without this, those chains appear as a blob of ~1px dots
// nobody can see; with it, they pop as the visible trails the mockup shows.
// ============================================================================

const TRAIL_MIN_LENGTH = 4         // chains shorter than this aren't drawn
const TRAIL_MAX_STEP = 250         // max galactic-units gap between chain links
const TRAIL_MAX_PER_TAG = 2        // limit per faction so we don't draw 50

function detectTrails(regions, projection) {
  // Compute signed coords once so distance math respects the wrap-around
  // (a region at raw X=4095 is right next to X=0, not 4095 units away).
  const annotated = regions.map(r => ({
    r,
    sx: toSignedRegion(r.region_x),
    sz: toSignedRegion(r.region_z),
    tag: (r.dominant_tag || 'personal').toLowerCase(),
  }))

  // Group by faction
  const byTag = new Map()
  for (const a of annotated) {
    if (!byTag.has(a.tag)) byTag.set(a.tag, [])
    byTag.get(a.tag).push(a)
  }

  const allTrails = []
  for (const [tag, tagRegions] of byTag.entries()) {
    if (tagRegions.length < TRAIL_MIN_LENGTH) continue

    // Sort by signed X then Z so linear scan finds adjacent regions
    const sorted = [...tagRegions].sort((a, b) => a.sx - b.sx || a.sz - b.sz)
    const used = new Set()
    const chains = []

    for (let i = 0; i < sorted.length; i++) {
      if (used.has(i)) continue
      const chain = [sorted[i]]
      used.add(i)
      let last = sorted[i]
      for (let j = i + 1; j < sorted.length; j++) {
        if (used.has(j)) continue
        const dx = sorted[j].sx - last.sx
        const dz = sorted[j].sz - last.sz
        const dist = Math.sqrt(dx * dx + dz * dz)
        if (dist <= TRAIL_MAX_STEP) {
          chain.push(sorted[j])
          used.add(j)
          last = sorted[j]
        }
      }
      if (chain.length >= TRAIL_MIN_LENGTH) chains.push(chain)
    }

    // Keep only the longest 2 chains per faction (avoid noise)
    chains.sort((a, b) => b.length - a.length)
    for (const chain of chains.slice(0, TRAIL_MAX_PER_TAG)) {
      // Project each chain link to screen — drop any that fall off the disk
      const points = chain
        .map(a => projection.get(`${a.r.region_x},${a.r.region_y},${a.r.region_z}`))
        .filter(Boolean)
      if (points.length >= TRAIL_MIN_LENGTH) {
        allTrails.push({ tag, points, chainLength: chain.length })
      }
    }
  }
  return allTrails
}

// ============================================================================
// Projection — SIGNED galactic coordinates with circular clip
//
// CRITICAL FIX (2026-04-29): NMS region coordinates use a SIGNED-WRAP
// encoding around 2048, not a linear scale.
//   - region_x in 0..2047  → signed +0..+2047  (galactic east)
//   - region_x in 2048..4095 → signed -2048..-1 (galactic west)
//   (Same logic for region_z: 0..2047 = north, 2048..4095 = south.)
//
// Source: backend/glyph_decoder.py lines 140-155.
//
// Without this conversion, GHUB at region_x=3101 renders to galactic east
// when it's actually at galactic west (signed_x = 3101 - 4096 = -995).
// Half of every galaxy ends up flipped to the wrong quadrant.
// ============================================================================

const VISIBLE_DISK_RADIUS = Math.min(MAP_W, MAP_H) * 0.46
const REGION_WRAP = 4096
const REGION_HALF = 2048

/** Convert a raw region coordinate (0..4095) to signed galactic units (-2048..+2047) */
function toSignedRegion(c) {
  return c < REGION_HALF ? c : c - REGION_WRAP
}

// Non-linear radius compression. Real Euclid data has 73% of regions sitting at
// galactic radius 1000-2000 with a sparse inner core — a linear projection makes
// that look like a hollow donut. Applying r' = r^0.6 spreads the inner cluster
// outward and tightens the outer ring inward, producing a disk-like fill.
const RADIUS_POWER = 0.6

function projectGalactic(regions) {
  const out = new Map()
  if (!regions || regions.length === 0) return out

  const cx = MAP_W / 2
  const cy = MAP_H / 2

  const signed = regions.map(r => ({
    r,
    sx: toSignedRegion(r.region_x),
    sz: toSignedRegion(r.region_z),
  }))

  // Pre-compute compressed radii and angles. Fit p95(compressed) to 90% of
  // the visible disk so the densest band lands well inside the frame.
  const compressed = signed.map(s => {
    const galRadius = Math.sqrt(s.sx * s.sx + s.sz * s.sz)
    const angle = Math.atan2(s.sz, s.sx)
    const cr = Math.pow(galRadius, RADIUS_POWER)
    return { s, galRadius, angle, cr }
  })
  const sortedCr = compressed.map(c => c.cr).sort((a, b) => a - b)
  const p95Index = Math.floor(sortedCr.length * 0.95)
  const p95Cr = sortedCr[p95Index] || sortedCr[sortedCr.length - 1] || 1
  const scale = (VISIBLE_DISK_RADIUS * 0.9) / Math.max(p95Cr, 1)

  for (const c of compressed) {
    const screenR = c.cr * scale
    if (screenR > VISIBLE_DISK_RADIUS) continue
    // +signed_z = galactic north = screen up (flip y because screen-Y goes down)
    out.set(`${c.s.r.region_x},${c.s.r.region_y},${c.s.r.region_z}`, {
      x: cx + screenR * Math.cos(c.angle),
      y: cy - screenR * Math.sin(c.angle),
    })
  }
  return out
}

// ============================================================================
// Helpers + styles
// ============================================================================

function CenteredMsg({ title, subtitle }) {
  return (
    <div style={{ padding: 80, textAlign: 'center' }}>
      <div style={{ fontFamily: POSTER_FONTS.serif, fontSize: 32, fontStyle: 'italic', color: POSTER_COLORS.text, marginBottom: 8 }}>{title}</div>
      {subtitle && <div style={{ fontSize: 13, color: POSTER_COLORS.dim }}>{subtitle}</div>}
    </div>
  )
}

const s = {
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 },
  brandRow: { display: 'flex', alignItems: 'center', gap: 10 },
  brandTitle: { fontSize: 12, letterSpacing: 2.5, color: POSTER_COLORS.text, fontWeight: 600 },
  brandSub: { fontSize: 11, color: POSTER_COLORS.accent, letterSpacing: 1, marginTop: 2, fontStyle: 'italic' },
  drawnAt: { fontSize: 10, color: POSTER_COLORS.dim, letterSpacing: 2 },
  titleBlock: { textAlign: 'center', padding: '12px 0 18px' },
  galaxyName: {
    fontFamily: POSTER_FONTS.serif,
    fontSize: 56, fontWeight: 500,
    color: POSTER_COLORS.amber,
    fontStyle: 'italic',
    lineHeight: 1,
  },
  subStats: { fontSize: 11, color: POSTER_COLORS.accent, letterSpacing: 2, marginTop: 14 },
  mapRow: { display: 'grid', gridTemplateColumns: `${MAP_W}px 1fr`, gap: 16, marginBottom: 16 },
  mapBox: { position: 'relative', height: MAP_H },
  svg: { display: 'block' },
  compassWrap: { position: 'absolute', top: 6, left: 6, zIndex: 2 },
  indexPanel: {
    background: POSTER_COLORS.surface,
    border: `1px solid ${POSTER_COLORS.border}`,
    borderRadius: 12,
    padding: 14,
    overflow: 'hidden',
  },
  panelLabel: { fontSize: 10, color: POSTER_COLORS.amber, letterSpacing: 2, marginBottom: 12 },
  indexRow: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 },
  indexBadge: {
    width: 22, height: 22, borderRadius: '50%',
    border: '1.5px solid',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 11, fontWeight: 600, flexShrink: 0,
  },
  indexText: { flex: 1, minWidth: 0 },
  indexName: { fontFamily: POSTER_FONTS.serif, fontSize: 14, fontStyle: 'italic', color: POSTER_COLORS.text, lineHeight: 1.1 },
  indexSub: { fontSize: 9, color: POSTER_COLORS.dim, marginTop: 2, letterSpacing: 1 },
  factionsPanel: {
    background: POSTER_COLORS.surface,
    border: `1px solid ${POSTER_COLORS.border}`,
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
  },
  factionsGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', columnGap: 16, rowGap: 6 },
  factionRow: { display: 'flex', alignItems: 'center', gap: 8 },
  factionDot: { width: 10, height: 10, borderRadius: '50%', flexShrink: 0 },
  factionName: { fontSize: 11, color: POSTER_COLORS.text, flex: 1 },
  factionCount: { fontSize: 11, color: POSTER_COLORS.text, fontWeight: 500 },
  emptyHint: { fontSize: 11, color: POSTER_COLORS.dim, fontStyle: 'italic' },
  legendPanel: {
    background: POSTER_COLORS.surface,
    border: `1px solid ${POSTER_COLORS.border}`,
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
  },
  legendRow: {
    display: 'flex', alignItems: 'center', gap: 10,
    marginBottom: 6,
  },
  legendDot: {
    display: 'inline-block',
    borderRadius: '50%',
    flexShrink: 0,
    marginLeft: 6,
  },
  legendBigMarker: {
    width: 14, height: 14,
    border: '1.2px solid',
    borderRadius: '50%',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  legendBigDot: {
    width: 5, height: 5,
    borderRadius: '50%',
  },
  legendText: { fontSize: 11, color: POSTER_COLORS.text },
}
