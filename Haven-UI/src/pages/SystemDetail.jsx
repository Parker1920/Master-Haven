import React, { useEffect, useState, useContext } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import axios from 'axios'
import Card from '../components/Card'
import Button from '../components/Button'
import GlyphDisplay from '../components/GlyphDisplay'
import { AuthContext } from '../utils/AuthContext'
import { getTradeGoodById } from '../utils/economyTradeGoods'
import { getFaunaColor, getFloraColor, getSentinelColor } from '../utils/adjectiveColors'

// Helper to normalize photo paths - handles "photos\file.jpg", "photos/file.jpg", or just "file.jpg"
function getPhotoUrl(photo) {
  if (!photo) return null
  if (photo.startsWith('http')) return photo
  // Normalize backslashes to forward slashes first, then extract just the filename
  const normalized = photo.replace(/\\/g, '/')
  const parts = normalized.split('/')
  const filename = parts[parts.length - 1]
  return `/haven-ui-photos/${encodeURIComponent(filename)}`
}

// Format date for display
function formatDate(dateStr) {
  if (!dateStr) return null
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  } catch {
    return dateStr
  }
}

// Format a contributor date nicely
function formatContribDate(dateStr) {
  if (!dateStr) return null
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return null
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch { return null }
}

// Contributors Modal Component
function ContributorsModal({ system, onClose }) {
  if (!system) return null

  // Parse contributors JSON - supports both old ["name"] and new [{name, action, date}] formats
  let contributors = []
  if (system.contributors) {
    try {
      const raw = typeof system.contributors === 'string'
        ? JSON.parse(system.contributors)
        : system.contributors
      // Normalize: old format strings become upload entries
      contributors = (raw || []).map(entry =>
        typeof entry === 'string'
          ? { name: entry, action: 'upload', date: null }
          : entry
      )
    } catch {
      contributors = []
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-gray-800 rounded-lg shadow-xl max-w-md w-full p-6 border border-gray-700"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xl font-bold text-purple-400">System Contributors</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Original Uploader */}
        <div className="mb-4 p-3 bg-gray-900 rounded">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Original Uploader</div>
          <div className="text-lg text-yellow-400 font-medium">
            {system.discovered_by || 'Unknown'}
          </div>
          {(system.discovered_at || (contributors[0] && contributors[0].date)) && (
            <div className="text-xs text-gray-500 mt-1">
              {formatContribDate(system.discovered_at || contributors[0]?.date)}
            </div>
          )}
        </div>

        {/* All Contributors */}
        {contributors.length > 0 && (
          <div className="p-3 bg-gray-900 rounded">
            <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">All Contributors</div>
            <div className="space-y-2">
              {contributors.map((entry, idx) => {
                const isUpload = entry.action === 'upload'
                return (
                  <div
                    key={idx}
                    className={`flex items-center justify-between px-3 py-2 rounded-lg ${
                      isUpload
                        ? 'bg-yellow-600/20 border border-yellow-600/40'
                        : 'bg-gray-700/60'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={isUpload ? 'text-yellow-400 font-medium' : 'text-gray-300'}>
                        {entry.name}
                      </span>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        isUpload
                          ? 'bg-yellow-600/40 text-yellow-300'
                          : 'bg-blue-600/40 text-blue-300'
                      }`}>
                        {isUpload ? 'OG' : 'edit'}
                      </span>
                    </div>
                    {entry.date && (
                      <span className="text-xs text-gray-500">
                        {formatContribDate(entry.date)}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* No data message */}
        {!system.discovered_by && contributors.length === 0 && (
          <div className="text-center text-gray-500 py-4">
            No contributor information available for this system.
          </div>
        )}

        <div className="mt-6 text-center">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default function SystemDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [system, setSystem] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedPlanets, setExpandedPlanets] = useState({})
  const [showContributors, setShowContributors] = useState(false)
  const [expandedGradeCategory, setExpandedGradeCategory] = useState(null)

  useEffect(() => {
    loadSystem()
  }, [id])

  async function loadSystem() {
    try {
      setLoading(true)
      const response = await axios.get(`/api/systems/${encodeURIComponent(id)}`)
      setSystem(response.data)
      setError(null)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load system')
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete() {
    if (!confirm(`Are you sure you want to delete the system "${system.name}"?`)) {
      return
    }

    try {
      await axios.delete(`/api/systems/${encodeURIComponent(id)}`)
      alert('System deleted successfully')
      navigate('/systems')
    } catch (err) {
      alert(`Failed to delete system: ${err.response?.data?.detail || err.message}`)
    }
  }

  function togglePlanetExpanded(index) {
    setExpandedPlanets(prev => ({
      ...prev,
      [index]: !prev[index]
    }))
  }

  if (loading) {
    return (
      <div className="p-6">
        <Card>
          <div className="text-center py-8">Loading system...</div>
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

  if (!system) {
    return (
      <div className="p-6">
        <Card>
          <div className="text-center py-8">System not found</div>
          <div className="text-center mt-4">
            <Button onClick={() => navigate('/systems')}>Back to Systems</Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto">
      {/* Header Section */}
      <Card className="mb-6">
        <div className="flex flex-col sm:flex-row justify-between items-start gap-3 mb-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl sm:text-3xl font-bold mb-2 break-words">{system.name}</h1>
            <div className="text-sm text-gray-400">
              <span className="mr-4">Galaxy: {system.galaxy || 'Euclid'}</span>
              {system.region_x !== null && system.region_x !== undefined && (
                <span className="mr-4">Region: [{system.region_x}, {system.region_y}, {system.region_z}]</span>
              )}
              <span className="block sm:inline mt-1 sm:mt-0">ID: {system.id}</span>
            </div>
            {/* Glyph Code */}
            {system.glyph_code && (
              <div className="mt-2 flex items-center gap-3">
                <GlyphDisplay glyphCode={system.glyph_code} size="large" />
                <span className="text-purple-400 font-mono text-sm">({system.glyph_code})</span>
              </div>
            )}
          </div>
          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto flex-shrink-0">
            <a
              href={`/map/system/${system.id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 rounded text-white text-center font-medium transition-colors w-full sm:w-auto"
            >
              3D Map
            </a>
            <Button
              className="bg-blue-600 hover:bg-blue-700 w-full sm:w-auto"
              onClick={() => navigate(`/create?edit=${encodeURIComponent(system.id || system.name)}`)}
            >
              Edit
            </Button>
            <Button
              className="bg-purple-600 hover:bg-purple-700 w-full sm:w-auto"
              onClick={() => setShowContributors(true)}
            >
              Contributors
            </Button>
            {auth?.isAdmin && (
              <Button
                className="bg-red-600 hover:bg-red-700 w-full sm:w-auto"
                onClick={handleDelete}
              >
                Delete
              </Button>
            )}
            <Button
              className="bg-gray-600 hover:bg-gray-700 w-full sm:w-auto"
              onClick={() => navigate('/systems')}
            >
              Back
            </Button>
          </div>
        </div>

        {/* Completeness Grade Panel */}
        {system.completeness_grade && (() => {
          const gradeStyles = {
            'S': { color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30', label: 'Archive Quality' },
            'A': { color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', label: 'Well Documented' },
            'B': { color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30', label: 'Partial Data' },
            'C': { color: 'text-gray-400', bg: 'bg-gray-500/10', border: 'border-gray-500/30', label: 'Basic Info' },
          }
          const g = gradeStyles[system.completeness_grade] || gradeStyles['C']
          const b = system.completeness_breakdown || {}
          const details = b.details || {}
          const score = system.completeness_score || 0
          const categories = [
            { key: 'system_core', label: 'System Core', value: b.system_core || 0, max: 35 },
            { key: 'system_extra', label: 'System Extra', value: b.system_extra || 0, max: 10 },
            { key: 'planet_coverage', label: 'Planet Coverage', value: b.planet_coverage || 0, max: 10 },
            { key: 'planet_environment', label: 'Planet Environment', value: b.planet_environment || 0, max: 25 },
            { key: 'planet_life', label: 'Planet Life', value: b.planet_life || 0, max: 15 },
            { key: 'space_station', label: 'Space Station', value: b.space_station || 0, max: 5 },
          ]
          const isPlanetCategory = (key) => key === 'planet_environment' || key === 'planet_life'
          return (
            <div className={`mb-4 p-4 rounded border ${g.bg} ${g.border}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className={`text-3xl font-black ${g.color}`}>{system.completeness_grade}</span>
                  <div>
                    <div className={`text-sm font-semibold ${g.color}`}>{g.label}</div>
                    <div className="text-xs text-gray-400">{score}% complete{b.planet_count != null ? ` \u00B7 ${b.planet_count} planet${b.planet_count !== 1 ? 's' : ''}` : ''}</div>
                  </div>
                </div>
                {/* Overall progress bar */}
                <div className="w-32 sm:w-48">
                  <div className="h-2 rounded-full bg-gray-700 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        score >= 85 ? 'bg-amber-400' : score >= 65 ? 'bg-emerald-400' : score >= 40 ? 'bg-blue-400' : 'bg-gray-400'
                      }`}
                      style={{ width: `${score}%` }}
                    />
                  </div>
                </div>
              </div>
              {/* Category breakdown - clickable */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                {categories.map(cat => {
                  const catDetails = details[cat.key]
                  const hasDetails = catDetails && (Array.isArray(catDetails) ? catDetails.length > 0 : true)
                  return (
                    <button
                      key={cat.key}
                      type="button"
                      className={`text-center rounded p-1.5 transition-colors ${
                        hasDetails ? 'hover:bg-white/5 cursor-pointer' : 'cursor-default'
                      } ${expandedGradeCategory === cat.key ? 'bg-white/5 ring-1 ring-white/10' : ''}`}
                      onClick={() => hasDetails && setExpandedGradeCategory(expandedGradeCategory === cat.key ? null : cat.key)}
                    >
                      <div className="text-[10px] text-gray-400 mb-1 truncate" title={cat.label}>{cat.label}</div>
                      <div className="h-1.5 rounded-full bg-gray-700 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            cat.value >= cat.max ? 'bg-amber-400' : cat.value >= cat.max * 0.65 ? 'bg-emerald-400' : cat.value >= cat.max * 0.4 ? 'bg-blue-400' : 'bg-gray-500'
                          }`}
                          style={{ width: `${cat.max > 0 ? (cat.value / cat.max) * 100 : 0}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-gray-500 mt-0.5">{cat.value}/{cat.max}</div>
                    </button>
                  )
                })}
              </div>
              {/* Expanded detail panel */}
              {expandedGradeCategory && details[expandedGradeCategory] && (
                <div className="mt-3 pt-3 border-t border-white/10">
                  {isPlanetCategory(expandedGradeCategory) ? (
                    /* Planet-level breakdown: show each planet with its fields */
                    <div className="space-y-2">
                      {details[expandedGradeCategory].map((planet, pi) => (
                        <div key={pi} className="bg-black/20 rounded p-2">
                          <div className="text-xs font-medium text-gray-300 mb-1.5">
                            {planet.name}
                            <span className="ml-2 text-gray-500">{planet.filled}/{planet.total}</span>
                          </div>
                          <div className="flex flex-wrap gap-x-4 gap-y-1">
                            {planet.fields.map((f, fi) => (
                              <div key={fi} className="flex items-center gap-1.5 text-xs">
                                <span className={`inline-block w-1.5 h-1.5 rounded-full ${
                                  f.status === 'filled' ? 'bg-emerald-400' : f.status === 'skipped' ? 'bg-gray-600' : 'bg-red-400'
                                }`} />
                                <span className="text-gray-400">{f.name}:</span>
                                <span className={f.status === 'filled' ? 'text-gray-200' : f.status === 'skipped' ? 'text-gray-600 italic' : 'text-red-400 italic'}>
                                  {f.status === 'filled' ? f.value : f.status === 'skipped' ? 'N/A' : 'Missing'}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    /* System-level breakdown: flat field list */
                    <div className="flex flex-wrap gap-x-4 gap-y-1.5">
                      {details[expandedGradeCategory].map((f, fi) => (
                        <div key={fi} className="flex items-center gap-1.5 text-xs">
                          <span className={`inline-block w-1.5 h-1.5 rounded-full ${
                            f.status === 'filled' ? 'bg-emerald-400' : 'bg-red-400'
                          }`} />
                          <span className="text-gray-400">{f.name}:</span>
                          <span className={f.status === 'filled' ? 'text-gray-200' : 'text-red-400 italic'}>
                            {f.status === 'filled' ? f.value : 'Missing'}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })()}

        {/* Coordinates */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4 p-4 bg-gray-800 rounded">
          <div>
            <div className="text-xs text-gray-400">X Coordinate</div>
            <div className="text-lg font-mono">{system.x || '0'}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Y Coordinate</div>
            <div className="text-lg font-mono">{system.y || '0'}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Z Coordinate</div>
            <div className="text-lg font-mono">{system.z || '0'}</div>
          </div>
        </div>

        {/* System Properties (from NMS live extraction) */}
        {(system.star_type || system.economy_type || system.economy_level || system.conflict_level || system.dominant_lifeform || system.stellar_classification) && (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4 mb-4 p-4 bg-gray-800 rounded">
            {system.star_type && (
              <div>
                <div className="text-xs text-gray-400">Star Type</div>
                <div className={
                  system.star_type === 'Yellow' ? 'text-yellow-400' :
                  system.star_type === 'Red' ? 'text-red-400' :
                  system.star_type === 'Green' ? 'text-green-400' :
                  system.star_type === 'Blue' ? 'text-blue-400' :
                  system.star_type === 'Purple' ? 'text-purple-400' : 'text-gray-400'
                }>{system.star_type}</div>
              </div>
            )}
            {system.stellar_classification && (
              <div>
                <div className="text-xs text-gray-400">Spectral Class</div>
                <div className={`font-mono ${
                  (() => {
                    const firstChar = system.stellar_classification[0]?.toUpperCase();
                    switch(firstChar) {
                      case 'O': case 'B': return 'text-blue-300';
                      case 'F': case 'G': return 'text-yellow-300';
                      case 'K': case 'M': return 'text-red-400';
                      case 'E': return 'text-green-400';
                      case 'X': case 'Y': return 'text-purple-400';
                      default: return 'text-gray-300';
                    }
                  })()
                }`}>{system.stellar_classification}</div>
              </div>
            )}
            {system.economy_type && (
              <div>
                <div className="text-xs text-gray-400">Economy</div>
                <div className="text-green-400">{system.economy_type}</div>
              </div>
            )}
            {system.economy_level && (
              <div>
                <div className="text-xs text-gray-400">Wealth</div>
                <div className={
                  system.economy_level === 'High' ? 'text-yellow-400' :
                  system.economy_level === 'Medium' ? 'text-blue-400' : 'text-gray-300'
                }>{system.economy_level}</div>
              </div>
            )}
            {system.conflict_level && (
              <div>
                <div className="text-xs text-gray-400">Conflict</div>
                <div className={
                  system.conflict_level === 'High' ? 'text-red-400' :
                  system.conflict_level === 'Medium' ? 'text-orange-400' : 'text-green-400'
                }>{system.conflict_level}</div>
              </div>
            )}
            {system.dominant_lifeform && (
              <div>
                <div className="text-xs text-gray-400">Dominant Lifeform</div>
                <div className={
                  system.dominant_lifeform === "Vy'keen" ? 'text-red-400' :
                  system.dominant_lifeform === 'Gek' ? 'text-yellow-400' :
                  system.dominant_lifeform === 'Korvax' ? 'text-cyan-400' : 'text-gray-300'
                }>{system.dominant_lifeform}</div>
              </div>
            )}
          </div>
        )}

        {/* Description */}
        {system.description && (
          <div className="mt-4">
            <h3 className="font-semibold mb-2">Description</h3>
            <p className="text-gray-300">{system.description}</p>
          </div>
        )}
      </Card>

      {/* Space Station Section */}
      {system.space_station && (
        <Card className="mb-6">
          <h2 className="text-2xl font-bold mb-4">Space Station</h2>
          <div className="bg-purple-900/30 border border-purple-600 rounded p-4">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
              <div>
                <div className="text-xs text-gray-400">Name</div>
                <div className="font-semibold">{system.space_station.name}</div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Race</div>
                <div>{system.space_station.race || 'Unknown'}</div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Economy</div>
                <div>{system.economy_type || 'Unknown'}</div>
              </div>
            </div>

            {/* Trade Goods */}
            {system.space_station.trade_goods && system.space_station.trade_goods.length > 0 && (
              <div>
                <div className="text-xs text-gray-400 mb-2">Trade Goods Available</div>
                <div className="flex flex-wrap gap-2">
                  {system.space_station.trade_goods.map(goodId => {
                    const good = getTradeGoodById(goodId)
                    return (
                      <span
                        key={goodId}
                        className="px-2 py-1 bg-purple-800/50 border border-purple-500 rounded text-sm"
                        title={good?.description || ''}
                      >
                        {good?.name || goodId}
                      </span>
                    )
                  })}
                </div>
              </div>
            )}
            {(!system.space_station.trade_goods || system.space_station.trade_goods.length === 0) && (
              <div className="text-xs text-gray-500 italic">
                No trade goods recorded for this station
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Planets Section */}
      <Card>
        <h2 className="text-2xl font-bold mb-4">
          Planets ({system.planets?.length || 0})
        </h2>

        {!system.planets || system.planets.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            No planets in this system
          </div>
        ) : (
          <div className="space-y-4">
            {system.planets.map((planet, index) => (
              <div key={index} className="border border-gray-700 rounded overflow-hidden">
                {/* Planet Header */}
                <div
                  className="bg-gray-800 p-4 cursor-pointer hover:bg-gray-750 transition-colors"
                  onClick={() => togglePlanetExpanded(index)}
                >
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="text-xl font-semibold flex items-center gap-2">
                        {planet.name}
                        {planet.is_moon === 1 && <span className="text-sm text-purple-400">(Moon)</span>}
                        {planet.data_source === 'remote' && (
                          <span className="text-xs bg-amber-500 text-white px-1.5 py-0.5 rounded" title="Remote data - visit for full detail (weather, flora, fauna, sentinels)">
                            📡 Remote
                          </span>
                        )}
                      </h3>
                      <div className="text-sm text-gray-400 mt-1 flex flex-wrap gap-x-4">
                        {planet.biome && (
                          <span className="text-green-400">{planet.biome}</span>
                        )}
                        {planet.planet_size && (
                          <span>{planet.planet_size}</span>
                        )}
                        {planet.moons && planet.moons.length > 0 && (
                          <span>{planet.moons.length} moon{planet.moons.length !== 1 ? 's' : ''}</span>
                        )}
                        <span className={getSentinelColor(planet.sentinel || planet.sentinel_level)}>
                          Sentinel: {planet.sentinel || planet.sentinel_level || 'Unknown'}
                        </span>
                        {planet.fauna && (
                          <span className={getFaunaColor(planet.fauna)}>Fauna: {planet.fauna}</span>
                        )}
                        {planet.flora && (
                          <span className={getFloraColor(planet.flora)}>Flora: {planet.flora}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-2xl">
                        {expandedPlanets[index] ? '−' : '+'}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Planet Details (Expanded) */}
                {expandedPlanets[index] && (
                  <div className="p-4 bg-gray-900/50 space-y-3">
                    {/* Environment & Weather Section */}
                    <div className="p-3 bg-emerald-900/15 border border-emerald-800/40 rounded-lg">
                      <div className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                        <span>{'\u{1F30D}'}</span> Environment
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                        {planet.biome && (
                          <div>
                            <div className="text-xs text-gray-500">Biome</div>
                            <div className="text-green-400 font-medium">{planet.biome}</div>
                          </div>
                        )}
                        {planet.biome_subtype && planet.biome_subtype !== 'None_' && (
                          <div>
                            <div className="text-xs text-gray-500">Subtype</div>
                            <div>{planet.biome_subtype}</div>
                          </div>
                        )}
                        {planet.planet_size && (
                          <div>
                            <div className="text-xs text-gray-500">Size</div>
                            <div>{planet.planet_size}</div>
                          </div>
                        )}
                        {planet.weather && (
                          <div>
                            <div className="text-xs text-gray-500">Weather</div>
                            <div className="text-blue-300">{planet.weather}</div>
                          </div>
                        )}
                        {planet.climate && (
                          <div>
                            <div className="text-xs text-gray-500">Climate</div>
                            <div>{planet.climate}</div>
                          </div>
                        )}
                        {planet.storm_frequency && planet.storm_frequency !== 'Unknown' && (
                          <div>
                            <div className="text-xs text-gray-500">Storm Frequency</div>
                            <div className={
                              planet.storm_frequency === 'Always' ? 'text-red-400' :
                              planet.storm_frequency === 'High' ? 'text-orange-400' :
                              planet.storm_frequency === 'Low' ? 'text-yellow-400' : ''
                            }>{planet.storm_frequency}</div>
                          </div>
                        )}
                        {planet.weather_intensity && planet.weather_intensity !== 'Unknown' && (
                          <div>
                            <div className="text-xs text-gray-500">Weather Intensity</div>
                            <div className={planet.weather_intensity === 'Extreme' ? 'text-red-400' : ''}>{planet.weather_intensity}</div>
                          </div>
                        )}
                        {planet.has_water === 1 && (
                          <div>
                            <div className="text-xs text-gray-500">Water</div>
                            <div className="text-cyan-400">Present {'\u{1F30A}'}</div>
                          </div>
                        )}
                        {planet.building_density && planet.building_density !== 'Unknown' && (
                          <div>
                            <div className="text-xs text-gray-500">Building Density</div>
                            <div>{planet.building_density}</div>
                          </div>
                        )}
                      </div>
                      {(planet.weather_text || planet.sentinels_text) && (
                        <div className="mt-2 pt-2 border-t border-emerald-800/30 grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {planet.weather_text && (
                            <div className="text-xs text-gray-400 italic">{planet.weather_text}</div>
                          )}
                          {planet.sentinels_text && (
                            <div className="text-xs text-gray-400 italic">{planet.sentinels_text}</div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Life Section */}
                    <div className="p-3 bg-amber-900/15 border border-amber-800/40 rounded-lg">
                      <div className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                        <span>{'\u{1F43E}'}</span> Life & Sentinels
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="text-center p-2 bg-white/5 rounded-lg">
                          <div className="text-xs text-gray-500 mb-0.5">Sentinels</div>
                          <div className={`font-medium ${getSentinelColor(planet.sentinel || planet.sentinel_level)}`}>
                            {planet.sentinel || planet.sentinel_level || 'Unknown'}
                          </div>
                        </div>
                        <div className="text-center p-2 bg-white/5 rounded-lg">
                          <div className="text-xs text-gray-500 mb-0.5">Fauna</div>
                          <div className={`font-medium ${getFaunaColor(planet.fauna)}`}>
                            {planet.fauna || 'N/A'}
                            {planet.fauna_count > 0 && <span className="text-xs text-gray-500 ml-1">({planet.fauna_count})</span>}
                          </div>
                        </div>
                        <div className="text-center p-2 bg-white/5 rounded-lg">
                          <div className="text-xs text-gray-500 mb-0.5">Flora</div>
                          <div className={`font-medium ${getFloraColor(planet.flora)}`}>
                            {planet.flora || 'N/A'}
                            {planet.flora_count > 0 && <span className="text-xs text-gray-500 ml-1">({planet.flora_count})</span>}
                          </div>
                        </div>
                      </div>
                      {(planet.fauna_text || planet.flora_text) && (
                        <div className="mt-2 pt-2 border-t border-amber-800/30 grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {planet.fauna_text && (
                            <div className="text-xs text-gray-400 italic">{planet.fauna_text}</div>
                          )}
                          {planet.flora_text && (
                            <div className="text-xs text-gray-400 italic">{planet.flora_text}</div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Hazards Section */}
                    {(planet.hazard_temperature !== 0 || planet.hazard_radiation !== 0 || planet.hazard_toxicity !== 0) && (
                      <div className="p-3 bg-red-900/15 border border-red-800/40 rounded-lg">
                        <div className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                          <span>{'\u{26A0}\u{FE0F}'}</span> Environmental Hazards
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                          {planet.hazard_temperature !== 0 && (
                            <div className="text-center p-2 bg-white/5 rounded-lg">
                              <div className="text-xs text-gray-500 mb-0.5">Temperature</div>
                              <div className={`font-medium ${planet.hazard_temperature > 0 ? 'text-orange-400' : 'text-cyan-400'}`}>
                                {planet.hazard_temperature > 0 ? '+' : ''}{planet.hazard_temperature?.toFixed(1)}°
                              </div>
                            </div>
                          )}
                          {planet.hazard_radiation !== 0 && (
                            <div className="text-center p-2 bg-white/5 rounded-lg">
                              <div className="text-xs text-gray-500 mb-0.5">Radiation</div>
                              <div className="text-yellow-400 font-medium">{planet.hazard_radiation?.toFixed(1)} rad</div>
                            </div>
                          )}
                          {planet.hazard_toxicity !== 0 && (
                            <div className="text-center p-2 bg-white/5 rounded-lg">
                              <div className="text-xs text-gray-500 mb-0.5">Toxicity</div>
                              <div className="text-green-500 font-medium">{planet.hazard_toxicity?.toFixed(1)} tox</div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Resources Section */}
                    {(planet.common_resource || planet.uncommon_resource || planet.rare_resource || planet.materials) && (
                      <div className="p-3 bg-blue-900/15 border border-blue-800/40 rounded-lg">
                        <div className="text-xs font-semibold text-blue-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                          <span>{'\u{1F48E}'}</span> Resources
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                          {planet.common_resource && planet.common_resource !== 'Unknown' && (
                            <div className="p-2 bg-white/5 rounded-lg">
                              <div className="text-xs text-gray-500 mb-0.5">Common</div>
                              <div className="text-gray-300">{planet.common_resource}</div>
                            </div>
                          )}
                          {planet.uncommon_resource && planet.uncommon_resource !== 'Unknown' && (
                            <div className="p-2 bg-white/5 rounded-lg">
                              <div className="text-xs text-gray-500 mb-0.5">Uncommon</div>
                              <div className="text-blue-300">{planet.uncommon_resource}</div>
                            </div>
                          )}
                          {planet.rare_resource && planet.rare_resource !== 'Unknown' && (
                            <div className="p-2 bg-white/5 rounded-lg">
                              <div className="text-xs text-gray-500 mb-0.5">Rare</div>
                              <div className="text-purple-400">{planet.rare_resource}</div>
                            </div>
                          )}
                        </div>
                        {planet.materials && (
                          <div className="mt-2 pt-2 border-t border-blue-800/30">
                            <div className="text-xs text-gray-500 mb-1">All Materials</div>
                            <div className="flex flex-wrap gap-1.5">
                              {planet.materials.split(',').map((mat, mi) => (
                                <span key={mi} className="px-2 py-0.5 bg-blue-900/40 border border-blue-700/40 rounded text-xs text-blue-200">{mat.trim()}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Planet Attributes Section */}
                    {(() => {
                      const attrs = [
                        { key: 'has_rings', label: 'Has Rings', icon: '\u{1FA90}' },
                        { key: 'is_dissonant', label: 'Dissonant', icon: '\u{1F50A}' },
                        { key: 'is_infested', label: 'Infested', icon: '\u{1F9A0}' },
                        { key: 'extreme_weather', label: 'Extreme Weather', icon: '\u{26A1}' },
                        { key: 'water_world', label: 'Water World', icon: '\u{1F30A}' },
                        { key: 'vile_brood', label: 'Vile Brood', icon: '\u{1F480}' },
                        { key: 'ancient_bones', label: 'Ancient Bones', icon: '\u{1F9B4}' },
                        { key: 'salvageable_scrap', label: 'Salvageable Scrap', icon: '\u{2699}' },
                        { key: 'storm_crystals', label: 'Storm Crystals', icon: '\u{1F48E}' },
                        { key: 'gravitino_balls', label: 'Gravitino Balls', icon: '\u{1F7E3}' },
                      ].filter(a => planet[a.key])
                      const hasExoticTrophy = planet.exotic_trophy && planet.exotic_trophy.trim()
                      if (attrs.length === 0 && !hasExoticTrophy) return null
                      return (
                        <div className="p-3 bg-purple-900/15 border border-purple-800/40 rounded-lg">
                          <div className="text-xs font-semibold text-purple-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                            <span>{'\u{2728}'}</span> Special Attributes
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {attrs.map(a => (
                              <span key={a.key} className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-purple-500/20 border border-purple-500/40 rounded-full text-sm text-purple-200">
                                <span>{a.icon}</span> {a.label}
                              </span>
                            ))}
                            {hasExoticTrophy && (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-yellow-500/20 border border-yellow-500/40 rounded-full text-sm text-yellow-200">
                                <span>{'\u{1F3C6}'}</span> {planet.exotic_trophy}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })()}

                    {/* Additional Info */}
                    {(planet.base_location || planet.description || planet.notes) && (
                      <div className="p-3 bg-gray-800/50 border border-gray-700/50 rounded-lg space-y-2">
                        {planet.base_location && (
                          <div>
                            <span className="text-xs text-gray-500">Base Location: </span>
                            <span className="text-gray-300">{planet.base_location}</span>
                          </div>
                        )}
                        {planet.description && (
                          <div>
                            <span className="text-xs text-gray-500">Description: </span>
                            <span className="text-gray-300">{planet.description}</span>
                          </div>
                        )}
                        {planet.notes && (
                          <div>
                            <span className="text-xs text-gray-500">Notes: </span>
                            <span className="text-sm text-gray-300">{planet.notes}</span>
                          </div>
                        )}
                      </div>
                    )}

                    {planet.photo && (
                      <div>
                        <img
                          src={getPhotoUrl(planet.photo)}
                          alt={planet.name}
                          className="w-full max-w-md rounded-lg border border-gray-700"
                        />
                      </div>
                    )}

                    {/* Moons */}
                    {planet.moons && planet.moons.length > 0 && (
                      <div className="p-3 bg-cyan-900/15 border border-cyan-800/40 rounded-lg">
                        <div className="text-xs font-semibold text-cyan-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                          <span>{'\u{1F319}'}</span> Moons ({planet.moons.length})
                        </div>
                        <div className="space-y-3">
                          {planet.moons.map((moon, moonIndex) => (
                            <div key={moonIndex} className="bg-gray-800/80 rounded-lg border border-cyan-800/30 overflow-hidden">
                              <div className="px-3 py-2 bg-cyan-900/20 border-b border-cyan-800/30">
                                <span className="font-medium text-cyan-200">{moon.name || `Moon ${moonIndex + 1}`}</span>
                                {moon.biome && <span className="ml-2 text-xs text-green-400">{moon.biome}</span>}
                              </div>
                              <div className="p-3">
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
                                  <div className="text-center p-1.5 bg-white/5 rounded">
                                    <div className="text-[10px] text-gray-500">Sentinels</div>
                                    <div className={`text-sm ${getSentinelColor(moon.sentinel)}`}>
                                      {moon.sentinel || 'Unknown'}
                                    </div>
                                  </div>
                                  <div className="text-center p-1.5 bg-white/5 rounded">
                                    <div className="text-[10px] text-gray-500">Fauna</div>
                                    <div className={`text-sm ${getFaunaColor(moon.fauna)}`}>
                                      {moon.fauna || 'N/A'}
                                    </div>
                                  </div>
                                  <div className="text-center p-1.5 bg-white/5 rounded">
                                    <div className="text-[10px] text-gray-500">Flora</div>
                                    <div className={`text-sm ${getFloraColor(moon.flora)}`}>
                                      {moon.flora || 'N/A'}
                                    </div>
                                  </div>
                                  {(moon.climate || moon.weather) && (
                                    <div className="text-center p-1.5 bg-white/5 rounded">
                                      <div className="text-[10px] text-gray-500">Weather</div>
                                      <div className="text-sm text-blue-300">{moon.weather || moon.climate}</div>
                                    </div>
                                  )}
                                </div>
                                {moon.materials && (
                                  <div className="mt-2">
                                    <div className="flex flex-wrap gap-1">
                                      {moon.materials.split(',').map((mat, mi) => (
                                        <span key={mi} className="px-1.5 py-0.5 bg-blue-900/30 border border-blue-700/30 rounded text-xs text-blue-200">{mat.trim()}</span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {/* Moon Attributes */}
                                {(() => {
                                  const moonAttrs = [
                                    { key: 'has_rings', label: 'Rings', icon: '\u{1FA90}' },
                                    { key: 'is_dissonant', label: 'Dissonant', icon: '\u{1F50A}' },
                                    { key: 'is_infested', label: 'Infested', icon: '\u{1F9A0}' },
                                    { key: 'extreme_weather', label: 'Extreme', icon: '\u{26A1}' },
                                    { key: 'water_world', label: 'Water', icon: '\u{1F30A}' },
                                    { key: 'vile_brood', label: 'Vile Brood', icon: '\u{1F480}' },
                                  ].filter(a => moon[a.key])
                                  const hasMoonTrophy = moon.exotic_trophy && moon.exotic_trophy.trim()
                                  if (moonAttrs.length === 0 && !hasMoonTrophy) return null
                                  return (
                                    <div className="mt-2 flex flex-wrap gap-1.5">
                                      {moonAttrs.map(a => (
                                        <span key={a.key} className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-500/15 border border-purple-500/30 rounded-full text-xs text-purple-300">
                                          <span>{a.icon}</span> {a.label}
                                        </span>
                                      ))}
                                      {hasMoonTrophy && (
                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-yellow-500/15 border border-yellow-500/30 rounded-full text-xs text-yellow-300">
                                          <span>{'\u{1F3C6}'}</span> {moon.exotic_trophy}
                                        </span>
                                      )}
                                    </div>
                                  )
                                })()}
                                {(moon.description || moon.notes) && (
                                  <div className="mt-2 pt-2 border-t border-gray-700/50 text-xs text-gray-400">
                                    {moon.description && <div>{moon.description}</div>}
                                    {moon.notes && <div className="italic">{moon.notes}</div>}
                                  </div>
                                )}
                                {moon.photo && (
                                  <div className="mt-2">
                                    <img
                                      src={getPhotoUrl(moon.photo)}
                                      alt={moon.name}
                                      className="max-w-xs max-h-32 rounded border border-gray-700"
                                    />
                                  </div>
                                )}
                              </div>
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
      </Card>

      {/* Contributors Modal */}
      {showContributors && (
        <ContributorsModal
          system={system}
          onClose={() => setShowContributors(false)}
        />
      )}
    </div>
  )
}
