// Wizard live completeness score for the progress bar + grade guidance panel.
//
// This is a CLIENT-SIDE mirror of services/completeness.py — used purely for
// live UI feedback. The authoritative score is computed by the backend on
// save/approve. This lets the user see "+N to next grade" before submitting.
//
// It matches the backend's SIX weighted categories exactly:
//   System Core 35 · System Extra 10 · Planet Coverage 10 ·
//   Planet Environment 25 · Planet Life 15 · Space Station 5   (= 100)
// (System Extra dropped `description` on 2026-06-19 — glyph_code +
//  stellar_classification only, 5 pts each.)
//
// Grade thresholds match constants.py: S(85+) A(65+) B(40+) C(<40). X ("fully
// charted") is a checklist on top of S — the wizard can verify the parts it has
// data for (wonder notes, base, station) but NOT the discovery-on-every-body
// requirement, so it's surfaced as guidance (`splus`) rather than promoting the
// displayed grade. The backend has the final say at approval.

import { useMemo } from 'react'

// Mirror of constants.NO_LIFE_BIOMES.
const NO_LIFE_BIOMES = new Set([
  'Dead', 'Lifeless', 'Life-Incompatible', 'Airless', 'Low Atmosphere',
  'Gas Giant', 'Empty',
])

// Mirror of services/completeness.WONDER_FIELDS.
const WONDER_FIELDS = ['estimated_age', 'core_element', 'lore_notes', 'root_structure', 'nutrient_source']

function isFilled(val, { allowNone = false } = {}) {
  if (val == null) return false
  const s = String(val).trim()
  if (!s) return false
  if (s === 'N/A') return false
  if (s === 'None' && !allowNone) return false
  return true
}

