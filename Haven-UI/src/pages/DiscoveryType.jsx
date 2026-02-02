import React, { useEffect, useState, useMemo } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'
import Button from '../components/Button'
import DiscoverySubmitModal from '../components/DiscoverySubmitModal'
import { DiscoveryCard, DiscoveryFilters, DiscoveryDetailModal } from '../components/discoveries'

/**
 * DiscoveryType - Type-specific discovery showcase page
 *
 * Shows all discoveries of a specific type (fauna, starship, etc.)
 * with filtering, sorting, and pagination.
 */

// Type metadata for display
const TYPE_INFO = {
  fauna: { emoji: '🦗', label: 'Fauna', description: 'Creatures and wildlife' },
  flora: { emoji: '🌿', label: 'Flora', description: 'Plants and vegetation' },
  mineral: { emoji: '💎', label: 'Mineral', description: 'Minerals and resources' },
  ancient: { emoji: '🏛️', label: 'Ancient', description: 'Ancient structures and ruins' },
  history: { emoji: '📜', label: 'History', description: 'Historical findings' },
  bones: { emoji: '🦴', label: 'Bones', description: 'Skeletal remains and fossils' },
  alien: { emoji: '👽', label: 'Alien', description: 'Alien encounters' },
  starship: { emoji: '🚀', label: 'Starship', description: 'Ships and spacecraft' },
  multitool: { emoji: '⚙️', label: 'Multi-tool', description: 'Multi-tools and gear' },
  lore: { emoji: '📖', label: 'Lore', description: 'Stories and knowledge' },
  base: { emoji: '🏠', label: 'Custom Base', description: 'Player-built bases' },
  other: { emoji: '🆕', label: 'Other', description: 'Miscellaneous discoveries' },
}

// Custom hook for debouncing
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => clearTimeout(handler)
  }, [value, delay])

  return debouncedValue
}

