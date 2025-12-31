import React, { useEffect, useState, useContext, useMemo, useCallback, useRef } from 'react'
import axios from 'axios'
import Card from '../components/Card'
import Button from '../components/Button'
import FormField from '../components/FormField'
import { TrashIcon, PencilIcon, ChevronDownIcon, ChevronRightIcon, Squares2X2Icon, ListBulletIcon, GlobeAltIcon, CubeIcon } from '@heroicons/react/24/outline'
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

// Helper to normalize photo paths
function getPhotoUrl(photo) {
  if (!photo) return null
  if (photo.startsWith('http')) return photo
  const normalized = photo.replace(/\\/g, '/')
  const parts = normalized.split('/')
  const filename = parts[parts.length - 1]
  return `/haven-ui-photos/${encodeURIComponent(filename)}`
}

// Directional/cardinal region names to optionally hide
const DIRECTIONAL_REGIONS = [
  'Center Bottom', 'Center Top',
  'East Core', 'North Core', 'South Core', 'West Core',
  'North-East Top', 'North-West Bottom', 'North-West Top',
  'South-East Bottom', 'South-East Top', 'South-West Bottom', 'South-West Top'
]

export default function Systems() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [regions, setRegions] = useState([])
  const [q, setQ] = useState('')
  const debouncedQuery = useDebounce(q, 300) // Debounced search for better performance
  const [loading, setLoading] = useState(true)
  const [expandedRegion, setExpandedRegion] = useState(null)
  const [expandedSystem, setExpandedSystem] = useState(null)
  const [expandedPlanets, setExpandedPlanets] = useState({})
  const [editingRegionName, setEditingRegionName] = useState(null)
  const [newRegionName, setNewRegionName] = useState('')
  const [submittingRegionName, setSubmittingRegionName] = useState(false)
  // Discord tag filtering (super admin only)
  const [discordTags, setDiscordTags] = useState([])
  const [filterTag, setFilterTag] = useState('all')
  // Toggle to hide directional/cardinal regions
  const [hideDirectional, setHideDirectional] = useState(false)
  // View mode toggle: 'list' or 'grid'
  const [viewMode, setViewMode] = useState('list')
  // Lazy-loaded systems cache per region (key: "x,y,z" -> systems array)
  const [regionSystems, setRegionSystems] = useState({})
  const [loadingRegionSystems, setLoadingRegionSystems] = useState({})

  // Fetch discord tags for filter dropdown (available to all users)
  useEffect(() => {
    axios.get('/api/discord_tags').then(r => {
      setDiscordTags(r.data.tags || [])
    }).catch(() => {})
  }, [])

  useEffect(() => { load() }, [])

  // Load region summaries (without systems) - much faster initial load
  async function load() {
    setLoading(true)
    try {
      // Use include_systems=false for fast initial load (returns region summaries only)
      const r = await axios.get('/api/regions/grouped?include_systems=false')
      setRegions(r.data.regions || [])
      // Clear cached systems when reloading
      setRegionSystems({})
    } catch (e) {
      console.error('Failed to load regions:', e)
      setRegions([])
    } finally {
      setLoading(false)
    }
  }

  // Lazy load systems for a specific region when expanded
  const loadSystemsForRegion = useCallback(async (region) => {
    const key = `${region.region_x},${region.region_y},${region.region_z}`

    // Already loaded or loading
    if (regionSystems[key] || loadingRegionSystems[key]) return

    setLoadingRegionSystems(prev => ({ ...prev, [key]: true }))

    try {
      // Load systems with planets using the new lazy-loading endpoint
      const r = await axios.get(
        `/api/regions/${region.region_x}/${region.region_y}/${region.region_z}/systems?include_planets=true`
      )
      setRegionSystems(prev => ({ ...prev, [key]: r.data.systems || [] }))
    } catch (e) {
      console.error('Failed to load systems for region:', e)
      setRegionSystems(prev => ({ ...prev, [key]: [] }))
    } finally {
      setLoadingRegionSystems(prev => ({ ...prev, [key]: false }))
    }
  }, [regionSystems, loadingRegionSystems])

  // Helper to get systems for a region (from cache or original data)
  const getRegionSystemsData = useCallback((region) => {
    const key = `${region.region_x},${region.region_y},${region.region_z}`
    return regionSystems[key] || region.systems || []
  }, [regionSystems])

  // Memoized filtered regions - recalculates only when dependencies change
  const filteredRegions = useMemo(() => {
    let filtered = regions

    // Filter out directional/cardinal regions if toggle is enabled
    if (hideDirectional) {
      filtered = filtered.filter(region => {
        const regionName = region.custom_name || ''
        return !DIRECTIONAL_REGIONS.includes(regionName)
      })
    }

    // Apply discord_tag filter (available to all users)
    // Note: This filter only works on regions with loaded systems
    if (filterTag !== 'all') {
      filtered = filtered.map(region => {
        const key = `${region.region_x},${region.region_y},${region.region_z}`
        const systems = regionSystems[key] || region.systems || []
        // Filter systems within each region by discord_tag
        const filteredSystems = systems.filter(system => {
          if (filterTag === 'untagged') return !system.discord_tag
          return system.discord_tag === filterTag
        })
        return { ...region, _filteredSystems: filteredSystems, _filteredCount: filteredSystems.length }
      }).filter(region => region._filteredCount > 0) // Remove empty regions
    }

    // Then apply text search filter using debounced query
    if (debouncedQuery.trim()) {
      const query = debouncedQuery.toLowerCase().trim()
      filtered = filtered.filter(region => {
        // Check if region name matches
        if (region.display_name?.toLowerCase().includes(query)) return true
        if (region.custom_name?.toLowerCase().includes(query)) return true

        // Check if any cached system matches (if systems are loaded)
        const key = `${region.region_x},${region.region_y},${region.region_z}`
        const systems = regionSystems[key] || []
        return systems.some(system =>
          system.name?.toLowerCase().includes(query) ||
          system.galaxy?.toLowerCase().includes(query) ||
          system.glyph_code?.toLowerCase().includes(query) ||
          system.description?.toLowerCase().includes(query)
        )
      })
    }

    return filtered
  }, [regions, hideDirectional, filterTag, debouncedQuery, regionSystems])

  // Get discord tag badge with color
  function getDiscordTagBadge(tag, personalDiscordUsername = null, showPersonalUsername = false) {
    if (!tag) {
      return (
        <span className="text-xs bg-gray-500 text-white px-1.5 py-0.5 rounded">
          UNTAGGED
        </span>
      )
    }

    // Special handling for "personal" tag - magenta/fuchsia color
    // Only show username if showPersonalUsername is true (super admin only)
    if (tag === 'personal') {
      return (
        <span className="text-xs bg-fuchsia-600 text-white px-1.5 py-0.5 rounded">
          PERSONAL {showPersonalUsername && personalDiscordUsername && `(${personalDiscordUsername})`}
        </span>
      )
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
    return (
      <span className={`text-xs px-1.5 py-0.5 rounded ${colorClass}`}>
        {tag}
      </span>
    )
  }

  // Calculate stats for a region (planets and moons count) - uses cached systems
  function getRegionStats(region) {
    const key = `${region.region_x},${region.region_y},${region.region_z}`
    const systems = regionSystems[key] || region.systems || []
    let planets = 0
    let moons = 0
    systems.forEach(system => {
      const systemPlanets = system.planets || []
      planets += systemPlanets.length
      systemPlanets.forEach(planet => {
        moons += (planet.moons || []).length
      })
    })
    return { systems: systems.length || region.system_count || 0, planets, moons }
  }

  function toggleRegion(regionKey, region) {
    if (expandedRegion === regionKey) {
      setExpandedRegion(null)
      setExpandedSystem(null)
      setExpandedPlanets({})
    } else {
      setExpandedRegion(regionKey)
      setExpandedSystem(null)
      setExpandedPlanets({})
      // Lazy load systems when expanding a region
      if (region) {
        loadSystemsForRegion(region)
      }
    }
  }

  function toggleSystem(systemId) {
    if (expandedSystem === systemId) {
      setExpandedSystem(null)
      setExpandedPlanets({})
    } else {
      setExpandedSystem(systemId)
      setExpandedPlanets({})
    }
  }

  function togglePlanet(planetIndex) {
    setExpandedPlanets(prev => ({
      ...prev,
      [planetIndex]: !prev[planetIndex]
    }))
  }

  // Quick tag assignment for super admin
  async function quickAssignTag(systemId, newTag) {
    try {
      // Get the current system data
      const systemResponse = await axios.get(`/api/systems/${encodeURIComponent(systemId)}`)
      const systemData = systemResponse.data

      // Update with new tag
      systemData.discord_tag = newTag || null

      // Save the system
      await axios.post('/api/save_system', systemData)

      // Reload to show updated data
      load()
    } catch (err) {
      alert('Failed to update tag: ' + (err.response?.data?.detail || err.message))
    }
  }

  async function removeSystem(id, e) {
    e.stopPropagation()
    if (!confirm('Delete system?')) return
    try {
      await axios.delete(`/api/systems/${encodeURIComponent(id)}`)
      load()
    } catch (e) {
      alert('Delete failed: ' + (e.response?.data?.detail || e.message))
    }
  }

  function startEditingRegionName(region, e) {
    e.stopPropagation()
    setEditingRegionName(`${region.region_x},${region.region_y},${region.region_z}`)
    setNewRegionName(region.custom_name || '')
  }

  function cancelEditingRegionName() {
    setEditingRegionName(null)
    setNewRegionName('')
  }

  async function submitRegionName(region, e) {
    e.preventDefault()
    e.stopPropagation()

    if (!newRegionName.trim()) {
      alert('Please enter a region name')
      return
    }

    setSubmittingRegionName(true)
    try {
      // Submit for approval (same as existing region name submission flow)
      await axios.post(`/api/regions/${region.region_x}/${region.region_y}/${region.region_z}/submit`, {
        proposed_name: newRegionName.trim()
      })
      alert('Region name submitted for approval!')
      setEditingRegionName(null)
      setNewRegionName('')
    } catch (err) {
      alert('Failed to submit: ' + (err.response?.data?.detail || err.message))
    } finally {
      setSubmittingRegionName(false)
    }
  }

  // Count total systems across filtered regions (using cached data where available)
  const totalSystemsCount = useMemo(() => {
    return filteredRegions.reduce((sum, region) => {
      // Use filtered count if tag filter is applied, otherwise use system_count
      if (region._filteredCount !== undefined) {
        return sum + region._filteredCount
      }
      const key = `${region.region_x},${region.region_y},${region.region_z}`
      const cachedSystems = regionSystems[key]
      return sum + (cachedSystems ? cachedSystems.length : (region.system_count || 0))
    }, 0)
  }, [filteredRegions, regionSystems])

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
            <input
              aria-label="Search systems"
              className="w-full px-3 py-2 rounded"
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="Search by region name, system name, or galaxy"
            />
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
            {hideDirectional ? '🧭 Showing Named Only' : '🧭 Show All'}
          </button>
          {/* Discord Tag Filter - Available to all users */}
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

      {/* Results Summary */}
      <div className="mb-4 text-sm text-gray-400">
        {filteredRegions.length} region{filteredRegions.length !== 1 ? 's' : ''}
        {' '}({totalSystemsCount} systems)
        {debouncedQuery && ` matching "${debouncedQuery}"`}
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
            {q ? 'No regions match your search' : 'No systems found'}
          </div>
        </Card>
      ) : viewMode === 'grid' ? (
        /* Grid View - Region Stats Cards */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredRegions.map(region => {
            const regionKey = `${region.region_x},${region.region_y},${region.region_z}`
            const stats = getRegionStats(region)
            const isDirectional = DIRECTIONAL_REGIONS.includes(region.custom_name || '')

            return (
              <Card
                key={regionKey}
                className="p-4 cursor-pointer hover:bg-gray-800 transition-colors border-l-4 border-l-purple-500"
                onClick={() => {
                  setViewMode('list')
                  toggleRegion(regionKey, region)
                }}
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
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-gray-800 rounded p-2">
                    <div className="text-2xl font-bold text-cyan-400">{stats.systems}</div>
                    <div className="text-xs text-gray-400">Systems</div>
                  </div>
                  <div className="bg-gray-800 rounded p-2">
                    <div className="text-2xl font-bold text-green-400">{stats.planets}</div>
                    <div className="text-xs text-gray-400">Planets</div>
                  </div>
                  <div className="bg-gray-800 rounded p-2">
                    <div className="text-2xl font-bold text-yellow-400">{stats.moons}</div>
                    <div className="text-xs text-gray-400">Moons</div>
                  </div>
                </div>

                <div className="mt-3 text-xs text-gray-500 text-center">
                  Click to expand in list view
                </div>
              </Card>
            )
          })}
        </div>
      ) : (
        /* List View - Existing expandable list */
        <div className="space-y-2">
          {filteredRegions.map(region => {
            const regionKey = `${region.region_x},${region.region_y},${region.region_z}`
            const isExpanded = expandedRegion === regionKey
            const isEditing = editingRegionName === regionKey

            return (
              <Card key={regionKey} className="overflow-hidden p-0">
                {/* Region Header */}
                <div
                  className="p-4 cursor-pointer hover:bg-gray-800 transition-colors flex items-center justify-between"
                  onClick={() => toggleRegion(regionKey, region)}
                >
                  <div className="flex items-center gap-3">
                    {isExpanded ? (
                      <ChevronDownIcon className="w-5 h-5 text-gray-400" />
                    ) : (
                      <ChevronRightIcon className="w-5 h-5 text-gray-400" />
                    )}
                    <div>
                      <div className="text-lg font-semibold">
                        {region.custom_name ? (
                          <span className="text-purple-400">{region.custom_name}</span>
                        ) : (
                          <span className="text-gray-300">Region ({region.region_x}, {region.region_y}, {region.region_z})</span>
                        )}
                      </div>
                      <div className="text-sm text-gray-400">
                        {region._filteredCount !== undefined ? region._filteredCount : region.system_count} system{(region._filteredCount !== undefined ? region._filteredCount : region.system_count) !== 1 ? 's' : ''}
                        {region.custom_name && (
                          <span className="ml-2">• Coords: [{region.region_x}, {region.region_y}, {region.region_z}]</span>
                        )}
                        {loadingRegionSystems[regionKey] && (
                          <span className="ml-2 text-cyan-400">Loading...</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Expanded Region Content */}
                {isExpanded && (
                  <div className="border-t border-gray-700">
                    {/* Region Name Edit Section */}
                    <div className="p-4 bg-gray-800/50 border-b border-gray-700">
                      {isEditing ? (
                        <form onSubmit={(e) => submitRegionName(region, e)} className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                          <input
                            type="text"
                            className="flex-1 px-3 py-2 rounded bg-gray-700 border border-gray-600 focus:border-purple-500 focus:outline-none"
                            value={newRegionName}
                            onChange={e => setNewRegionName(e.target.value)}
                            placeholder="Enter region name"
                            autoFocus
                          />
                          <Button type="submit" variant="primary" disabled={submittingRegionName}>
                            {submittingRegionName ? 'Submitting...' : 'Submit'}
                          </Button>
                          <Button type="button" variant="ghost" onClick={cancelEditingRegionName}>
                            Cancel
                          </Button>
                        </form>
                      ) : (
                        <div className="flex items-center justify-between">
                          <div className="text-sm text-gray-400">
                            {region.custom_name ? (
                              <>Custom name: <span className="text-purple-400">{region.custom_name}</span></>
                            ) : (
                              'No custom name set for this region'
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <a
                              href={`/map/region?rx=${region.region_x}&ry=${region.region_y}&rz=${region.region_z}`}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <Button variant="ghost" className="text-sm text-cyan-400 hover:text-cyan-300">
                                <GlobeAltIcon className="w-4 h-4 mr-1 inline" />
                                Region View
                              </Button>
                            </a>
                            <Button
                              variant="ghost"
                              onClick={(e) => startEditingRegionName(region, e)}
                              className="text-sm"
                            >
                              <PencilIcon className="w-4 h-4 mr-1 inline" />
                              {region.custom_name ? 'Change Name' : 'Set Name'}
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Systems in this Region */}
                    <div className="divide-y divide-gray-700">
                      {loadingRegionSystems[regionKey] ? (
                        <div className="p-4 text-center text-gray-400">
                          Loading systems...
                        </div>
                      ) : (region._filteredSystems || regionSystems[regionKey] || region.systems || []).map(system => {
                        const isSystemExpanded = expandedSystem === system.id

                        return (
                          <div key={system.id} className="bg-gray-900/30">
                            {/* System Header */}
                            <div
                              className="p-4 pl-8 cursor-pointer hover:bg-gray-800/50 transition-colors flex items-center justify-between"
                              onClick={() => toggleSystem(system.id)}
                            >
                              <div className="flex items-center gap-3">
                                {isSystemExpanded ? (
                                  <ChevronDownIcon className="w-4 h-4 text-gray-400" />
                                ) : (
                                  <ChevronRightIcon className="w-4 h-4 text-gray-400" />
                                )}
                                <div>
                                  <div className="font-semibold flex items-center gap-2">
                                    {system.name}
                                    {/* Data Source Badge - remote vs visited */}
                                    {system.data_source === 'remote' && (
                                      <span className="text-xs bg-amber-500 text-white px-1.5 py-0.5 rounded" title="Remote data only - visit for full detail">
                                        📡
                                      </span>
                                    )}
                                    {system.data_source === 'mixed' && (
                                      <span className="text-xs bg-blue-500 text-white px-1.5 py-0.5 rounded" title="Partial data - some planets need visiting">
                                        ⚡
                                      </span>
                                    )}
                                    {/* Discord Tag Badge - visible to all, but personal username only for super admin */}
                                    {getDiscordTagBadge(system.discord_tag, system.personal_discord_username, auth?.isSuperAdmin)}
                                    {system.is_phantom && (
                                      <span className="text-xs bg-purple-600 text-white px-1.5 py-0.5 rounded" title="Phantom Star - Not normally accessible on Galactic Map">
                                        👻
                                      </span>
                                    )}
                                    {system.is_in_core && (
                                      <span className="text-xs bg-red-600 text-white px-1.5 py-0.5 rounded" title="Located in Galactic Core Void">
                                        🌀
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-sm text-gray-400">
                                    {system.galaxy || 'Euclid'} • x:{system.x} y:{system.y} z:{system.z}
                                    {system.glyph_code && (
                                      <span className="ml-2 font-mono text-xs text-purple-400">({system.glyph_code})</span>
                                    )}
                                    {system.planets?.length > 0 && (
                                      <span className="ml-2">• {system.planets.length} planet{system.planets.length !== 1 ? 's' : ''}</span>
                                    )}
                                  </div>
                                </div>
                              </div>

                              {/* System Actions */}
                              <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                                <Link to={`/wizard?edit=${encodeURIComponent(system.id || system.name)}`}>
                                  <Button variant="ghost" className="p-2">
                                    <PencilIcon className="w-4 h-4" />
                                  </Button>
                                </Link>
                                {auth?.isAdmin && (
                                  <Button
                                    variant="ghost"
                                    className="p-2"
                                    onClick={(e) => removeSystem(system.id || system.name, e)}
                                  >
                                    <TrashIcon className="w-4 h-4 text-red-400" />
                                  </Button>
                                )}
                              </div>
                            </div>

                            {/* Expanded System Content */}
                            {isSystemExpanded && (
                              <div className="pl-12 pr-4 pb-4 bg-gray-900/50">
                                {/* System Info */}
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 p-4 bg-gray-800 rounded">
                                  <div>
                                    <div className="text-xs text-gray-400">Galaxy</div>
                                    <div>{system.galaxy || 'Euclid'}</div>
                                  </div>
                                  <div>
                                    <div className="text-xs text-gray-400">Coordinates</div>
                                    <div className="font-mono text-sm">{system.x}, {system.y}, {system.z}</div>
                                  </div>
                                  {system.glyph_code && (
                                    <div>
                                      <div className="text-xs text-gray-400">Glyph Code</div>
                                      <div className="font-mono text-purple-400">{system.glyph_code}</div>
                                    </div>
                                  )}
                                  {/* Quick Tag Assignment - Super Admin Only */}
                                  {auth?.isSuperAdmin && (
                                    <div>
                                      <div className="text-xs text-gray-400">Discord Tag</div>
                                      <select
                                        className="mt-1 px-2 py-1 text-sm rounded bg-gray-700 border border-gray-600 w-full"
                                        value={system.discord_tag || ''}
                                        onChange={(e) => quickAssignTag(system.id, e.target.value)}
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        <option value="">Untagged</option>
                                        <option value="personal">Personal</option>
                                        {discordTags.map(t => (
                                          <option key={t.tag} value={t.tag}>{t.name}</option>
                                        ))}
                                      </select>
                                    </div>
                                  )}
                                  {/* Personal Discord Username - shown only to super admin */}
                                  {auth?.isSuperAdmin && system.discord_tag === 'personal' && system.personal_discord_username && (
                                    <div>
                                      <div className="text-xs text-gray-400">Contact Discord</div>
                                      <div className="text-fuchsia-400">{system.personal_discord_username}</div>
                                    </div>
                                  )}
                                  {system.star_type && (
                                    <div>
                                      <div className="text-xs text-gray-400">Star Color</div>
                                      <div className="text-yellow-400">{system.star_type}</div>
                                    </div>
                                  )}
                                  {(system.economy_type || system.economy_level) && (
                                    <div>
                                      <div className="text-xs text-gray-400">Economy</div>
                                      <div>{system.economy_type}{system.economy_level && ` (${system.economy_level})`}</div>
                                    </div>
                                  )}
                                  {system.conflict_level && (
                                    <div>
                                      <div className="text-xs text-gray-400">Conflict</div>
                                      <div>{system.conflict_level}</div>
                                    </div>
                                  )}
                                  {system.dominant_lifeform && (
                                    <div>
                                      <div className="text-xs text-gray-400">Lifeform</div>
                                      <div>{system.dominant_lifeform}</div>
                                    </div>
                                  )}
                                  {system.discovered_by && (
                                    <div>
                                      <div className="text-xs text-gray-400">Discovered By</div>
                                      <div>{system.discovered_by}</div>
                                    </div>
                                  )}
                                </div>

                                {/* System 3D View Button */}
                                <div className="mb-4">
                                  <a href={`/map/system/${encodeURIComponent(system.id)}`}>
                                    <Button variant="neutral" className="text-sm">
                                      <CubeIcon className="w-4 h-4 mr-2 inline" />
                                      View Star System (3D)
                                    </Button>
                                  </a>
                                </div>

                                {system.description && (
                                  <div className="mb-4 p-3 bg-gray-800/50 rounded">
                                    <div className="text-xs text-gray-400 mb-1">Description</div>
                                    <div className="text-gray-300">{system.description}</div>
                                  </div>
                                )}

                                {/* Discoveries */}
                                {system.discoveries?.length > 0 && (
                                  <div className="mb-4">
                                    <h4 className="text-sm font-semibold text-yellow-400 mb-2">
                                      Discoveries ({system.discoveries.length})
                                    </h4>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                      {system.discoveries.map((discovery, idx) => (
                                        <div key={idx} className="p-2 bg-yellow-900/20 border border-yellow-800/50 rounded text-sm">
                                          <div className="font-medium">{discovery.discovery_name || 'Unnamed Discovery'}</div>
                                          {discovery.discovery_type && <div className="text-xs text-gray-400">{discovery.discovery_type}</div>}
                                          {discovery.description && <div className="text-xs text-gray-300 mt-1">{discovery.description}</div>}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* Planets */}
                                <div>
                                  <h4 className="text-sm font-semibold text-cyan-400 mb-2">
                                    Planets ({system.planets?.length || 0})
                                  </h4>

                                  {!system.planets || system.planets.length === 0 ? (
                                    <div className="text-sm text-gray-400 p-2">No planets in this system</div>
                                  ) : (
                                    <div className="space-y-2">
                                      {system.planets.map((planet, planetIndex) => (
                                        <div key={planetIndex} className="border border-gray-700 rounded overflow-hidden">
                                          {/* Planet Header */}
                                          <div
                                            className="bg-gray-800 p-3 cursor-pointer hover:bg-gray-750 transition-colors flex items-center justify-between"
                                            onClick={() => togglePlanet(planetIndex)}
                                          >
                                            <div className="flex items-center gap-2">
                                              {expandedPlanets[planetIndex] ? (
                                                <ChevronDownIcon className="w-4 h-4 text-gray-400" />
                                              ) : (
                                                <ChevronRightIcon className="w-4 h-4 text-gray-400" />
                                              )}
                                              <div>
                                                <span className="font-medium">{planet.name}</span>
                                                <span className="text-sm text-gray-400 ml-2">
                                                  {planet.moons?.length > 0 && `${planet.moons.length} moon${planet.moons.length !== 1 ? 's' : ''}`}
                                                </span>
                                              </div>
                                            </div>
                                          </div>

                                          {/* Planet Details */}
                                          {expandedPlanets[planetIndex] && (
                                            <div className="p-3 bg-gray-900/50">
                                              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                                                {planet.biome && (
                                                  <div>
                                                    <div className="text-xs text-gray-400">Biome</div>
                                                    <div className="text-green-400">{planet.biome}</div>
                                                  </div>
                                                )}
                                                {planet.weather && (
                                                  <div>
                                                    <div className="text-xs text-gray-400">Weather</div>
                                                    <div className="text-sky-400">{planet.weather}</div>
                                                  </div>
                                                )}
                                                <div>
                                                  <div className="text-xs text-gray-400">Sentinels</div>
                                                  <div>{planet.sentinel || planet.sentinel_level || 'Unknown'}</div>
                                                </div>
                                                <div>
                                                  <div className="text-xs text-gray-400">Fauna</div>
                                                  <div>{planet.fauna || 'N/A'}</div>
                                                </div>
                                                <div>
                                                  <div className="text-xs text-gray-400">Flora</div>
                                                  <div>{planet.flora || 'N/A'}</div>
                                                </div>
                                                {planet.climate && planet.climate !== planet.biome && (
                                                  <div>
                                                    <div className="text-xs text-gray-400">Climate</div>
                                                    <div>{planet.climate}</div>
                                                  </div>
                                                )}
                                                {planet.has_water === 1 && (
                                                  <div>
                                                    <div className="text-xs text-gray-400">Water</div>
                                                    <div className="text-cyan-400">Present</div>
                                                  </div>
                                                )}
                                                {planet.materials && (
                                                  <div className="col-span-2 md:col-span-3">
                                                    <div className="text-xs text-gray-400">Materials</div>
                                                    <div>{planet.materials}</div>
                                                  </div>
                                                )}
                                              </div>

                                              {planet.description && (
                                                <div className="mt-3">
                                                  <div className="text-xs text-gray-400">Description</div>
                                                  <div className="text-sm text-gray-300">{planet.description}</div>
                                                </div>
                                              )}

                                              {planet.photo && (
                                                <div className="mt-3">
                                                  <img
                                                    src={getPhotoUrl(planet.photo)}
                                                    alt={planet.name}
                                                    className="max-w-xs rounded border border-gray-700"
                                                  />
                                                </div>
                                              )}

                                              {/* Moons */}
                                              {planet.moons?.length > 0 && (
                                                <div className="mt-3">
                                                  <h5 className="text-xs font-semibold text-cyan-400 mb-2">
                                                    Moons ({planet.moons.length})
                                                  </h5>
                                                  <div className="space-y-2">
                                                    {planet.moons.map((moon, moonIdx) => (
                                                      <div key={moonIdx} className="bg-gray-800 p-2 rounded border border-cyan-900/50 text-sm">
                                                        <div className="font-medium mb-1">{moon.name}</div>
                                                        <div className="grid grid-cols-3 gap-2 text-xs">
                                                          {moon.biome && (
                                                            <div>
                                                              <span className="text-gray-400">Biome: </span>
                                                              <span className="text-green-400">{moon.biome}</span>
                                                            </div>
                                                          )}
                                                          {moon.weather && (
                                                            <div>
                                                              <span className="text-gray-400">Weather: </span>
                                                              <span className="text-sky-400">{moon.weather}</span>
                                                            </div>
                                                          )}
                                                          <div>
                                                            <span className="text-gray-400">Sentinels: </span>
                                                            {moon.sentinel || 'Unknown'}
                                                          </div>
                                                          <div>
                                                            <span className="text-gray-400">Fauna: </span>
                                                            {moon.fauna || 'N/A'}
                                                          </div>
                                                          <div>
                                                            <span className="text-gray-400">Flora: </span>
                                                            {moon.flora || 'N/A'}
                                                          </div>
                                                        </div>
                                                        {moon.description && (
                                                          <div className="mt-1 text-xs text-gray-300">{moon.description}</div>
                                                        )}
                                                      </div>
                                                    ))}
                                                  </div>
                                                </div>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
