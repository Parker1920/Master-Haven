/**
 * useFilters — translates the SystemsContext filter state into:
 *   1. apiParams: an object ready to spread into axios `params`. Multi-select
 *      array values are joined into comma-separated strings (the backend's
 *      _build_advanced_filter_clauses splits them with _split_csv and emits
 *      SQL IN (...)). Empty values are omitted.
 *   2. pills: an array of { key, label, value } display rows that
 *      FilterPillsRow renders.
 *
 * Filter shape (canonical — matches backend API param names):
 *   star_type          : string[]  (OR, multi)   e.g. ['Yellow','Blue']
 *   economy_type       : string    (single)
 *   economy_level      : string[]  (OR, multi)   e.g. ['T2','T3']
 *   conflict_level     : string[]  (OR, multi)
 *   dominant_lifeform  : string    (single)
 *   biome              : string    (single)
 *   weather            : string    (single)
 *   sentinel_level     : string    (single)
 *   resource           : string[]  (OR, multi)   e.g. ['Gold','Copper']
 *   is_complete        : string[]  (OR, multi)   e.g. ['S','A']  — grade
 *   has_moons          : bool|null (tri-state)
 *   min_planets        : number
 *   max_planets        : number
 */

import { useCallback, useMemo } from 'react'
import { useSystems } from '../contexts/SystemsContext'

export const FILTER_LABELS = {
  star_type: 'Star',
  economy_type: 'Economy',
  economy_level: 'Tier',
  conflict_level: 'Conflict',
  dominant_lifeform: 'Lifeform',
  biome: 'Biome',
  weather: 'Weather',
  sentinel_level: 'Sentinels',
  resource: 'Resource',
  is_complete: 'Grade',
  has_moons: 'Moons',
  min_planets: 'Planets ≥',
  max_planets: 'Planets ≤',
}

export const MULTI_KEYS = ['star_type', 'economy_level', 'conflict_level', 'is_complete', 'resource']

export function isEmptyFilterValue(v) {
  if (v == null) return true
  if (Array.isArray(v)) return v.length === 0
  if (typeof v === 'string') return v.trim() === ''
  if (typeof v === 'object') return Object.keys(v).length === 0
  return false
}

function formatValueLabel(key, value) {
  if (key === 'has_moons') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.join(', ')
  return String(value)
}

export default function useFilters() {
  const { filters, removeFilter, clearFilters, activeFilterCount, setFilters } = useSystems()

  const apiParams = useMemo(() => {
    const out = {}
    for (const [k, v] of Object.entries(filters)) {
      if (isEmptyFilterValue(v)) continue
      if (Array.isArray(v)) out[k] = v.join(',')
      else if (typeof v === 'boolean') out[k] = v
      else out[k] = v
    }
    return out
  }, [filters])

  const pills = useMemo(() => {
    return Object.entries(filters)
      .filter(([, v]) => !isEmptyFilterValue(v))
      .map(([key, value]) => ({
        key,
        label: FILTER_LABELS[key] || key,
        value: formatValueLabel(key, value),
        raw: value,
      }))
  }, [filters])

  // LOW-2: memoized so children that take these as props don't see a
  // fresh function identity on every render. setFilters from context is
  // already stable, so these only depend on it.
  const toggleMulti = useCallback((key, item) => {
    setFilters((prev) => {
      const cur = Array.isArray(prev[key]) ? prev[key] : []
      const next = cur.includes(item) ? cur.filter((x) => x !== item) : [...cur, item]
      const out = { ...prev }
      if (next.length === 0) delete out[key]
      else out[key] = next
      return out
    })
  }, [setFilters])

  const setSingle = useCallback((key, value) => {
    setFilters((prev) => {
      const out = { ...prev }
      if (isEmptyFilterValue(value)) delete out[key]
      else out[key] = value
      return out
    })
  }, [setFilters])

  return {
    filters, setFilters, apiParams, pills,
    activeFilterCount, removeFilter, clearFilters,
    toggleMulti, setSingle,
  }
}