export default function DiscoveryType() {
  const { type } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()

  // State
  const [discoveries, setDiscoveries] = useState([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [loading, setLoading] = useState(true)
  const [showSubmitModal, setShowSubmitModal] = useState(false)
  const [selectedDiscovery, setSelectedDiscovery] = useState(null)

  // Filter state from URL params
  const [searchQuery, setSearchQuery] = useState(searchParams.get('q') || '')
  const [sortBy, setSortBy] = useState(searchParams.get('sort') || 'newest')
  const [page, setPage] = useState(parseInt(searchParams.get('page') || '0', 10))

  // Debounced search
  const debouncedSearch = useDebounce(searchQuery, 300)

  // Type info
  const typeInfo = TYPE_INFO[type] || TYPE_INFO.other
  const isValidType = type in TYPE_INFO

  // Update URL params when filters change
  useEffect(() => {
    const params = new URLSearchParams()
    if (searchQuery) params.set('q', searchQuery)
    if (sortBy !== 'newest') params.set('sort', sortBy)
    if (page > 0) params.set('page', page.toString())
    setSearchParams(params, { replace: true })
  }, [searchQuery, sortBy, page, setSearchParams])

  // Fetch discoveries
  useEffect(() => {
    async function fetchDiscoveries() {
      setLoading(true)
      try {
        const params = new URLSearchParams()
        if (isValidType) params.set('type', type)
        if (debouncedSearch) params.set('q', debouncedSearch)
        if (sortBy) params.set('sort', sortBy)
        params.set('page', page.toString())
        params.set('limit', '24')

        const res = await fetch(`/api/discoveries/browse?${params}`)
        if (res.ok) {
          const data = await res.json()
          setDiscoveries(data.discoveries || [])
          setTotal(data.total || 0)
          setPages(data.pages || 0)
        }
      } catch (err) {
        console.error('Error fetching discoveries:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchDiscoveries()
  }, [type, debouncedSearch, sortBy, page, isValidType])

  // Handle feature toggle
  function handleFeatureToggle(discoveryId, isFeatured) {
    setDiscoveries(prev =>
      prev.map(d => d.id === discoveryId ? { ...d, is_featured: isFeatured } : d)
    )
    if (selectedDiscovery?.id === discoveryId) {
      setSelectedDiscovery(prev => ({ ...prev, is_featured: isFeatured }))
    }
  }

  // Refresh data after submission
  function handleSubmitSuccess() {
    setShowSubmitModal(false)
    // Re-fetch with current filters
    setPage(0)
  }

  // Pagination helpers
  const pageNumbers = useMemo(() => {
    const nums = []
    const maxVisible = 5
    let start = Math.max(0, page - Math.floor(maxVisible / 2))
    let end = Math.min(pages, start + maxVisible)

    if (end - start < maxVisible) {
      start = Math.max(0, end - maxVisible)
    }

    for (let i = start; i < end; i++) {
      nums.push(i)
    }
    return nums
  }, [page, pages])

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        {/* Back button */}
        <Link
          to="/discoveries"
          className="inline-flex items-center gap-2 text-gray-400 hover:text-white mb-4 transition-colors"
        >
          <ArrowLeftIcon className="w-4 h-4" />
          Back to Discoveries
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-4xl">{typeInfo.emoji}</span>
            <div>
              <h1 className="text-3xl font-bold text-white">{typeInfo.label}</h1>
              <p className="text-gray-400">{typeInfo.description}</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-gray-400">
              {total.toLocaleString()} {total === 1 ? 'discovery' : 'discoveries'}
            </span>
            <Button onClick={() => setShowSubmitModal(true)}>
              Submit Discovery
            </Button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <DiscoveryFilters
        searchQuery={searchQuery}
        onSearchChange={(q) => { setSearchQuery(q); setPage(0) }}
        sortBy={sortBy}
        onSortChange={(s) => { setSortBy(s); setPage(0) }}
        className="mb-6"
      />

      {/* Loading state */}
      {loading ? (
        <div className="flex items-center justify-center min-h-64">
          <div className="text-lg text-gray-400">Loading {typeInfo.label.toLowerCase()}...</div>
        </div>
      ) : discoveries.length === 0 ? (
        /* Empty state */
        <div className="flex flex-col items-center justify-center min-h-64 text-center">
          <span className="text-6xl mb-4 opacity-30">{typeInfo.emoji}</span>
          <h3 className="text-xl font-semibold text-white mb-2">No {typeInfo.label.toLowerCase()} found</h3>
          <p className="text-gray-400 mb-4">
            {searchQuery
              ? `No results matching "${searchQuery}"`
              : `Be the first to submit a ${typeInfo.label.toLowerCase()} discovery!`
            }
          </p>
          <Button onClick={() => setShowSubmitModal(true)}>
            Submit Discovery
          </Button>
        </div>
      ) : (
        <>
          {/* Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {discoveries.map(discovery => (
              <DiscoveryCard
                key={discovery.id}
                discovery={discovery}
                onClick={() => setSelectedDiscovery(discovery)}
              />
            ))}
          </div>

          {/* Pagination */}
          {pages > 1 && (
            <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
              <button
                onClick={() => setPage(0)}
                disabled={page === 0}
                className="px-3 py-2 rounded-lg bg-gray-800 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                First
              </button>
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-2 rounded-lg bg-gray-800 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Prev
              </button>

              {pageNumbers.map(p => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`
                    px-3 py-2 rounded-lg transition-colors
                    ${p === page
                      ? 'bg-cyan-600 text-white'
                      : 'bg-gray-800 text-gray-400 hover:text-white'
                    }
                  `}
                >
                  {p + 1}
                </button>
              ))}

              <button
                onClick={() => setPage(p => Math.min(pages - 1, p + 1))}
                disabled={page >= pages - 1}
                className="px-3 py-2 rounded-lg bg-gray-800 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
              <button
                onClick={() => setPage(pages - 1)}
                disabled={page >= pages - 1}
                className="px-3 py-2 rounded-lg bg-gray-800 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Last
              </button>
            </div>
          )}

          {/* Page info */}
          {pages > 1 && (
            <div className="mt-4 text-center text-gray-500 text-sm">
              Page {page + 1} of {pages} ({total.toLocaleString()} total)
            </div>
          )}
        </>
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
