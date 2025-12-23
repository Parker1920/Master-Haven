import React, { useEffect, useState, useContext } from 'react'
import { AuthContext } from '../utils/AuthContext'

export default function DBStats() {
  const auth = useContext(AuthContext)
  const { isAdmin, isSuperAdmin, isPartner, user } = auth || {}
  const [stats, setStats] = useState(null)
  const [discordTag, setDiscordTag] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Use partner-filtered stats if partner, otherwise use full stats
    const endpoint = isPartner ? '/api/partner/stats' : '/api/db_stats'

    fetch(endpoint, { credentials: 'include' })
      .then(r => r.json())
      .then(j => {
        setStats(j.stats || null)
        setDiscordTag(j.discord_tag || null)
      })
      .catch(() => setStats(null))
      .finally(() => setLoading(false))
  }, [isPartner])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-400">Loading statistics...</div>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-2 text-cyan-400">
        {isPartner ? 'Your Statistics' : 'Database Statistics'}
      </h2>

      {isPartner && discordTag && (
        <div className="mb-4 p-3 bg-cyan-900/30 border border-cyan-700 rounded">
          <p className="text-cyan-300 text-sm">
            Showing statistics for systems tagged with <strong className="text-cyan-400">{discordTag}</strong>
          </p>
        </div>
      )}

      {stats ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {Object.entries(stats).map(([k, v]) => (
            <div key={k} className="p-4 bg-gray-800 rounded border border-gray-700">
              <div className="text-2xl font-bold text-white">{String(v)}</div>
              <div className="text-sm text-gray-400 capitalize">{k.replace(/_/g, ' ')}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-gray-400">No statistics available.</div>
      )}

      {isPartner && (
        <div className="mt-6 p-4 bg-gray-800/50 border border-gray-700 rounded">
          <h3 className="text-lg font-semibold text-gray-300 mb-2">About Your Statistics</h3>
          <ul className="text-sm text-gray-400 space-y-1 list-disc list-inside">
            <li>These statistics only include systems tagged with your Discord ({discordTag})</li>
            <li>Planets, moons, and space stations are counted from your tagged systems</li>
            <li>To increase these numbers, create more systems or have the super admin tag existing systems with your Discord</li>
          </ul>
        </div>
      )}
    </div>
  )
}
