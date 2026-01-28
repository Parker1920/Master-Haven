import React, { useState, useEffect, useContext, useRef } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import { AuthContext, FEATURES } from '../utils/AuthContext'
import WarMap3D from '../components/WarMap3D'

// War Room themed card component
function WarCard({ children, className = '', title, danger = false }) {
  return (
    <div className={`
      rounded-lg border backdrop-blur-sm flex flex-col
      ${danger
        ? 'bg-red-950/40 border-red-500/30'
        : 'bg-gray-900/80 border-red-500/20'}
      ${className}
    `}>
      {title && (
        <div className="px-4 py-2 border-b border-red-500/20 flex-shrink-0">
          <h3 className="text-sm font-bold text-red-400 uppercase tracking-wider">{title}</h3>
        </div>
      )}
      <div className="p-4 flex-1 min-h-0">{children}</div>
    </div>
  )
}

// Conflict card component
function ConflictCard({ conflict }) {
  const statusColors = {
    pending: 'bg-yellow-500',
    acknowledged: 'bg-orange-500',
    active: 'bg-red-500 animate-pulse',
    resolved: 'bg-gray-500'
  }

  return (
    <div className="bg-gray-800/50 rounded border border-red-500/20 p-3 mb-2">
      <div className="flex items-center justify-between mb-2">
        <span className={`px-2 py-0.5 rounded text-xs font-bold ${statusColors[conflict.status]} text-white`}>
          {conflict.status.toUpperCase()}
        </span>
        <span className="text-xs text-gray-400">{new Date(conflict.declared_at).toLocaleDateString()}</span>
      </div>
      <div className="text-sm mb-1">
        <span style={{ color: conflict.attacker_color }} className="font-bold">{conflict.attacker_name}</span>
        <span className="text-gray-500 mx-2">vs</span>
        <span style={{ color: conflict.defender_color }} className="font-bold">{conflict.defender_name}</span>
      </div>
      <div className="text-xs text-gray-400">
        Target: <span className="text-white">{conflict.target_system_name}</span>
      </div>
    </div>
  )
}