// Mirror of _life_descriptor_filled: ANY non-empty string is real data.
function lifeDescriptorFilled(...vals) {
  return vals.some((v) => v != null && String(v).trim() !== '')
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

// `description` intentionally NOT here — dropped from scoring (matches backend).
const SYS_EXTRA_FIELDS = [
  { key: 'glyph_code', label: 'Glyph Code' },
  { key: 'stellar_classification', label: 'Spectral Class' },
]

export default function useCompletenessScore(system) {
  return useMemo(() => {
    if (!system) return { score: 0, max: 100, percent: 0, grade: 'C', breakdown: [], gaps: [], splus: null }

    const breakdown = []
    const gaps = []
    const abandoned = isAbandoned(system)
    const planets = system.planets || []

    // --- System Core (35 pts) ---
    let coreFilled = 0
    SYS_CORE_FIELDS.forEach(({ key, label }) => {
      const val = system[key]
      const isEcoOrConflict = ['economy_type', 'economy_level', 'conflict_level'].includes(key)
      // dominant_lifeform: "None"/"Abandoned" are both legitimate answers.
      // conflict_level: "None" is a legitimate answer too (a peaceful system
      // with a station can genuinely have no conflict), so it counts even when
      // the system isn't abandoned — mirrors the backend completeness.py.
      const allowNone = key === 'dominant_lifeform' || key === 'conflict_level'
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
    const planetCoverage = planets.length > 0 ? 10 : 0
    if (!planets.length) gaps.push({ delta: 10, text: 'Add at least one planet' })
    breakdown.push({ name: 'Planet Coverage', score: planetCoverage, max: 10 })

    // --- Planet Environment (25 pts) — per-planet avg of biome/weather/sentinel ---
    let envScore = 0
    let lifeScore = 0
    if (planets.length) {
      const envRatios = []
      const lifeRatios = []
      planets.forEach((p) => {
        // Environment: 3 fields
        let envFilled = 0
        if (isFilled(p.biome)) envFilled += 1
        if (isFilled(p.weather) || isFilled(p.weather_text)) envFilled += 1
        if (isFilled(p.sentinel, { allowNone: true }) || isFilled(p.sentinels_text)) envFilled += 1
        envRatios.push(Math.min(envFilled / 3, 1))

        // Life: fauna + flora (biome-aware) + resources
        const deadBiome = NO_LIFE_BIOMES.has((p.biome || '').trim()) || !!p.is_gas_giant
        let lifeFilled = 0
        let lifeApplicable = 0

        if (lifeDescriptorFilled(p.fauna, p.fauna_text)) { lifeFilled += 1; lifeApplicable += 1 }
        else if (!deadBiome) lifeApplicable += 1

        if (lifeDescriptorFilled(p.flora, p.flora_text)) { lifeFilled += 1; lifeApplicable += 1 }
        else if (!deadBiome) lifeApplicable += 1

        const hasMaterials = isFilled(p.materials)
        const hasAnyResource = ['common_resource', 'uncommon_resource', 'rare_resource'].some((k) => isFilled(p[k]))
        lifeApplicable += 1
        if (hasMaterials || hasAnyResource) lifeFilled += 1

        lifeRatios.push(lifeFilled / Math.max(lifeApplicable, 1))
      })
      envScore = Math.round((envRatios.reduce((a, b) => a + b, 0) / envRatios.length) * 25)
      lifeScore = Math.round((lifeRatios.reduce((a, b) => a + b, 0) / lifeRatios.length) * 15)
      if (envScore < 25) gaps.push({ delta: 25 - envScore, text: 'Fill in planet biomes / weather / sentinels' })
      if (lifeScore < 15) gaps.push({ delta: 15 - lifeScore, text: 'Add fauna / flora / resources to your planets' })
    }
    breakdown.push({ name: 'Planet Environment', score: envScore, max: 25 })
    breakdown.push({ name: 'Planet Life', score: lifeScore, max: 15 })

    // --- Space Station (5 pts) ---
    const station = system.space_station
    const noStation = !!system.no_space_station
    let stationScore = 0
    if (abandoned || noStation) {
      stationScore = 5 // full credit — abandoned OR explicitly marked no station
    } else if (station) {
      stationScore = 3
      const tg = station.trade_goods
      const hasTrade = Array.isArray(tg) ? tg.length > 0 : isFilled(tg)
      if (hasTrade) stationScore += 2
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

    // --- X guidance (checklist on top of S) ---
    // The wizard can verify the parts it has data for; it CANNOT verify a
    // discovery on every planet AND moon (no linked discovery data here), so
    // that requirement is reported as "verified at approval" and we never
    // promote the displayed grade to X on the client.
    // Bodies = planets + their moons (wonder + base can be satisfied by either).
    const allBodies = planets.flatMap((p) => [p, ...(p.moons || [])])
    const anyBodyHasWonder = allBodies.some((b) => WONDER_FIELDS.some((f) => isFilled(b[f])))
    // base lat/long may arrive as raw strings ('' mid-typing) — require both to parse.
    const hasBaseCoords = (b) => Number.isFinite(parseFloat(b.base_latitude)) && Number.isFinite(parseFloat(b.base_longitude))
    const hasBase = allBodies.some((b) => hasBaseCoords(b) || isFilled(b.base_location))
    const stationRecorded = abandoned || noStation || !!station
    const splus = {
      eligible: false, // never auto-promoted client-side; backend decides
      requirements: [
        { met: pct >= 85, label: 'Reach an S-grade score (85+)' },
        { met: anyBodyHasWonder, label: 'Wonder notes on at least one planet/moon' },
        { met: hasBase, label: 'Document a base (lat/long, or a base discovery)' },
        { met: stationRecorded, label: (abandoned || noStation) ? 'Station — N/A (no station)' : 'Record the space station' },
        { met: null, label: 'A discovery on every planet & moon (verified at approval)' },
      ],
    }

    // Sort gaps by delta desc, top 4
    gaps.sort((a, b) => b.delta - a.delta)

    return { score, max, percent: pct, grade, breakdown, gaps: gaps.slice(0, 4), splus }
  }, [system])
}
