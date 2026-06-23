import React, { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'

import PosterFrame, { POSTER_COLORS, POSTER_FONTS } from './_shared/PosterFrame'
import { markPosterReady } from './_shared/ready'
import { fetchTagColorsForPoster, getTagColorFromAPI, getDisplayTagName } from './_shared/colors'
// Use the shared StatTile so SystemThumb and WizardAdvancedPreview stay in
// visual sync. Parker (2026-05-11) was right that earlier "make tiles bigger"
// edits to the shared component never propagated here — SystemThumb had its
// own local Stat() function with the original 8/13/9 px fonts. Removing that
// in favor of the shared <StatTile> with 19/24/16 fonts.
import StatTile from '../components/shared/StatTile'
import { glyphImageSrc } from '../utils/glyphAssets'
import { GRADE_BADGE } from '../utils/gradeColors'
import { biomeTintHex } from '../data/biomeCategoryMappings'
import { STAR_HEX } from '../utils/starColors'

// ============================================================================
// System Thumbnail — 600×400 landscape card.
//
// Visual:
//   - Top eyebrow:   VOYAGER'S HAVEN · STAR SYSTEM
//   - Left half:     orbital diagram (real planet count, biome-tinted dots,
//                    smaller dots for moons, star color from star_type,
//                    space-station rendered as the outside diamond marker)
//   - Right half:    name + galaxy/reality + 2×3 stat tile grid
//   - Bottom strip:  12-glyph icon row decoded from glyph_code, using the
//                    transparent festival glyph art (public/glyphs/{0-F}.webp)
//                    rendered straight onto the chip — no blend-mode hack
//                    needed now that the art has a clear background.
//
// Per Parker (system-poster spec, this session):
//   A landscape · B real planet count + biome + moons · C star color
//   D stats = economy, conflict, planets/moons, grade, author, tag
//   E glyph row · F space station = diamond marker
// ============================================================================

// Native canvas bumped 600x400 → 720x480 + internal font sizes scaled up
// (Parker 2026-05-11: the 6 stat tiles were unreadable when displayed in
// the L4 card grid at ~250px wide, since fonts were sized for the native
// poster view, not the scaled-down card view). Aspect stays 3:2.
const W = 720
const H = 480

// Grade tile colors single-sourced from gradeColors.js (S+ / S / A / B / C).
const GRADE_BG = GRADE_BADGE

export default function SystemThumb({ routeKey }) {
  const params = useParams()
  const [search] = useSearchParams()
  const systemId = routeKey || params.key || params.id
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!systemId) { markPosterReady(); return }
    let cancelled = false
    Promise.all([
      fetchTagColorsForPoster(),
      fetch(`/api/systems/${encodeURIComponent(systemId)}`).then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([_, j]) => {
        if (cancelled) return
        if (!j) setError('not found')
        else setData(j)
        markPosterReady()
      })
      .catch(() => { if (!cancelled) { setError('error'); markPosterReady() } })
    return () => { cancelled = true }
  }, [systemId])

  // Hooks must run on every render (React Rules of Hooks) — compute glyph
  // chars BEFORE the early-return so the hook count is stable.
  const glyphChars = useGlyphChars(data?.glyph_code)

  if (error || !data) {
    return (
      <PosterFrame width={W} height={H}>
        <Centered text={error ? 'System unavailable' : 'Loading…'} />
      </PosterFrame>
    )
  }

  const starColor = STAR_HEX[data.star_type] || STAR_HEX.Yellow
  const planets = (data.planets || []).filter((p) => !p.is_moon)
  const moonsByPlanet = (data.planets || []).reduce((acc, p) => acc + (p.moons?.length ?? 0), 0)
  const hasStation = !!(data.space_station)
  const grade = data.completeness_grade || gradeFromScore(data.is_complete)
  const score = data.completeness_score ?? data.is_complete
  const tag = data.discord_tag || 'Personal'
  const tagColor = getTagColorFromAPI(tag) || POSTER_COLORS.primary
  const author = data.discovered_by || data.personal_discord_username || '—'

  return (
    <PosterFrame width={W} height={H} padded={false}>
      {/* Backdrop — starfield + radial glow from the star */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `radial-gradient(60% 60% at 28% 50%, ${starColor}22 0%, transparent 65%), linear-gradient(135deg, #0f1538 0%, ${POSTER_COLORS.bgPoster} 100%)`,
      }} />
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: 'absolute', inset: 0 }}>
        {Array.from({ length: 70 }).map((_, i) => {
          const x = (i * 97.7) % W
          const y = (i * 49.3) % H
          const r = ((i * 13) % 4 === 0) ? 0.8 : 0.4
          return <circle key={i} cx={x} cy={y} r={r} fill="rgba(255,255,255,0.40)" />
        })}
      </svg>

      {/* Header eyebrow */}
      <div style={{
        position: 'absolute', top: 16, left: 28, right: 28,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontFamily: POSTER_FONTS.mono, fontSize: 11, letterSpacing: 2,
        color: POSTER_COLORS.dim,
        fontWeight: 600,
      }}>
        <span>VOYAGER'S HAVEN · STAR SYSTEM</span>
        {hasStation && (
          <span style={{ color: POSTER_COLORS.primary, letterSpacing: 1.5, fontWeight: 700 }}>
            ◆ STATION
          </span>
        )}
      </div>

      {/* Main row: orbital diagram + text panel */}
      <div style={{
        position: 'absolute', top: 46, left: 28, right: 28, bottom: 84,
        display: 'flex', gap: 22,
      }}>
        <div style={{ width: 240, flexShrink: 0, position: 'relative' }}>
          <OrbitalDiagram
            star={starColor}
            planets={planets}
            moons={data.planets || []}
            hasStation={hasStation}
          />
        </div>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <div style={{
              fontFamily: POSTER_FONTS.serif, fontSize: 32, fontStyle: 'italic',
              color: POSTER_COLORS.text, lineHeight: 1.05,
              textShadow: '0 2px 12px rgba(0,0,0,0.5)',
            }}>
              {data.name || 'Unknown'}
            </div>
            <div style={{
              fontFamily: POSTER_FONTS.mono, fontSize: 14, letterSpacing: 1.4,
              color: POSTER_COLORS.dim, marginTop: 4,
              fontWeight: 500,
            }}>
              {data.galaxy || 'Euclid'} · {data.reality || 'Normal'}
            </div>
          </div>

          {/* 2-col tile grid (was 3-col) so each of the 6 stat tiles gets
              ~200 px of horizontal room instead of ~130 px — fonts inside
              StatTile bumped up to read clearly at L4 card scale. */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7,
          }}>
            <StatTile label="ECONOMY" value={data.economy_type || '—'} sub={data.economy_level || null} />
            <StatTile label="CONFLICT" value={data.conflict_level || '—'} valueColor={conflictColor(data.conflict_level)} />
            <StatTile label="PLANETS / MOONS" value={`${planets.length} / ${moonsByPlanet}`} />
            <StatTile
              label="GRADE"
              value={grade}
              sub={score != null ? `${score}%` : null}
              tile={grade && GRADE_BG[grade]}
            />
            <StatTile label="AUTHOR" value={author} truncate />
            <StatTile
              label="TAG"
              value={getDisplayTagName(tag)}
              valueColor={tagColor}
            />
          </div>
        </div>
      </div>

      {/* Glyph row */}
      <div style={{
        position: 'absolute', bottom: 18, left: 28, right: 28,
        display: 'flex', alignItems: 'center', gap: 5,
      }}>
        {glyphChars.length === 12 ? (
          glyphChars.map((c, i) => <GlyphIcon key={i} hex={c} />)
        ) : (
          <span style={{
            fontFamily: POSTER_FONTS.mono, fontSize: 13, color: POSTER_COLORS.dim,
            letterSpacing: 2, fontWeight: 600,
          }}>
            GLYPH PENDING
          </span>
        )}
        <div style={{ flex: 1 }} />
        {glyphChars.length === 12 && (
          <span style={{
            fontFamily: POSTER_FONTS.mono, fontSize: 13, color: POSTER_COLORS.dim,
            letterSpacing: 1.5, fontWeight: 500,
          }}>
            {glyphChars.join('')}
          </span>
        )}
      </div>
    </PosterFrame>
  )
}

