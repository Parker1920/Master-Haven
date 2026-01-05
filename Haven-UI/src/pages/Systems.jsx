import React, { useEffect, useState, useContext, useMemo } from 'react'
import axios from 'axios'
import Card from '../components/Card'
import Button from '../components/Button'
import FormField from '../components/FormField'
import { Squares2X2Icon, ListBulletIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { Link, useNavigate } from 'react-router-dom'
import { AuthContext } from '../utils/AuthContext'

// Custom debounce hook for search performance
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(handler)
    }
  }, [value, delay])

  return debouncedValue
}

// Directional/cardinal region names to optionally hide
const DIRECTIONAL_REGIONS = [
  'Center Bottom', 'Center Top',
  'East Core', 'North Core', 'South Core', 'West Core',
  'North-East Top', 'North-West Bottom', 'North-West Top',
  'South-East Bottom', 'South-East Top', 'South-West Bottom', 'South-West Top'
]

// Discord tag badge
function getDiscordTagBadge(tag) {
  if (!tag) return null
  if (tag === 'personal') {
    return <span className="text-xs bg-fuchsia-600 text-white px-1.5 py-0.5 rounded">Personal</span>
  }
  const tagColors = {
    'Haven': 'bg-cyan-500 text-white',
    'IEA': 'bg-green-500 text-white',
    'B.E.S': 'bg-orange-500 text-white',
    'ARCH': 'bg-purple-500 text-white',
    'TBH': 'bg-yellow-500 text-black',
    'EVRN': 'bg-pink-500 text-white',
  }
  const colorClass = tagColors[tag] || 'bg-indigo-500 text-white'
  return <span className={`text-xs px-1.5 py-0.5 rounded ${colorClass}`}>{tag}</span>
}

