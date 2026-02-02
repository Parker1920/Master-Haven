import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import Button from '../components/Button'
import DiscoverySubmitModal from '../components/DiscoverySubmitModal'
import { TypeCard, DiscoveryCard, DiscoveryDetailModal } from '../components/discoveries'

/**
 * Discoveries Landing Page
 *
 * Shows:
 * - Total discovery stats
 * - Grid of 12 type cards linking to type-specific pages
 * - Recent discoveries section
 * - Quick search bar
 * - Submit discovery button
 */

// Discovery type order for the grid
const TYPE_ORDER = [
  'fauna', 'flora', 'mineral', 'ancient',
  'history', 'bones', 'alien', 'starship',
  'multitool', 'lore', 'base', 'other'
]

export default function Discoveries() {
  const [stats, setStats] = useState(null)
  const [recentDiscoveries, setRecentDiscoveries] = useState([])
  const [loading, setLoading] = useState(true)
  const [showSubmitModal, setShowSubmitModal] = useState(false)
  const [selectedDiscovery, setSelectedDiscovery] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Fetch stats and recent discoveries
  useEffect(() => {
    async function fetchData() {
      try {
        const [statsRes, recentRes] = await Promise.all([
          fetch('/api/discoveries/stats'),
          fetch('/api/discoveries/recent?limit=6')
        ])

        if (statsRes.ok) {
          const statsData = await statsRes.json()
          setStats(statsData)
        }

        if (recentRes.ok) {
          const recentData = await recentRes.json()
          setRecentDiscoveries(recentData.discoveries || [])
        }
      } catch (err) {
        console.error('Error fetching discovery data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // Handle search (navigate to search results)
  function handleSearch(e) {
    e.preventDefault()
    if (searchQuery.trim()) {
      // Navigate to a search view - for now just show in other type
      window.location.href = `/discoveries/other?q=${encodeURIComponent(searchQuery.trim())}`
    }
  }

  // Handle feature toggle
  function handleFeatureToggle(discoveryId, isFeatured) {
    setRecentDiscoveries(prev =>
      prev.map(d => d.id === discoveryId ? { ...d, is_featured: isFeatured } : d)
    )
    if (selectedDiscovery?.id === discoveryId) {
      setSelectedDiscovery(prev => ({ ...prev, is_featured: isFeatured }))
    }
  }

  // Refresh data after submission
  function handleSubmitSuccess() {
    setShowSubmitModal(false)
    // Refresh stats and recent
    fetch('/api/discoveries/stats')
      .then(r => r.json())
      .then(data => setStats(data))
      .catch(() => {})
    fetch('/api/discoveries/recent?limit=6')
      .then(r => r.json())
      .then(data => setRecentDiscoveries(data.discoveries || []))
      .catch(() => {})
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-400">Loading discoveries...</div>
      </div>
    )
  }

  const typeInfo = stats?.type_info || {}
  const byType = stats?.by_type || {}

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Discoveries</h1>
          {stats && (
            <p className="mt-1 text-gray-400">
              {stats.total.toLocaleString()} discoveries across 12 types
              {stats.this_week > 0 && (
                <span className="ml-2 text-cyan-400">
                  (+{stats.this_week} this week)
                </span>
              )}
            </p>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Quick search */}
          <form onSubmit={handleSearch} className="hidden sm:flex items-center">
            <div className="relative">
              <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search all..."
                className="pl-10 pr-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none w-48"
              />
            </div>
          </form>

          <Button onClick={() => setShowSubmitModal(true)}>
            Submit Discovery
          </Button>
        </div>
      </div>

      {/* Type Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mb-10">
        {TYPE_ORDER.map(slug => {
          const info = typeInfo[slug] || { emoji: '?', label: slug }
          const count = byType[slug] || 0

          return (
            <TypeCard
              key={slug}
              slug={slug}
              emoji={info.emoji}
              label={info.label}
              count={count}
            />
          )
        })}
      </div>

      {/* Recent Discoveries Section */}
      {recentDiscoveries.length > 0 && (
        <div className="mt-10">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-white">Recent Discoveries</h2>
            <Link
              to="/discoveries/other"
              className="text-cyan-400 hover:text-cyan-300 text-sm"
            >
              View all
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {recentDiscoveries.map(discovery => (
              <DiscoveryCard
                key={discovery.id}
                discovery={discovery}
                onClick={() => setSelectedDiscovery(discovery)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Submit Modal */}
      <DiscoverySubmitModal
        isOpen={showSubmitModal}
        onClose={() => setShowSubmitModal(false)}
        onSuccess={handleSubmitSuccess}
      />

      {/* Detail Modal */}
      <DiscoveryDetailModal
        discovery={selectedDiscovery}
        isOpen={!!selectedDiscovery}
        onClose={() => setSelectedDiscovery(null)}
        onFeatureToggle={handleFeatureToggle}
      />
    </div>
  )
}
