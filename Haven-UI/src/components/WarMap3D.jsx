import React, { useRef, useState, useEffect, useMemo, useCallback } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Text, Line } from '@react-three/drei'
import * as THREE from 'three'
import axios from 'axios'

// Scale factor for positions (smaller = tighter grouping)
const POSITION_SCALE = 0.02

// War Room color palette
const WAR_COLORS = {
  background: '#050508',
  grid: '#1a0a0a',
  gridLines: '#3d1515',
  accent: '#ef4444',
  contested: '#ff0000',
  hqGlow: '#fbbf24',
  text: '#e5e7eb',
  defaultRegion: '#666666'
}

// Tactical grid component
function TacticalGrid({ size = 200 }) {
  const gridRef = useRef()

  return (
    <group>
      {/* Main grid */}
      <gridHelper
        args={[size, 40, WAR_COLORS.gridLines, WAR_COLORS.grid]}
        rotation={[0, 0, 0]}
        position={[0, -50, 0]}
      />
      {/* Secondary faint grid */}
      <gridHelper
        args={[size, 80, WAR_COLORS.grid, 'transparent']}
        rotation={[0, 0, 0]}
        position={[0, -50, 0]}
      />
    </group>
  )
}

// Animated pulsing ring for contested regions
function ContestedPulse({ position, color, size = 0.5 }) {
  const ringRef = useRef()

  useFrame((state) => {
    const t = state.clock.elapsedTime
    const pulse = 1 + Math.sin(t * 3) * 0.3
    if (ringRef.current) {
      ringRef.current.scale.set(pulse, pulse, pulse)
      ringRef.current.material.opacity = 0.3 + Math.sin(t * 3) * 0.2
    }
  })

  return (
    <mesh ref={ringRef} position={position}>
      <ringGeometry args={[size + 0.2, size + 0.4, 32]} />
      <meshBasicMaterial
        color={WAR_COLORS.contested}
        transparent
        opacity={0.5}
        side={THREE.DoubleSide}
      />
    </mesh>
  )
}

// HQ Beacon with animated glow
function HQBeacon({ position, color, name }) {
  const beaconRef = useRef()
  const glowRef = useRef()

  useFrame((state) => {
    const t = state.clock.elapsedTime
    if (glowRef.current) {
      glowRef.current.scale.set(
        1 + Math.sin(t * 2) * 0.15,
        1 + Math.sin(t * 2) * 0.15,
        1 + Math.sin(t * 2) * 0.15
      )
      glowRef.current.material.opacity = 0.4 + Math.sin(t * 2) * 0.2
    }
  })

  return (
    <group position={position}>
      {/* Outer glow */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[0.8, 16, 16]} />
        <meshBasicMaterial
          color={WAR_COLORS.hqGlow}
          transparent
          opacity={0.4}
        />
      </mesh>
      {/* Inner beacon */}
      <mesh ref={beaconRef}>
        <sphereGeometry args={[0.5, 16, 16]} />
        <meshBasicMaterial color={color || WAR_COLORS.hqGlow} />
      </mesh>
      {/* Vertical beam */}
      <mesh position={[0, 3, 0]}>
        <cylinderGeometry args={[0.05, 0.05, 6, 8]} />
        <meshBasicMaterial
          color={WAR_COLORS.hqGlow}
          transparent
          opacity={0.3}
        />
      </mesh>
      {/* HQ Label */}
      <Text
        position={[0, 1.5, 0]}
        fontSize={0.4}
        color={WAR_COLORS.hqGlow}
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.02}
        outlineColor="#000000"
      >
        HQ
      </Text>
    </group>
  )
}

