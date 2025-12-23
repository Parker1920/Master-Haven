import React, { useEffect, useState, useContext } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import Card from '../components/Card'
import Button from '../components/Button'
import { AuthContext } from '../utils/AuthContext'

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

export default function SystemDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [system, setSystem] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedPlanets, setExpandedPlanets] = useState({})

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
              <div className="mt-2">
                <span className="text-purple-400 font-mono text-lg tracking-wider">{system.glyph_code}</span>
              </div>
            )}
          </div>
          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto flex-shrink-0">
            <Button
              className="bg-blue-600 hover:bg-blue-700 w-full sm:w-auto"
              onClick={() => navigate(`/create?edit=${encodeURIComponent(system.id || system.name)}`)}
            >
              Edit
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

        {/* Coordinates */}
        <div className="grid grid-cols-3 gap-4 mb-4 p-4 bg-gray-800 rounded">
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
        {(system.star_type || system.economy_type || system.economy_level || system.conflict_level || system.dominant_lifeform) && (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4 mb-4 p-4 bg-gray-800 rounded">
            {system.star_type && (
              <div>
                <div className="text-xs text-gray-400">Star Type</div>
                <div className="text-yellow-400">{system.star_type}</div>
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
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-gray-400">Name</div>
                <div className="font-semibold">{system.space_station.name}</div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Race</div>
                <div>{system.space_station.race || 'Unknown'}</div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Sell %</div>
                <div>{system.space_station.sell_percent || '80'}%</div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Buy %</div>
                <div>{system.space_station.buy_percent || '50'}%</div>
              </div>
            </div>
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
                      <h3 className="text-xl font-semibold">
                        {planet.name}
                        {planet.is_moon === 1 && <span className="ml-2 text-sm text-purple-400">(Moon)</span>}
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
                    <div className="text-2xl">
                      {expandedPlanets[index] ? '−' : '+'}
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
                        <div className="grid grid-cols-3 gap-4">
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
                                {moon.orbit_radius !== undefined && moon.orbit_radius !== null && (
                                  <div>
                                    <div className="text-xs text-gray-400">Orbit Radius</div>
                                    <div>{moon.orbit_radius}</div>
                                  </div>
                                )}
                                {moon.orbit_speed !== undefined && moon.orbit_speed !== null && moon.orbit_speed !== 0 && (
                                  <div>
                                    <div className="text-xs text-gray-400">Orbit Speed</div>
                                    <div>{moon.orbit_speed}</div>
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
    </div>
  )
}