export default function Systems() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [regions, setRegions] = useState([])
  const [q, setQ] = useState('')
  const debouncedQuery = useDebounce(q, 300)
  const [loading, setLoading] = useState(true)

  // Backend search results
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)

  // Discord tag filtering
  const [discordTags, setDiscordTags] = useState([])
  const [filterTag, setFilterTag] = useState('all')

  // Toggle to hide directional/cardinal regions
  const [hideDirectional, setHideDirectional] = useState(false)

  // View mode toggle: 'list' or 'grid'
  const [viewMode, setViewMode] = useState('list')

  // Fetch discord tags for filter dropdown
  useEffect(() => {
    axios.get('/api/discord_tags').then(r => {
      setDiscordTags(r.data.tags || [])
    }).catch(() => {})
  }, [])

  // Load regions on mount
  useEffect(() => { load() }, [])

  // Backend search when query changes
  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setSearchResults([])
      return
    }

    setIsSearching(true)
    axios.get(`/api/systems/search?q=${encodeURIComponent(debouncedQuery)}&limit=20`)
      .then(r => setSearchResults(r.data.results || []))
      .catch(() => setSearchResults([]))
      .finally(() => setIsSearching(false))
  }, [debouncedQuery])

  // Load region summaries (without systems) - fast initial load
  async function load() {
    setLoading(true)
    try {
      const r = await axios.get('/api/regions/grouped?include_systems=false')
      setRegions(r.data.regions || [])
    } catch (e) {
      console.error('Failed to load regions:', e)
      setRegions([])
    } finally {
      setLoading(false)
    }
  }

  // Filtered regions (client-side filtering of region list)
  const filteredRegions = useMemo(() => {
    let filtered = regions

    // Filter out directional/cardinal regions if toggle is enabled
    if (hideDirectional) {
      filtered = filtered.filter(region => {
        const regionName = region.custom_name || ''
        return !DIRECTIONAL_REGIONS.includes(regionName)
      })
    }

    // Filter regions by name if searching (but keep showing search results above)
    if (debouncedQuery.trim()) {
      const query = debouncedQuery.toLowerCase().trim()
      filtered = filtered.filter(region => {
        if (region.display_name?.toLowerCase().includes(query)) return true
        if (region.custom_name?.toLowerCase().includes(query)) return true
        // Match on coordinates too
        const coordStr = `${region.region_x},${region.region_y},${region.region_z}`
        if (coordStr.includes(query)) return true
        return false
      })
    }

    return filtered
  }, [regions, hideDirectional, debouncedQuery])

  // Count total systems across filtered regions
  const totalSystemsCount = useMemo(() => {
    return filteredRegions.reduce((sum, region) => sum + (region.system_count || 0), 0)
  }, [filteredRegions])

  // Navigate to region detail page
  function openRegion(region) {
    navigate(`/regions/${region.region_x}/${region.region_y}/${region.region_z}`)
  }

  if (loading) {
    return (
      <div className="p-6">
        <Card>
          <div className="text-center py-8">Loading systems...</div>
        </Card>
      </div>
    )
  }

  return (
    <div>
      {/* Search and Actions Bar */}
      <div className="mb-6 flex flex-col lg:grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 flex gap-2">
          <FormField className="flex-1">
            <div className="relative">
              <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                aria-label="Search systems"
                className="w-full pl-10 pr-3 py-2 rounded bg-gray-800 border border-gray-700 focus:border-cyan-500 focus:outline-none"
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Search systems by name, glyph code, or galaxy..."
              />
              {isSearching && (
                <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-cyan-400 text-sm">
                  Searching...
                </span>
              )}
            </div>
          </FormField>
          {/* Hide Directional Regions Toggle */}
          <button
            className={`px-3 py-2 rounded border transition-colors ${
              hideDirectional
                ? 'bg-purple-600 border-purple-500 text-white'
                : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
            }`}
            onClick={() => setHideDirectional(!hideDirectional)}
            title="Hide directional region names (Center Top, North-East Bottom, etc.)"
          >
            {hideDirectional ? '🧭 Named Only' : '🧭 Show All'}
          </button>
          {/* Discord Tag Filter */}
          <select
            className="px-3 py-2 rounded bg-gray-700 text-white border border-gray-600"
            value={filterTag}
            onChange={e => setFilterTag(e.target.value)}
          >
            <option value="all">All Communities</option>
            <option value="untagged">Untagged Only</option>
            <option value="personal">Personal Only</option>
            {discordTags.map(t => (
              <option key={t.tag} value={t.tag}>{t.name}</option>
            ))}
          </select>
          {/* View Mode Toggle */}
          <div className="flex rounded border border-gray-600 overflow-hidden">
            <button
              className={`px-3 py-2 flex items-center gap-1 transition-colors ${
                viewMode === 'list'
                  ? 'bg-cyan-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
              onClick={() => setViewMode('list')}
              title="List view"
            >
              <ListBulletIcon className="w-4 h-4" />
            </button>
            <button
              className={`px-3 py-2 flex items-center gap-1 transition-colors ${
                viewMode === 'grid'
                  ? 'bg-cyan-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
              onClick={() => setViewMode('grid')}
              title="Grid view"
            >
              <Squares2X2Icon className="w-4 h-4" />
            </button>
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <Button onClick={() => { setQ(''); setFilterTag('all'); setHideDirectional(false) }} variant="ghost">Clear</Button>
          <Button onClick={load} variant="ghost">Reload</Button>
          <Link to="/wizard"><Button variant="neutral">New</Button></Link>
        </div>
      </div>

      {/* Search Results Section */}
      {debouncedQuery.trim() && (searchResults.length > 0 || isSearching) && (
        <Card className="mb-6">
          <h3 className="text-lg font-semibold mb-3 text-cyan-400">
            System Search Results {searchResults.length > 0 && `(${searchResults.length})`}
          </h3>
          {isSearching ? (
            <div className="text-gray-400 py-4 text-center">Searching...</div>
          ) : (
            <div className="space-y-2">
              {searchResults.map(system => (
                <div
                  key={system.id}
                  className="p-3 bg-gray-800 rounded hover:bg-gray-700 cursor-pointer flex items-center justify-between transition-colors"
                  onClick={() => navigate(`/systems/${encodeURIComponent(system.id)}`)}
                >
                  <div>
                    <div className="font-semibold flex items-center gap-2">
                      {system.name}
                      {getDiscordTagBadge(system.discord_tag)}
                      {system.star_type && (
                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                          system.star_type === 'Yellow' ? 'bg-yellow-500 text-black' :
                          system.star_type === 'Red' ? 'bg-red-500 text-white' :
                          system.star_type === 'Blue' ? 'bg-blue-500 text-white' :
                          system.star_type === 'Green' ? 'bg-green-500 text-white' :
                          'bg-gray-500 text-white'
                        }`}>
                          {system.star_type}
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-400">
                      {system.region_name ? (
                        <span className="text-purple-400">{system.region_name}</span>
                      ) : (
                        <span>Region ({system.region_x}, {system.region_y}, {system.region_z})</span>
                      )}
                      <span className="ml-2">• {system.galaxy || 'Euclid'}</span>
                      <span className="ml-2">• {system.planet_count || 0} planets</span>
                      {system.glyph_code && (
                        <span className="ml-2 font-mono text-purple-400">({system.glyph_code})</span>
                      )}
                    </div>
                  </div>
                  <Button variant="ghost" className="text-sm">View →</Button>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Results Summary */}
      <div className="mb-4 text-sm text-gray-400">
        {filteredRegions.length} region{filteredRegions.length !== 1 ? 's' : ''}
        {' '}({totalSystemsCount} systems)
        {debouncedQuery && searchResults.length === 0 && !isSearching && ` • No systems match "${debouncedQuery}"`}
        {hideDirectional && (
          <span className="ml-2">
            • <span className="text-purple-400">Hiding directional regions</span>
          </span>
        )}
        {filterTag !== 'all' && (
          <span className="ml-2">
            • Filtered by: <span className="text-cyan-400">{filterTag === 'untagged' ? 'Untagged' : filterTag === 'personal' ? 'Personal' : filterTag}</span>
          </span>
        )}
      </div>

      {/* Regions Display */}
      {filteredRegions.length === 0 ? (
        <Card>
          <div className="text-center py-8 text-gray-400">
            {q ? 'No regions match your search' : 'No regions found'}
          </div>
        </Card>
      ) : viewMode === 'grid' ? (
        /* Grid View - Region Cards */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredRegions.map(region => {
            const regionKey = `${region.region_x},${region.region_y},${region.region_z}`
            const isDirectional = DIRECTIONAL_REGIONS.includes(region.custom_name || '')

            return (
              <Card
                key={regionKey}
                className="p-4 cursor-pointer hover:bg-gray-800 transition-colors border-l-4 border-l-purple-500"
                onClick={() => openRegion(region)}
              >
                <div className="mb-3">
                  <h3 className="font-semibold text-lg truncate">
                    {region.custom_name ? (
                      <span className={isDirectional ? 'text-gray-400' : 'text-purple-400'}>
                        {region.custom_name}
                      </span>
                    ) : (
                      <span className="text-gray-400">
                        ({region.region_x}, {region.region_y}, {region.region_z})
                      </span>
                    )}
                  </h3>
                  {region.custom_name && (
                    <div className="text-xs text-gray-500 font-mono">
                      [{region.region_x}, {region.region_y}, {region.region_z}]
                    </div>
                  )}
                </div>

                {/* Stats */}
                <div className="flex items-center justify-between">
                  <div className="text-2xl font-bold text-cyan-400">{region.system_count || 0}</div>
                  <div className="text-sm text-gray-400">systems</div>
                </div>

                <div className="mt-3 text-xs text-gray-500 text-center">
                  Click to view details →
                </div>
              </Card>
            )
          })}
        </div>
      ) : (
        /* List View - Clickable region rows */
        <div className="space-y-2">
          {filteredRegions.map(region => {
            const regionKey = `${region.region_x},${region.region_y},${region.region_z}`
            const isDirectional = DIRECTIONAL_REGIONS.includes(region.custom_name || '')

            return (
              <Card
                key={regionKey}
                className="p-4 cursor-pointer hover:bg-gray-800 transition-colors flex items-center justify-between"
                onClick={() => openRegion(region)}
              >
                <div className="flex items-center gap-4">
                  <div className="text-2xl font-bold text-cyan-400 w-16 text-center">
                    {region.system_count || 0}
                  </div>
                  <div>
                    <div className="text-lg font-semibold">
                      {region.custom_name ? (
                        <span className={isDirectional ? 'text-gray-400' : 'text-purple-400'}>
                          {region.custom_name}
                        </span>
                      ) : (
                        <span className="text-gray-300">
                          Region ({region.region_x}, {region.region_y}, {region.region_z})
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-400">
                      {region.system_count || 0} system{(region.system_count || 0) !== 1 ? 's' : ''}
                      {region.custom_name && (
                        <span className="ml-2">• Coords: [{region.region_x}, {region.region_y}, {region.region_z}]</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="text-gray-500">
                  View →
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