// Region point with hover/click interaction
function RegionPoint({ region, isSelected, onSelect, onHover, onDoubleClick }) {
  const meshRef = useRef()
  const [hovered, setHovered] = useState(false)

  const color = useMemo(() => {
    return region.controlling_civ?.color ||
           region.ownership?.owner?.color ||
           WAR_COLORS.defaultRegion
  }, [region])

  // Much smaller base size
  const size = useMemo(() => {
    const baseSize = 0.25
    const systemBonus = Math.min((region.system_count || 1) * 0.02, 0.25)
    return baseSize + systemBonus
  }, [region])

  useFrame((state) => {
    if (meshRef.current) {
      // Subtle floating animation
      meshRef.current.position.y = Math.sin(state.clock.elapsedTime + region.region_x) * 0.05
      // Scale on hover
      const targetScale = hovered || isSelected ? 1.5 : 1
      meshRef.current.scale.lerp(
        new THREE.Vector3(targetScale, targetScale, targetScale),
        0.1
      )
    }
  })

  const position = useMemo(() => [
    (region.region_x - 2048) * POSITION_SCALE,
    (region.region_y - 128) * POSITION_SCALE * 2,
    (region.region_z - 2048) * POSITION_SCALE
  ], [region])

  return (
    <group position={position}>
      {/* Contested pulse effect */}
      {region.contested && <ContestedPulse position={[0, 0, 0]} color={color} size={size} />}

      {/* Main region sphere */}
      <mesh
        ref={meshRef}
        onClick={(e) => {
          e.stopPropagation()
          onSelect(region)
        }}
        onDoubleClick={(e) => {
          e.stopPropagation()
          if (onDoubleClick) onDoubleClick(region)
        }}
        onPointerOver={(e) => {
          e.stopPropagation()
          setHovered(true)
          onHover(region)
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={(e) => {
          setHovered(false)
          onHover(null)
          document.body.style.cursor = 'auto'
        }}
      >
        <sphereGeometry args={[size, 16, 16]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={hovered || isSelected ? 1 : 0.85}
        />
      </mesh>

      {/* Ownership ring (cyan for >50% ownership) */}
      {region.ownership && region.ownership.percentage > 50 && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[size + 0.1, size + 0.15, 32]} />
          <meshBasicMaterial
            color="#22d3d1"
            transparent
            opacity={0.6}
            side={THREE.DoubleSide}
          />
        </mesh>
      )}

      {/* Selection ring when selected */}
      {isSelected && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[size + 0.2, size + 0.25, 32]} />
          <meshBasicMaterial
            color="#ffffff"
            transparent
            opacity={0.8}
            side={THREE.DoubleSide}
          />
        </mesh>
      )}
    </group>
  )
}

// Territory connection lines between regions of same civ
function TerritoryConnections({ regions, enrolledCivs }) {
  const lines = useMemo(() => {
    const connections = []

    enrolledCivs.forEach(civ => {
      const civRegions = regions.filter(r =>
        r.controlling_civ?.partner_id === civ.partner_id ||
        r.ownership?.owner?.partner_id === civ.partner_id
      )

      // Connect nearby regions of same civ
      for (let i = 0; i < civRegions.length; i++) {
        for (let j = i + 1; j < civRegions.length; j++) {
          const r1 = civRegions[i]
          const r2 = civRegions[j]

          // Calculate distance
          const dx = r1.region_x - r2.region_x
          const dy = r1.region_y - r2.region_y
          const dz = r1.region_z - r2.region_z
          const dist = Math.sqrt(dx*dx + dy*dy + dz*dz)

          // Only connect if reasonably close
          if (dist < 500) {
            connections.push({
              start: [
                (r1.region_x - 2048) * POSITION_SCALE,
                (r1.region_y - 128) * POSITION_SCALE * 2,
                (r1.region_z - 2048) * POSITION_SCALE
              ],
              end: [
                (r2.region_x - 2048) * POSITION_SCALE,
                (r2.region_y - 128) * POSITION_SCALE * 2,
                (r2.region_z - 2048) * POSITION_SCALE
              ],
              color: civ.color || WAR_COLORS.defaultRegion
            })
          }
        }
      }
    })

    return connections
  }, [regions, enrolledCivs])

  return (
    <group>
      {lines.map((line, i) => (
        <Line
          key={i}
          points={[line.start, line.end]}
          color={line.color}
          lineWidth={1}
          transparent
          opacity={0.2}
          dashed
          dashSize={2}
          gapSize={1}
        />
      ))}
    </group>
  )
}

