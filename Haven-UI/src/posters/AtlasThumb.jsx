import React, { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import PosterFrame, { POSTER_COLORS, POSTER_FONTS } from './_shared/PosterFrame'
import { markPosterReady } from './_shared/ready'
import { fetchTagColorsForPoster, getTagColorFromAPI } from './_shared/colors'

// ============================================================================
// Atlas Thumbnail — 400×400 simplified galaxy disk for Systems-tab cards.
// Same data + projection as the full GalaxyAtlas, no chrome, no panels.
// ============================================================================

const SIZE = 400
const REGION_WRAP = 4096
const REGION_HALF = 2048
const VISIBLE_DISK_RADIUS = SIZE * 0.46

function toSignedRegion(c) {
  return c < REGION_HALF ? c : c - REGION_WRAP
}

export default function AtlasThumb({ routeKey }) {
  const params = useParams()
  const galaxy = routeKey || params.galaxy || 'Euclid'
  const [data, setData] = useState(null)

  useEffect(() => {
    let cancelled = false
    setData(null)
    Promise.all([
      fetchTagColorsForPoster(),
      fetch(`/api/public/galaxy-atlas?galaxy=${encodeURIComponent(galaxy)}`)
        .then(r => r.ok ? r.json() : null),
    ]).then(([_, j]) => {
      if (cancelled) return
      setData(j)
      markPosterReady()
    }).catch(() => {
      if (cancelled) return
      markPosterReady()
    })
    return () => { cancelled = true }
  }, [galaxy])

  const { points, dotMaxCount } = useMemo(() => {
    if (!data) return { points: [], dotMaxCount: 1 }
    const cx = SIZE / 2
    const cy = SIZE / 2
    const RADIUS_POWER = 0.6  // matches GalaxyAtlas — see projectGalactic()
    const compressed = data.regions.map(r => {
      const sx = toSignedRegion(r.region_x)
      const sz = toSignedRegion(r.region_z)
      const galRadius = Math.sqrt(sx * sx + sz * sz)
      return {
        r, sx, sz, galRadius,
        angle: Math.atan2(sz, sx),
        cr: Math.pow(galRadius, RADIUS_POWER),
      }
    })
    const sortedCr = compressed.map(c => c.cr).sort((a, b) => a - b)
    const p95 = sortedCr[Math.floor(sortedCr.length * 0.95)] || 1
    const scale = (VISIBLE_DISK_RADIUS * 0.9) / Math.max(p95, 1)
    const out = []
    let maxCount = 1
    for (const c of compressed) {
      const screenR = c.cr * scale
      if (screenR > VISIBLE_DISK_RADIUS) continue
      out.push({
        x: cx + screenR * Math.cos(c.angle),
        y: cy - screenR * Math.sin(c.angle),
        count: c.r.system_count,
        tag: c.r.dominant_tag,
      })
      if (c.r.system_count > maxCount) maxCount = c.r.system_count
    }
    return { points: out, dotMaxCount: maxCount }
  }, [data])

  const sortedPoints = useMemo(
    () => [...points].sort((a, b) => a.count - b.count),
    [points]
  )

  return (
    <PosterFrame width={SIZE} height={SIZE} padded={false}>
      <div style={{
        width: SIZE, height: SIZE,
        position: 'relative',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: POSTER_COLORS.bgPoster,
        overflow: 'hidden',
      }}>
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
          <defs>
            <radialGradient id="thumbGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(60,90,180,0.18)" />
              <stop offset="100%" stopColor="rgba(60,90,180,0)" />
            </radialGradient>
          </defs>
          <ellipse cx={SIZE / 2} cy={SIZE / 2}
            rx={SIZE * 0.48} ry={SIZE * 0.34}
            fill="url(#thumbGlow)" />
          <ellipse cx={SIZE / 2} cy={SIZE / 2}
            rx={SIZE * 0.40} ry={SIZE * 0.26}
            stroke="rgba(0,194,179,0.12)" strokeWidth="0.6" fill="none" strokeDasharray="2 4" />
          {sortedPoints.map((p, i) => {
            const ratio = Math.log(p.count + 1) / Math.log(dotMaxCount + 1)
            const radius = 0.6 + ratio * 4.5
            const color = getTagColorFromAPI(p.tag) || '#94a3b8'
            const opacity = 0.65 + Math.min(0.3, radius * 0.06)
            return (
              <circle key={i} cx={p.x} cy={p.y} r={radius}
                fill={color} opacity={opacity} />
            )
          })}
        </svg>
        <div style={{
          position: 'absolute', bottom: 12, left: 14,
          fontFamily: POSTER_FONTS.serif, fontSize: 22,
          fontStyle: 'italic', color: POSTER_COLORS.amber,
          letterSpacing: 1, textShadow: '0 2px 8px rgba(0,0,0,0.8)',
        }}>{data?.galaxy || galaxy}</div>
        {data && (
          <div style={{
            position: 'absolute', bottom: 14, right: 14,
            fontFamily: POSTER_FONTS.mono, fontSize: 10,
            color: POSTER_COLORS.dim, letterSpacing: 1, textAlign: 'right',
          }}>
            {data.total_systems.toLocaleString()} stars<br />
            {data.total_factions} factions
          </div>
        )}
      </div>
    </PosterFrame>
  )
}
