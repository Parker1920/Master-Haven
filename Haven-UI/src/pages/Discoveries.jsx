import React, { useEffect, useState, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import Button from '../components/Button'
import DiscoverySubmitModal from '../components/DiscoverySubmitModal'
import { TypeCard, DiscoveryCard, DiscoveryDetailModal } from '../components/discoveries'

/**
 * Discoveries Landing Page — Route: /discoveries
 * Auth: Public (no login required). Submit button opens a modal that
 *       sends submissions to the pending approval queue.
 *
 * Shows a grid of 12 discovery type cards (linking to /discoveries/:type),
 * total stats with weekly delta, recent discoveries, and a search bar.
 *
 * API endpoints:
 *   GET /api/discoveries/stats      — total count + per-type breakdown
 *   GET /api/discoveries/recent     — latest 6 discoveries for the bottom section
 */

// Discovery type order for the grid
const TYPE_ORDER = [
  'fauna', 'flora', 'mineral', 'ancient',
  'history', 'bones', 'alien', 'starship',
  'multitool', 'lore', 'base', 'other'
]

export default function Discoveries() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [recentDiscoveries, setRecentDiscoveries] = useState([])
  const [loading, setLoading] = useState(true)
  const [showSubmitModal, setShowSubmitModal] = useState(false)
  const [selectedDiscovery, setSelectedDiscovery] = useState(null)
  const [editDiscovery, setEditDiscovery] = useState(null)
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

  // Handle search — navigate to the "all" sub-page with the query. Previously
  // this hard-routed to /discoveries/other (the wrong type, so the search
  // matched nothing for fauna/flora/etc names) AND used a full page reload.
  // Now uses SPA navigation. DiscoveryType handles 'all' as a no-type-filter
  // sentinel (renders 'All Discoveries').
  function handleSearch(e) {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/discoveries/all?q=${encodeURIComponent(searchQuery.trim())}`)
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

  // Open the submit modal in edit mode for an existing discovery
  function handleEditDiscovery(d) {
    setSelectedDiscovery(null)
    setEditDiscovery(d)
    setShowSubmitModal(true)
  }

  // Refresh data after submission
  function handleSubmitSuccess() {
    setShowSubmitModal(false)
    setEditDiscovery(null)
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
        <div className="text-lg" style={{ color: 'var(--muted)' }}>Loading discoveries...</div>
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
          <h1 className="text-3xl font-bold" style={{ color: 'var(--app-text)' }}>Discoveries</h1>
          {stats && (
            <p className="mt-1" style={{ color: 'var(--muted)' }}>
              {stats.total.toLocaleString()} discoveries across 12 types
              {stats.this_week > 0 && (
                <span className="ml-2" style={{ color: 'var(--app-primary)' }}>
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
              <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--muted)' }} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search all..."
                className="haven-input pl-10 pr-4 py-2 w-48"
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
            <h2 className="text-xl font-semibold" style={{ color: 'var(--app-text)' }}>Recent Discoveries</h2>
            <Link
              to="/discoveries/other"
              className="text-sm hover:underline"
              style={{ color: 'var(--app-primary)' }}
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

      {/* Submit / Edit Modal */}
      <DiscoverySubmitModal
        isOpen={showSubmitModal}
        editDiscovery={editDiscovery}
        onClose={() => { setShowSubmitModal(false); setEditDiscovery(null) }}
        onSuccess={handleSubmitSuccess}
      />

      {/* Detail Modal */}
      <DiscoveryDetailModal
        discovery={selectedDiscovery}
        isOpen={!!selectedDiscovery}
        onClose={() => setSelectedDiscovery(null)}
        onFeatureToggle={handleFeatureToggle}
        onEdit={handleEditDiscovery}
      />
    </div>
  )
}