// Camera controls and scene setup
function Scene({ regions, homeRegions, enrolledCivs, selectedRegion, onSelectRegion, onHoverRegion, focusTarget, onFocusComplete, onRegionDrillDown }) {
  const { camera } = useThree()
  const controlsRef = useRef()

  useEffect(() => {
    // Set initial camera position
    camera.position.set(20, 30, 40)
    camera.lookAt(0, 0, 0)
  }, [camera])

  // Animate camera to focus on a region
  useFrame(() => {
    if (focusTarget && controlsRef.current) {
      const targetPos = new THREE.Vector3(
        (focusTarget.region_x - 2048) * POSITION_SCALE,
        (focusTarget.region_y - 128) * POSITION_SCALE * 2,
        (focusTarget.region_z - 2048) * POSITION_SCALE
      )

      // Smoothly move camera target
      controlsRef.current.target.lerp(targetPos, 0.08)

      // Move camera closer to the target
      const cameraOffset = new THREE.Vector3(2, 2, 3)
      const desiredCameraPos = targetPos.clone().add(cameraOffset)
      camera.position.lerp(desiredCameraPos, 0.05)

      // Check if close enough to clear focus
      if (camera.position.distanceTo(desiredCameraPos) < 0.1) {
        onFocusComplete()
      }
    }
  })

  return (
    <>
      {/* Ambient light */}
      <ambientLight intensity={0.5} />

      {/* Tactical grid */}
      <TacticalGrid size={100} />

      {/* Galaxy center marker */}
      <mesh position={[0, 0, 0]}>
        <sphereGeometry args={[0.2, 16, 16]} />
        <meshBasicMaterial color={WAR_COLORS.accent} transparent opacity={0.8} />
      </mesh>

      {/* Territory connections */}
      <TerritoryConnections regions={regions} enrolledCivs={enrolledCivs} />

      {/* HQ Beacons */}
      {homeRegions.map((hr, i) => (
        <HQBeacon
          key={`hq-${i}`}
          position={[
            (hr.region_x - 2048) * POSITION_SCALE,
            (hr.region_y - 128) * POSITION_SCALE * 2,
            (hr.region_z - 2048) * POSITION_SCALE
          ]}
          color={hr.civ?.color}
          name={hr.civ?.display_name}
        />
      ))}

      {/* Region points */}
      {regions.map((region, i) => (
        <RegionPoint
          key={`region-${region.region_x}-${region.region_y}-${region.region_z}`}
          region={region}
          isSelected={selectedRegion?.region_x === region.region_x &&
                      selectedRegion?.region_y === region.region_y &&
                      selectedRegion?.region_z === region.region_z}
          onSelect={onSelectRegion}
          onHover={onHoverRegion}
          onDoubleClick={onRegionDrillDown}
        />
      ))}

      {/* Orbit controls - allow much closer zoom */}
      <OrbitControls
        ref={controlsRef}
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        minDistance={1}
        maxDistance={150}
        maxPolarAngle={Math.PI * 0.85}
        zoomSpeed={1.2}
      />
    </>
  )
}

