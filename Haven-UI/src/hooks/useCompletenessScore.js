// Wizard v1 (May 2026): live completeness score for the wizard's progress bar
// + grade guidance panel.
//
// This is a CLIENT-SIDE approximation of services/completeness.py — used
// purely for live UI feedback. The authoritative score is computed by the
// backend on save/approve. Frontend score lets the user see "+15 to next
// grade" suggestions before submitting.
//
// Grade thresholds match constants.py: S(85+) A(65+) B(40+) C(<40).
// Total weights ~= backend (35 + 10 + 5 + 50 spread across planets).

import { useMemo } from 'react'

const NO_LIFE_BIOMES = new Set(['Dead', 'Airless', 'Gas Giant'])

function isFilled(val, { allowNone = false } = {}) {
  if (val == null) return false
  const s = String(val).trim()
  if (!s) return false
  if (s === 'N/A') return false
  if (s === 'None' && !allowNone) return false
  return true
}

function isAbandoned(system) {
  const t = system?.economy_type
  return t === 'None' || t === 'Abandoned'
}

const SYS_CORE_FIELDS = [
  { key: 'star_type', label: 'Star Color' },
  { key: 'economy_type', label: 'Economy Type' },
  { key: 'economy_level', label: 'Economy Tier' },
  { key: 'conflict_level', label: 'Conflict Level' },
  { key: 'dominant_lifeform', label: 'Dominant Lifeform' },
]

const SYS_EXTRA_FIELDS = [
  { key: 'glyph_code', label: 'Glyph Code' },
  { key: 'stellar_classification', label: 'Spectral Class' },
  { key: 'description', label: 'Description' },
]

export default function useCompletenessScore(system) {
  return useMemo(() => {
    if (!system) return { score: 0, grade: 'C', breakdown: [], gaps: [] }

    const breakdown = []
    const gaps = []

    // --- System Core (35 pts) ---
    let coreFilled = 0
    const abandoned = isAbandoned(system)
    SYS_CORE_FIELDS.forEach(({ key, label }) => {
      const val = system[key]
      const isEcoOrConflict = ['economy_type', 'economy_level', 'conflict_level'].includes(key)
      // dominant_lifeform: "None" and "Abandoned" are now BOTH legitimate
      // answers (a system with no race vs a system whose race left). Both
      // count as filled — they're real data, not missing data.
      const allowNone = key === 'dominant_lifeform'
      const filled = (isEcoOrConflict && abandoned) || isFilled(val, { allowNone })
      if (filled) coreFilled += 1
      else gaps.push({ delta: Math.round(35 / SYS_CORE_FIELDS.length), text: `Add ${label}` })
    })
    const coreScore = Math.round((coreFilled / SYS_CORE_FIELDS.length) * 35)
    breakdown.push({ name: 'System Core', score: coreScore, max: 35 })

    // --- System Extra (10 pts) ---
    let extraFilled = 0
    SYS_EXTRA_FIELDS.forEach(({ key, label }) => {
      if (isFilled(system[key])) extraFilled += 1
      else gaps.push({ delta: Math.round(10 / SYS_EXTRA_FIELDS.length), text: `Add ${label}` })
    })
    const extraScore = Math.round((extraFilled / SYS_EXTRA_FIELDS.length) * 10)
    breakdown.push({ name: 'System Extra', score: extraScore, max: 10 })

    // --- Planet Coverage (10 pts) ---
    const planets = system.planets || []
    const planetCoverage = planets.length > 0 ? 10 : 0
    if (!planets.length) gaps.push({ delta: 10, text: 'Add at least one planet' })
    breakdown.push({ name: 'Planet Coverage', score: planetCoverage, max: 10 })

    // --- Planet Environment (15 pts spread) ---
    let envFilled = 0
    let envTotal = 0
    planets.forEach((p) => {
      ['biome', 'weather', 'sentinel'].forEach((k) => {
        envTotal += 1
        if (isFilled(p[k], { allowNone: k === 'sentinel' })) envFilled += 1
      })
    })
    const envScore = envTotal > 0 ? Math.round((envFilled / envTotal) * 15) : 0
    breakdown.push({ name: 'Planet Environment', score: envScore, max: 15 })
    if (envFilled < envTotal) gaps.push({ delta: 15 - envScore, text: 'Fill in planet biomes / weather / sentinels' })

    // --- Planet Life (15 pts spread) — biome-aware ---
    let lifeFilled = 0
    let lifeTotal = 0
    planets.forEach((p) => {
      const dead = NO_LIFE_BIOMES.has(p.biome) || p.is_gas_giant
      if (dead) {
        // Dead planets get full credit even without fauna/flora values
        lifeFilled += 2
        lifeTotal += 2
        return
      }
      ['fauna', 'flora'].forEach((k) => {
        lifeTotal += 1
        const v = p[k]
        if (v != null && String(v).trim()) lifeFilled += 1
      })
    })
    const lifeScore = lifeTotal > 0 ? Math.round((lifeFilled / lifeTotal) * 15) : 0
    breakdown.push({ name: 'Planet Life', score: lifeScore, max: 15 })
    if (lifeFilled < lifeTotal) gaps.push({ delta: 15 - lifeScore, text: 'Add fauna/flora values to your planets' })

    // --- Planet Detail (10 pts) — resources, base location ---
    let detailFilled = 0
    let detailTotal = 0
    planets.forEach((p) => {
      detailTotal += 2
      if (isFilled(p.materials)) detailFilled += 1
      if (isFilled(p.base_location)) detailFilled += 1
    })
    const detailScore = detailTotal > 0 ? Math.round((detailFilled / detailTotal) * 10) : 0
    breakdown.push({ name: 'Planet Detail', score: detailScore, max: 10 })

    // --- Space Station (5 pts) ---
    const station = system.space_station
    let stationScore = 0
    if (abandoned) {
      stationScore = 5  // Full credit for abandoned (no station expected)
    } else if (station && isFilled(station.name) && isFilled(station.race)) {
      stationScore = 5
    } else if (station) {
      stationScore = 2
    } else {
      gaps.push({ delta: 5, text: 'Document the space station' })
    }
    breakdown.push({ name: 'Space Station', score: stationScore, max: 5 })

    // Total
    const score = breakdown.reduce((sum, b) => sum + b.score, 0)
    const max = breakdown.reduce((sum, b) => sum + b.max, 0)
    const pct = max > 0 ? Math.round((score / max) * 100) : 0

    let grade = 'C'
    if (pct >= 85) grade = 'S'
    else if (pct >= 65) grade = 'A'
    else if (pct >= 40) grade = 'B'

    // Sort gaps by delta desc, top 4
    gaps.sort((a, b) => b.delta - a.delta)

    return { score, max, percent: pct, grade, breakdown, gaps: gaps.slice(0, 4) }
  }, [system])
}
