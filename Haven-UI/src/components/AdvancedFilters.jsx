import React, { useEffect, useState, useMemo } from 'react'
import axios from 'axios'
import SearchableSelect from './SearchableSelect'
import {
  FunnelIcon,
  XMarkIcon,
  ChevronDownIcon,
  ChevronUpIcon
} from '@heroicons/react/24/outline'

/**
 * AdvancedFilters - Collapsible filter panel for the Systems page.
 *
 * Fetches available filter options from `/api/systems/filter-options`
 * and renders searchable dropdowns grouped by category.
 *
 * Props:
 *   filters - Object with current filter values
 *   onChange - Callback when filters change: (newFilters) => void
 *   reality - Optional reality scope for filter options
 *   galaxy  - Optional galaxy scope for filter options
 */

const EMPTY_FILTERS = {
  star_type: '',
  economy_type: '',
  economy_level: '',
  conflict_level: '',
  dominant_lifeform: '',
  stellar_classification: '',
  biome: '',
  weather: '',
  sentinel_level: '',
  resource: '',
  has_moons: '',
  min_planets: '',
  max_planets: '',
  is_complete: ''
}

export { EMPTY_FILTERS }

export default function AdvancedFilters({ filters, onChange, reality, galaxy }) {
  const [isOpen, setIsOpen] = useState(false)
  const [options, setOptions] = useState(null)
  const [loading, setLoading] = useState(false)

  // Count active filters
  const activeCount = useMemo(() => {
    return Object.entries(filters).filter(([, v]) => v !== '' && v !== null && v !== undefined).length
  }, [filters])

  // Fetch filter options when panel opens or scope changes
  useEffect(() => {
    if (!isOpen) return

    setLoading(true)
    const params = new URLSearchParams()
    if (reality) params.append('reality', reality)
    if (galaxy) params.append('galaxy', galaxy)

    axios.get(`/api/systems/filter-options?${params.toString()}`)
      .then(r => setOptions(r.data))
      .catch(() => setOptions({}))
      .finally(() => setLoading(false))
  }, [isOpen, reality, galaxy])

  function handleChange(key, value) {
    onChange({ ...filters, [key]: value })
  }

  function clearAll() {
    onChange({ ...EMPTY_FILTERS })
  }

  // Build dropdown options from fetched data
  function toOptions(arr) {
    if (!arr) return []
    return arr.map(v => ({ value: v, label: v }))
  }

  return (
    <div className="space-y-2">
      {/* Toggle button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors border ${
          isOpen || activeCount > 0
            ? 'bg-cyan-600 border-cyan-500 text-white'
            : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'
        }`}
      >
        {isOpen ? <XMarkIcon className="w-4 h-4" /> : <FunnelIcon className="w-4 h-4" />}
        Advanced Filters
        {activeCount > 0 && (
          <span className="bg-white text-cyan-600 text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
            {activeCount}
          </span>
        )}
        {isOpen ? <ChevronUpIcon className="w-4 h-4" /> : <ChevronDownIcon className="w-4 h-4" />}
      </button>

      {/* Filter panel */}
      {isOpen && (
        <div className="bg-gray-800/70 rounded-xl border border-gray-700 p-4 space-y-5">
          {loading && !options ? (
            <div className="text-center py-4 text-gray-400 text-sm">Loading filter options...</div>
          ) : (
            <>
              {/* System Properties */}
              <FilterSection title="System Properties">
                <FilterField label="Star Type">
                  <SearchableSelect
                    options={toOptions(options?.star_types)}
                    value={filters.star_type}
                    onChange={v => handleChange('star_type', v)}
                    placeholder="Any star type"
                  />
                </FilterField>
                <FilterField label="Economy">
                  <SearchableSelect
                    options={toOptions(options?.economy_types)}
                    value={filters.economy_type}
                    onChange={v => handleChange('economy_type', v)}
                    placeholder="Any economy"
                  />
                </FilterField>
                <FilterField label="Economy Level">
                  <SearchableSelect
                    options={toOptions(options?.economy_levels)}
                    value={filters.economy_level}
                    onChange={v => handleChange('economy_level', v)}
                    placeholder="Any level"
                  />
                </FilterField>
                <FilterField label="Conflict Level">
                  <SearchableSelect
                    options={toOptions(options?.conflict_levels)}
                    value={filters.conflict_level}
                    onChange={v => handleChange('conflict_level', v)}
                    placeholder="Any conflict"
                  />
                </FilterField>
                <FilterField label="Dominant Lifeform">
                  <SearchableSelect
                    options={toOptions(options?.dominant_lifeforms)}
                    value={filters.dominant_lifeform}
                    onChange={v => handleChange('dominant_lifeform', v)}
                    placeholder="Any lifeform"
                  />
                </FilterField>
                <FilterField label="Stellar Class">
                  <SearchableSelect
                    options={toOptions(options?.stellar_classifications)}
                    value={filters.stellar_classification}
                    onChange={v => handleChange('stellar_classification', v)}
                    placeholder="Any class"
                  />
                </FilterField>
              </FilterSection>

              {/* Planet Properties */}
              <FilterSection title="Planet Properties">
                <FilterField label="Biome">
                  <SearchableSelect
                    options={toOptions(options?.biomes)}
                    value={filters.biome}
                    onChange={v => handleChange('biome', v)}
                    placeholder="Any biome"
                  />
                </FilterField>
                <FilterField label="Weather">
                  <SearchableSelect
                    options={toOptions(options?.weather_types)}
                    value={filters.weather}
                    onChange={v => handleChange('weather', v)}
                    placeholder="Any weather"
                  />
                </FilterField>
                <FilterField label="Sentinel Level">
                  <SearchableSelect
                    options={toOptions(options?.sentinel_levels)}
                    value={filters.sentinel_level}
                    onChange={v => handleChange('sentinel_level', v)}
                    placeholder="Any sentinel level"
                  />
                </FilterField>
                <FilterField label="Resource">
                  <SearchableSelect
                    options={toOptions(options?.resources)}
                    value={filters.resource}
                    onChange={v => handleChange('resource', v)}
                    placeholder="Any resource"
                  />
                </FilterField>
              </FilterSection>

              {/* Other Filters */}
              <FilterSection title="Other">
                <FilterField label="Has Moons">
                  <select
                    className="w-full px-3 py-2 rounded bg-gray-700/50 border border-gray-600 text-white text-sm"
                    value={filters.has_moons}
                    onChange={e => handleChange('has_moons', e.target.value)}
                  >
                    <option value="">Any</option>
                    <option value="true">Yes - Has moons</option>
                    <option value="false">No - No moons</option>
                  </select>
                </FilterField>
                <FilterField label="Min Planets">
                  <input
                    type="number"
                    min="0"
                    max="6"
                    className="w-full px-3 py-2 rounded bg-gray-700/50 border border-gray-600 text-white text-sm"
                    value={filters.min_planets}
                    onChange={e => handleChange('min_planets', e.target.value)}
                    placeholder="0"
                  />
                </FilterField>
                <FilterField label="Max Planets">
                  <input
                    type="number"
                    min="0"
                    max="6"
                    className="w-full px-3 py-2 rounded bg-gray-700/50 border border-gray-600 text-white text-sm"
                    value={filters.max_planets}
                    onChange={e => handleChange('max_planets', e.target.value)}
                    placeholder="6"
                  />
                </FilterField>
                <FilterField label="Data Grade">
                  <select
                    className="w-full px-3 py-2 rounded bg-gray-700/50 border border-gray-600 text-white text-sm"
                    value={filters.is_complete}
                    onChange={e => handleChange('is_complete', e.target.value)}
                  >
                    <option value="">Any</option>
                    <option value="S">S - Archive Quality</option>
                    <option value="A">A - Well Documented</option>
                    <option value="B">B - Partial Data</option>
                    <option value="C">C - Basic Info</option>
                  </select>
                </FilterField>
              </FilterSection>

              {/* Clear All */}
              {activeCount > 0 && (
                <div className="flex justify-end pt-2 border-t border-gray-700">
                  <button
                    onClick={clearAll}
                    className="px-4 py-2 rounded-lg text-sm font-medium text-red-400 hover:bg-red-400/10 transition-colors"
                  >
                    Clear All Filters ({activeCount})
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}


function FilterSection({ title, children }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">{title}</h4>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {children}
      </div>
    </div>
  )
}


function FilterField({ label, children }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      {children}
    </div>
  )
}
