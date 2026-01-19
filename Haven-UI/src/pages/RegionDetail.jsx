import React, { useEffect, useState, useContext, useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import axios from 'axios'
import Card from '../components/Card'
import Button from '../components/Button'
import Modal from '../components/Modal'
import { AuthContext } from '../utils/AuthContext'
import { ChevronDownIcon, ChevronUpIcon, GlobeAltIcon, PencilIcon, FunnelIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { aggregateBiomesByCategory, getBiomeCategoryColor } from '../data/biomeCategoryMappings'

// Custom debounce hook
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value)
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(handler)
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

// Star type colors
function getStarTypeBadge(starType) {
  if (!starType) return null
  const colors = {
    'Yellow': 'bg-yellow-500 text-black',
    'Red': 'bg-red-500 text-white',
    'Green': 'bg-green-500 text-white',
    'Blue': 'bg-blue-500 text-white',
    'Purple': 'bg-purple-500 text-white',
  }
  const colorClass = colors[starType] || 'bg-gray-500 text-white'
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded ${colorClass}`}>
      {starType}
    </span>
  )
}

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

// System Card Component
function SystemCard({ system, isSelected, onSelect, showCheckbox, onClick }) {
  const photoUrl = getPhotoUrl(system.photo || (system.planets?.[0]?.photo))

  return (
    <div
      className={`relative rounded-lg border transition-all cursor-pointer hover:shadow-lg ${
        isSelected
          ? 'border-indigo-500 bg-indigo-900/30 ring-2 ring-indigo-400'
          : 'border-gray-700 bg-gray-800/50 hover:bg-gray-700/50 hover:border-gray-600'
      }`}
      onClick={onClick}
    >
      {/* Selection checkbox */}
      {showCheckbox && (
        <div className="absolute top-2 left-2 z-10" onClick={e => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onSelect}
            className="w-5 h-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
          />
        </div>
      )}

      {/* Photo thumbnail */}
      <div className="h-32 bg-gray-900 rounded-t-lg overflow-hidden">
        {photoUrl ? (
          <img
            src={photoUrl}
            alt={system.name}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-600">
            <GlobeAltIcon className="w-12 h-12" />
          </div>
        )}
      </div>

      {/* System info */}
      <div className="p-3">
        <h3 className="font-semibold text-lg truncate mb-2" title={system.name}>
          {system.name}
        </h3>

        {/* Badges row */}
        <div className="flex flex-wrap gap-1 mb-2">
          {getStarTypeBadge(system.star_type)}
          <span className="text-xs bg-blue-600/50 text-blue-200 px-1.5 py-0.5 rounded">
            {system.galaxy || 'Euclid'}
          </span>
          {getDiscordTagBadge(system.discord_tag)}
        </div>

        {/* Stats */}
        <div className="text-sm text-gray-400 flex items-center gap-3">
          <span>{system.planets?.length || system.planet_count || 0} planets</span>
          {system.glyph_code && (
            <span className="font-mono text-purple-400 text-xs truncate" title={system.glyph_code}>
              {system.glyph_code.substring(0, 8)}...
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default function RegionDetail() {
  const { rx, ry, rz } = useParams()
  const navigate = useNavigate()
  const auth = useContext(AuthContext)

  // Data state
  const [region, setRegion] = useState(null)
  const [systems, setSystems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [totalSystems, setTotalSystems] = useState(0)
  const systemsPerPage = 100

  // Discord tags for filter
  const [discordTags, setDiscordTags] = useState([])

  // Filter state
  const [searchQuery, setSearchQuery] = useState('')
  const debouncedSearch = useDebounce(searchQuery, 300)
  const [filterGalaxy, setFilterGalaxy] = useState('all')
  const [filterStarType, setFilterStarType] = useState('all')
  const [filterDiscordTag, setFilterDiscordTag] = useState('all')

  // Sort state
  const [sortBy, setSortBy] = useState('name')
  const [sortOrder, setSortOrder] = useState('asc')

  // Mobile filter panel toggle
  const [showFilters, setShowFilters] = useState(false)

  // Bulk selection (admin)
  const [bulkMode, setBulkMode] = useState(false)
  const [selectedSystems, setSelectedSystems] = useState(new Set())

  // Stats breakdown visibility
  const [showBreakdown, setShowBreakdown] = useState(false)

  // Edit region name modal
  const [editNameModalOpen, setEditNameModalOpen] = useState(false)
  const [newRegionName, setNewRegionName] = useState('')
  const [newRegionDiscordTag, setNewRegionDiscordTag] = useState(null)
  const [submitterDiscordUsername, setSubmitterDiscordUsername] = useState('')
  const [submittingName, setSubmittingName] = useState(false)

  // Load data when region changes (reset to page 1)
  useEffect(() => {
    setCurrentPage(1)
    loadRegion()
  }, [rx, ry, rz])

  // Load systems when page changes
  useEffect(() => {
    loadSystems()
  }, [rx, ry, rz, currentPage])

  useEffect(() => {
    axios.get('/api/discord_tags').then(r => {
      setDiscordTags(r.data.tags || [])
    }).catch(() => {})
  }, [])

  async function loadRegion() {
    setLoading(true)
    setError(null)
    try {
      const regionRes = await axios.get(`/api/regions/${rx}/${ry}/${rz}`)
      setRegion(regionRes.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load region data')
    } finally {
      setLoading(false)
    }
  }

  async function loadSystems() {
    try {
      const systemsRes = await axios.get(
        `/api/regions/${rx}/${ry}/${rz}/systems?include_planets=true&limit=${systemsPerPage}&page=${currentPage}`
      )
      setSystems(systemsRes.data.systems || [])
      setTotalSystems(systemsRes.data.total || 0)
    } catch (err) {
      console.error('Failed to load systems:', err)
      setSystems([])
      setTotalSystems(0)
    }
  }

  // Combined reload function for UI buttons
  async function loadData() {
    await Promise.all([loadRegion(), loadSystems()])
  }

  // Compute stats from loaded systems
  const stats = useMemo(() => {
    let planetCount = 0
    let moonCount = 0
    let discoveryCount = 0
    const galaxies = new Set()
    const rawBiomeDistribution = {}
    const economyDistribution = {}
    const starTypeDistribution = {}

    systems.forEach(system => {
      galaxies.add(system.galaxy || 'Euclid')

      const starType = system.star_type || 'Unknown'
      starTypeDistribution[starType] = (starTypeDistribution[starType] || 0) + 1

      const economy = system.economy_type || 'Unknown'
      economyDistribution[economy] = (economyDistribution[economy] || 0) + 1

      discoveryCount += (system.discoveries?.length || 0)

      const planets = system.planets || []
      planetCount += planets.length

      planets.forEach(planet => {
        moonCount += (planet.moons?.length || 0)

        const biome = planet.biome || 'Unknown'
        rawBiomeDistribution[biome] = (rawBiomeDistribution[biome] || 0) + 1
      })
    })

    // Aggregate biomes by parent category
    const biomeDistribution = aggregateBiomesByCategory(rawBiomeDistribution)

    return {
      systemCount: systems.length,
      planetCount,
      moonCount,
      discoveryCount,
      galaxies: Array.from(galaxies),
      biomeDistribution,
      rawBiomeDistribution,
      economyDistribution,
      starTypeDistribution
    }
  }, [systems])

  // Get unique values for filters
  const filterOptions = useMemo(() => {
    const galaxies = new Set()
    const starTypes = new Set()

    systems.forEach(system => {
      if (system.galaxy) galaxies.add(system.galaxy)
      if (system.star_type) starTypes.add(system.star_type)
    })

    return {
      galaxies: Array.from(galaxies).sort(),
      starTypes: Array.from(starTypes).sort()
    }
  }, [systems])

  // Count active filters for mobile badge
  const activeFilterCount = useMemo(() => {
    let count = 0
    if (filterGalaxy !== 'all') count++
    if (filterStarType !== 'all') count++
    if (filterDiscordTag !== 'all') count++
    return count
  }, [filterGalaxy, filterStarType, filterDiscordTag])

  // Pagination calculations
  const totalPages = Math.ceil(totalSystems / systemsPerPage)
  const startSystem = totalSystems === 0 ? 0 : (currentPage - 1) * systemsPerPage + 1
  const endSystem = Math.min(currentPage * systemsPerPage, totalSystems)

  // Filtered and sorted systems
  const filteredSystems = useMemo(() => {
    let result = [...systems]

    // Search filter
    if (debouncedSearch.trim()) {
      const query = debouncedSearch.toLowerCase()
      result = result.filter(s =>
        s.name?.toLowerCase().includes(query) ||
        s.glyph_code?.toLowerCase().includes(query) ||
        s.description?.toLowerCase().includes(query)
      )
    }

    // Galaxy filter
    if (filterGalaxy !== 'all') {
      result = result.filter(s => s.galaxy === filterGalaxy)
    }

    // Star type filter
    if (filterStarType !== 'all') {
      result = result.filter(s => s.star_type === filterStarType)
    }

    // Discord tag filter
    if (filterDiscordTag !== 'all') {
      if (filterDiscordTag === 'untagged') {
        result = result.filter(s => !s.discord_tag)
      } else {
        result = result.filter(s => s.discord_tag === filterDiscordTag)
      }
    }

    // Sort
    result.sort((a, b) => {
      let cmp = 0
      switch (sortBy) {
        case 'name':
          cmp = (a.name || '').localeCompare(b.name || '')
          break
        case 'date':
          cmp = new Date(a.created_at || 0) - new Date(b.created_at || 0)
          break
        case 'planets':
          cmp = (a.planets?.length || 0) - (b.planets?.length || 0)
          break
        default:
          cmp = 0
      }
      return sortOrder === 'asc' ? cmp : -cmp
    })

    return result
  }, [systems, debouncedSearch, filterGalaxy, filterStarType, filterDiscordTag, sortBy, sortOrder])

  // Bulk selection handlers
  function toggleSystemSelection(systemId) {
    setSelectedSystems(prev => {
      const next = new Set(prev)
      if (next.has(systemId)) {
        next.delete(systemId)
      } else {
        next.add(systemId)
      }
      return next
    })
  }

  function selectAll() {
    setSelectedSystems(new Set(filteredSystems.map(s => s.id)))
  }

  function clearSelection() {
    setSelectedSystems(new Set())
  }

  function exitBulkMode() {
    setBulkMode(false)
    setSelectedSystems(new Set())
  }

  // Submit region name
  async function handleSubmitName(e) {
    e.preventDefault()
    if (!newRegionName.trim()) return

    // Check if user is logged in (partner/sub-admin) - use their session username
    const isLoggedIn = auth?.isAdmin && !auth?.isSuperAdmin
    const effectiveUsername = isLoggedIn ? auth?.user?.username : submitterDiscordUsername.trim()

    // Validation for non-super-admin users
    if (!auth?.isSuperAdmin) {
      if (!newRegionDiscordTag) {
        alert('Please select a Discord Community')
        return
      }
      // Only require manual Discord username for anonymous users
      if (!isLoggedIn && !submitterDiscordUsername.trim()) {
        alert('Please enter your Discord Username')
        return
      }
    }

    setSubmittingName(true)
    try {
      if (auth?.isSuperAdmin) {
        // Super admin can update directly
        await axios.put(`/api/regions/${rx}/${ry}/${rz}`, { custom_name: newRegionName.trim() })
      } else {
        // Others submit for approval with Discord info
        await axios.post(`/api/regions/${rx}/${ry}/${rz}/submit`, {
          proposed_name: newRegionName.trim(),
          discord_tag: newRegionDiscordTag,
          personal_discord_username: effectiveUsername
        })
      }
      setEditNameModalOpen(false)
      setNewRegionName('')
      setNewRegionDiscordTag(null)
      setSubmitterDiscordUsername('')
      loadData()
      alert(auth?.isSuperAdmin ? 'Region name updated!' : 'Name submitted for approval!')
    } catch (err) {
      alert('Failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setSubmittingName(false)
    }
  }

  // Distribution bar component
  function DistributionBar({ title, data, colorFn }) {
    const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
    const total = entries.reduce((sum, [, count]) => sum + count, 0)
    if (total === 0) return null

    return (
      <div className="bg-gray-800 rounded p-3">
        <h4 className="text-sm font-semibold mb-2 text-gray-300">{title}</h4>
        <div className="space-y-1">
          {entries.slice(0, 5).map(([name, count]) => (
            <div key={name} className="flex items-center gap-2">
              <div className="flex-1">
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="text-gray-400">{name}</span>
                  <span className="text-gray-500">{count}</span>
                </div>
                <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${colorFn ? colorFn(name) : 'bg-cyan-500'}`}
                    style={{ width: `${(count / total) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
          {entries.length > 5 && (
            <div className="text-xs text-gray-500 mt-1">+{entries.length - 5} more</div>
          )}
        </div>
      </div>
    )
  }

  // Biome Distribution component with scroll to show all categories
  function BiomeDistributionBar({ data }) {
    const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
    const total = entries.reduce((sum, [, count]) => sum + count, 0)
    if (total === 0) return null

    return (
      <div className="bg-gray-800 rounded p-3">
        <h4 className="text-sm font-semibold mb-2 text-gray-300">Biomes</h4>
        <div className="max-h-64 overflow-y-auto pr-1 space-y-1 scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800">
          {entries.map(([name, count]) => (
            <div key={name} className="flex items-center gap-2">
              <div className="flex-1">
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="text-gray-400">{name}</span>
                  <span className="text-gray-500">{count}</span>
                </div>
                <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${getBiomeCategoryColor(name)}`}
                    style={{ width: `${(count / total) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="text-xs text-gray-500 mt-2 pt-2 border-t border-gray-700">
          {entries.length} biome categories | {total} total planets
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="p-6">
        <Card>
          <div className="text-center py-8">Loading region...</div>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <Card>
          <div className="text-center py-8 text-red-500">{error}</div>
          <div className="text-center mt-4">
            <Button onClick={() => navigate('/systems')}>Back to Systems</Button>
          </div>
        </Card>
      </div>
    )
  }

  const regionName = region?.custom_name || `Region (${rx}, ${ry}, ${rz})`

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <Card className="mb-4">
        <div className="flex flex-col lg:flex-row justify-between items-start gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold mb-1">
              {region?.custom_name ? (
                <span className="text-purple-400">{region.custom_name}</span>
              ) : (
                <span className="text-gray-300">Region ({rx}, {ry}, {rz})</span>
              )}
            </h1>
            <div className="text-sm text-gray-400">
              Coordinates: [{rx}, {ry}, {rz}]
              {region?.pending_name && (
                <span className="ml-3 text-yellow-400">
                  Pending name: "{region.pending_name.proposed_name}"
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <a
              href={`/map/region?rx=${rx}&ry=${ry}&rz=${rz}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button className="bg-cyan-600 hover:bg-cyan-700">
                <GlobeAltIcon className="w-4 h-4 mr-1 inline" />
                3D Map
              </Button>
            </a>
            <Button
              className="bg-purple-600 hover:bg-purple-700"
              onClick={() => {
                setNewRegionName(region?.custom_name || '')
                setEditNameModalOpen(true)
              }}
            >
              <PencilIcon className="w-4 h-4 mr-1 inline" />
              {region?.custom_name ? 'Edit Name' : 'Set Name'}
            </Button>
            <Button
              className="bg-gray-600 hover:bg-gray-700"
              onClick={() => navigate('/systems')}
            >
              Back
            </Button>
          </div>
        </div>
      </Card>

      {/* Stats Bar */}
      <Card className="mb-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <div className="text-center p-3 bg-gray-800 rounded">
            <div className="text-2xl font-bold text-cyan-400">{totalSystems}</div>
            <div className="text-xs text-gray-400">Systems</div>
          </div>
          <div className="text-center p-3 bg-gray-800 rounded">
            <div className="text-2xl font-bold text-green-400">{stats.planetCount}</div>
            <div className="text-xs text-gray-400">Planets</div>
          </div>
          <div className="text-center p-3 bg-gray-800 rounded">
            <div className="text-2xl font-bold text-purple-400">{stats.moonCount}</div>
            <div className="text-xs text-gray-400">Moons</div>
          </div>
          <div className="text-center p-3 bg-gray-800 rounded">
            <div className="text-2xl font-bold text-yellow-400">{stats.discoveryCount}</div>
            <div className="text-xs text-gray-400">Discoveries</div>
          </div>
          <div className="text-center p-3 bg-gray-800 rounded">
            <div className="text-lg font-bold text-blue-400">{stats.galaxies.join(', ')}</div>
            <div className="text-xs text-gray-400">Galaxies</div>
          </div>
        </div>

        {/* Toggle breakdown */}
        <button
          className="w-full mt-3 py-2 text-sm text-gray-400 hover:text-white flex items-center justify-center gap-1"
          onClick={() => setShowBreakdown(!showBreakdown)}
        >
          {showBreakdown ? (
            <>Hide Breakdown <ChevronUpIcon className="w-4 h-4" /></>
          ) : (
            <>Show Breakdown <ChevronDownIcon className="w-4 h-4" /></>
          )}
        </button>

        {/* Distribution breakdown */}
        {showBreakdown && (
          <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-4">
            <BiomeDistributionBar data={stats.biomeDistribution} />
            <DistributionBar
              title="Star Types"
              data={stats.starTypeDistribution}
              colorFn={(name) => {
                const colors = {
                  'Yellow': 'bg-yellow-500', 'Red': 'bg-red-500', 'Green': 'bg-green-500',
                  'Blue': 'bg-blue-500', 'Purple': 'bg-purple-500'
                }
                return colors[name] || 'bg-gray-500'
              }}
            />
            <DistributionBar
              title="Economy Types"
              data={stats.economyDistribution}
              colorFn={() => 'bg-emerald-500'}
            />
          </div>
        )}
      </Card>

      {/* Filters & Sort Bar - Mobile Optimized */}
      <Card className="mb-4">
        <div className="space-y-3">
          {/* Top Row: Search + Filter Toggle (mobile) / Full controls (desktop) */}
          <div className="flex gap-2">
            {/* Search - Always visible */}
            <div className="flex-1">
              <input
                type="text"
                placeholder="Search systems..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full px-3 py-2 rounded bg-gray-800 border border-gray-700 focus:border-cyan-500 focus:outline-none"
              />
            </div>

            {/* Mobile: Filter toggle button */}
            <button
              className={`lg:hidden px-3 py-2 rounded border transition-colors flex items-center gap-1.5 ${
                showFilters || activeFilterCount > 0
                  ? 'bg-cyan-600 border-cyan-500 text-white'
                  : 'bg-gray-700 border-gray-600 text-gray-300'
              }`}
              onClick={() => setShowFilters(!showFilters)}
            >
              {showFilters ? <XMarkIcon className="w-5 h-5" /> : <FunnelIcon className="w-5 h-5" />}
              {activeFilterCount > 0 && !showFilters && (
                <span className="bg-white text-cyan-600 text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                  {activeFilterCount}
                </span>
              )}
            </button>

            {/* Desktop: Inline filters */}
            <div className="hidden lg:flex flex-wrap gap-2">
              <select
                value={filterGalaxy}
                onChange={e => setFilterGalaxy(e.target.value)}
                className="px-3 py-2 rounded bg-gray-800 border border-gray-700 text-sm"
              >
                <option value="all">All Galaxies</option>
                {filterOptions.galaxies.map(g => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>

              <select
                value={filterStarType}
                onChange={e => setFilterStarType(e.target.value)}
                className="px-3 py-2 rounded bg-gray-800 border border-gray-700 text-sm"
              >
                <option value="all">All Stars</option>
                {filterOptions.starTypes.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>

              <select
                value={filterDiscordTag}
                onChange={e => setFilterDiscordTag(e.target.value)}
                className="px-3 py-2 rounded bg-gray-800 border border-gray-700 text-sm"
              >
                <option value="all">All Tags</option>
                <option value="untagged">Untagged</option>
                {discordTags.map(t => (
                  <option key={t.tag} value={t.tag}>{t.name}</option>
                ))}
              </select>

              <select
                value={`${sortBy}-${sortOrder}`}
                onChange={e => {
                  const [by, order] = e.target.value.split('-')
                  setSortBy(by)
                  setSortOrder(order)
                }}
                className="px-3 py-2 rounded bg-gray-800 border border-gray-700 text-sm"
              >
                <option value="name-asc">Name A-Z</option>
                <option value="name-desc">Name Z-A</option>
                <option value="date-desc">Newest First</option>
                <option value="date-asc">Oldest First</option>
                <option value="planets-desc">Most Planets</option>
                <option value="planets-asc">Fewest Planets</option>
              </select>
            </div>
          </div>

          {/* Mobile: Collapsible Filter Panel */}
          {showFilters && (
            <div className="lg:hidden bg-gray-800/50 rounded-lg p-4 space-y-4 border border-gray-700">
              {/* Sort */}
              <div>
                <label className="block text-xs text-gray-400 mb-2">Sort By</label>
                <select
                  value={`${sortBy}-${sortOrder}`}
                  onChange={e => {
                    const [by, order] = e.target.value.split('-')
                    setSortBy(by)
                    setSortOrder(order)
                  }}
                  className="w-full px-3 py-2 rounded bg-gray-700 border border-gray-600 text-sm"
                >
                  <option value="name-asc">Name A-Z</option>
                  <option value="name-desc">Name Z-A</option>
                  <option value="date-desc">Newest First</option>
                  <option value="date-asc">Oldest First</option>
                  <option value="planets-desc">Most Planets</option>
                  <option value="planets-asc">Fewest Planets</option>
                </select>
              </div>

              {/* Galaxy Filter */}
              <div>
                <label className="block text-xs text-gray-400 mb-2">Galaxy</label>
                <select
                  value={filterGalaxy}
                  onChange={e => setFilterGalaxy(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-gray-700 border border-gray-600 text-sm"
                >
                  <option value="all">All Galaxies</option>
                  {filterOptions.galaxies.map(g => (
                    <option key={g} value={g}>{g}</option>
                  ))}
                </select>
              </div>

              {/* Star Type Filter */}
              <div>
                <label className="block text-xs text-gray-400 mb-2">Star Type</label>
                <select
                  value={filterStarType}
                  onChange={e => setFilterStarType(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-gray-700 border border-gray-600 text-sm"
                >
                  <option value="all">All Stars</option>
                  {filterOptions.starTypes.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              {/* Discord Tag Filter */}
              <div>
                <label className="block text-xs text-gray-400 mb-2">Community Tag</label>
                <select
                  value={filterDiscordTag}
                  onChange={e => setFilterDiscordTag(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-gray-700 border border-gray-600 text-sm"
                >
                  <option value="all">All Tags</option>
                  <option value="untagged">Untagged</option>
                  {discordTags.map(t => (
                    <option key={t.tag} value={t.tag}>{t.name}</option>
                  ))}
                </select>
              </div>

              {/* Clear Filters */}
              {activeFilterCount > 0 && (
                <button
                  onClick={() => {
                    setFilterGalaxy('all')
                    setFilterStarType('all')
                    setFilterDiscordTag('all')
                  }}
                  className="w-full py-2 text-sm text-cyan-400 hover:text-cyan-300 border border-gray-600 rounded"
                >
                  Clear All Filters
                </button>
              )}
            </div>
          )}
        </div>

        {/* Bulk mode toggle (admin only) */}
        {auth?.isAdmin && (
          <div className="mt-3 flex items-center justify-between border-t border-gray-700 pt-3">
            <div className="flex items-center gap-3">
              <Button
                className={bulkMode ? 'bg-amber-600 hover:bg-amber-700' : 'bg-indigo-600 hover:bg-indigo-700'}
                onClick={() => bulkMode ? exitBulkMode() : setBulkMode(true)}
              >
                {bulkMode ? 'Exit Bulk Mode' : 'Bulk Mode'}
              </Button>

              {bulkMode && (
                <>
                  <span className="text-sm text-gray-400">
                    {selectedSystems.size} selected
                  </span>
                  <button onClick={selectAll} className="text-sm text-indigo-400 hover:text-indigo-300 underline">
                    Select All
                  </button>
                  {selectedSystems.size > 0 && (
                    <button onClick={clearSelection} className="text-sm text-gray-400 hover:text-white underline">
                      Clear
                    </button>
                  )}
                </>
              )}
            </div>

            {bulkMode && selectedSystems.size > 0 && (
              <div className="flex gap-2">
                <Button className="bg-red-600 hover:bg-red-700 text-sm">
                  Delete ({selectedSystems.size})
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Results count */}
      <div className="mb-3 text-sm text-gray-400 flex flex-wrap items-center justify-between gap-2">
        <span>
          Showing {startSystem}-{endSystem} of {totalSystems} systems
          {debouncedSearch && ` (${filteredSystems.length} matching "${debouncedSearch}")`}
        </span>
        {totalPages > 1 && (
          <span className="text-cyan-400">
            Page {currentPage} of {totalPages}
          </span>
        )}
      </div>

      {/* Systems Grid */}
      {filteredSystems.length === 0 ? (
        <Card>
          <div className="text-center py-8 text-gray-400">
            {totalSystems === 0 ? 'No systems in this region' : 'No systems match your filters'}
          </div>
        </Card>
      ) : (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
          {filteredSystems.map(system => (
            <SystemCard
              key={system.id}
              system={system}
              isSelected={selectedSystems.has(system.id)}
              onSelect={() => toggleSystemSelection(system.id)}
              showCheckbox={bulkMode}
              onClick={() => {
                if (!bulkMode) {
                  navigate(`/systems/${encodeURIComponent(system.id)}`)
                }
              }}
            />
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          {/* First & Previous */}
          <Button
            variant="ghost"
            className="px-3 py-2"
            onClick={() => setCurrentPage(1)}
            disabled={currentPage === 1}
          >
            « First
          </Button>
          <Button
            variant="ghost"
            className="px-3 py-2"
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            ‹ Prev
          </Button>

          {/* Page numbers */}
          <div className="flex items-center gap-1">
            {(() => {
              const pages = []
              const maxVisible = 5
              let start = Math.max(1, currentPage - Math.floor(maxVisible / 2))
              let end = Math.min(totalPages, start + maxVisible - 1)

              if (end - start + 1 < maxVisible) {
                start = Math.max(1, end - maxVisible + 1)
              }

              if (start > 1) {
                pages.push(
                  <span key="start-ellipsis" className="px-2 text-gray-500">...</span>
                )
              }

              for (let i = start; i <= end; i++) {
                pages.push(
                  <button
                    key={i}
                    onClick={() => setCurrentPage(i)}
                    className={`px-3 py-1 rounded transition-colors ${
                      i === currentPage
                        ? 'bg-cyan-600 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    {i}
                  </button>
                )
              }

              if (end < totalPages) {
                pages.push(
                  <span key="end-ellipsis" className="px-2 text-gray-500">...</span>
                )
              }

              return pages
            })()}
          </div>

          {/* Next & Last */}
          <Button
            variant="ghost"
            className="px-3 py-2"
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
          >
            Next ›
          </Button>
          <Button
            variant="ghost"
            className="px-3 py-2"
            onClick={() => setCurrentPage(totalPages)}
            disabled={currentPage === totalPages}
          >
            Last »
          </Button>
        </div>
      )}

      {/* Edit Name Modal */}
      {editNameModalOpen && (
        <Modal
          title={region?.custom_name ? 'Edit Region Name' : 'Set Region Name'}
          onClose={() => setEditNameModalOpen(false)}
        >
          <form onSubmit={handleSubmitName} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold mb-2">Region Name</label>
              <input
                type="text"
                value={newRegionName}
                onChange={e => setNewRegionName(e.target.value)}
                placeholder="Enter region name..."
                className="w-full px-3 py-2 rounded border border-gray-600 bg-gray-800 focus:border-purple-500 focus:outline-none"
                autoFocus
              />
              {!auth?.isSuperAdmin && (
                <p className="text-xs text-gray-400 mt-1">
                  Your submission will be reviewed before approval.
                </p>
              )}
            </div>

            {/* Discord fields for non-super-admin users */}
            {!auth?.isSuperAdmin && (
              <>
                <div>
                  <label className="block text-sm font-semibold mb-2">
                    Discord Community <span className="text-red-400">*</span>
                  </label>
                  <select
                    className={`w-full px-3 py-2 rounded border bg-gray-800 focus:outline-none ${
                      !newRegionDiscordTag ? 'border-red-500' : 'border-gray-600 focus:border-purple-500'
                    }`}
                    value={newRegionDiscordTag || ''}
                    onChange={e => setNewRegionDiscordTag(e.target.value || null)}
                    required
                  >
                    <option value="">-- Select Community (Required) --</option>
                    {discordTags.map(t => (
                      <option key={t.tag} value={t.tag}>{t.name} ({t.tag})</option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    Which Discord community will review this region name?
                  </p>
                </div>

                {/* For logged-in users, show their username; for anonymous, show input field */}
                {auth?.isAdmin ? (
                  <div>
                    <label className="block text-sm font-semibold mb-2">Submitting As</label>
                    <div className="w-full px-3 py-2 rounded border border-gray-600 bg-gray-700 text-gray-300">
                      {auth?.user?.username || 'Unknown'}
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Your logged-in username will be used for tracking
                    </p>
                  </div>
                ) : (
                  <div>
                    <label className="block text-sm font-semibold mb-2">
                      Your Discord Username <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={submitterDiscordUsername}
                      onChange={e => setSubmitterDiscordUsername(e.target.value)}
                      placeholder="e.g., YourName#1234"
                      className={`w-full px-3 py-2 rounded border bg-gray-800 focus:outline-none ${
                        !submitterDiscordUsername.trim() ? 'border-red-500' : 'border-gray-600 focus:border-purple-500'
                      }`}
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      So we can contact you if needed
                    </p>
                  </div>
                )}
              </>
            )}

            <div className="flex gap-2">
              <Button
                type="submit"
                className="bg-purple-600 hover:bg-purple-700"
                disabled={submittingName || !newRegionName.trim()}
              >
                {submittingName ? 'Submitting...' : (auth?.isSuperAdmin ? 'Save' : 'Submit for Approval')}
              </Button>
              <Button
                type="button"
                className="bg-gray-600 hover:bg-gray-700"
                onClick={() => setEditNameModalOpen(false)}
                disabled={submittingName}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