// Main WarMap3D component
export default function WarMap3D({ className = '', onSystemSelect }) {
  const [mapData, setMapData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedRegion, setSelectedRegion] = useState(null)
  const [hoveredRegion, setHoveredRegion] = useState(null)
  const [focusTarget, setFocusTarget] = useState(null)
  const [drillDownRegion, setDrillDownRegion] = useState(null)
  const [regionSystems, setRegionSystems] = useState([])
  const [loadingSystems, setLoadingSystems] = useState(false)

  // Fetch map data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setError(null)
        const res = await axios.get('/api/warroom/map-data')
        console.log('War Map 3D data:', res.data)
        setMapData(res.data)
      } catch (err) {
        console.error('Failed to fetch map data:', err)
        setError(err.response?.data?.detail || 'Failed to load map data')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  // Fetch systems when drilling down into a region
  const handleDrillDown = useCallback(async (region) => {
    setDrillDownRegion(region)
    setFocusTarget(region)
    setLoadingSystems(true)
    try {
      // Fetch systems in this region
      const res = await axios.get('/api/systems', {
        params: {
          region_x: region.region_x,
          region_y: region.region_y,
          region_z: region.region_z,
          limit: 100
        }
      })
      setRegionSystems(res.data.systems || res.data || [])
    } catch (err) {
      console.error('Failed to fetch region systems:', err)
      setRegionSystems([])
    } finally {
      setLoadingSystems(false)
    }
  }, [])

  // Close drill-down view
  const closeDrillDown = useCallback(() => {
    setDrillDownRegion(null)
    setRegionSystems([])
  }, [])

  // Build regions array from map data
  const { regions, homeRegions, enrolledCivs } = useMemo(() => {
    if (!mapData) return { regions: [], homeRegions: [], enrolledCivs: [] }

    const regionMap = {}
    const rawRegions = mapData.regions || []
    const rawHomeRegions = mapData.home_regions || []
    const civs = mapData.enrolled_civs || []

    // Add regions
    rawRegions.forEach(r => {
      if (r.region_x != null && r.region_y != null && r.region_z != null) {
        const key = `${r.region_x}:${r.region_y}:${r.region_z}`
        regionMap[key] = r
      }
    })

    // Add home regions that aren't already in regions
    rawHomeRegions.forEach(hr => {
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
            is_home_region: true
          }
        } else {
          regionMap[key].is_home_region = true
        }
      }
    })

    return {
      regions: Object.values(regionMap),
      homeRegions: rawHomeRegions.filter(hr => hr.region_x != null),
      enrolledCivs: civs
    }
  }, [mapData])

  if (loading) {
    return (
      <div className={`h-full flex items-center justify-center bg-[#050508] ${className}`}>
        <div className="text-red-400 animate-pulse text-lg">Initializing War Map...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={`h-full flex items-center justify-center bg-[#050508] ${className}`}>
        <div className="text-center">
          <div className="text-4xl mb-4 opacity-50">⚠️</div>
          <p className="text-red-400 font-medium">Map System Offline</p>
          <p className="text-gray-500 text-sm mt-1">{error}</p>
        </div>
      </div>
    )
  }

  if (!mapData || !enrolledCivs.length) {
    return (
      <div className={`h-full flex items-center justify-center bg-[#050508] ${className}`}>
        <div className="text-center">
          <div className="text-4xl mb-4 opacity-50">🌌</div>
          <p className="text-gray-500">No enrolled civilizations.</p>
          <p className="text-gray-600 text-sm mt-1">Enroll civs in Admin to activate the war map.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`h-full relative bg-[#050508] ${className}`}>
      {/* 3D Canvas */}
      <Canvas
        camera={{ fov: 60, near: 0.1, far: 1000 }}
        gl={{ antialias: true, alpha: false }}
        style={{ background: WAR_COLORS.background }}
      >
        <color attach="background" args={[WAR_COLORS.background]} />
        <fog attach="fog" args={[WAR_COLORS.background, 100, 400]} />
        <Scene
          regions={regions}
          homeRegions={homeRegions}
          enrolledCivs={enrolledCivs}
          selectedRegion={selectedRegion}
          onSelectRegion={setSelectedRegion}
          onHoverRegion={setHoveredRegion}
          focusTarget={focusTarget}
          onFocusComplete={() => setFocusTarget(null)}
          onRegionDrillDown={handleDrillDown}
        />
      </Canvas>

      {/* Stats overlay */}
      <div className="absolute top-3 left-3 text-xs text-gray-400 bg-black/50 px-3 py-2 rounded">
        <span className="text-white font-bold">{enrolledCivs.length}</span> Civilizations •
        <span className="text-white font-bold ml-1">{regions.length}</span> Regions
        {mapData.active_conflict_count > 0 && (
          <span className="text-red-400 animate-pulse ml-2">
            • <span className="font-bold">{mapData.active_conflict_count}</span> Active Conflict{mapData.active_conflict_count !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Controls hint */}
      <div className="absolute bottom-3 left-3 text-xs text-gray-500 bg-black/50 px-3 py-2 rounded">
        <span className="text-gray-400">Controls:</span> Drag to rotate • Scroll to zoom • Right-drag to pan • Double-click to drill down
      </div>

      {/* Legend */}
      <div className="absolute top-3 right-3 bg-black/70 border border-red-500/30 rounded p-3 text-xs">
        <div className="text-red-400 font-bold mb-2 text-sm">LEGEND</div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-yellow-400 shadow-lg shadow-yellow-400/50" />
            <span className="text-gray-300">HQ (Headquarters)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-cyan-400 ring-1 ring-cyan-400" />
            <span className="text-gray-300">Owned (&gt;50%)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-gray-400" />
            <span className="text-gray-300">Claimed</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
            <span className="text-gray-300">Contested</span>
          </div>
        </div>
        <div className="mt-3 pt-2 border-t border-gray-700">
          <div className="text-gray-400 mb-1">Civilizations:</div>
          {enrolledCivs.map(civ => (
            <div key={civ.partner_id} className="flex items-center gap-2 mt-1">
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: civ.color || '#666' }}
              />
              <span className="text-gray-300 truncate max-w-[120px]">{civ.display_name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Selected region info panel */}
      {selectedRegion && !drillDownRegion && (
        <div className="absolute bottom-3 right-3 bg-black/90 border border-red-500/30 rounded p-4 max-w-xs">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{
                  backgroundColor: selectedRegion.controlling_civ?.color ||
                                   selectedRegion.ownership?.owner?.color || '#666'
                }}
              />
              <span className="font-bold text-white">
                {selectedRegion.region_name || `Region (${selectedRegion.region_x}, ${selectedRegion.region_y}, ${selectedRegion.region_z})`}
              </span>
            </div>
            <button
              onClick={() => setSelectedRegion(null)}
              className="text-gray-400 hover:text-white"
            >
              ✕
            </button>
          </div>

          <div className="space-y-1 text-sm">
            {selectedRegion.is_home_region && (
              <div className="inline-block bg-yellow-500/20 text-yellow-400 text-xs px-2 py-0.5 rounded mb-1">
                HEADQUARTERS
              </div>
            )}
            {selectedRegion.contested && (
              <div className="inline-block bg-red-500/20 text-red-400 text-xs px-2 py-0.5 rounded mb-1 ml-1 animate-pulse">
                CONTESTED
              </div>
            )}

            {selectedRegion.ownership ? (
              <p className="text-gray-400">
                Owned by: <span style={{ color: selectedRegion.ownership.owner?.color }} className="font-medium">
                  {selectedRegion.ownership.owner?.display_name}
                </span>
                <span className="text-gray-500"> ({selectedRegion.ownership.percentage}%)</span>
              </p>
            ) : selectedRegion.controlling_civ ? (
              <p className="text-gray-400">
                Controlled by: <span style={{ color: selectedRegion.controlling_civ.color }} className="font-medium">
                  {selectedRegion.controlling_civ.display_name}
                </span>
              </p>
            ) : null}

            {selectedRegion.system_count > 0 && (
              <p className="text-gray-500">
                {selectedRegion.system_count} system{selectedRegion.system_count !== 1 ? 's' : ''}
              </p>
            )}

            <p className="text-gray-600 text-xs mt-2">
              Coords: ({selectedRegion.region_x}, {selectedRegion.region_y}, {selectedRegion.region_z})
              {selectedRegion.galaxy && ` • ${selectedRegion.galaxy}`}
            </p>

            {/* Drill-down button */}
            <button
              onClick={() => handleDrillDown(selectedRegion)}
              className="mt-3 w-full px-3 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 rounded text-red-400 text-sm font-medium transition-colors"
            >
              View Systems →
            </button>
          </div>
        </div>
      )}

      {/* Drill-down systems panel */}
      {drillDownRegion && (
        <div className="absolute bottom-3 right-3 bg-black/95 border border-red-500/30 rounded p-4 w-80 max-h-[400px] flex flex-col">
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{
                    backgroundColor: drillDownRegion.controlling_civ?.color ||
                                     drillDownRegion.ownership?.owner?.color || '#666'
                  }}
                />
                <span className="font-bold text-white text-sm">
                  {drillDownRegion.region_name || 'Region'}
                </span>
              </div>
              <p className="text-gray-500 text-xs mt-1">
                ({drillDownRegion.region_x}, {drillDownRegion.region_y}, {drillDownRegion.region_z})
              </p>
            </div>
            <button
              onClick={closeDrillDown}
              className="text-gray-400 hover:text-white text-lg"
            >
              ✕
            </button>
          </div>

          <div className="text-red-400 text-xs font-bold mb-2 uppercase tracking-wider">
            Systems in Region
          </div>

          <div className="flex-1 overflow-y-auto min-h-0">
            {loadingSystems ? (
              <div className="text-gray-500 text-center py-4 animate-pulse">
                Loading systems...
              </div>
            ) : regionSystems.length === 0 ? (
              <div className="text-gray-500 text-center py-4">
                No systems found in this region
              </div>
            ) : (
              <div className="space-y-2">
                {regionSystems.map((system, i) => (
                  <button
                    key={system.id || i}
                    onClick={() => onSystemSelect?.(system)}
                    className="w-full text-left p-2 bg-gray-900/50 hover:bg-red-500/20 border border-gray-700/50 hover:border-red-500/50 rounded transition-colors group"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-white text-sm font-medium truncate group-hover:text-red-300">
                        {system.system_name || system.name || 'Unknown System'}
                      </span>
                      {system.discord_tag && (
                        <span
                          className="text-xs px-1.5 py-0.5 rounded ml-2 flex-shrink-0"
                          style={{
                            backgroundColor: `${enrolledCivs.find(c => c.discord_tag === system.discord_tag)?.color || '#666'}30`,
                            color: enrolledCivs.find(c => c.discord_tag === system.discord_tag)?.color || '#666'
                          }}
                        >
                          {system.discord_tag}
                        </span>
                      )}
                    </div>
                    {system.glyph_code && (
                      <p className="text-gray-500 text-xs mt-0.5 font-mono">
                        {system.glyph_code}
                      </p>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {regionSystems.length > 0 && (
            <div className="text-gray-500 text-xs mt-2 pt-2 border-t border-gray-700">
              {regionSystems.length} system{regionSystems.length !== 1 ? 's' : ''} • Click to select for war declaration
            </div>
          )}
        </div>
      )}

      {/* Hover tooltip */}
      {hoveredRegion && !selectedRegion && (
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 bg-black/90 border border-gray-700 rounded px-3 py-2 text-sm pointer-events-none">
          <span className="text-white">
            {hoveredRegion.region_name || `Region (${hoveredRegion.region_x}, ${hoveredRegion.region_y}, ${hoveredRegion.region_z})`}
          </span>
          {(hoveredRegion.controlling_civ || hoveredRegion.ownership?.owner) && (
            <span
              className="ml-2"
              style={{ color: hoveredRegion.controlling_civ?.color || hoveredRegion.ownership?.owner?.color }}
            >
              {hoveredRegion.controlling_civ?.display_name || hoveredRegion.ownership?.owner?.display_name}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