// ============================================================================
// Sub-components
// ============================================================================

function OrbitalDiagram({ star, planets, moons, hasStation }) {
  // Render a 240x240 orbital system.
  // - Star at center, glow + solid core
  // - Real planet count, even angular spacing around concentric orbits
  // - Biome tint via biomeTintHex (adjective -> parent category -> hex)
  // - Smaller moon dots offset from their planet
  // - Space station: purple diamond marker on the outer ring
  const SIZE = 240
  const CX = SIZE / 2
  const CY = SIZE / 2

  // Compute orbital radii — evenly spaced ramp, capped at 100px
  const N = Math.max(1, Math.min(planets.length, 6))
  const innerR = 38
  const outerR = 100
  const orbitR = (i) => N === 1 ? (innerR + outerR) / 2 : innerR + (outerR - innerR) * (i / (N - 1))

  return (
    <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}
      style={{ position: 'absolute', inset: '50% auto auto 50%', transform: 'translate(-50%, -50%)' }}>
      {/* Orbit rings */}
      {planets.map((_, i) => (
        <circle key={`ring-${i}`}
          cx={CX} cy={CY} r={orbitR(i)}
          fill="none"
          stroke="rgba(255,255,255,0.12)" strokeWidth={0.6}
        />
      ))}

      {/* Star glow + core */}
      <defs>
        <radialGradient id="starGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={star} stopOpacity="0.9" />
          <stop offset="40%" stopColor={star} stopOpacity="0.35" />
          <stop offset="100%" stopColor={star} stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx={CX} cy={CY} r={50} fill="url(#starGlow)" />
      <circle cx={CX} cy={CY} r={18} fill={star} />

      {/* Planet dots */}
      {planets.map((p, i) => {
        const angle = (i / Math.max(1, planets.length)) * Math.PI * 2 - Math.PI / 2
        const r = orbitR(i)
        const px = CX + r * Math.cos(angle)
        const py = CY + r * Math.sin(angle)
        const tint = biomeTintHex(p.biome) || POSTER_COLORS.primary
        const planetRow = moons.find((m) => m.id === p.id) || p
        const planetMoons = planetRow.moons || []
        return (
          <g key={`p-${i}`}>
            <circle cx={px} cy={py} r={6} fill={tint} opacity="0.95" />
            {/* Moons — render up to 3 around the planet at small offset */}
            {planetMoons.slice(0, 3).map((m, mi) => {
              const ma = mi * (Math.PI * 2 / 3) + angle
              const mr = 11
              const mx = px + mr * Math.cos(ma)
              const my = py + mr * Math.sin(ma)
              return <circle key={`m-${i}-${mi}`} cx={mx} cy={my} r={2} fill={tint} opacity="0.7" />
            })}
          </g>
        )
      })}

      {/* Space station diamond — sits outside the outermost orbit */}
      {hasStation && (
        <g transform={`translate(${CX}, ${CY - outerR - 16}) rotate(45)`}>
          <rect x={-5} y={-5} width={10} height={10}
            fill="none" stroke={POSTER_COLORS.accent} strokeWidth={1.5} />
        </g>
      )}
    </svg>
  )
}

