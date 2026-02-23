import React, { useEffect, useState, useContext } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import axios from 'axios'
import Card from '../components/Card'
import Button from '../components/Button'
import GlyphDisplay from '../components/GlyphDisplay'
import { AuthContext } from '../utils/AuthContext'
import { getTradeGoodById } from '../utils/economyTradeGoods'

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
          const score = system.completeness_score || 0
          const categories = [
            { label: 'System Core', value: b.system_core || 0, max: 35 },
            { label: 'System Extra', value: b.system_extra || 0, max: 10 },
            { label: 'Planet Coverage', value: b.planet_coverage || 0, max: 10 },
            { label: 'Planet Environment', value: b.planet_environment || 0, max: 25 },
            { label: 'Planet Life', value: b.planet_life || 0, max: 15 },
            { label: 'Space Station', value: b.space_station || 0, max: 5 },
          ]
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
              {/* Category breakdown */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                {categories.map(cat => (
                  <div key={cat.label} className="text-center">
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
                  </div>
                ))}
              </div>
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
                <div className="text-yellow-400">{system.star_type}</div>
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
                        <span className={
                          (planet.sentinel || planet.sentinel_level) === 'Aggressive' ? 'text-red-400' :
                          (planet.sentinel || planet.sentinel_level) === 'Low' ? 'text-green-400' : ''
                        }>Sentinel: {planet.sentinel || planet.sentinel_level || 'Unknown'}</span>
                        {planet.fauna && planet.fauna !== 'N/A' && planet.fauna !== 'None' && (
                          <span className={planet.fauna === 'Rich' ? 'text-yellow-400' : ''}>Fauna: {planet.fauna}</span>
                        )}
                        {planet.flora && planet.flora !== 'N/A' && planet.flora !== 'None' && (
                          <span className={planet.flora === 'Rich' ? 'text-green-400' : ''}>Flora: {planet.flora}</span>
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
                  <div className="p-4 bg-gray-900/50">
                    {/* Core Properties */}
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-4">
                      {/* Biome/Environment */}
                      {planet.biome && (
                        <div>
                          <div className="text-xs text-gray-400">Biome</div>
                          <div className="text-green-400 font-medium">{planet.biome}</div>
                        </div>
                      )}
                      {planet.biome_subtype && planet.biome_subtype !== 'None_' && (
                        <div>
                          <div className="text-xs text-gray-400">Biome Subtype</div>
                          <div>{planet.biome_subtype}</div>
                        </div>
                      )}
                      {planet.planet_size && (
                        <div>
                          <div className="text-xs text-gray-400">Size</div>
                          <div>{planet.planet_size}</div>
                        </div>
                      )}
                      {planet.is_moon === 1 && (
                        <div>
                          <div className="text-xs text-gray-400">Type</div>
                          <div className="text-purple-400">Moon</div>
                        </div>
                      )}

                      {/* Sentinel */}
                      <div>
                        <div className="text-xs text-gray-400">Sentinel Level</div>
                        <div className={
                          (planet.sentinel || planet.sentinel_level) === 'Aggressive' ? 'text-red-400' :
                          (planet.sentinel || planet.sentinel_level) === 'High' ? 'text-orange-400' :
                          (planet.sentinel || planet.sentinel_level) === 'Low' ? 'text-green-400' : ''
                        }>{planet.sentinel || planet.sentinel_level || 'Unknown'}</div>
                      </div>
                      {planet.sentinels_text && (
                        <div>
                          <div className="text-xs text-gray-400">Sentinel Info</div>
                          <div className="text-sm">{planet.sentinels_text}</div>
                        </div>
                      )}

                      {/* Fauna */}
                      <div>
                        <div className="text-xs text-gray-400">Fauna</div>
                        <div className={
                          planet.fauna === 'Rich' ? 'text-yellow-400' :
                          planet.fauna === 'Average' ? 'text-blue-300' : ''
                        }>{planet.fauna || 'N/A'}{planet.fauna_count > 0 && ` (${planet.fauna_count} species)`}</div>
                      </div>
                      {planet.fauna_text && (
                        <div>
                          <div className="text-xs text-gray-400">Fauna Info</div>
                          <div className="text-sm">{planet.fauna_text}</div>
                        </div>
                      )}

                      {/* Flora */}
                      <div>
                        <div className="text-xs text-gray-400">Flora</div>
                        <div className={
                          planet.flora === 'Rich' ? 'text-green-400' :
                          planet.flora === 'Average' ? 'text-blue-300' : ''
                        }>{planet.flora || 'N/A'}{planet.flora_count > 0 && ` (${planet.flora_count} species)`}</div>
                      </div>
                      {planet.flora_text && (
                        <div>
                          <div className="text-xs text-gray-400">Flora Info</div>
                          <div className="text-sm">{planet.flora_text}</div>
                        </div>
                      )}

                      {/* Climate/Weather */}
                      {planet.climate && (
                        <div>
                          <div className="text-xs text-gray-400">Climate</div>
                          <div>{planet.climate}</div>
                        </div>
                      )}
                      {planet.weather && (
                        <div>
                          <div className="text-xs text-gray-400">Weather</div>
                          <div className="text-blue-300">{planet.weather}</div>
                        </div>
                      )}
                      {planet.weather_text && (
                        <div>
                          <div className="text-xs text-gray-400">Weather Info</div>
                          <div className="text-sm">{planet.weather_text}</div>
                        </div>
                      )}
                      {planet.storm_frequency && planet.storm_frequency !== 'Unknown' && (
                        <div>
                          <div className="text-xs text-gray-400">Storm Frequency</div>
                          <div className={
                            planet.storm_frequency === 'Always' ? 'text-red-400' :
                            planet.storm_frequency === 'High' ? 'text-orange-400' :
                            planet.storm_frequency === 'Low' ? 'text-yellow-400' : ''
                          }>{planet.storm_frequency}</div>
                        </div>
                      )}
                      {planet.weather_intensity && planet.weather_intensity !== 'Unknown' && (
                        <div>
                          <div className="text-xs text-gray-400">Weather Intensity</div>
                          <div className={planet.weather_intensity === 'Extreme' ? 'text-red-400' : ''}>{planet.weather_intensity}</div>
                        </div>
                      )}

                      {/* Building Density */}
                      {planet.building_density && planet.building_density !== 'Unknown' && (
                        <div>
                          <div className="text-xs text-gray-400">Building Density</div>
                          <div>{planet.building_density}</div>
                        </div>
                      )}

                      {/* Water */}
                      {planet.has_water === 1 && (
                        <div>
                          <div className="text-xs text-gray-400">Water</div>
                          <div className="text-cyan-400">Present</div>
                        </div>
                      )}
                    </div>

                    {/* Hazards Section */}
                    {(planet.hazard_temperature !== 0 || planet.hazard_radiation !== 0 || planet.hazard_toxicity !== 0) && (
                      <div className="mb-4 p-3 bg-red-900/20 border border-red-800/50 rounded">
                        <div className="text-xs text-gray-400 mb-2 font-semibold">Environmental Hazards</div>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                          {planet.hazard_temperature !== 0 && (
                            <div>
                              <div className="text-xs text-gray-400">Temperature</div>
                              <div className={planet.hazard_temperature > 0 ? 'text-orange-400' : 'text-cyan-400'}>
                                {planet.hazard_temperature > 0 ? '+' : ''}{planet.hazard_temperature?.toFixed(1)}°
                              </div>
                            </div>
                          )}
                          {planet.hazard_radiation !== 0 && (
                            <div>
                              <div className="text-xs text-gray-400">Radiation</div>
                              <div className="text-yellow-400">{planet.hazard_radiation?.toFixed(1)} rad</div>
                            </div>
                          )}
                          {planet.hazard_toxicity !== 0 && (
                            <div>
                              <div className="text-xs text-gray-400">Toxicity</div>
                              <div className="text-green-500">{planet.hazard_toxicity?.toFixed(1)} tox</div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Resources Section */}
                    {(planet.common_resource || planet.uncommon_resource || planet.rare_resource || planet.materials) && (
                      <div className="mb-4 p-3 bg-blue-900/20 border border-blue-800/50 rounded">
                        <div className="text-xs text-gray-400 mb-2 font-semibold">Resources</div>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                          {planet.common_resource && planet.common_resource !== 'Unknown' && (
                            <div>
                              <div className="text-xs text-gray-400">Common</div>
                              <div className="text-gray-300">{planet.common_resource}</div>
                            </div>
                          )}
                          {planet.uncommon_resource && planet.uncommon_resource !== 'Unknown' && (
                            <div>
                              <div className="text-xs text-gray-400">Uncommon</div>
                              <div className="text-blue-300">{planet.uncommon_resource}</div>
                            </div>
                          )}
                          {planet.rare_resource && planet.rare_resource !== 'Unknown' && (
                            <div>
                              <div className="text-xs text-gray-400">Rare</div>
                              <div className="text-purple-400">{planet.rare_resource}</div>
                            </div>
                          )}
                          {planet.materials && (
                            <div className="col-span-2 md:col-span-3">
                              <div className="text-xs text-gray-400">All Materials</div>
                              <div>{planet.materials}</div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Additional Info */}
                    <div className="grid grid-cols-1 gap-4 mb-4">
                      {planet.base_location && (
                        <div>
                          <div className="text-xs text-gray-400">Base Location</div>
                          <div>{planet.base_location}</div>
                        </div>
                      )}
                      {planet.description && (
                        <div>
                          <div className="text-xs text-gray-400">Description</div>
                          <div className="text-gray-300">{planet.description}</div>
                        </div>
                      )}
                    </div>

                    {planet.notes && (
                      <div className="mb-4">
                        <div className="text-xs text-gray-400 mb-1">Notes</div>
                        <div className="text-sm text-gray-300">{planet.notes}</div>
                      </div>
                    )}

                    {planet.photo && (
                      <div className="mb-4">
                        <div className="text-xs text-gray-400 mb-2">Photo</div>
                        <img
                          src={getPhotoUrl(planet.photo)}
                          alt={planet.name}
                          className="w-full max-w-md rounded border border-gray-700"
                        />
                      </div>
                    )}

                    {/* Moons */}
                    {planet.moons && planet.moons.length > 0 && (
                      <div className="mt-4">
                        <h4 className="font-semibold mb-2 text-cyan-400">Moons ({planet.moons.length})</h4>
                        <div className="space-y-2">
                          {planet.moons.map((moon, moonIndex) => (
                            <div key={moonIndex} className="bg-gray-800 p-3 rounded border border-cyan-800">
                              <div className="font-medium mb-2">{moon.name}</div>
                              <div className="grid grid-cols-2 gap-2 text-sm">
                                {/* Always show core moon properties */}
                                <div>
                                  <div className="text-xs text-gray-400">Sentinel</div>
                                  <div>{moon.sentinel || 'Unknown'}</div>
                                </div>
                                <div>
                                  <div className="text-xs text-gray-400">Fauna</div>
                                  <div>{moon.fauna || 'N/A'}</div>
                                </div>
                                <div>
                                  <div className="text-xs text-gray-400">Flora</div>
                                  <div>{moon.flora || 'N/A'}</div>
                                </div>
                                {moon.climate && (
                                  <div>
                                    <div className="text-xs text-gray-400">Climate</div>
                                    <div>{moon.climate}</div>
                                  </div>
                                )}
                                {moon.materials && (
                                  <div className="col-span-2">
                                    <div className="text-xs text-gray-400">Materials</div>
                                    <div>{moon.materials}</div>
                                  </div>
                                )}
                              </div>
                              {moon.description && (
                                <div className="mt-2">
                                  <div className="text-xs text-gray-400">Description</div>
                                  <div className="text-sm text-gray-300">{moon.description}</div>
                                </div>
                              )}
                              {moon.notes && (
                                <div className="mt-2">
                                  <div className="text-xs text-gray-400">Notes</div>
                                  <div className="text-sm text-gray-300">{moon.notes}</div>
                                </div>
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
