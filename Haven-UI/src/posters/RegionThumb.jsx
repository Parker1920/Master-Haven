import React, { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'

import PosterFrame, { POSTER_COLORS, POSTER_FONTS } from './_shared/PosterFrame'
import { markPosterReady } from './_shared/ready'
import { fetchTagColorsForPoster, getTagColorFromAPI } from './_shared/colors'

// ============================================================================
// Region Thumbnail — 600×300, banner-aspect 2:1.
//
// Visualises a single region as a 3D voxel cube with each contained star
// system placed at its deterministic position inside the region. Positions
// come straight from `star_x/star_y/star_z` on each system row — those are
// computed once in backend/glyph_decoder.calculate_star_position_in_region()
// via SHA-256 of (region_x, region_y, region_z, solar_system_index).
//
// Cube is 128×128×128 coord units (NMS region size). We render an isometric
// projection (30°-cabinet) with the cube edges traced lightly and each star
// drawn as a tiny dot whose color picks the community tag with a star-type
// tint as fallback. The whole thing is overlaid with the region name and
// canonical coords so it looks at home next to the galaxy poster.
//
// URL: /poster/region_thumb/<rx>_<ry>_<rz>?galaxy=Euclid&reality=Normal
// ============================================================================

const W = 600
const H = 300

// Iso projection: x → right, z → right+down, y → up. Tilt + scale are tuned
// so a full 128-unit region fills ~70% of the canvas.
const ISO_COS = Math.cos(Math.PI / 6) // cos 30°
const ISO_SIN = Math.sin(Math.PI / 6)
// Edge length on screen for one region. Bumped from 200 → 280 (Parker
// 2026-05-11): the left half of the 600px poster has ~340px of usable
// width before the 260px text panel, so the cube was leaving a lot of
// empty space. 280 fills the canvas without crowding the text column.
const CUBE_PX = 280

function project(localX, localY, localZ) {
  // localX/localY/localZ are in [-64, +64] (a 128-cube centered at 0).
  const scale = CUBE_PX / 128
  const x = localX * scale
  const y = localY * scale
  const z = localZ * scale
  const sx = (x - z) * ISO_COS
  const sy = (x + z) * ISO_SIN - y
  return [sx, sy]
}

// Star-type colors — per Parker (2026-05-11): dots show the actual star
// color (not the community tag). Community color now goes on the OUTER
// border so both bits of info still read at a glance.
const STAR_TINT = {
  Yellow: '#facc15',
  Blue: '#60a5fa',
  Red: '#ef4444',
  Green: '#34d399',
  Purple: '#a855f7',
}

// Pick the community color that owns the region — that's whichever
// discord_tag has the most systems inside it. Falls back to muted neutral
// when the region has no tagged systems.
function dominantTagColor(systems, getColor) {
  if (!Array.isArray(systems) || systems.length === 0) return null
  const counts = new Map()
  for (const s of systems) {
    const tag = s.discord_tag
    if (!tag || tag === 'personal') continue
    counts.set(tag, (counts.get(tag) || 0) + 1)
  }
  if (counts.size === 0) return null
  let bestTag = null, bestCount = 0
  for (const [tag, count] of counts) {
    if (count > bestCount) { bestTag = tag; bestCount = count }
  }
  return { tag: bestTag, color: getColor(bestTag), share: bestCount / systems.length }
}

export default function RegionThumb({ routeKey }) {
  const params = useParams()
  const [search] = useSearchParams()
  const key = routeKey || params.key || ''
  const [rx, ry, rz] = key.split('_').map((s) => parseInt(s, 10))
  const galaxy = search.get('galaxy') || 'Euclid'
  const reality = search.get('reality') || 'Normal'

  const [data, setData] = useState(null)
  const [region, setRegion] = useState(null)

  useEffect(() => {
    if (Number.isNaN(rx) || Number.isNaN(ry) || Number.isNaN(rz)) {
      markPosterReady()
      return
    }
    let cancelled = false
    Promise.all([
      fetchTagColorsForPoster(),
      fetch(`/api/regions/${rx}/${ry}/${rz}/systems?reality=${encodeURIComponent(reality)}&galaxy=${encodeURIComponent(galaxy)}&limit=600`)
        .then((r) => (r.ok ? r.json() : null)),
      fetch(`/api/regions/${rx}/${ry}/${rz}?reality=${encodeURIComponent(reality)}&galaxy=${encodeURIComponent(galaxy)}`)
        .then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([_, sys, reg]) => {
        if (cancelled) return
        setData(sys)
        setRegion(reg)
        markPosterReady()
      })
      .catch(() => {
        if (cancelled) return
        markPosterReady()
      })
    return () => { cancelled = true }
  }, [rx, ry, rz, galaxy, reality])

  const points = useMemo(() => {
    if (!data || !data.systems) return []
    return data.systems
      .map((s) => {
        // Convert region grid coords to signed center
        const baseX = s.region_x <= 0x7FF ? s.region_x : s.region_x - 0x1000
        const baseY = s.region_y <= 0x7F ? s.region_y : s.region_y - 0x100
        const baseZ = s.region_z <= 0x7FF ? s.region_z : s.region_z - 0x1000
        // star_x/star_y/star_z are absolute galaxy coords; subtract region
        // origin to get local position in [-64, +64].
        let lx = (s.star_x ?? baseX) - baseX
        let ly = (s.star_y ?? baseY) - baseY
        let lz = (s.star_z ?? baseZ) - baseZ
        lx = Math.max(-64, Math.min(64, lx))
        ly = Math.max(-64, Math.min(64, ly))
        lz = Math.max(-64, Math.min(64, lz))
        // Star color drives the dot (per Parker's spec change). Untyped
        // stars get a muted gray so they're visible but secondary.
        const tint = STAR_TINT[s.star_type] || 'rgba(255,255,255,0.45)'
        return { lx, ly, lz, tint, name: s.name }
      })
      .sort((a, b) => (a.lz + a.lx) - (b.lz + b.lx)) // back-to-front (painter)
  }, [data])

  // Outer-frame color = dominant community tag in this region.
  const tagFrame = useMemo(() => dominantTagColor(data?.systems || [], getTagColorFromAPI), [data])

  const named = !!region?.custom_name
  const displayName = region?.custom_name || `Region (${rx}, ${ry}, ${rz})`
  // STARS reads from the region row (canonical count), not the fetch length
  // — fetches cap at 600 so dense regions used to underreport.
  const systemCount = region?.system_count ?? data?.systems?.length ?? 0

  // Cube vertices for the wireframe
  const cubeEdges = useMemo(() => {
    const v = []
    for (const x of [-64, 64]) for (const y of [-64, 64]) for (const z of [-64, 64]) v.push([x, y, z])
    const projected = v.map((c) => project(...c))
    // 12 edges of a cube indexed against v[]
    const idx = [
      [0,1],[0,2],[0,4],[1,3],[1,5],[2,3],
      [2,6],[3,7],[4,5],[4,6],[5,7],[6,7],
    ]
    return idx.map(([a, b]) => [projected[a], projected[b]])
  }, [])

  // Center the projection inside the left ~340px (text panel claims the
  // right 260). Cube grew from 200 → 280, so cx nudged right to keep it
  // optically centered in the available column.
  const cx = 165
  const cy = H / 2

  // Frame color sourced from dominant community tag; falls back to teal.
  const frameColor = tagFrame?.color || POSTER_COLORS.primary
  return (
    <PosterFrame width={W} height={H} padded={false}>
      {/* Outer 4px frame — community tag color */}
      <div style={{
        position: 'absolute', inset: 0,
        border: `4px solid ${frameColor}`,
        borderRadius: 0,
        pointerEvents: 'none',
        zIndex: 30,
      }} />
      <div style={{
        position: 'absolute', inset: 0,
        background: `radial-gradient(120% 70% at 35% 50%, rgba(157,78,221,0.16) 0%, transparent 60%), linear-gradient(135deg, #0f1538 0%, ${POSTER_COLORS.bgPoster} 100%)`,
      }} />

      {/* Starfield speckles */}
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: 'absolute', inset: 0 }}>
        {Array.from({ length: 60 }).map((_, i) => {
          const x = (i * 89.123) % W
          const y = (i * 47.7) % H
          const r = ((i * 7) % 3 === 0) ? 0.7 : 0.35
          return <circle key={i} cx={x} cy={y} r={r} fill="rgba(255,255,255,0.35)" />
        })}

        {/* Cube wireframe — draw centered at (cx, cy) */}
        <g transform={`translate(${cx}, ${cy})`}>
          {cubeEdges.map(([a, b], i) => (
            <line key={i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="rgba(0,194,179,0.25)" strokeWidth={0.6} strokeDasharray="2 3" />
          ))}
          {/* Light cube fill on the "back" face */}
          <polygon points={[
            project(-64, -64, 64).join(','),
            project( 64, -64, 64).join(','),
            project( 64,  64, 64).join(','),
            project(-64,  64, 64).join(','),
          ].join(' ')} fill="rgba(60,90,180,0.05)" />

          {/* Points — dot radius bumped 1.5 → 2 alongside the larger
              cube so stars stay legible at the new scale. */}
          {points.map((p, i) => {
            const [sx, sy] = project(p.lx, p.ly, p.lz)
            return <circle key={i} cx={sx} cy={sy} r={2} fill={p.tint} opacity={0.9} />
          })}
        </g>
      </svg>

      {/* Text overlay — right side */}
      <div style={{
        position: 'absolute', top: 0, right: 0, bottom: 0, width: 260,
        padding: 24, display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{
            fontFamily: POSTER_FONTS.mono, fontSize: 9, letterSpacing: 2,
            color: POSTER_COLORS.dim, marginBottom: 6,
          }}>
            VOYAGER'S HAVEN · REGION
          </div>
          <div style={{
            fontFamily: POSTER_FONTS.serif, fontSize: 28, fontStyle: 'italic',
            color: named ? POSTER_COLORS.amber : POSTER_COLORS.text,
            lineHeight: 1.05, letterSpacing: 0.5,
            textShadow: '0 2px 12px rgba(0,0,0,0.6)',
          }}>
            {displayName}
          </div>
          <div style={{
            fontFamily: POSTER_FONTS.mono, fontSize: 10, color: POSTER_COLORS.dim,
            marginTop: 6, letterSpacing: 1.5,
          }}>
            {rx} · {ry} · {rz}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Stat label="STARS" value={systemCount.toLocaleString()} />
          <Stat label="GALAXY" value={galaxy} />
          <Stat label="REALITY" value={reality} />
        </div>
      </div>
    </PosterFrame>
  )
}

function Stat({ label, value }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
      paddingTop: 6,
      borderTop: '1px solid rgba(255,255,255,0.08)',
    }}>
      <span style={{
        fontFamily: POSTER_FONTS.mono, fontSize: 9, letterSpacing: 1.5,
        color: POSTER_COLORS.dim,
      }}>{label}</span>
      <span style={{
        fontFamily: POSTER_FONTS.mono, fontSize: 13,
        color: POSTER_COLORS.text, fontWeight: 600,
      }}>{value}</span>
    </div>
  )
}