// (Local Stat() function removed 2026-05-11 — replaced by the shared
//  <StatTile> import at the top. Parker caught that this orphan was
//  serving the original 8/13/9 px fonts while the shared component had
//  been bumped to 19/24/16.)

function GlyphIcon({ hex }) {
  const src = glyphImageSrc(hex)
  // Bumped 28→36 (Parker 2026-05-11) for legibility at L4 card scale.
  if (!src) return <span style={{ width: 36, height: 36 }} />
  return (
    <div style={{
      width: 36, height: 36,
      borderRadius: 5,
      border: '1px solid rgba(255,255,255,0.08)',
      background: 'rgba(0,0,0,0.30)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      overflow: 'hidden',
    }}>
      <img
        src={src}
        alt={hex}
        style={{ width: 30, height: 30, objectFit: 'contain' }}
      />
    </div>
  )
}

function Centered({ text }) {
  return (
    <div style={{
      position: 'absolute', inset: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: POSTER_FONTS.mono, fontSize: 14, color: POSTER_COLORS.dim,
    }}>
      {text}
    </div>
  )
}

function useGlyphChars(glyphCode) {
  return useMemo(() => {
    const g = (glyphCode || '').trim().toUpperCase().replace(/[-\s]/g, '')
    if (g.length !== 12) return []
    return g.split('')
  }, [glyphCode])
}

function gradeFromScore(score) {
  if (score == null) return '—'
  if (score >= 85) return 'S'
  if (score >= 65) return 'A'
  if (score >= 40) return 'B'
  return 'C'
}

function conflictColor(level) {
  if (level === 'Low') return '#34d399'
  if (level === 'High') return '#fca5a5'
  if (level === 'Pirate') return '#a855f7'
  return undefined
}
