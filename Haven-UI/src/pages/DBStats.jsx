import React, { useEffect, useState, useContext } from 'react'
import { AuthContext } from '../utils/AuthContext'

// Format stat labels for display
function formatLabel(key) {
  // Check for custom labels first
  if (customLabels[key]) return customLabels[key]
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

// Format large numbers with commas
function formatNumber(num) {
  return num.toLocaleString()
}

// Custom labels for specific stats
const customLabels = {
  'total_regions': 'Named Regions',
  'populated_regions': 'Populated Regions',
  'regions': 'Named Regions'
}

// Group stats into categories for super admin view
function categorizeStats(stats, userType) {
  if (userType === 'super_admin') {
    return {
      'Core Data': ['total_systems', 'total_planets', 'total_moons', 'populated_regions', 'total_regions', 'total_space_stations', 'total_planet_pois', 'total_discoveries', 'unique_galaxies'],
      'Administration': ['partner_accounts', 'sub_admin_accounts', 'api_keys', 'active_communities'],
      'Pending Approvals': ['pending_systems', 'pending_region_names', 'pending_edit_requests'],
      'Audit & Activity': ['approval_audit_entries', 'activity_log_entries', 'data_restrictions']
    }
  }
  return null
}

export default function DBStats() {
  const auth = useContext(AuthContext)
  const { isSuperAdmin, isPartner, isSubAdmin, user } = auth || {}
  const [stats, setStats] = useState(null)
  const [discordTag, setDiscordTag] = useState(null)
  const [userType, setUserType] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // All users use the same endpoint - backend filters by permission
    fetch('/api/db_stats', { credentials: 'include' })
      .then(r => r.json())
      .then(j => {
        setStats(j.stats || null)
        setDiscordTag(j.discord_tag || null)
        setUserType(j.user_type || 'public')
      })
      .catch(() => setStats(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-400">Loading statistics...</div>
      </div>
    )
  }

  const categories = categorizeStats(stats, userType)
  const isPartnerOrSubAdmin = userType === 'partner' || userType === 'sub_admin'

  // Get title based on user type
  const getTitle = () => {
    if (userType === 'super_admin') return 'Admin Dashboard'
    if (isPartnerOrSubAdmin && discordTag) return `${discordTag} Statistics`
    return 'Database Statistics'
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-2 text-cyan-400">
        {getTitle()}
      </h2>

      {/* Partner/Sub-admin info banner */}
      {isPartnerOrSubAdmin && discordTag && (
        <div className="mb-4 p-3 bg-cyan-900/30 border border-cyan-700 rounded">
          <p className="text-cyan-300 text-sm">
            Showing statistics for your community: <strong className="text-cyan-400">{discordTag}</strong>
          </p>
        </div>
      )}

      {/* Public user info */}
      {userType === 'public' && (
        <div className="mb-4 p-3 bg-gray-800/50 border border-gray-600 rounded">
          <p className="text-gray-400 text-sm">
            Showing global database statistics. Log in to see community-specific stats.
          </p>
        </div>
      )}

      {stats ? (
        <>
          {/* Super Admin: Categorized view */}
          {userType === 'super_admin' && categories ? (
            <div className="space-y-6">
              {Object.entries(categories).map(([category, keys]) => {
                const categoryStats = keys.filter(k => stats[k] !== undefined)
                if (categoryStats.length === 0) return null

                return (
                  <div key={category}>
                    <h3 className="text-lg font-semibold text-gray-300 mb-3 border-b border-gray-700 pb-2">
                      {category}
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                      {categoryStats.map(k => (
                        <div key={k} className="p-4 bg-gray-800 rounded border border-gray-700 hover:border-cyan-600 transition-colors">
                          <div className="text-2xl font-bold text-white">{formatNumber(stats[k])}</div>
                          <div className="text-sm text-gray-400">{formatLabel(k)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            /* Partner/Sub-admin/Public: Simple grid */
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {Object.entries(stats).map(([k, v]) => (
                <div key={k} className="p-4 bg-gray-800 rounded border border-gray-700 hover:border-cyan-600 transition-colors">
                  <div className="text-2xl font-bold text-white">{formatNumber(v)}</div>
                  <div className="text-sm text-gray-400">{formatLabel(k)}</div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="text-gray-400">No statistics available.</div>
      )}

      {/* Partner/Sub-admin info footer */}
      {isPartnerOrSubAdmin && discordTag && (
        <div className="mt-6 p-4 bg-gray-800/50 border border-gray-700 rounded">
          <h3 className="text-lg font-semibold text-gray-300 mb-2">About Your Statistics</h3>
          <ul className="text-sm text-gray-400 space-y-1 list-disc list-inside">
            <li>These statistics only include systems tagged with {discordTag}</li>
            <li>Planets, moons, and POIs are counted from your community's systems</li>
            <li>Create more systems or request the admin to tag existing systems with your community tag</li>
          </ul>
        </div>
      )}
    </div>
  )
}
