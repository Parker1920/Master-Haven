import React, { useEffect, useState, useContext, useMemo } from 'react'
import axios from 'axios'
import Card from '../components/Card'
import Button from '../components/Button'
import FormField from '../components/FormField'
import RealitySelector from '../components/RealitySelector'
import GalaxyGrid from '../components/GalaxyGrid'
import RegionBrowser from '../components/RegionBrowser'
import SystemsList from '../components/SystemsList'
import DiscordTagBadge from '../components/DiscordTagBadge'
import AdvancedFilters, { EMPTY_FILTERS } from '../components/AdvancedFilters'
import {
  MagnifyingGlassIcon,
  ChevronRightIcon,
  HomeIcon,
  XMarkIcon,
  FunnelIcon
} from '@heroicons/react/24/outline'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
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

/**
 * Containerized Systems Page
 *
 * Hierarchy: Reality → Galaxy → Region → System
 * Each level loads data lazily when selected.
 */
export default function Systems() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [searchParams, setSearchParams] = useSearchParams()

  // Hierarchy state - can be controlled via URL params
  const [selectedReality, setSelectedReality] = useState(searchParams.get('reality') || null)
  const [selectedGalaxy, setSelectedGalaxy] = useState(searchParams.get('galaxy') || null)
  const [selectedRegion, setSelectedRegion] = useState(() => {
    const rx = searchParams.get('rx')
    const ry = searchParams.get('ry')
    const rz = searchParams.get('rz')
    if (rx && ry && rz) {
      return {
        region_x: parseInt(rx),
        region_y: parseInt(ry),
        region_z: parseInt(rz),
        display_name: searchParams.get('rname') || null
      }
    }
    return null
  })

  // Search state
  const [q, setQ] = useState('')
  const debouncedQuery = useDebounce(q, 300)
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)

  // Discord tag filtering
  const [discordTags, setDiscordTags] = useState([])
  const [filterTag, setFilterTag] = useState('all')

  // View All Systems mode - shows all systems for a discord tag across all regions
  const [viewAllSystems, setViewAllSystems] = useState(false)

  // Mobile filter panel toggle
  const [showFilters, setShowFilters] = useState(false)

  // Advanced filters state
  const [advancedFilters, setAdvancedFilters] = useState({ ...EMPTY_FILTERS })

  // Fetch discord tags for filter dropdown
  useEffect(() => {
    axios.get('/api/discord_tags').then(r => {
      setDiscordTags(r.data.tags || [])
    }).catch(() => {})
  }, [])

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

  // Update URL when selection changes
  useEffect(() => {
    const params = new URLSearchParams()
    if (selectedReality) params.set('reality', selectedReality)
    if (selectedGalaxy) params.set('galaxy', selectedGalaxy)
    if (selectedRegion) {
      params.set('rx', selectedRegion.region_x.toString())
      params.set('ry', selectedRegion.region_y.toString())
      params.set('rz', selectedRegion.region_z.toString())
      if (selectedRegion.display_name) {
        params.set('rname', selectedRegion.display_name)
      }
    }
    setSearchParams(params, { replace: true })
  }, [selectedReality, selectedGalaxy, selectedRegion])

  // Selection handlers with hierarchy reset
  function handleRealitySelect(reality) {
    setSelectedReality(reality)
    setSelectedGalaxy(null)
    setSelectedRegion(null)
  }

  function handleGalaxySelect(galaxy) {
    setSelectedGalaxy(galaxy)
    setSelectedRegion(null)
  }

  function handleRegionSelect(region) {
    setSelectedRegion(region)
    setViewAllSystems(false) // Exit view all mode when selecting a region
  }

  // Handler for View All Systems button in RegionBrowser
  function handleViewAllSystems() {
    setViewAllSystems(true)
    setSelectedRegion(null) // Clear any selected region
  }

  // Breadcrumb navigation
  function goToLevel(level) {
    if (level === 'root') {
      setSelectedReality(null)
      setSelectedGalaxy(null)
      setSelectedRegion(null)
      setViewAllSystems(false)
    } else if (level === 'reality') {
      setSelectedGalaxy(null)
      setSelectedRegion(null)
      setViewAllSystems(false)
    } else if (level === 'galaxy') {
      setSelectedRegion(null)
      setViewAllSystems(false)
    } else if (level === 'viewAll') {
      // Go back to region browser from view all systems
      setViewAllSystems(false)
    }
  }

  // Determine current hierarchy depth
  const currentLevel = useMemo(() => {
    if (viewAllSystems) return 'viewAllSystems'
    if (selectedRegion) return 'systems'
    if (selectedGalaxy) return 'regions'
    if (selectedReality) return 'galaxies'
    return 'realities'
  }, [selectedReality, selectedGalaxy, selectedRegion, viewAllSystems])

  // Breadcrumb items
  const breadcrumbs = useMemo(() => {
    const items = [
      { label: 'Systems', level: 'root', active: currentLevel === 'realities' }
    ]

    if (selectedReality) {
      items.push({
        label: selectedReality,
        level: 'reality',
        active: currentLevel === 'galaxies'
      })
    }

    if (selectedGalaxy) {
      items.push({
        label: selectedGalaxy,
        level: 'galaxy',
        active: currentLevel === 'regions'
      })
    }

    if (viewAllSystems) {
      items.push({
        label: `All ${filterTag} Systems`,
        level: 'viewAll',
        active: currentLevel === 'viewAllSystems'
      })
    } else if (selectedRegion) {
      const regionName = selectedRegion.display_name || selectedRegion.custom_name ||
        `(${selectedRegion.region_x}, ${selectedRegion.region_y}, ${selectedRegion.region_z})`
      items.push({
        label: regionName,
        level: 'region',
        active: currentLevel === 'systems'
      })
    }

    return items
  }, [selectedReality, selectedGalaxy, selectedRegion, currentLevel, viewAllSystems, filterTag])

  return (
    <div className="space-y-6">
      {/* Header with Search and Breadcrumbs */}
      <div className="space-y-4">
        {/* Search Bar */}
        <div className="flex gap-2">
          <FormField className="flex-1">
            <div className="relative">
              <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                aria-label="Search systems"
                className="w-full pl-10 pr-3 py-2 rounded bg-gray-800 border border-gray-700 focus:border-cyan-500 focus:outline-none"
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Search all systems..."
              />
              {isSearching && (
                <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-cyan-400 text-sm">
                  ...
                </span>
              )}
            </div>
          </FormField>

          {/* Mobile filter toggle */}
          <button
            className={`lg:hidden px-3 py-2 rounded border transition-colors flex items-center gap-1.5 ${
              showFilters || filterTag !== 'all'
                ? 'bg-cyan-600 border-cyan-500 text-white'
                : 'bg-gray-700 border-gray-600 text-gray-300'
            }`}
            onClick={() => setShowFilters(!showFilters)}
          >
            {showFilters ? <XMarkIcon className="w-5 h-5" /> : <FunnelIcon className="w-5 h-5" />}
          </button>

          {/* Desktop filter */}
          <div className="hidden lg:flex gap-2">
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
            <Link to="/wizard"><Button variant="neutral">New System</Button></Link>
          </div>
        </div>

        {/* Mobile filter panel */}
        {showFilters && (
          <div className="lg:hidden bg-gray-800/50 rounded-lg p-4 space-y-4 border border-gray-700">
            <div>
              <label className="block text-xs text-gray-400 mb-2">Community Filter</label>
              <select
                className="w-full px-3 py-2 rounded bg-gray-700 text-white border border-gray-600"
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
            </div>
            <div className="flex gap-2 pt-2 border-t border-gray-700">
              <Button
                onClick={() => setFilterTag('all')}
                variant="ghost"
                className="flex-1"
              >
                Clear Filter
              </Button>
              <Link to="/wizard" className="flex-1">
                <Button variant="neutral" className="w-full">New System</Button>
              </Link>
            </div>
          </div>
        )}

        {/* Advanced Filters */}
        <AdvancedFilters
          filters={advancedFilters}
          onChange={setAdvancedFilters}
          reality={selectedReality}
          galaxy={selectedGalaxy}
        />

        {/* Breadcrumb Navigation */}
        <nav className="flex items-center gap-1 text-sm flex-wrap">
          {breadcrumbs.map((item, idx) => (
            <React.Fragment key={item.level}>
              {idx > 0 && (
                <ChevronRightIcon className="w-4 h-4 text-gray-500 shrink-0" />
              )}
              {item.active ? (
                <span className="px-2 py-1 rounded bg-cyan-600 text-white font-medium">
                  {idx === 0 && <HomeIcon className="w-4 h-4 inline mr-1" />}
                  {item.label}
                </span>
              ) : (
                <button
                  onClick={() => goToLevel(item.level)}
                  className="px-2 py-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
                >
                  {idx === 0 && <HomeIcon className="w-4 h-4 inline mr-1" />}
                  {item.label}
                </button>
              )}
            </React.Fragment>
          ))}
        </nav>
      </div>

      {/* Search Results (always visible when searching) */}
      {debouncedQuery.trim() && (searchResults.length > 0 || isSearching) && (
        <Card className="border-cyan-500/50">
          <h3 className="text-lg font-semibold mb-3 text-cyan-400">
            Search Results {searchResults.length > 0 && `(${searchResults.length})`}
          </h3>
          {isSearching ? (
            <div className="text-gray-400 py-4 text-center">Searching...</div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {searchResults.map(system => (
                <div
                  key={system.id}
                  className="p-3 bg-gray-800 rounded hover:bg-gray-700 cursor-pointer flex items-center justify-between transition-colors"
                  onClick={() => navigate(`/systems/${encodeURIComponent(system.id)}`)}
                >
                  <div>
                    <div className="font-semibold flex items-center gap-2">
                      {system.name}
                      <DiscordTagBadge tag={system.discord_tag} />
                      {system.star_type && (
                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                          system.star_type === 'Yellow' ? 'bg-yellow-500 text-black' :
                          system.star_type === 'Red' ? 'bg-red-500 text-white' :
                          system.star_type === 'Blue' ? 'bg-blue-500 text-white' :
                          system.star_type === 'Green' ? 'bg-green-500 text-white' :
                          system.star_type === 'Purple' ? 'bg-purple-500 text-white' :
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
                      <span className="ml-2">• {system.reality || 'Normal'}</span>
                      {system.glyph_code && (
                        <span className="ml-2 font-mono text-purple-400">({system.glyph_code})</span>
                      )}
                    </div>
                  </div>
                  <Button variant="ghost" className="text-sm shrink-0">View →</Button>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Hierarchy Content */}
      <div className="min-h-[400px]">
        {currentLevel === 'realities' && (
          <RealitySelector
            onSelect={handleRealitySelect}
            selectedReality={selectedReality}
          />
        )}

        {currentLevel === 'galaxies' && (
          <GalaxyGrid
            reality={selectedReality}
            onSelect={handleGalaxySelect}
            selectedGalaxy={selectedGalaxy}
            filters={advancedFilters}
            discordTag={filterTag}
          />
        )}

        {currentLevel === 'regions' && (
          <RegionBrowser
            reality={selectedReality}
            galaxy={selectedGalaxy}
            onSelect={handleRegionSelect}
            selectedRegion={selectedRegion}
            discordTag={filterTag}
            onViewAllSystems={handleViewAllSystems}
          />
        )}

        {currentLevel === 'systems' && (
          <SystemsList
            reality={selectedReality}
            galaxy={selectedGalaxy}
            region={selectedRegion}
            discordTag={filterTag}
            filters={advancedFilters}
          />
        )}

        {currentLevel === 'viewAllSystems' && (
          <SystemsList
            reality={selectedReality}
            galaxy={selectedGalaxy}
            discordTag={filterTag}
            globalMode={true}
            globalModeTitle={`All ${filterTag} Systems in ${selectedGalaxy}`}
            filters={advancedFilters}
          />
        )}
      </div>
    </div>
  )
}