// News ticker component
function NewsTicker({ news }) {
  if (!news.length) return null

  return (
    <div className="bg-gray-900/90 border-t border-red-500/30 py-2 overflow-hidden">
      <div className="flex animate-marquee whitespace-nowrap">
        {news.concat(news).map((item, i) => (
          <span key={i} className="mx-8 text-sm">
            <span className="text-red-400 font-bold mr-2">BREAKING:</span>
            <span className="text-gray-300">{item.headline}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

// Debrief panel component
function DebriefPanel({ debrief, onUpdate, canEdit }) {
  const [editing, setEditing] = useState(false)
  const [objectives, setObjectives] = useState([])

  useEffect(() => {
    setObjectives(debrief.objectives || [])
  }, [debrief])

  const handleSave = async () => {
    await onUpdate(objectives)
    setEditing(false)
  }

  return (
    <WarCard title="Current Mission Debrief" danger>
      {editing ? (
        <div className="space-y-2">
          <textarea
            className="w-full bg-gray-800 border border-red-500/30 rounded p-2 text-sm text-gray-200"
            rows={4}
            value={objectives.join('\n')}
            onChange={(e) => setObjectives(e.target.value.split('\n').filter(Boolean))}
            placeholder="Enter objectives, one per line..."
          />
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              className="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-sm font-bold"
            >
              Save
            </button>
            <button
              onClick={() => setEditing(false)}
              className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div>
          {objectives.length > 0 ? (
            <ul className="space-y-1">
              {objectives.map((obj, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className="text-red-400 font-bold">{i + 1}.</span>
                  <span className="text-gray-200">{obj}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500 text-sm italic">No current objectives set.</p>
          )}
          {canEdit && (
            <button
              onClick={() => setEditing(true)}
              className="mt-3 text-xs text-red-400 hover:text-red-300"
            >
              Edit Objectives
            </button>
          )}
          {debrief.updated_at && (
            <p className="mt-2 text-xs text-gray-500">
              Last updated: {new Date(debrief.updated_at).toLocaleString()} by {debrief.updated_by}
            </p>
          )}
        </div>
      )}
    </WarCard>
  )
}

// War Map visualization component
function WarMap({ leaderboard }) {
  const [mapData, setMapData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedRegion, setSelectedRegion] = useState(null)

  useEffect(() => {
    const fetchMapData = async () => {
      try {
        setError(null)
        const res = await axios.get('/api/warroom/map-data')
        console.log('War Map data received:', res.data)
        setMapData(res.data)
      } catch (err) {
        console.error('Failed to fetch map data:', err)
        setError(err.response?.data?.detail || err.message || 'Failed to load map data')
      } finally {
        setLoading(false)
      }
    }
    fetchMapData()
    // Refresh every 30 seconds
    const interval = setInterval(fetchMapData, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-red-400 animate-pulse">Loading war map...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4 opacity-50">⚠️</div>
          <p className="text-red-400 font-medium">Error loading map</p>
          <p className="text-gray-500 text-sm mt-1">{error}</p>
        </div>
      </div>
    )
  }

  if (!mapData || !mapData.enrolled_civs || !mapData.enrolled_civs.length) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4 opacity-50">🌌</div>
          <p className="text-gray-500">No enrolled civilizations yet.</p>
          <p className="text-gray-600 text-sm mt-1">Enroll civs in the Admin tab to see territory.</p>
        </div>
      </div>
    )
  }

  const { regions = [], home_regions = [], enrolled_civs, active_conflict_count } = mapData

  // Build a map of all regions by coordinates
  const regionMap = {}
  regions.forEach(r => {
    if (r.region_x != null && r.region_y != null && r.region_z != null) {
      const key = `${r.region_x}:${r.region_y}:${r.region_z}`
      regionMap[key] = r
    }
  })

  // Add home regions that might not have claims
  home_regions.forEach(hr => {
    if (hr.region_x != null && hr.region_y != null && hr.region_z != null) {
      const key = `${hr.region_x}:${hr.region_y}:${hr.region_z}`
      if (!regionMap[key]) {
        regionMap[key] = {
          region_x: hr.region_x,
          region_y: hr.region_y,
          region_z: hr.region_z,
          region_name: hr.region_name,
          galaxy: hr.galaxy,
          controlling_civ: hr.civ,
          system_count: 0,
          contested: false,
          active_conflicts: [],
          is_home_region: true
        }
      }
    }
  })

  const allRegions = Object.values(regionMap)

  // Handle empty regions case
  if (allRegions.length === 0) {
    return (
      <div className="h-full flex flex-col">
        <div className="flex items-center justify-between mb-3 text-xs">
          <span className="text-gray-400">
            <span className="text-white font-bold">{enrolled_civs.length}</span> Civilizations
          </span>
        </div>
        <div className="flex-1 flex items-center justify-center bg-gray-950/50 rounded border border-red-500/20">
          <div className="text-center">
            <div className="text-4xl mb-4 opacity-50">🗺️</div>
            <p className="text-gray-500">No territory claimed yet.</p>
            <p className="text-gray-600 text-sm mt-1">Civs need to upload systems or claim territory to appear on the map.</p>
          </div>
        </div>
        {/* Civilization legend */}
        <div className="mt-3 flex flex-wrap gap-2">
          {enrolled_civs.map(civ => (
            <div
              key={civ.partner_id}
              className="flex items-center gap-1.5 px-2 py-1 bg-gray-800/50 rounded text-xs"
            >
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: civ.color || '#666' }}
              />
              <span className="text-gray-300">{civ.display_name}</span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // Calculate bounds for visualization
  const xCoords = allRegions.map(r => r.region_x)
  const zCoords = allRegions.map(r => r.region_z)
  const minX = Math.min(...xCoords)
  const maxX = Math.max(...xCoords)
  const minZ = Math.min(...zCoords)
  const maxZ = Math.max(...zCoords)

  // Scale function (normalize to 0-100 range with padding)
  const scaleX = (x) => ((x - minX) / (maxX - minX || 1)) * 80 + 10
  const scaleZ = (z) => ((z - minZ) / (maxZ - minZ || 1)) * 80 + 10

  return (
    <div className="h-full flex flex-col">
      {/* Map header with stats */}
      <div className="flex items-center justify-between mb-3 text-xs">
        <div className="flex items-center gap-4">
          <span className="text-gray-400">
            <span className="text-white font-bold">{enrolled_civs.length}</span> Civilizations
          </span>
          <span className="text-gray-400">
            <span className="text-white font-bold">{allRegions.length}</span> Regions
          </span>
          {active_conflict_count > 0 && (
            <span className="text-red-400 animate-pulse">
              <span className="font-bold">{active_conflict_count}</span> Active Conflict{active_conflict_count !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        {/* Legend */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded border-2 border-yellow-400 bg-yellow-400/30" />
            <span className="text-gray-400">HQ</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-cyan-500/50 border border-cyan-400" />
            <span className="text-gray-400">Owned</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-gray-500" />
            <span className="text-gray-400">Claimed</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-red-500 animate-pulse" />
            <span className="text-gray-400">Contested</span>
          </div>
        </div>
      </div>

      {/* Map visualization */}
      <div className="flex-1 relative bg-gray-950/50 rounded border border-red-500/20 overflow-hidden">
        {/* Grid background */}
        <div className="absolute inset-0 opacity-20" style={{
          backgroundImage: 'linear-gradient(rgba(239,68,68,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(239,68,68,0.3) 1px, transparent 1px)',
          backgroundSize: '20px 20px'
        }} />

        {/* Region markers */}
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
          {/* Connections between home regions and claims of same civ */}
          {enrolled_civs.map(civ => {
            const civRegions = allRegions.filter(r => r.controlling_civ?.partner_id === civ.partner_id)
            const homeRegion = home_regions.find(hr => hr.civ.partner_id === civ.partner_id)
            if (!homeRegion || civRegions.length < 2) return null
            const homeX = scaleX(homeRegion.region_x)
            const homeZ = scaleZ(homeRegion.region_z)
            return civRegions.map((r, i) => {
              if (r.is_home_region && r.region_x === homeRegion.region_x) return null
              return (
                <line
                  key={`${civ.partner_id}-${i}`}
                  x1={homeX}
                  y1={homeZ}
                  x2={scaleX(r.region_x)}
                  y2={scaleZ(r.region_z)}
                  stroke={civ.color || '#666'}
                  strokeWidth="0.3"
                  strokeOpacity="0.3"
                  strokeDasharray="2,2"
                />
              )
            })
          })}

          {/* Region circles */}
          {allRegions.map((region, i) => {
            const x = scaleX(region.region_x)
            const z = scaleZ(region.region_z)
            const color = region.controlling_civ?.color || region.ownership?.owner?.color || '#666'
            const isHome = region.is_home_region
            const isContested = region.contested
            const isOwned = region.ownership && region.ownership.percentage > 50
            const size = isHome ? 4 : Math.min(3 + (region.system_count || 0) * 0.3, 6)

            return (
              <g
                key={i}
                onClick={() => setSelectedRegion(region)}
                className="cursor-pointer"
                transform={`translate(${x}, ${z})`}
              >
                {/* Contested pulse effect */}
                {isContested && (
                  <circle
                    cx={0}
                    cy={0}
                    r={size + 2}
                    fill="none"
                    stroke="#ef4444"
                    strokeWidth="0.5"
                    opacity="0.6"
                  >
                    <animate attributeName="r" values={`${size};${size + 4};${size}`} dur="1.5s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.6;0.1;0.6" dur="1.5s" repeatCount="indefinite" />
                  </circle>
                )}
                {/* Home region glow */}
                {isHome && (
                  <circle
                    cx={0}
                    cy={0}
                    r={size + 1.5}
                    fill="none"
                    stroke="#fbbf24"
                    strokeWidth="1"
                    opacity="0.6"
                  />
                )}
                {/* Owned region indicator (cyan ring) */}
                {isOwned && !isHome && (
                  <circle
                    cx={0}
                    cy={0}
                    r={size + 1}
                    fill="none"
                    stroke="#22d3d1"
                    strokeWidth="0.6"
                    opacity="0.8"
                    strokeDasharray="1,1"
                  />
                )}
                {/* Main circle */}
                <circle
                  cx={0}
                  cy={0}
                  r={size}
                  fill={color}
                  fillOpacity={isHome ? 0.9 : isOwned ? 0.8 : 0.7}
                  stroke={isContested ? '#ef4444' : isHome ? '#fbbf24' : isOwned ? '#22d3d1' : color}
                  strokeWidth={isContested || isHome ? 0.8 : isOwned ? 0.5 : 0.3}
                />
                {/* Home icon */}
                {isHome && (
                  <text
                    x={0}
                    y={1}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize="4"
                    fill="white"
                    fontWeight="bold"
                  >
                    H
                  </text>
                )}
              </g>
            )
          })}
        </svg>

        {/* Selected region info panel */}
        {selectedRegion && (
          <div className="absolute bottom-2 left-2 right-2 bg-gray-900/95 border border-red-500/30 rounded p-3">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: selectedRegion.controlling_civ?.color || selectedRegion.ownership?.owner?.color || '#666' }}
                  />
                  <span className="font-bold text-white">
                    {selectedRegion.region_name || `Region (${selectedRegion.region_x}, ${selectedRegion.region_y}, ${selectedRegion.region_z})`}
                  </span>
                  {selectedRegion.is_home_region && (
                    <span className="text-xs bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded">HQ</span>
                  )}
                  {selectedRegion.ownership && selectedRegion.ownership.percentage > 50 && (
                    <span className="text-xs bg-cyan-500/20 text-cyan-400 px-1.5 py-0.5 rounded">
                      OWNED {selectedRegion.ownership.percentage}%
                    </span>
                  )}
                  {selectedRegion.contested && (
                    <span className="text-xs bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded animate-pulse">CONTESTED</span>
                  )}
                </div>
                <div className="text-xs text-gray-400">
                  {selectedRegion.ownership ? (
                    <>
                      Owned by: <span style={{ color: selectedRegion.ownership.owner?.color }} className="font-medium">{selectedRegion.ownership.owner?.display_name}</span>
                      <span> • {selectedRegion.ownership.system_count} system{selectedRegion.ownership.system_count !== 1 ? 's' : ''}</span>
                    </>
                  ) : selectedRegion.controlling_civ ? (
                    <>
                      Controlled by: <span style={{ color: selectedRegion.controlling_civ?.color }}>{selectedRegion.controlling_civ?.display_name || 'Unknown'}</span>
                      {selectedRegion.system_count > 0 && <span> • {selectedRegion.system_count} claim{selectedRegion.system_count !== 1 ? 's' : ''}</span>}
                    </>
                  ) : (
                    <span>Unclaimed</span>
                  )}
                  {selectedRegion.galaxy && <span> • {selectedRegion.galaxy}</span>}
                </div>
                {selectedRegion.active_conflicts?.length > 0 && (
                  <div className="mt-1 text-xs text-red-400">
                    Under attack by: {selectedRegion.active_conflicts.map(c => c.attacker).join(', ')}
                  </div>
                )}
              </div>
              <button
                onClick={() => setSelectedRegion(null)}
                className="text-gray-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Civilization legend */}
      <div className="mt-3 flex flex-wrap gap-2">
        {enrolled_civs.map(civ => (
          <div
            key={civ.partner_id}
            className="flex items-center gap-1.5 px-2 py-1 bg-gray-800/50 rounded text-xs"
          >
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: civ.color || '#666' }}
            />
            <span className="text-gray-300">{civ.display_name}</span>
            {civ.home_region && (
              <span className="text-yellow-400 text-[10px]">⌂</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// Leaderboard component
function CivLeaderboard({ leaderboard }) {
  return (
    <WarCard title="Civilization Rankings">
      {leaderboard.length === 0 ? (
        <p className="text-gray-500 text-sm">No enrolled civilizations yet.</p>
      ) : (
        <div className="space-y-2">
          {leaderboard.map((civ, i) => (
            <div key={civ.partner_id} className="flex items-center justify-between bg-gray-800/50 rounded p-2">
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-gray-500">#{i + 1}</span>
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: civ.color }}
                />
                <span className="font-medium text-gray-200">{civ.display_name}</span>
              </div>
              <div className="flex gap-4 text-xs">
                <div className="text-center">
                  <div className="text-gray-400">Controlled</div>
                  <div className="font-bold text-green-400">{civ.systems_controlled}</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-400">Conquered</div>
                  <div className="font-bold text-red-400">{civ.systems_conquered}</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-400">Win Rate</div>
                  <div className="font-bold text-yellow-400">{civ.win_rate}%</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </WarCard>
  )
}

// Statistics display
function WarStats({ stats }) {
  const statLabels = {
    longest_defense: { label: 'Longest Defense', icon: '🛡️' },
    fastest_invasion: { label: 'Fastest Invasion', icon: '⚔️' },
    largest_battle: { label: 'Largest Battle', icon: '💥' },
    most_conquered: { label: 'Most Conquests', icon: '👑' }
  }

  return (
    <WarCard title="War Records">
      <div className="grid grid-cols-2 gap-3">
        {Object.entries(statLabels).map(([key, { label, icon }]) => {
          const stat = stats[key]
          return (
            <div key={key} className="bg-gray-800/50 rounded p-2 text-center">
              <div className="text-lg mb-1">{icon}</div>
              <div className="text-xs text-gray-400">{label}</div>
              {stat ? (
                <>
                  <div className="font-bold text-white">{stat.value} {stat.unit}</div>
                  <div className="text-xs text-red-400">{stat.holder || 'N/A'}</div>
                </>
              ) : (
                <div className="text-xs text-gray-500 italic">No record yet</div>
              )}
            </div>
          )
        })}
      </div>
    </WarCard>
  )
}

// Declare War Modal with improved UI
function DeclareWarModal({ open, onClose, onSuccess, claims, isSuperAdmin, enrolledCivs, myPartnerId }) {
  const [selectedClaim, setSelectedClaim] = useState(null)
  const [attackerPartnerId, setAttackerPartnerId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  if (!open) return null

  // Filter claims: for regular partner, exclude own claims; for super admin with attacker selected, exclude that attacker's claims
  const attackerIdToExclude = isSuperAdmin ? parseInt(attackerPartnerId) : myPartnerId
  const availableTargets = claims.filter(c => c.claimant_partner_id !== attackerIdToExclude)

  // Group claims by owner for easier viewing
  const claimsByOwner = availableTargets.reduce((acc, claim) => {
    const key = claim.claimant_display_name
    if (!acc[key]) acc[key] = { color: claim.claimant_color, claims: [] }
    acc[key].claims.push(claim)
    return acc
  }, {})

  const handleDeclare = async () => {
    if (!selectedClaim) {
      setError('Please select a target system')
      return
    }
    if (isSuperAdmin && !attackerPartnerId) {
      setError('Please select an attacking civilization')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const payload = { target_system_id: selectedClaim.system_id }
      if (isSuperAdmin) {
        payload.attacker_partner_id = parseInt(attackerPartnerId)
      }
      await axios.post('/api/warroom/conflicts', payload)
      onSuccess()
      onClose()
      setSelectedClaim(null)
      setAttackerPartnerId('')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to declare attack')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-red-500/30 rounded-lg p-6 w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        <h2 className="text-xl font-bold text-red-500 mb-4">DECLARE WAR</h2>
        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        {/* Super admin: select attacker */}
        {isSuperAdmin && (
          <div className="mb-4">
            <label className="block text-sm text-gray-400 mb-2">Attacking Civilization</label>
            <select
              value={attackerPartnerId}
              onChange={(e) => { setAttackerPartnerId(e.target.value); setSelectedClaim(null); }}
              className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
            >
              <option value="">-- Select attacking civilization --</option>
              {enrolledCivs.map(civ => (
                <option key={civ.partner_id} value={civ.partner_id}>{civ.display_name}</option>
              ))}
            </select>
          </div>
        )}

        {/* Selected target display */}
        {selectedClaim && (
          <div className="mb-4 bg-red-950/50 border border-red-500/50 rounded p-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs text-red-400 uppercase font-bold">Target Selected</div>
                <div className="font-bold text-white">{selectedClaim.system_name || selectedClaim.system_id}</div>
                <div className="text-xs text-gray-400">
                  Region ({selectedClaim.region_x}, {selectedClaim.region_y}, {selectedClaim.region_z})
                  {' '}&bull;{' '}{selectedClaim.galaxy}
                </div>
                <div className="text-xs mt-1">
                  Controlled by: <span style={{ color: selectedClaim.claimant_color }}>{selectedClaim.claimant_display_name}</span>
                </div>
              </div>
              <button onClick={() => setSelectedClaim(null)} className="text-gray-400 hover:text-white text-sm">
                Change
              </button>
            </div>
          </div>
        )}

        {/* Target selection - scrollable list of claims grouped by owner */}
        {!selectedClaim && (
          <div className="mb-4 flex-1 overflow-hidden">
            <label className="block text-sm text-gray-400 mb-2">Select Target System</label>
            {(isSuperAdmin && !attackerPartnerId) ? (
              <p className="text-gray-500 text-sm text-center py-8">Select an attacking civilization first</p>
            ) : Object.keys(claimsByOwner).length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-8">No enemy territories to attack</p>
            ) : (
              <div className="max-h-64 overflow-y-auto space-y-3 pr-2">
                {Object.entries(claimsByOwner).map(([ownerName, { color, claims: ownerClaims }]) => (
                  <div key={ownerName} className="bg-gray-800/50 rounded border border-gray-700">
                    <div className="px-3 py-2 border-b border-gray-700 flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                      <span className="text-sm font-medium" style={{ color }}>{ownerName}</span>
                      <span className="text-xs text-gray-500">({ownerClaims.length} systems)</span>
                    </div>
                    <div className="p-2 space-y-1">
                      {ownerClaims.map(claim => (
                        <button
                          key={claim.id}
                          onClick={() => setSelectedClaim(claim)}
                          className="w-full text-left px-3 py-2 rounded hover:bg-red-900/30 border border-transparent hover:border-red-500/50 transition-colors"
                        >
                          <div className="font-medium text-white text-sm">{claim.system_name || claim.system_id}</div>
                          <div className="text-xs text-gray-400">
                            Region ({claim.region_x}, {claim.region_y}, {claim.region_z}) &bull; {claim.galaxy}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex gap-3 pt-2 border-t border-gray-700">
          <button
            onClick={handleDeclare}
            disabled={loading || !selectedClaim}
            className="flex-1 py-2 bg-red-600 hover:bg-red-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded font-bold"
          >
            {loading ? 'Declaring...' : 'DECLARE ATTACK'}
          </button>
          <button onClick={onClose} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded">
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

// Claim Territory Modal with searchable system browser
function ClaimTerritoryModal({ open, onClose, onSuccess, isSuperAdmin, enrolledCivs }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [selectedSystem, setSelectedSystem] = useState(null)
  const [partnerId, setPartnerId] = useState('')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState(null)
  const searchTimeoutRef = useRef(null)

  // Debounced search
  useEffect(() => {
    if (!open) return

    if (searchQuery.length < 2) {
      setSearchResults([])
      return
    }

    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }

    searchTimeoutRef.current = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await axios.get(`/api/systems/search?q=${encodeURIComponent(searchQuery)}&limit=20`)
        setSearchResults(res.data.results || [])
      } catch (err) {
        console.error('Search failed:', err)
        setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 300)

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }
    }
  }, [searchQuery, open])

  if (!open) return null

  const handleClaim = async () => {
    if (!selectedSystem) {
      setError('Please select a system to claim')
      return
    }
    if (isSuperAdmin && !partnerId) {
      setError('Please select a civilization')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const payload = { system_id: selectedSystem.id, notes }
      if (isSuperAdmin) {
        payload.partner_id = parseInt(partnerId)
      }
      await axios.post('/api/warroom/claims', payload)
      onSuccess()
      onClose()
      setSearchQuery('')
      setSelectedSystem(null)
      setPartnerId('')
      setNotes('')
      setSearchResults([])
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to claim territory')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectSystem = (system) => {
    setSelectedSystem(system)
    setSearchQuery('')
    setSearchResults([])
  }

  const handleClearSelection = () => {
    setSelectedSystem(null)
  }

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-green-500/30 rounded-lg p-6 w-full max-w-lg">
        <h2 className="text-xl font-bold text-green-500 mb-4">CLAIM TERRITORY</h2>
        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        {/* Super admin: select claiming civilization */}
        {isSuperAdmin && (
          <div className="mb-4">
            <label className="block text-sm text-gray-400 mb-2">Claiming Civilization</label>
            <select
              value={partnerId}
              onChange={(e) => setPartnerId(e.target.value)}
              className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
            >
              <option value="">-- Select civilization --</option>
              {enrolledCivs.map(civ => (
                <option key={civ.partner_id} value={civ.partner_id}>{civ.display_name}</option>
              ))}
            </select>
          </div>
        )}

        {/* System search */}
        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-2">Search System</label>
          {selectedSystem ? (
            <div className="bg-gray-800 border border-green-500/50 rounded p-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-bold text-green-400">{selectedSystem.name}</div>
                  <div className="text-xs text-gray-400">
                    {selectedSystem.region_name || `Region (${selectedSystem.region_x}, ${selectedSystem.region_y}, ${selectedSystem.region_z})`}
                    {' '}&bull;{' '}{selectedSystem.galaxy}
                    {selectedSystem.discord_tag && <span className="ml-1 text-cyan-400">({selectedSystem.discord_tag})</span>}
                  </div>
                  {selectedSystem.glyph_code && (
                    <div className="text-xs text-gray-500 font-mono mt-1">{selectedSystem.glyph_code}</div>
                  )}
                </div>
                <button
                  onClick={handleClearSelection}
                  className="text-red-400 hover:text-red-300 text-sm"
                >
                  Change
                </button>
              </div>
            </div>
          ) : (
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Type system name, glyph code, or region..."
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
              />
              {searching && (
                <div className="absolute right-3 top-2 text-gray-400 text-sm">Searching...</div>
              )}
              {/* Search results dropdown */}
              {searchResults.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-600 rounded shadow-lg max-h-60 overflow-y-auto">
                  {searchResults.map(system => (
                    <button
                      key={system.id}
                      onClick={() => handleSelectSystem(system)}
                      className="w-full text-left px-3 py-2 hover:bg-gray-700 border-b border-gray-700 last:border-b-0"
                    >
                      <div className="font-medium text-white">{system.name}</div>
                      <div className="text-xs text-gray-400">
                        {system.region_name || `(${system.region_x}, ${system.region_y}, ${system.region_z})`}
                        {' '}&bull;{' '}{system.galaxy}
                        {system.discord_tag && <span className="ml-1 text-cyan-400">({system.discord_tag})</span>}
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {searchQuery.length >= 2 && !searching && searchResults.length === 0 && (
                <div className="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-600 rounded p-3 text-center text-gray-400 text-sm">
                  No systems found matching "{searchQuery}"
                </div>
              )}
            </div>
          )}
          <p className="text-xs text-gray-500 mt-1">Search for cataloged systems by name, glyph code, or region</p>
        </div>

        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-2">Notes (optional)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Strategic importance, resources, etc."
            className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
            rows={2}
          />
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleClaim}
            disabled={loading}
            className="flex-1 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 rounded font-bold"
          >
            {loading ? 'Claiming...' : 'CLAIM TERRITORY'}
          </button>
          <button onClick={onClose} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded">
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

// Activity Feed Panel - shows public war activity
function ActivityFeedPanel({ maxItems = 15 }) {
  const [feed, setFeed] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchFeed = async () => {
      try {
        const res = await axios.get(`/api/warroom/activity-feed?limit=${maxItems}`)
        setFeed(res.data)
      } catch (err) {
        console.error('Failed to fetch activity feed:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchFeed()
    const interval = setInterval(fetchFeed, 15000) // Update every 15 seconds
    return () => clearInterval(interval)
  }, [maxItems])

  const getEventIcon = (eventType) => {
    const icons = {
      'war_declared': '⚔️',
      'conflict_acknowledged': '🤝',
      'conflict_resolved': '🏆',
      'conflict_cancelled': '🏳️',
      'battle_skirmish': '💥',
      'battle_capture': '🎯',
      'battle_defense': '🛡️',
      'battle_retreat': '🏃',
      'battle_reinforcement': '📢',
      'ally_joined': '🤝',
      'resolution_proposed': '📝',
      'resolution_agreed': '✅',
      'territory_claimed': '📍',
      'news_published': '📰'
    }
    return icons[eventType] || '📌'
  }

  const getEventColor = (eventType) => {
    if (eventType.includes('battle')) return 'border-orange-500/30 bg-orange-950/20'
    if (eventType.includes('resolved') || eventType.includes('agreed')) return 'border-green-500/30 bg-green-950/20'
    if (eventType.includes('declared') || eventType.includes('war')) return 'border-red-500/30 bg-red-950/20'
    if (eventType.includes('cancelled')) return 'border-gray-500/30 bg-gray-950/20'
    return 'border-yellow-500/30 bg-yellow-950/20'
  }

  if (loading) {
    return (
      <WarCard title="Live Activity Feed">
        <div className="text-center py-8 text-gray-400 animate-pulse">Loading activity...</div>
      </WarCard>
    )
  }

  return (
    <WarCard title="Live Activity Feed">
      {feed.length === 0 ? (
        <div className="text-center py-8 text-gray-500">No recent activity</div>
      ) : (
        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2">
          {feed.map((entry) => (
            <div
              key={entry.id}
              className={`p-3 rounded border ${getEventColor(entry.event_type)}`}
            >
              <div className="flex items-start gap-2">
                <span className="text-lg">{getEventIcon(entry.event_type)}</span>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-white text-sm">{entry.headline}</div>
                  {entry.details && (
                    <div className="text-xs text-gray-400 mt-1">{entry.details}</div>
                  )}
                  <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                    <span>{new Date(entry.created_at).toLocaleString()}</span>
                    {entry.system_name && (
                      <span className="text-cyan-400">@ {entry.system_name}</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </WarCard>
  )
}

// Notifications Panel - dropdown for user notifications
function NotificationsPanel({ count, onRead }) {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchNotifications = async () => {
    setLoading(true)
    try {
      const res = await axios.get('/api/warroom/notifications?limit=20')
      setNotifications(res.data)
    } catch (err) {
      console.error('Failed to fetch notifications:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await axios.put('/api/warroom/notifications/read-all')
      setNotifications(prev => prev.map(n => ({ ...n, read_at: new Date().toISOString() })))
      onRead?.()
    } catch (err) {
      console.error('Failed to mark notifications read:', err)
    }
  }

  useEffect(() => {
    if (open) {
      fetchNotifications()
    }
  }, [open])

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
      >
        <span>🔔</span>
        {count > 0 && (
          <span className="bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-2 w-80 bg-gray-900 border border-red-500/30 rounded-lg shadow-xl z-50">
            <div className="flex items-center justify-between p-3 border-b border-gray-700">
              <span className="font-bold text-red-400">War Alerts</span>
              {notifications.length > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="text-xs text-gray-400 hover:text-white"
                >
                  Mark all read
                </button>
              )}
            </div>

            <div className="max-h-80 overflow-y-auto">
              {loading ? (
                <div className="p-4 text-center text-gray-400">Loading...</div>
              ) : notifications.length === 0 ? (
                <div className="p-4 text-center text-gray-500">No notifications</div>
              ) : (
                notifications.map(notif => (
                  <div
                    key={notif.id}
                    className={`p-3 border-b border-gray-800 ${!notif.read_at ? 'bg-red-950/20' : ''}`}
                  >
                    <div className="font-medium text-sm text-white">{notif.title}</div>
                    <div className="text-xs text-gray-400 mt-1">{notif.message}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      {new Date(notif.created_at).toLocaleString()}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// My Territory Panel - shows user's claims
function MyTerritoryPanel({ partnerId, isSuperAdmin, onReleaseClaim, discordTag }) {
  const [claims, setClaims] = useState([])
  const [territory, setTerritory] = useState({ systems: [], regions: {}, total_systems: 0 })
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState('territory') // 'territory' or 'claims'

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [claimsRes, territoryRes] = await Promise.all([
          axios.get('/api/warroom/claims'),
          discordTag ? axios.get(`/api/warroom/territory/by-tag?discord_tag=${encodeURIComponent(discordTag)}`) : Promise.resolve({ data: { systems: [], regions: {} } })
        ])

        // Filter claims
        const myClaims = isSuperAdmin ? claimsRes.data : claimsRes.data.filter(c => c.claimant_partner_id === partnerId)
        setClaims(myClaims)
        setTerritory(territoryRes.data)
      } catch (err) {
        console.error('Failed to fetch territory:', err)
      } finally {
        setLoading(false)
      }
    }
    if (partnerId || isSuperAdmin) {
      fetchData()
    }
  }, [partnerId, isSuperAdmin, discordTag])

  const handleRelease = async (claimId) => {
    if (!confirm('Release this territorial claim?')) return
    try {
      await axios.delete(`/api/warroom/claims/${claimId}`)
      setClaims(prev => prev.filter(c => c.id !== claimId))
      onReleaseClaim?.()
    } catch (err) {
      console.error('Failed to release claim:', err)
    }
  }

  if (loading) {
    return (
      <WarCard title="My Territory">
        <div className="text-center py-4 text-gray-400">Loading...</div>
      </WarCard>
    )
  }

  return (
    <WarCard title={isSuperAdmin ? "All Territory" : "My Territory"}>
      {/* View Toggle */}
      <div className="flex gap-1 mb-3 bg-gray-800/50 rounded p-1">
        <button
          onClick={() => setViewMode('territory')}
          className={`flex-1 px-2 py-1 text-xs font-medium rounded ${
            viewMode === 'territory' ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          Systems ({territory.total_systems || 0})
        </button>
        <button
          onClick={() => setViewMode('claims')}
          className={`flex-1 px-2 py-1 text-xs font-medium rounded ${
            viewMode === 'claims' ? 'bg-cyan-600 text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          War Claims ({claims.length})
        </button>
      </div>

      {viewMode === 'territory' ? (
        /* Territory from discord_tag */
        territory.total_systems === 0 ? (
          <div className="text-center py-4 text-gray-500 text-sm">No systems uploaded with your tag</div>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {/* Show by region */}
            {Object.entries(territory.regions || {}).map(([key, region]) => (
              <div key={key} className="bg-gray-800/50 rounded p-2">
                <div className="flex items-center justify-between">
                  <div className="font-medium text-green-400 text-sm">{region.region_name || `Region (${region.region_x}, ${region.region_y}, ${region.region_z})`}</div>
                  <span className="text-xs text-gray-400">{region.system_count} systems</span>
                </div>
                <div className="text-xs text-gray-500">{region.galaxy}</div>
              </div>
            ))}
          </div>
        )
      ) : (
        /* War Claims */
        claims.length === 0 ? (
          <div className="text-center py-4 text-gray-500 text-sm">No war territory claims</div>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {claims.map(claim => (
              <div key={claim.id} className="flex items-center justify-between bg-gray-800/50 rounded p-2">
                <div>
                  <div className="font-medium text-white text-sm">{claim.system_name || claim.system_id}</div>
                  <div className="text-xs text-gray-400">
                    {claim.galaxy} &bull; ({claim.region_x}, {claim.region_y}, {claim.region_z})
                  </div>
                  {isSuperAdmin && (
                    <div className="text-xs mt-1" style={{ color: claim.claimant_color }}>
                      {claim.claimant_display_name}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => handleRelease(claim.id)}
                  className="text-xs text-red-400 hover:text-red-300 px-2 py-1"
                >
                  Release
                </button>
              </div>
            ))}
          </div>
        )
      )}
    </WarCard>
  )
}

// Peace Treaty Modal - Civ6-style peace negotiations
function PeaceTreatyModal({ open, onClose, conflictId, onSuccess, isAttacker, myPartnerId }) {
  const [negotiationStatus, setNegotiationStatus] = useState(null)
  const [proposals, setProposals] = useState([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  // Form state for new proposal
  const [selectedSystems, setSelectedSystems] = useState([])
  const [message, setMessage] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [showProposalForm, setShowProposalForm] = useState(false)

  useEffect(() => {
    if (!open || !conflictId) return
    fetchNegotiationData()
  }, [open, conflictId])

  const fetchNegotiationData = async () => {
    setLoading(true)
    try {
      const [statusRes, proposalsRes] = await Promise.all([
        axios.get(`/api/warroom/conflicts/${conflictId}/negotiation-status`),
        axios.get(`/api/warroom/conflicts/${conflictId}/peace-proposals`)
      ])
      setNegotiationStatus(statusRes.data)
      setProposals(proposalsRes.data)
    } catch (err) {
      console.error('Failed to fetch negotiation data:', err)
      setError('Failed to load negotiation data')
    } finally {
      setLoading(false)
    }
  }

  // Search for systems to include in proposal
  useEffect(() => {
    if (searchQuery.length < 2) {
      setSearchResults([])
      return
    }
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await axios.get(`/api/warroom/territory/search?q=${encodeURIComponent(searchQuery)}&limit=20`)
        // Filter to only show partner-owned systems
        setSearchResults(res.data.filter(s => s.is_partner_owned))
      } catch (err) {
        console.error('Search failed:', err)
      } finally {
        setSearching(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  const handleAddSystem = (system) => {
    if (!selectedSystems.find(s => s.id === system.id)) {
      setSelectedSystems([...selectedSystems, {
        ...system,
        direction: 'give' // Default to giving
      }])
    }
    setSearchQuery('')
    setSearchResults([])
  }

  const handleRemoveSystem = (systemId) => {
    setSelectedSystems(selectedSystems.filter(s => s.id !== systemId))
  }

  const handleToggleDirection = (systemId) => {
    setSelectedSystems(selectedSystems.map(s =>
      s.id === systemId ? { ...s, direction: s.direction === 'give' ? 'receive' : 'give' } : s
    ))
  }

  const handleSubmitProposal = async (isCounter = false) => {
    if (selectedSystems.length === 0) {
      setError('Please select at least one system to include in the proposal')
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      await axios.post(`/api/warroom/conflicts/${conflictId}/propose-peace`, {
        items: selectedSystems.map(s => ({
          type: 'system',
          direction: s.direction,
          system_id: s.id,
          system_name: s.name,
          from_partner_id: s.direction === 'give' ? myPartnerId : null,
          to_partner_id: s.direction === 'receive' ? myPartnerId : null
        })),
        message,
        is_counter: isCounter
      })
      setSelectedSystems([])
      setMessage('')
      setShowProposalForm(false)
      fetchNegotiationData()
      onSuccess?.()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit proposal')
    } finally {
      setSubmitting(false)
    }
  }

  const handleAcceptProposal = async (proposalId) => {
    if (!confirm('Accept this peace treaty? This will end the war and transfer territory as specified.')) return
    setSubmitting(true)
    try {
      await axios.put(`/api/warroom/peace-proposals/${proposalId}/accept`)
      onSuccess?.()
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to accept proposal')
    } finally {
      setSubmitting(false)
    }
  }

  const handleRejectProposal = async (proposalId, walkAway = false) => {
    const message = walkAway
      ? 'Walk away from negotiations? The war will continue.'
      : 'Reject this proposal? You may still send a counter-offer.'
    if (!confirm(message)) return

    setSubmitting(true)
    try {
      await axios.put(`/api/warroom/peace-proposals/${proposalId}/reject`, { walk_away: walkAway })
      fetchNegotiationData()
      onSuccess?.()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reject proposal')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  const pendingProposal = proposals.find(p => p.status === 'pending')
  const isRecipient = pendingProposal?.recipient_partner_id === myPartnerId
  const myCountersRemaining = isAttacker
    ? negotiationStatus?.attacker_counters_remaining
    : negotiationStatus?.defender_counters_remaining

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-amber-500/30 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-amber-500/20">
          <h2 className="text-xl font-bold text-amber-500">PEACE NEGOTIATIONS</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">✕</button>
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading negotiation status...</div>
        ) : (
          <div className="flex-1 overflow-y-auto p-4">
            {error && <p className="text-red-400 text-sm mb-4 p-2 bg-red-950/30 rounded">{error}</p>}

            {/* Negotiation Status */}
            <div className="bg-gray-800/50 rounded p-4 mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-bold text-amber-400">STATUS</span>
                <span className={`px-2 py-1 rounded text-xs font-bold ${
                  negotiationStatus?.negotiation_status === 'pending' ? 'bg-amber-500' :
                  negotiationStatus?.negotiation_status === 'failed' ? 'bg-red-500' :
                  negotiationStatus?.negotiation_status === 'accepted' ? 'bg-green-500' :
                  'bg-gray-500'
                } text-white`}>
                  {negotiationStatus?.negotiation_status?.toUpperCase() || 'NONE'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Your counter-offers remaining: </span>
                  <span className={`font-bold ${myCountersRemaining > 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {myCountersRemaining ?? 2}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400">War status: </span>
                  <span className="font-bold text-white">{negotiationStatus?.conflict_status?.toUpperCase()}</span>
                </div>
              </div>
            </div>

            {/* Pending Proposal to Respond To */}
            {pendingProposal && isRecipient && (
              <div className="bg-amber-950/30 border border-amber-500/30 rounded p-4 mb-4">
                <h3 className="text-sm font-bold text-amber-400 mb-3">INCOMING PROPOSAL</h3>
                <div className="text-sm text-gray-300 mb-2">
                  From: <span style={{ color: pendingProposal.proposer_color }} className="font-bold">
                    {pendingProposal.proposer_name}
                  </span>
                </div>
                {pendingProposal.message && (
                  <div className="text-sm text-gray-400 italic mb-3">"{pendingProposal.message}"</div>
                )}

                {/* Items in proposal */}
                <div className="space-y-2 mb-4">
                  <div className="text-xs text-gray-500 uppercase">Terms:</div>
                  {pendingProposal.items.map((item, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm bg-gray-800/50 rounded p-2">
                      <span className={item.direction === 'give' ? 'text-red-400' : 'text-green-400'}>
                        {item.direction === 'give' ? '↑ GIVE' : '↓ RECEIVE'}
                      </span>
                      <span className="text-white">{item.system_name || `Region (${item.region_x}, ${item.region_y}, ${item.region_z})`}</span>
                    </div>
                  ))}
                </div>

                {/* Response buttons */}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleAcceptProposal(pendingProposal.id)}
                    disabled={submitting}
                    className="flex-1 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 rounded font-bold text-sm"
                  >
                    Accept Treaty
                  </button>
                  <button
                    onClick={() => handleRejectProposal(pendingProposal.id, false)}
                    disabled={submitting}
                    className="px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-gray-600 rounded font-bold text-sm"
                  >
                    Counter
                  </button>
                  <button
                    onClick={() => handleRejectProposal(pendingProposal.id, true)}
                    disabled={submitting}
                    className="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:bg-gray-600 rounded font-bold text-sm"
                  >
                    Walk Away
                  </button>
                </div>
              </div>
            )}

            {/* Waiting for response */}
            {pendingProposal && !isRecipient && (
              <div className="bg-gray-800/50 border border-gray-500/30 rounded p-4 mb-4 text-center">
                <div className="text-amber-400 text-lg mb-2">Awaiting Response...</div>
                <div className="text-sm text-gray-400">
                  Your proposal was sent to <span className="font-bold text-white">{pendingProposal.recipient_name}</span>
                </div>
              </div>
            )}

            {/* Create New Proposal / Counter-Offer */}
            {(!pendingProposal || (isRecipient && myCountersRemaining > 0)) && (
              <>
                {!showProposalForm ? (
                  <button
                    onClick={() => setShowProposalForm(true)}
                    className="w-full py-3 bg-amber-600 hover:bg-amber-500 rounded font-bold text-lg mb-4"
                  >
                    {pendingProposal ? 'Send Counter-Offer' : 'Propose Peace Terms'}
                  </button>
                ) : (
                  <div className="bg-gray-800/50 rounded p-4 mb-4">
                    <h3 className="text-sm font-bold text-amber-400 mb-3">
                      {pendingProposal ? 'COUNTER-OFFER' : 'PEACE PROPOSAL'}
                    </h3>

                    {/* System Search */}
                    <div className="mb-4">
                      <label className="block text-sm text-gray-400 mb-2">Search Systems to Include</label>
                      <div className="relative">
                        <input
                          type="text"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          placeholder="Search by system name..."
                          className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
                        />
                        {searching && <span className="absolute right-3 top-2 text-gray-400 text-sm">...</span>}
                        {searchResults.length > 0 && (
                          <div className="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-600 rounded shadow-lg max-h-48 overflow-y-auto">
                            {searchResults.map(s => (
                              <button
                                key={s.id}
                                onClick={() => handleAddSystem(s)}
                                className="w-full text-left px-3 py-2 hover:bg-gray-700 text-sm"
                              >
                                <span className="font-medium text-white">{s.name}</span>
                                <span className="text-gray-400 ml-2">({s.owner_name})</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Selected Systems */}
                    {selectedSystems.length > 0 && (
                      <div className="mb-4">
                        <label className="block text-sm text-gray-400 mb-2">Terms ({selectedSystems.length} systems)</label>
                        <div className="space-y-2 max-h-40 overflow-y-auto">
                          {selectedSystems.map(s => (
                            <div key={s.id} className="flex items-center gap-2 bg-gray-700/50 rounded p-2">
                              <button
                                onClick={() => handleToggleDirection(s.id)}
                                className={`px-2 py-1 rounded text-xs font-bold ${
                                  s.direction === 'give' ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'
                                }`}
                              >
                                {s.direction === 'give' ? '↑ GIVE' : '↓ RECEIVE'}
                              </button>
                              <span className="flex-1 text-sm text-white">{s.name}</span>
                              <button
                                onClick={() => handleRemoveSystem(s.id)}
                                className="text-red-400 hover:text-red-300 text-sm"
                              >
                                ✕
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Message */}
                    <div className="mb-4">
                      <label className="block text-sm text-gray-400 mb-2">Message (optional)</label>
                      <textarea
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        placeholder="Diplomatic message..."
                        className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
                        rows={2}
                      />
                    </div>

                    {/* Submit */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleSubmitProposal(!!pendingProposal)}
                        disabled={submitting || selectedSystems.length === 0}
                        className="flex-1 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-gray-600 rounded font-bold"
                      >
                        {submitting ? 'Sending...' : (pendingProposal ? 'Send Counter-Offer' : 'Send Proposal')}
                      </button>
                      <button
                        onClick={() => {
                          setShowProposalForm(false)
                          setSelectedSystems([])
                          setMessage('')
                        }}
                        className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Proposal History */}
            {proposals.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-bold text-gray-400 mb-2">NEGOTIATION HISTORY</h3>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {proposals.map(p => (
                    <div key={p.id} className={`p-3 rounded border text-sm ${
                      p.status === 'accepted' ? 'bg-green-950/30 border-green-500/30' :
                      p.status === 'rejected' ? 'bg-red-950/30 border-red-500/30' :
                      p.status === 'pending' ? 'bg-amber-950/30 border-amber-500/30' :
                      'bg-gray-800/50 border-gray-500/30'
                    }`}>
                      <div className="flex items-center justify-between mb-1">
                        <span style={{ color: p.proposer_color }} className="font-bold">{p.proposer_name}</span>
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          p.status === 'accepted' ? 'bg-green-500' :
                          p.status === 'rejected' ? 'bg-red-500' :
                          p.status === 'pending' ? 'bg-amber-500' :
                          'bg-gray-500'
                        } text-white`}>
                          {p.status.toUpperCase()}
                        </span>
                      </div>
                      <div className="text-xs text-gray-400">
                        {p.proposal_type === 'counter' && `Counter #${p.counter_number} • `}
                        {new Date(p.proposed_at).toLocaleString()}
                      </div>
                      {p.items.length > 0 && (
                        <div className="text-xs text-gray-500 mt-1">
                          {p.items.length} system(s) in terms
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
    </div>
  )
}

// Conflict Detail Modal - shows full conflict info with timeline
function ConflictDetailModal({ open, onClose, conflictId, onUpdate, myPartnerId }) {
  const [conflict, setConflict] = useState(null)
  const [events, setEvents] = useState([])
  const [parties, setParties] = useState([])
  const [loading, setLoading] = useState(true)
  const [newEventType, setNewEventType] = useState('skirmish')
  const [newEventDetails, setNewEventDetails] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [showPeaceTreaty, setShowPeaceTreaty] = useState(false)

  useEffect(() => {
    if (!open || !conflictId) return

    const fetchConflictDetails = async () => {
      setLoading(true)
      try {
        const [conflictsRes, eventsRes, partiesRes] = await Promise.all([
          axios.get('/api/warroom/conflicts/active'),
          axios.get(`/api/warroom/conflicts/${conflictId}/events`),
          axios.get(`/api/warroom/conflicts/${conflictId}/parties`)
        ])
        const thisConflict = conflictsRes.data.find(c => c.id === conflictId)
        setConflict(thisConflict)
        setEvents(eventsRes.data)
        setParties(partiesRes.data)
      } catch (err) {
        console.error('Failed to fetch conflict details:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchConflictDetails()
  }, [open, conflictId])

  const handleAddEvent = async () => {
    if (!newEventDetails.trim()) return
    setSubmitting(true)
    try {
      await axios.post(`/api/warroom/conflicts/${conflictId}/events`, {
        event_type: newEventType,
        details: newEventDetails
      })
      // Refresh events
      const eventsRes = await axios.get(`/api/warroom/conflicts/${conflictId}/events`)
      setEvents(eventsRes.data)
      setNewEventDetails('')
      onUpdate?.()
    } catch (err) {
      console.error('Failed to add event:', err)
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-red-500/30 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-red-500/20">
          <h2 className="text-xl font-bold text-red-500">CONFLICT DETAILS</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">✕</button>
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading conflict details...</div>
        ) : !conflict ? (
          <div className="p-8 text-center text-gray-400">Conflict not found</div>
        ) : (
          <div className="flex-1 overflow-y-auto p-4">
            {/* Conflict Overview */}
            <div className="bg-gray-800/50 rounded p-4 mb-4">
              <div className="flex items-center justify-between mb-3">
                <span className={`px-2 py-1 rounded text-xs font-bold ${
                  conflict.status === 'active' ? 'bg-red-500 animate-pulse' :
                  conflict.status === 'pending' ? 'bg-yellow-500' : 'bg-gray-500'
                } text-white`}>
                  {conflict.status.toUpperCase()}
                </span>
                <span className="text-xs text-gray-400">ID: {conflict.id}</span>
              </div>
              <div className="text-lg font-bold text-white mb-2">
                Battle for {conflict.target_system_name}
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span style={{ color: conflict.attacker_color }} className="font-bold">
                  {conflict.attacker_name}
                </span>
                <span className="text-red-400">⚔️</span>
                <span style={{ color: conflict.defender_color }} className="font-bold">
                  {conflict.defender_name}
                </span>
              </div>
              <div className="text-xs text-gray-400 mt-2">
                Declared: {new Date(conflict.declared_at).toLocaleString()}
              </div>
            </div>

            {/* Allied Parties */}
            {parties.length > 2 && (
              <div className="bg-gray-800/50 rounded p-4 mb-4">
                <h3 className="text-sm font-bold text-yellow-400 mb-2">ALLIED PARTIES</h3>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <div className="text-xs text-gray-400 mb-1">Attackers</div>
                    {parties.filter(p => p.side === 'attacker').map(p => (
                      <div key={p.partner_id} className="text-sm flex items-center gap-1">
                        <span style={{ color: p.color }}>{p.display_name}</span>
                        {p.is_primary === 1 && <span className="text-xs text-yellow-400">(Lead)</span>}
                      </div>
                    ))}
                  </div>
                  <div>
                    <div className="text-xs text-gray-400 mb-1">Defenders</div>
                    {parties.filter(p => p.side === 'defender').map(p => (
                      <div key={p.partner_id} className="text-sm flex items-center gap-1">
                        <span style={{ color: p.color }}>{p.display_name}</span>
                        {p.is_primary === 1 && <span className="text-xs text-yellow-400">(Lead)</span>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Timeline */}
            <div className="mb-4">
              <h3 className="text-sm font-bold text-red-400 mb-2">BATTLE TIMELINE</h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {events.map((event, i) => (
                  <div key={event.id} className="flex gap-3 bg-gray-800/30 rounded p-2">
                    <div className="flex flex-col items-center">
                      <div className={`w-3 h-3 rounded-full ${
                        event.event_type === 'declared' ? 'bg-red-500' :
                        event.event_type === 'acknowledged' ? 'bg-yellow-500' :
                        event.event_type === 'resolved' ? 'bg-green-500' :
                        'bg-gray-500'
                      }`} />
                      {i < events.length - 1 && <div className="w-0.5 flex-1 bg-gray-700 mt-1" />}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-gray-300 uppercase">
                          {event.event_type}
                        </span>
                        <span className="text-xs text-gray-500">
                          {new Date(event.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="text-sm text-gray-400">{event.details}</div>
                      {event.actor_username && (
                        <div className="text-xs text-cyan-400">by {event.actor_username}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Add Event (if conflict is active) */}
            {conflict.status !== 'resolved' && (
              <div className="bg-gray-800/50 rounded p-4">
                <h3 className="text-sm font-bold text-yellow-400 mb-2">ADD BATTLE EVENT</h3>
                <div className="flex gap-2 mb-2">
                  <select
                    value={newEventType}
                    onChange={(e) => setNewEventType(e.target.value)}
                    className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm"
                  >
                    <option value="skirmish">Skirmish</option>
                    <option value="capture">Capture</option>
                    <option value="defense">Defense</option>
                    <option value="retreat">Retreat</option>
                    <option value="reinforcement">Reinforcement</option>
                    <option value="note">Note</option>
                  </select>
                  <input
                    type="text"
                    value={newEventDetails}
                    onChange={(e) => setNewEventDetails(e.target.value)}
                    placeholder="Event details..."
                    className="flex-1 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm"
                  />
                  <button
                    onClick={handleAddEvent}
                    disabled={submitting || !newEventDetails.trim()}
                    className="px-3 py-1 bg-red-600 hover:bg-red-500 disabled:bg-gray-600 rounded text-sm font-bold"
                  >
                    Add
                  </button>
                </div>
              </div>
            )}

            {/* Peace Treaty Button (if conflict is active and user is a party) */}
            {conflict.status === 'active' && myPartnerId && (
              <div className="mt-4">
                <button
                  onClick={() => setShowPeaceTreaty(true)}
                  className="w-full py-3 bg-amber-600 hover:bg-amber-500 rounded font-bold text-lg"
                >
                  Propose Peace Treaty
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Peace Treaty Modal */}
      <PeaceTreatyModal
        open={showPeaceTreaty}
        onClose={() => setShowPeaceTreaty(false)}
        conflictId={conflictId}
        onSuccess={() => {
          onUpdate?.()
          setShowPeaceTreaty(false)
        }}
        isAttacker={conflict?.attacker_partner_id === myPartnerId}
        myPartnerId={myPartnerId}
      />
    </div>
  )
}

// News Room Panel - Full news management
function NewsRoomPanel({ isCorrespondent, isSuperAdmin, onCreateNews }) {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedArticle, setSelectedArticle] = useState(null)

  useEffect(() => {
    const fetchNews = async () => {
      try {
        const res = await axios.get('/api/warroom/news?limit=50')
        setArticles(res.data)
      } catch (err) {
        console.error('Failed to fetch news:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchNews()
  }, [])

  const getArticleTypeIcon = (type) => {
    const icons = {
      'breaking': '🔴',
      'report': '📋',
      'analysis': '📊',
      'editorial': '✍️',
      'announcement': '📢'
    }
    return icons[type] || '📰'
  }

  if (loading) {
    return <div className="text-center py-8 text-gray-400">Loading news...</div>
  }

  return (
    <div className="space-y-4">
      {/* News List */}
      <div className="space-y-3">
        {articles.length === 0 ? (
          <div className="text-center py-8 text-gray-500">No news articles yet</div>
        ) : (
          articles.map(article => (
            <div
              key={article.id}
              onClick={() => setSelectedArticle(article)}
              className="bg-gray-800/50 border border-yellow-500/20 rounded p-4 cursor-pointer hover:border-yellow-500/50 transition-colors"
            >
              <div className="flex items-start gap-3">
                <span className="text-2xl">{getArticleTypeIcon(article.article_type)}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    {article.is_pinned === 1 && (
                      <span className="text-xs bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded">PINNED</span>
                    )}
                    <span className="text-xs text-gray-500 uppercase">{article.article_type || 'news'}</span>
                  </div>
                  <h3 className="font-bold text-white">{article.headline}</h3>
                  <p className="text-sm text-gray-400 mt-1 line-clamp-2">{article.body}</p>
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                    <span>By {article.author_name || 'Unknown'}</span>
                    {article.reporting_org_name && (
                      <span className="text-cyan-400">{article.reporting_org_name}</span>
                    )}
                    <span>{new Date(article.created_at).toLocaleDateString()}</span>
                    {article.view_count > 0 && (
                      <span>👁 {article.view_count}</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Article Detail Modal */}
      {selectedArticle && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-yellow-500/30 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-yellow-500/20">
              <div className="flex items-center gap-2">
                <span className="text-2xl">{getArticleTypeIcon(selectedArticle.article_type)}</span>
                <span className="text-xs text-gray-400 uppercase">{selectedArticle.article_type || 'news'}</span>
              </div>
              <button onClick={() => setSelectedArticle(null)} className="text-gray-400 hover:text-white">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              <h1 className="text-2xl font-bold text-white mb-4">{selectedArticle.headline}</h1>
              <div className="flex items-center gap-3 text-sm text-gray-400 mb-6">
                <span>By {selectedArticle.author_name || 'Unknown'}</span>
                {selectedArticle.reporting_org_name && (
                  <span className="text-cyan-400">• {selectedArticle.reporting_org_name}</span>
                )}
                <span>• {new Date(selectedArticle.created_at).toLocaleString()}</span>
              </div>
              <div className="prose prose-invert max-w-none">
                <p className="text-gray-300 whitespace-pre-wrap">{selectedArticle.body}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Create News Modal - Enhanced with article types
function CreateNewsModal({ open, onClose, onSuccess }) {
  const [headline, setHeadline] = useState('')
  const [body, setBody] = useState('')
  const [articleType, setArticleType] = useState('breaking')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  if (!open) return null

  const handleCreate = async () => {
    if (!headline || !body) {
      setError('Headline and body are required')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await axios.post('/api/warroom/news', { headline, body, article_type: articleType })
      onSuccess()
      onClose()
      setHeadline('')
      setBody('')
      setArticleType('breaking')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create news')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-yellow-500/30 rounded-lg p-6 w-full max-w-lg">
        <h2 className="text-xl font-bold text-yellow-500 mb-4">CREATE WAR NEWS</h2>
        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-2">Article Type</label>
          <select
            value={articleType}
            onChange={(e) => setArticleType(e.target.value)}
            className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
          >
            <option value="breaking">🔴 Breaking News</option>
            <option value="report">📋 Battle Report</option>
            <option value="analysis">📊 Analysis</option>
            <option value="editorial">✍️ Editorial</option>
            <option value="announcement">📢 Announcement</option>
          </select>
        </div>

        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-2">Headline</label>
          <input
            type="text"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            placeholder="Breaking news headline..."
            className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
          />
        </div>
        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-2">Article Body</label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Full article content..."
            className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
            rows={8}
          />
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleCreate}
            disabled={loading}
            className="flex-1 py-2 bg-yellow-600 hover:bg-yellow-500 disabled:bg-gray-600 rounded font-bold text-black"
          >
            {loading ? 'Publishing...' : 'PUBLISH NEWS'}
          </button>
          <button onClick={onClose} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded">
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

// Main War Room component
export default function WarRoom() {
  const auth = useContext(AuthContext)
  const [loading, setLoading] = useState(true)
  const [enrollmentStatus, setEnrollmentStatus] = useState(null)
  const [activeConflicts, setActiveConflicts] = useState([])
  const [debrief, setDebrief] = useState({ objectives: [] })
  const [statistics, setStatistics] = useState({})
  const [leaderboard, setLeaderboard] = useState([])
  const [newsTicker, setNewsTicker] = useState([])
  const [notificationCount, setNotificationCount] = useState(0)
  const [error, setError] = useState(null)
  const [allClaims, setAllClaims] = useState([])

  // View state - tabs
  const [activeTab, setActiveTab] = useState('command') // 'command' or 'news'

  // Modal states
  const [showDeclareWar, setShowDeclareWar] = useState(false)
  const [showClaimTerritory, setShowClaimTerritory] = useState(false)
  const [showCreateNews, setShowCreateNews] = useState(false)
  const [selectedConflictId, setSelectedConflictId] = useState(null)

  const fetchData = async () => {
    try {
      const [
        statusRes,
        conflictsRes,
        debriefRes,
        statsRes,
        leaderboardRes,
        newsRes,
        notifRes,
        claimsRes
      ] = await Promise.all([
        axios.get('/api/warroom/enrollment/status'),
        axios.get('/api/warroom/conflicts/active'),
        axios.get('/api/warroom/debrief'),
        axios.get('/api/warroom/statistics'),
        axios.get('/api/warroom/statistics/leaderboard'),
        axios.get('/api/warroom/news/ticker'),
        axios.get('/api/warroom/notifications/count'),
        axios.get('/api/warroom/claims')
      ])

      setEnrollmentStatus(statusRes.data)
      setActiveConflicts(conflictsRes.data)
      setDebrief(debriefRes.data)
      setStatistics(statsRes.data)
      setLeaderboard(leaderboardRes.data)
      setNewsTicker(newsRes.data)
      setNotificationCount(notifRes.data.count)
      setAllClaims(claimsRes.data)
    } catch (err) {
      console.error('Failed to fetch War Room data:', err)
      setError(err.response?.data?.detail || 'Failed to load War Room data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    // Poll every 30 seconds for live updates
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleUpdateDebrief = async (objectives) => {
    await axios.put('/api/warroom/debrief', { objectives })
    setDebrief(prev => ({ ...prev, objectives }))
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center"
           style={{ backgroundColor: '#0a0c10' }}>
        <div className="text-red-400 text-xl animate-pulse">Loading War Room...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center"
           style={{ backgroundColor: '#0a0c10' }}>
        <div className="text-center">
          <div className="text-red-500 text-xl mb-4">Access Denied</div>
          <p className="text-gray-400">{error}</p>
          <Link to="/" className="text-red-400 hover:underline mt-4 inline-block">
            Return to Dashboard
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen -m-6 -mb-6" style={{ backgroundColor: '#0a0c10' }}>
      {/* Custom CSS for War Room */}
      <style>{`
        @keyframes marquee {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .animate-marquee {
          animation: marquee 30s linear infinite;
        }
        .war-grid {
          background-image:
            linear-gradient(rgba(239, 68, 68, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(239, 68, 68, 0.05) 1px, transparent 1px);
          background-size: 50px 50px;
        }
      `}</style>

      {/* Header */}
      <div className="border-b border-red-500/30 bg-gray-900/90 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold text-red-500 tracking-wider">WAR ROOM</h1>
            {auth.isCorrespondent && (
              <div className="flex items-center gap-2 px-3 py-1 bg-yellow-500/20 border border-yellow-500/30 rounded">
                <div className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
                <span className="text-xs text-yellow-400 font-medium">
                  WAR CORRESPONDENT
                </span>
              </div>
            )}
            {enrollmentStatus?.enrolled && !auth.isCorrespondent && (
              <div className="flex items-center gap-2 px-3 py-1 bg-green-500/20 border border-green-500/30 rounded">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-xs text-green-400 font-medium">
                  {enrollmentStatus.display_name || 'ENROLLED'}
                </span>
              </div>
            )}

            {/* View Tabs */}
            <div className="flex items-center gap-1 bg-gray-800/50 rounded p-1 ml-4">
              <button
                onClick={() => setActiveTab('command')}
                className={`px-3 py-1 text-sm font-medium rounded transition-colors ${
                  activeTab === 'command'
                    ? 'bg-red-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-700'
                }`}
              >
                Command Center
              </button>
              <button
                onClick={() => setActiveTab('news')}
                className={`px-3 py-1 text-sm font-medium rounded transition-colors ${
                  activeTab === 'news'
                    ? 'bg-yellow-600 text-black'
                    : 'text-gray-400 hover:text-white hover:bg-gray-700'
                }`}
              >
                News Room
              </button>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Action Buttons - only show if enrolled */}
            {enrollmentStatus?.enrolled && !enrollmentStatus?.is_super_admin && (
              <>
                <button
                  onClick={() => setShowClaimTerritory(true)}
                  className="px-3 py-1 bg-green-600 hover:bg-green-500 rounded text-sm font-bold"
                >
                  Claim Territory
                </button>
                <button
                  onClick={() => setShowDeclareWar(true)}
                  className="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-sm font-bold"
                >
                  Declare War
                </button>
              </>
            )}
            {/* Correspondents can only create news */}
            {auth.isCorrespondent && (
              <button
                onClick={() => setShowCreateNews(true)}
                className="px-3 py-1 bg-yellow-600 hover:bg-yellow-500 rounded text-sm font-bold text-black"
              >
                + News
              </button>
            )}
            {auth.isSuperAdmin && (
              <>
                <button
                  onClick={() => setShowCreateNews(true)}
                  className="px-3 py-1 bg-yellow-600 hover:bg-yellow-500 rounded text-sm font-bold text-black"
                >
                  + News
                </button>
                <button
                  onClick={() => setShowClaimTerritory(true)}
                  className="px-3 py-1 bg-green-600 hover:bg-green-500 rounded text-sm font-bold"
                >
                  Claim
                </button>
                <button
                  onClick={() => setShowDeclareWar(true)}
                  className="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-sm font-bold"
                >
                  War
                </button>
              </>
            )}
            {/* Notifications Panel */}
            <NotificationsPanel
              count={notificationCount}
              onRead={() => setNotificationCount(0)}
            />
            {auth.isSuperAdmin && (
              <Link
                to="/war-room/admin"
                className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm ml-2"
              >
                Admin
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Main content - switches based on active tab */}
      {activeTab === 'command' ? (
        /* COMMAND CENTER VIEW */
        <div className="p-6 war-grid">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column - War Map */}
            <div className="lg:col-span-2">
              <WarCard title="Galactic War Map" className="h-[550px]">
                <WarMap3D className="h-full rounded" />
              </WarCard>

              {/* Active Conflicts - clickable for details */}
              <div className="mt-6">
                <WarCard title={`Active Conflicts (${activeConflicts.length})`}>
                  {activeConflicts.length === 0 ? (
                    <p className="text-gray-500 text-sm text-center py-4">
                      No active conflicts. The galaxy is at peace... for now.
                    </p>
                  ) : (
                    <div className="max-h-64 overflow-y-auto pr-2">
                      {activeConflicts.map(c => (
                        <div
                          key={c.id}
                          onClick={() => setSelectedConflictId(c.id)}
                          className="cursor-pointer hover:ring-1 hover:ring-red-500/50 rounded transition-all"
                        >
                          <ConflictCard conflict={c} />
                        </div>
                      ))}
                    </div>
                  )}
                </WarCard>
              </div>
            </div>

            {/* Right Column */}
            <div className="space-y-6">
              {/* Debrief */}
              <DebriefPanel
                debrief={debrief}
                onUpdate={handleUpdateDebrief}
                canEdit={auth.isSuperAdmin}
              />

              {/* Live Activity Feed */}
              <ActivityFeedPanel maxItems={10} />

              {/* My Territory - only if enrolled */}
              {(enrollmentStatus?.enrolled || auth.isSuperAdmin) && (
                <MyTerritoryPanel
                  partnerId={enrollmentStatus?.partner_id}
                  isSuperAdmin={auth.isSuperAdmin}
                  onReleaseClaim={fetchData}
                  discordTag={enrollmentStatus?.discord_tag}
                />
              )}

              {/* Statistics */}
              <WarStats stats={statistics} />

              {/* Leaderboard */}
              <CivLeaderboard leaderboard={leaderboard} />
            </div>
          </div>
        </div>
      ) : (
        /* NEWS ROOM VIEW */
        <div className="p-6 war-grid">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Main News Column */}
            <div className="lg:col-span-3">
              <WarCard title="War News & Reports" className="min-h-[600px]">
                <NewsRoomPanel
                  isCorrespondent={auth.isCorrespondent}
                  isSuperAdmin={auth.isSuperAdmin}
                  onCreateNews={() => setShowCreateNews(true)}
                />
              </WarCard>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Quick Actions */}
              {(auth.isCorrespondent || auth.isSuperAdmin) && (
                <WarCard title="Reporter Actions">
                  <div className="space-y-2">
                    <button
                      onClick={() => setShowCreateNews(true)}
                      className="w-full py-2 bg-yellow-600 hover:bg-yellow-500 rounded font-bold text-black text-sm"
                    >
                      Write Article
                    </button>
                  </div>
                </WarCard>
              )}

              {/* Activity Feed in News View too */}
              <ActivityFeedPanel maxItems={8} />

              {/* Active Conflicts Summary */}
              <WarCard title="Active Conflicts">
                {activeConflicts.length === 0 ? (
                  <p className="text-gray-500 text-sm">No active conflicts</p>
                ) : (
                  <div className="space-y-2">
                    {activeConflicts.slice(0, 5).map(c => (
                      <div
                        key={c.id}
                        onClick={() => {
                          setSelectedConflictId(c.id)
                          setActiveTab('command')
                        }}
                        className="cursor-pointer p-2 bg-gray-800/50 rounded hover:bg-gray-800 text-sm"
                      >
                        <div className="font-medium text-white">{c.target_system_name}</div>
                        <div className="text-xs text-gray-400">
                          <span style={{ color: c.attacker_color }}>{c.attacker_name}</span>
                          {' vs '}
                          <span style={{ color: c.defender_color }}>{c.defender_name}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </WarCard>
            </div>
          </div>
        </div>
      )}

      {/* News Ticker - always visible at bottom */}
      <NewsTicker news={newsTicker} />

      {/* Modals */}
      <DeclareWarModal
        open={showDeclareWar}
        onClose={() => setShowDeclareWar(false)}
        onSuccess={fetchData}
        claims={allClaims}
        isSuperAdmin={auth.isSuperAdmin}
        enrolledCivs={leaderboard}
        myPartnerId={enrollmentStatus?.partner_id}
      />
      <ClaimTerritoryModal
        open={showClaimTerritory}
        onClose={() => setShowClaimTerritory(false)}
        onSuccess={fetchData}
        isSuperAdmin={auth.isSuperAdmin}
        enrolledCivs={leaderboard}
      />
      <CreateNewsModal
        open={showCreateNews}
        onClose={() => setShowCreateNews(false)}
        onSuccess={fetchData}
      />
      <ConflictDetailModal
        open={!!selectedConflictId}
        onClose={() => setSelectedConflictId(null)}
        conflictId={selectedConflictId}
        onUpdate={fetchData}
        myPartnerId={enrollmentStatus?.partner_id}
      />
    </div>
  )
}
