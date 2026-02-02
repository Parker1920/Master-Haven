import React, { useState } from 'react'
import { MagnifyingGlassIcon, FunnelIcon, XMarkIcon } from '@heroicons/react/24/outline'

/**
 * DiscoveryFilters - Search and sort controls for discovery browsing
 *
 * Features:
 * - Search input with debounce
 * - Sort dropdown (newest, oldest, name, views)
 * - Mobile-responsive collapsible panel
 */

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'name', label: 'Name A-Z' },
  { value: 'views', label: 'Most Viewed' },
]

export default function DiscoveryFilters({
  searchQuery,
  onSearchChange,
  sortBy,
  onSortChange,
  className = ''
}) {
  const [showMobileFilters, setShowMobileFilters] = useState(false)

  const hasActiveFilters = searchQuery.trim().length > 0

  return (
    <div className={className}>
      {/* Desktop view */}
      <div className="hidden sm:flex items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search discoveries..."
            className="w-full pl-10 pr-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Sort */}
        <div className="flex items-center gap-2">
          <span className="text-gray-400 text-sm">Sort:</span>
          <select
            value={sortBy}
            onChange={(e) => onSortChange(e.target.value)}
            className="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-cyan-500 focus:outline-none"
          >
            {SORT_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Mobile view */}
      <div className="sm:hidden">
        {/* Search + Filter toggle row */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search..."
              className="w-full pl-10 pr-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
            />
          </div>

          <button
            onClick={() => setShowMobileFilters(!showMobileFilters)}
            className={`
              p-2 rounded-lg border transition-colors
              ${showMobileFilters
                ? 'bg-cyan-600 border-cyan-500 text-white'
                : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white'
              }
            `}
          >
            <FunnelIcon className="w-5 h-5" />
            {hasActiveFilters && (
              <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-cyan-500" />
            )}
          </button>
        </div>

        {/* Collapsible filter panel */}
        {showMobileFilters && (
          <div className="mt-3 p-3 rounded-lg bg-gray-800/50 border border-gray-700 space-y-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Sort by</label>
              <select
                value={sortBy}
                onChange={(e) => onSortChange(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white"
              >
                {SORT_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            {hasActiveFilters && (
              <button
                onClick={() => {
                  onSearchChange('')
                  onSortChange('newest')
                }}
                className="w-full py-2 text-sm text-gray-400 hover:text-white transition-colors"
              >
                Clear all filters
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
