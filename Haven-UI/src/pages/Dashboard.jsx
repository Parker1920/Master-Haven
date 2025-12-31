import React, { useEffect, useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import AnimatedCounter from '../components/AnimatedCounter'
import { useInactivityAware } from '../hooks/useInactivityAware'
import {
  GlobeAltIcon,
  PlusIcon,
  ChartBarIcon,
  MagnifyingGlassIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline'

// Event type icons and colors for activity logs
const EVENT_CONFIG = {
  system_submitted: { icon: '📤', color: '#00C2B3', label: 'Submitted' },
  system_approved: { icon: '✅', color: '#4ade80', label: 'Approved' },
  system_rejected: { icon: '❌', color: '#ef4444', label: 'Rejected' },
  system_saved: { icon: '💾', color: '#00C2B3', label: 'Saved' },
  system_deleted: { icon: '🗑️', color: '#ef4444', label: 'Deleted' },
  system_edited: { icon: '✏️', color: '#f0ad4e', label: 'Edited' },
  region_submitted: { icon: '🗺️', color: '#9d4edd', label: 'Region' },
  region_approved: { icon: '✅', color: '#4ade80', label: 'Region' },
  region_rejected: { icon: '❌', color: '#ef4444', label: 'Region' },
  discovery_added: { icon: '🔭', color: '#9d4edd', label: 'Discovery' },
  map_generated: { icon: '🌌', color: '#00C2B3', label: 'Map' },
  watcher_upload: { icon: '👁️', color: '#f0ad4e', label: 'Watcher' },
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [dbStats, setDbStats] = useState(null)
  const [recent, setRecent] = useState([])
  const [pending, setPending] = useState({ systems: 0, regions: 0 })
  const [regions, setRegions] = useState([])
  const [isOnline, setIsOnline] = useState(true)
  const [activityLogs, setActivityLogs] = useState([])
  const [logsPaused, setLogsPaused] = useState(false)
  const logsRef = useRef(null)
  const pollIntervalRef = useRef(null)
  const { isDisconnected, registerConnection, unregisterConnection } = useInactivityAware()

  useEffect(() => {
    // Fetch all stats - OPTIMIZED: use lightweight endpoints, no full data loading
    const fetchData = async () => {
      try {
        // Use optimized endpoints that don't load all data:
        // - /api/stats: uses direct COUNT queries (fast)
        // - /api/db_stats: uses COUNT queries for all tables (fast)
        // - /api/regions/grouped?include_systems=false&limit=5: just region summaries (fast)
        // - /api/systems/recent?limit=10: only recent systems (new fast endpoint)
        const [statsRes, dbStatsRes, regionsRes, recentRes] = await Promise.all([
          axios.get('/api/stats').catch(() => ({ data: null })),
          axios.get('/api/db_stats').catch(() => ({ data: { stats: {} } })),
          axios.get('/api/regions/grouped?include_systems=false&limit=5').catch(() => ({ data: { regions: [] } })),
          axios.get('/api/systems/recent?limit=10').catch(() => ({ data: { systems: [] } }))
        ])

        setStats(statsRes.data)
        setDbStats(dbStatsRes.data?.stats || {})

        // Recent systems from the optimized endpoint
        setRecent(recentRes.data?.systems || [])

        // Get top 5 regions with proper names (already limited in API call)
        const allRegions = regionsRes.data?.regions || []
        const topRegions = allRegions.map(r => ({
          name: r.display_name || r.custom_name || `Region (${r.region_x}, ${r.region_y}, ${r.region_z})`,
          count: r.system_count || 0,
          hasCustomName: !!r.custom_name
        }))
        setRegions(topRegions)

        setIsOnline(true)
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err)
        setIsOnline(false)
      }
    }

    fetchData()

    // Fetch pending approvals
    axios.get('/api/pending-approvals').then(r => {
      const data = r.data || {}
      setPending({
        systems: (data.systems || []).length,
        regions: (data.regions || []).length
      })
    }).catch(() => {})

    // Fetch activity logs
    const fetchActivityLogs = async () => {
      try {
        const res = await axios.get('/api/activity_logs?limit=50')
        setActivityLogs(res.data?.logs || [])
        setIsOnline(true)
      } catch (err) {
        console.error('Failed to fetch activity logs:', err)
      }
    }

    // Don't start polling if disconnected due to inactivity
    if (isDisconnected) return

    fetchActivityLogs()

    // Start polling function
    const startPolling = () => {
      pollIntervalRef.current = setInterval(() => {
        if (!logsPaused) {
          fetchActivityLogs()
        }
      }, 5000)
    }

    startPolling()

    // Register with inactivity system
    registerConnection('dashboard-activity-polling', {
      cleanup: () => {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
          pollIntervalRef.current = null
        }
      },
      restore: () => {
        fetchActivityLogs()
        startPolling()
      }
    })

    return () => {
      unregisterConnection('dashboard-activity-polling')
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [logsPaused, isDisconnected, registerConnection, unregisterConnection])

  useEffect(() => {
    if (!logsPaused && logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight
    }
  }, [activityLogs, logsPaused])

  const totalSystems = stats?.total || dbStats?.systems || 0
  const totalPlanets = dbStats?.planets || 0
  const totalMoons = dbStats?.moons || 0
  const totalRegions = dbStats?.regions || stats?.regions?.length || 0
  const totalDiscoveries = dbStats?.discoveries || 0

  const formatTime = (timestamp) => {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
    const now = new Date()
    const diff = Math.floor((now - date) / 1000)
    if (diff < 60) return 'now'
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
  }

  return (
    <div className="space-y-6">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-2xl" style={{
        background: 'linear-gradient(135deg, rgba(20, 27, 61, 0.95) 0%, rgba(10, 14, 39, 0.98) 100%)',
        border: '1px solid rgba(0, 194, 179, 0.2)',
        boxShadow: '0 0 60px rgba(0, 194, 179, 0.1), inset 0 1px 0 rgba(255,255,255,0.05)'
      }}>
        {/* Background glow effect */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-1/2 -left-1/4 w-1/2 h-full rounded-full opacity-20"
               style={{ background: 'radial-gradient(circle, rgba(0, 194, 179, 0.4) 0%, transparent 70%)' }} />
          <div className="absolute -bottom-1/2 -right-1/4 w-1/2 h-full rounded-full opacity-15"
               style={{ background: 'radial-gradient(circle, rgba(157, 78, 221, 0.4) 0%, transparent 70%)' }} />
        </div>

        <div className="relative p-6 lg:p-8">
          {/* Header row */}
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl lg:text-3xl font-bold tracking-tight" style={{ color: 'var(--app-text)' }}>
              Haven Control Room
            </h1>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium"
                 style={{
                   background: isOnline ? 'rgba(0, 194, 179, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                   color: isOnline ? '#00C2B3' : '#ef4444'
                 }}>
              <span className="relative flex h-2 w-2">
                <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${isOnline ? 'animate-ping' : ''}`}
                      style={{ background: isOnline ? '#00C2B3' : '#ef4444' }} />
                <span className="relative inline-flex rounded-full h-2 w-2"
                      style={{ background: isOnline ? '#00C2B3' : '#ef4444' }} />
              </span>
              {isOnline ? 'Systems Online' : 'Connection Lost'}
            </div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 lg:gap-6 mb-8">
            {[
              { icon: '⭐', label: 'Systems', value: totalSystems, change: '+12' },
              { icon: '🪐', label: 'Planets', value: totalPlanets, change: '+45' },
              { icon: '🌙', label: 'Moons', value: totalMoons, change: '+18' },
              { icon: '🗺️', label: 'Regions', value: totalRegions, change: '+3' },
              { icon: '🔭', label: 'Discoveries', value: totalDiscoveries, change: '+24' },
            ].map((stat, i) => (
              <div key={i} className="text-center p-4 rounded-xl transition-all duration-300 hover:scale-105"
                   style={{
                     background: 'rgba(255, 255, 255, 0.03)',
                     border: '1px solid rgba(255, 255, 255, 0.06)'
                   }}>
                <div className="text-2xl mb-1">{stat.icon}</div>
                <div className="text-2xl lg:text-3xl font-bold" style={{ color: '#00C2B3' }}>
                  <AnimatedCounter value={stat.value} duration={1200} />
                </div>
                <div className="text-xs uppercase tracking-wider mt-1" style={{ color: 'var(--muted)' }}>
                  {stat.label}
                </div>
                <div className="text-xs mt-1" style={{ color: '#4ade80' }}>
                  ▲ {stat.change}
                </div>
              </div>
            ))}
          </div>

          {/* CTA Button */}
          <div className="flex flex-wrap gap-3 justify-center">
            <Link to="/wizard"
               className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white transition-all duration-300 hover:scale-105"
               style={{
                 background: 'linear-gradient(135deg, #00C2B3 0%, #00a89a 100%)',
                 boxShadow: '0 4px 20px rgba(0, 194, 179, 0.4)'
               }}>
              <PlusIcon className="w-5 h-5" />
              Add New System
            </Link>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Mini Map Preview */}
        <div className="lg:col-span-2 rounded-xl overflow-hidden" style={{
          background: 'var(--app-card)',
          border: '1px solid rgba(255, 255, 255, 0.06)'
        }}>
          <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
            <h2 className="font-semibold flex items-center gap-2" style={{ color: '#00C2B3' }}>
              <GlobeAltIcon className="w-5 h-5" />
              Galaxy Overview
            </h2>
            <a href="/map/latest" target="_blank" rel="noreferrer"
               className="text-sm hover:underline" style={{ color: 'var(--muted)' }}>
              Open Full Map →
            </a>
          </div>
          <div className="relative" style={{ height: '320px' }}>
            <iframe
              src="/map/latest?embed=true&hideUI=true"
              className="w-full h-full border-0"
              title="Galaxy Map Preview"
              style={{ background: '#050810' }}
            />
            <div className="absolute inset-0 pointer-events-none"
                 style={{
                   background: 'linear-gradient(to bottom, transparent 80%, var(--app-card) 100%)',
                   borderRadius: '0 0 12px 12px'
                 }} />
            <a href="/map/latest" target="_blank" rel="noreferrer"
               className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity duration-300 cursor-pointer"
               style={{ background: 'rgba(0, 0, 0, 0.5)' }}>
              <span className="px-6 py-3 rounded-xl font-semibold text-white"
                    style={{ background: 'rgba(0, 194, 179, 0.9)' }}>
                Click to Open Full Map
              </span>
            </a>
          </div>
        </div>

        {/* Pending Approvals */}
        <div className="rounded-xl p-5" style={{
          background: 'var(--app-card)',
          border: '1px solid rgba(255, 255, 255, 0.06)'
        }}>
          <h2 className="font-semibold mb-4 flex items-center gap-2" style={{ color: '#f0ad4e' }}>
            <ExclamationCircleIcon className="w-5 h-5" />
            Pending Review
          </h2>

          {pending.systems + pending.regions > 0 ? (
            <div className="space-y-3">
              {pending.systems > 0 && (
                <div className="flex items-center justify-between p-3 rounded-lg"
                     style={{ background: 'rgba(240, 173, 78, 0.1)', border: '1px solid rgba(240, 173, 78, 0.2)' }}>
                  <span className="text-sm">Systems awaiting approval</span>
                  <span className="px-2 py-1 rounded-full text-xs font-bold"
                        style={{ background: 'rgba(240, 173, 78, 0.2)', color: '#f0ad4e' }}>
                    {pending.systems}
                  </span>
                </div>
              )}
              {pending.regions > 0 && (
                <div className="flex items-center justify-between p-3 rounded-lg"
                     style={{ background: 'rgba(240, 173, 78, 0.1)', border: '1px solid rgba(240, 173, 78, 0.2)' }}>
                  <span className="text-sm">Region names pending</span>
                  <span className="px-2 py-1 rounded-full text-xs font-bold"
                        style={{ background: 'rgba(240, 173, 78, 0.2)', color: '#f0ad4e' }}>
                    {pending.regions}
                  </span>
                </div>
              )}
              <Link to="/pending-approvals"
                 className="block w-full text-center py-2 rounded-lg text-sm font-medium transition-colors"
                 style={{ background: 'rgba(240, 173, 78, 0.15)', color: '#f0ad4e' }}>
                Review All →
              </Link>
            </div>
          ) : (
            <div className="text-center py-8">
              <CheckCircleIcon className="w-12 h-12 mx-auto mb-2" style={{ color: '#4ade80' }} />
              <p className="text-sm" style={{ color: 'var(--muted)' }}>All caught up!</p>
              <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>No pending approvals</p>
            </div>
          )}

          {/* Quick Stats */}
          <div className="mt-6 pt-4 border-t" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
            <h3 className="text-xs uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
              Quick Actions
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <Link to="/systems" className="flex items-center gap-2 p-2 rounded-lg text-xs transition-colors hover:bg-white/5">
                <ChartBarIcon className="w-4 h-4" style={{ color: '#00C2B3' }} />
                <span>Systems</span>
              </Link>
              <Link to="/discoveries" className="flex items-center gap-2 p-2 rounded-lg text-xs transition-colors hover:bg-white/5">
                <MagnifyingGlassIcon className="w-4 h-4" style={{ color: '#9d4edd' }} />
                <span>Discoveries</span>
              </Link>
              <Link to="/db_stats" className="flex items-center gap-2 p-2 rounded-lg text-xs transition-colors hover:bg-white/5">
                <ChartBarIcon className="w-4 h-4" style={{ color: '#00C2B3' }} />
                <span>DB Stats</span>
              </Link>
              <button onClick={() => fetch('/api/generate_map', { method: 'POST' })}
                      className="flex items-center gap-2 p-2 rounded-lg text-xs transition-colors hover:bg-white/5 text-left">
                <GlobeAltIcon className="w-4 h-4" style={{ color: '#9d4edd' }} />
                <span>Regen Map</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Top Regions */}
        <div className="rounded-xl p-5" style={{
          background: 'var(--app-card)',
          border: '1px solid rgba(255, 255, 255, 0.06)'
        }}>
          <h2 className="font-semibold mb-4 flex items-center gap-2" style={{ color: '#00C2B3' }}>
            🌍 Top Regions
          </h2>
          <div className="space-y-2">
            {regions.length > 0 ? regions.map((region, i) => (
              <div key={i} className="flex items-center justify-between p-2 rounded-lg"
                   style={{ background: 'rgba(255, 255, 255, 0.02)' }}>
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 flex items-center justify-center rounded text-xs font-bold"
                        style={{
                          background: i === 0 ? 'rgba(255, 215, 0, 0.2)' :
                                     i === 1 ? 'rgba(192, 192, 192, 0.2)' :
                                     i === 2 ? 'rgba(205, 127, 50, 0.2)' : 'rgba(255,255,255,0.05)',
                          color: i === 0 ? '#ffd700' : i === 1 ? '#c0c0c0' : i === 2 ? '#cd7f32' : 'var(--muted)'
                        }}>
                    {i + 1}
                  </span>
                  <span className="text-sm truncate max-w-[140px]" style={{ color: region.hasCustomName ? '#9d4edd' : 'var(--muted)' }}>
                    {region.name}
                  </span>
                </div>
                <span className="text-xs px-2 py-1 rounded" style={{ background: 'rgba(0, 194, 179, 0.1)', color: '#00C2B3' }}>
                  {region.count} sys
                </span>
              </div>
            )) : (
              <p className="text-sm text-center py-4" style={{ color: 'var(--muted)' }}>No regions yet</p>
            )}
          </div>
        </div>

        {/* Live Activity Feed */}
        <div className="rounded-xl p-5" style={{
          background: 'var(--app-card)',
          border: '1px solid rgba(255, 255, 255, 0.06)'
        }}>
          <h2 className="font-semibold mb-4 flex items-center gap-2" style={{ color: '#9d4edd' }}>
            <ClockIcon className="w-5 h-5" />
            Recent Activity
          </h2>
          <div className="space-y-2">
            {recent.length > 0 ? recent.slice(0, 6).map((system, i) => (
              <div key={system.id || i} className="flex items-start gap-2 p-2 rounded-lg"
                   style={{ background: 'rgba(255, 255, 255, 0.02)' }}>
                <span className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: '#00C2B3' }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate">{system.name}</p>
                  <p className="text-xs" style={{ color: 'var(--muted)' }}>
                    {system.galaxy || 'Euclid'} • {system.planets?.length || 0} planets
                  </p>
                </div>
              </div>
            )) : (
              <p className="text-sm text-center py-4" style={{ color: 'var(--muted)' }}>No recent activity</p>
            )}
          </div>
          <Link to="/systems" className="block text-center text-sm mt-3 pt-3 border-t"
             style={{ borderColor: 'rgba(255,255,255,0.06)', color: 'var(--muted)' }}>
            View All Systems →
          </Link>
        </div>

        {/* Activity Log */}
        <div className="rounded-xl overflow-hidden flex flex-col self-start" style={{
          background: 'var(--app-card)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          height: '290px'
        }}>
          <div className="flex items-center justify-between p-4 border-b flex-shrink-0" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
            <h2 className="font-semibold text-sm flex items-center gap-2">
              📋 Activity Log
              {!logsPaused && <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: '#4ade80' }} />}
            </h2>
            <div className="flex gap-2">
              <button onClick={() => setLogsPaused(!logsPaused)}
                      className="px-2 py-1 rounded text-xs transition-colors"
                      style={{
                        background: logsPaused ? 'rgba(239, 68, 68, 0.2)' : 'rgba(255,255,255,0.05)',
                        color: logsPaused ? '#ef4444' : 'var(--app-text)'
                      }}>
                {logsPaused ? '⏸ Paused' : '▶ Live'}
              </button>
            </div>
          </div>
          <div ref={logsRef} className="p-3 overflow-y-auto text-xs flex-1" style={{ background: 'rgba(0,0,0,0.2)' }}>
            {activityLogs.length > 0 ? [...activityLogs].reverse().map((log) => {
              const config = EVENT_CONFIG[log.event_type] || { icon: '📝', color: 'var(--muted)', label: 'Event' }
              return (
                <div key={log.id} className="py-1.5 flex items-start gap-2 border-b border-white/5 last:border-0">
                  <span className="flex-shrink-0">{config.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="truncate" style={{ color: config.color }}>{log.message}</p>
                    <div className="flex items-center gap-2 mt-0.5" style={{ color: 'var(--muted)' }}>
                      <span>{formatTime(log.timestamp)}</span>
                      {log.user_name && <span>• {log.user_name}</span>}
                    </div>
                  </div>
                </div>
              )
            }) : (
              <div className="flex flex-col items-center justify-center h-full" style={{ color: 'var(--muted)' }}>
                <span className="text-2xl mb-2">📋</span>
                <p>No activity yet...</p>
                <p className="text-xs mt-1">Activity will appear here as it happens</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
