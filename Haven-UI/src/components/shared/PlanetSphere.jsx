import React from 'react'
import { biomeTintHex } from '../../data/biomeCategoryMappings'

// Parametric planet/moon illustration. Renders a stylized sphere whose
// look is a function of the body's properties — biome color, atmospheric
// glow, ring overlay if has_rings, water sheen if water_world, dissonant
// dashed-orbit overlay if is_dissonant, storm swirl if extreme_weather,
// gas-giant banded gradient + larger radius, bubble translucent shell.
//
// Photo, if present, overrides everything except the moon dots and the
// special-feature overlays.
//
// Used as the always-visible visual at the top of <PlanetCard> and
// <MoonCard> when no photo is attached. Same component is reused for
// moons by passing is_moon=true (renders smaller, no moon dots of its
// own, no rings).

export default function PlanetSphere({
  size = 200,
  biome,
  photo,
  hasRings = false,
  waterWorld = false,
  isDissonant = false,
  extremeWeather = false,
  isGasGiant = false,
  isBubble = false,
  isFloatingIslands = false,
  isMoon = false,
  moonCount = 0,
  exoticTrophy = null,
  index = null,
  badge = null,  // small badge label e.g. "P1" / "M1"
}) {
  const tint = biomeTintHex(biome) || (isMoon ? '#94a3b8' : 'rgba(255,255,255,0.30)')
  const cx = size / 2
  const cy = size / 2
  // Sphere radius. Gas giants render larger; moons smaller.
  const baseR = isMoon ? size * 0.22 : isGasGiant ? size * 0.34 : size * 0.28
  const ringRx = baseR + size * 0.07
  const ringRy = size * 0.03

  // Photo override: use the photo as the sphere fill. Photos rendered as
  // a clipped circle behind any special-feature overlays.
  const usePhoto = photo && typeof photo === 'string' && photo.length > 0
  const photoUrl = usePhoto ? (photo.startsWith('http') || photo.startsWith('/')
    ? photo
    : `/haven-ui-photos/${photo.split(/[/\\]/).pop()}`) : null

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-hidden="true"
      style={{ display: 'block' }}
    >
      <defs>
        <radialGradient id={`bg-${biome || 'none'}-${size}`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={tint} stopOpacity="0.18" />
          <stop offset="100%" stopColor={tint} stopOpacity="0" />
        </radialGradient>
        <radialGradient id={`sphere-${biome || 'none'}-${size}`} cx="35%" cy="32%" r="65%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity={isMoon ? '0.45' : '0.55'} />
          <stop offset="40%" stopColor={tint} stopOpacity="0.85" />
          <stop offset="100%" stopColor={tint} stopOpacity="0.25" />
        </radialGradient>
        {isGasGiant && (
          <linearGradient id={`bands-${size}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={tint} stopOpacity="0" />
            <stop offset="33%" stopColor={tint} stopOpacity="0.35" />
            <stop offset="50%" stopColor="#000" stopOpacity="0.20" />
            <stop offset="66%" stopColor={tint} stopOpacity="0.35" />
            <stop offset="100%" stopColor={tint} stopOpacity="0" />
          </linearGradient>
        )}
        <clipPath id={`clip-${size}-${biome || 'none'}`}>
          <circle cx={cx} cy={cy} r={baseR} />
        </clipPath>
      </defs>

      {/* Atmospheric glow */}
      <circle cx={cx} cy={cy} r={baseR + size * 0.20} fill={`url(#bg-${biome || 'none'}-${size})`} />

      {/* Dissonant dashed outer orbit */}
      {isDissonant && (
        <circle
          cx={cx}
          cy={cy}
          r={baseR + size * 0.10}
          fill="none"
          stroke="#a855f7"
          strokeWidth={size * 0.005}
          strokeDasharray={`${size * 0.012} ${size * 0.020}`}
          opacity="0.7"
        />
      )}

      {/* Ring (drawn behind sphere if has_rings) */}
      {hasRings && !isMoon && (
        <ellipse
          cx={cx}
          cy={cy}
          rx={ringRx + size * 0.04}
          ry={ringRy + size * 0.012}
          fill="none"
          stroke={tint}
          strokeWidth={size * 0.012}
          opacity="0.55"
        />
      )}

      {/* Sphere core */}
      {usePhoto ? (
        <image
          href={photoUrl}
          x={cx - baseR}
          y={cy - baseR}
          width={baseR * 2}
          height={baseR * 2}
          preserveAspectRatio="xMidYMid slice"
          clipPath={`url(#clip-${size}-${biome || 'none'})`}
        />
      ) : (
        <circle cx={cx} cy={cy} r={baseR} fill={`url(#sphere-${biome || 'none'}-${size})`} />
      )}

      {/* Gas giant banding */}
      {isGasGiant && !usePhoto && (
        <rect
          x={cx - baseR}
          y={cy - baseR}
          width={baseR * 2}
          height={baseR * 2}
          fill={`url(#bands-${size})`}
          clipPath={`url(#clip-${size}-${biome || 'none'})`}
          opacity="0.6"
        />
      )}

      {/* Water world: bright highlight crescent */}
      {waterWorld && !usePhoto && (
        <ellipse
          cx={cx - baseR * 0.25}
          cy={cy - baseR * 0.30}
          rx={baseR * 0.45}
          ry={baseR * 0.20}
          fill="#ffffff"
          opacity="0.30"
          clipPath={`url(#clip-${size}-${biome || 'none'})`}
        />
      )}

      {/* Storm swirl for extreme weather */}
      {extremeWeather && (
        <path
          d={`M ${cx - baseR * 0.35} ${cy} a ${baseR * 0.30} ${baseR * 0.12} 0 0 1 ${baseR * 0.70} 0 a ${baseR * 0.18} ${baseR * 0.08} 0 0 0 -${baseR * 0.40} 0`}
          fill="none"
          stroke="rgba(255,255,255,0.60)"
          strokeWidth={size * 0.006}
          clipPath={`url(#clip-${size}-${biome || 'none'})`}
        />
      )}

      {/* Bubble planet: translucent shell halo */}
      {isBubble && (
        <circle
          cx={cx}
          cy={cy}
          r={baseR + size * 0.04}
          fill="none"
          stroke="#a855f7"
          strokeWidth={size * 0.008}
          opacity="0.45"
        />
      )}

      {/* Ring front-half (over sphere, for depth) */}
      {hasRings && !isMoon && (
        <path
          d={`M ${cx - ringRx - size * 0.04} ${cy} A ${ringRx + size * 0.04} ${ringRy + size * 0.012} 0 0 0 ${cx + ringRx + size * 0.04} ${cy}`}
          fill="none"
          stroke={tint}
          strokeWidth={size * 0.012}
          opacity="0.85"
        />
      )}

      {/* Moons — small dots at orbital positions */}
      {!isMoon && moonCount > 0 && (
        <g>
          {Array.from({ length: Math.min(moonCount, 4) }).map((_, i) => {
            const angle = (i / Math.max(1, Math.min(moonCount, 4))) * Math.PI * 2 - Math.PI / 2 + Math.PI / 6
            const orbitR = baseR + size * 0.16
            const mx = cx + orbitR * Math.cos(angle)
            const my = cy + orbitR * Math.sin(angle)
            return (
              <circle
                key={i}
                cx={mx}
                cy={my}
                r={size * 0.025}
                fill={tint}
                opacity="0.85"
              />
            )
          })}
        </g>
      )}

      {/* Floating islands accent — a small upper detail circle */}
      {isFloatingIslands && (
        <circle
          cx={cx + baseR * 0.45}
          cy={cy - baseR * 0.45}
          r={size * 0.018}
          fill="#fbbf24"
          opacity="0.85"
        />
      )}

      {/* Exotic trophy small star marker */}
      {exoticTrophy && (
        <text
          x={cx + baseR * 0.5}
          y={cy + baseR * 0.55}
          fontSize={size * 0.08}
          fill="#fbbf24"
          textAnchor="middle"
        >★</text>
      )}

      {/* Badge label (P1 / M1) */}
      {badge && (
        <g>
          <rect
            x={size * 0.04}
            y={size * 0.04}
            width={size * 0.16}
            height={size * 0.10}
            rx={size * 0.012}
            fill="rgba(0,0,0,0.65)"
          />
          <text
            x={size * 0.12}
            y={size * 0.115}
            fontSize={size * 0.07}
            fontFamily='"JetBrains Mono", "SF Mono", "Consolas", monospace'
            fontWeight="700"
            fill="white"
            textAnchor="middle"
          >{badge}</text>
        </g>
      )}
    </svg>
  )
}

