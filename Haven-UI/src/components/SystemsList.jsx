import React, { useEffect, useState, useMemo, useCallback } from 'react'
import axios from 'axios'
import { Link } from 'react-router-dom'
import Card from './Card'
import { StarIcon, ArrowPathIcon, ChevronLeftIcon, ChevronRightIcon, GlobeAltIcon } from '@heroicons/react/24/outline'
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid'
import { usePersonalColor } from '../utils/usePersonalColor'

/**
 * Level 4 Hierarchy: Systems List
 *
 * Shows a paginated list of systems within the selected region.
 * Clicking a system navigates to the system detail page.
 */
export default function SystemsList({ reality, galaxy, region, discordTag = 'all', globalMode = false, globalModeTitle = null, filters = {} }) {
  const [systems, setSystems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState({ total: 0, pages: 0 })
  const limit = 50 // Systems per page
  const { personalColor } = usePersonalColor()

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1)
  }, [JSON.stringify(filters)])

  useEffect(() => {
    // In global mode, we don't need a region - just load all systems for the filter
    if (globalMode) {
      loadSystems()
    } else if (reality && galaxy && region) {
      loadSystems()
    }
  }, [reality, galaxy, region, page, discordTag, globalMode, JSON.stringify(filters)])

  async function loadSystems() {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString(),
        include_planets: 'false' // Don't load planets in list view
      })

      // In global mode, region is optional - just filter by discord tag
      if (!globalMode && region) {
        params.append('reality', reality)
        params.append('galaxy', galaxy)
        params.append('region_x', region.region_x.toString())
        params.append('region_y', region.region_y.toString())
        params.append('region_z', region.region_z.toString())
      } else if (globalMode) {
        // In global mode, optionally filter by reality/galaxy if provided
        if (reality) params.append('reality', reality)
        if (galaxy) params.append('galaxy', galaxy)
      }

      if (discordTag && discordTag !== 'all') {
        params.append('discord_tag', discordTag)
      }

      // Append advanced filter params
      if (filters) {
        Object.entries(filters).forEach(([key, value]) => {
          if (value !== '' && value !== null && value !== undefined) {
            params.append(key, value.toString())
          }
        })
      }

      const res = await axios.get(`/api/systems?${params.toString()}`)
      setSystems(res.data.systems || [])
      setPagination(res.data.pagination || { total: 0, pages: 0 })
    } catch (err) {
      console.error('Failed to load systems:', err)
      setError('Failed to load system data')
      setSystems([])
    } finally {
      setLoading(false)
    }
  }

  // Star type colors
  const starColors = {
    'Yellow': 'text-yellow-400',
    'Red': 'text-red-400',
    'Green': 'text-green-400',
    'Blue': 'text-blue-400',
    'Purple': 'text-purple-400'
  }

  // Get stellar classification color based on first letter
  function getStellarClassColor(stellarClass) {
    if (!stellarClass) return 'text-gray-300';
    const firstChar = stellarClass[0]?.toUpperCase();
    switch(firstChar) {
      case 'O': case 'B': return 'text-blue-300';
      case 'F': case 'G': return 'text-yellow-300';
      case 'K': case 'M': return 'text-red-400';
      case 'E': return 'text-green-400';
      case 'X': case 'Y': return 'text-purple-400';
      default: return 'text-gray-300';
    }
  }

  // Economy colors
  const economyColors = {
    'Trading': 'bg-emerald-600',
    'Mining': 'bg-amber-600',
    'Technology': 'bg-blue-600',
    'Manufacturing': 'bg-orange-600',
    'Scientific': 'bg-purple-600',
    'Power Generation': 'bg-yellow-600'
  }

  // Completeness grade config (NMS-style C-B-A-S)
  const gradeConfig = {
    'S': { label: 'S', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', tip: 'Archive Quality' },
    'A': { label: 'A', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', tip: 'Well Documented' },
    'B': { label: 'B', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', tip: 'Partial Data' },
    'C': { label: 'C', color: 'bg-gray-500/20 text-gray-400 border-gray-500/30', tip: 'Basic Info' },
  }

  // Pre-defined tag colors (memoized)
  const tagColors = useMemo(() => ({
    'Haven': 'bg-cyan-500 text-white',
    'IEA': 'bg-green-500 text-white',
    'B.E.S': 'bg-orange-500 text-white',
    'ARCH': 'bg-purple-500 text-white',
    'TBH': 'bg-yellow-500 text-black',
    'EVRN': 'bg-pink-500 text-white',
  }), [])

  // Discord tag badge - memoized
  const getDiscordTagBadge = useCallback((tag) => {
    if (!tag) return null
    if (tag === 'personal') {
      return (
        <span
          className="text-xs text-white px-1.5 py-0.5 rounded"
          style={{ backgroundColor: personalColor }}
        >
          Personal
        </span>
      )
    }
    const colorClass = tagColors[tag] || 'bg-indigo-500 text-white'
    return <span className={`text-xs px-1.5 py-0.5 rounded ${colorClass}`}>{tag}</span>
  }, [tagColors, personalColor])

  // Pagination controls
  const canPrevPage = page > 1
  const canNextPage = page < pagination.pages
  const totalPages = pagination.pages || 0

  // Generate page numbers to display (show up to 7 pages with ellipsis) - memoized
  const pageNumbers = useMemo(() => {
    const pages = []
    const currentPage = page

    if (totalPages <= 7) {
      // Show all pages if 7 or fewer
      for (let i = 1; i <= totalPages; i++) pages.push(i)
    } else {
      // Always show first page
      pages.push(1)

      if (currentPage > 3) {
        pages.push('...')
      }

      // Show pages around current - use Set for O(1) lookup instead of includes O(n)
      const start = Math.max(2, currentPage - 1)
      const end = Math.min(totalPages - 1, currentPage + 1)
      const pagesSet = new Set(pages)

      for (let i = start; i <= end; i++) {
        if (!pagesSet.has(i)) {
          pages.push(i)
          pagesSet.add(i)
        }
      }

      if (currentPage < totalPages - 2) {
        pages.push('...')
      }

      // Always show last page
      if (!pagesSet.has(totalPages)) pages.push(totalPages)
    }

    return pages
  }, [page, totalPages])

  if (loading && systems.length === 0) {
    return (
      <Card>
        <div className="text-center py-8 text-gray-400">
          <ArrowPathIcon className="w-6 h-6 animate-spin mx-auto mb-2" />
          Loading systems...
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <div className="text-center py-8">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={loadSystems}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white"
          >
            Retry
          </button>
        </div>
      </Card>
    )
  }

  if (systems.length === 0) {
    return (
      <Card>
        <div className="text-center py-8 text-gray-400">
          <StarIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No systems found in this region.</p>
        </div>
      </Card>
    )
  }

  const regionName = region?.display_name || region?.custom_name ||
    (region ? `Region (${region.region_x}, ${region.region_y}, ${region.region_z})` : '')

  // Title for global mode or region mode
  const displayTitle = globalMode
    ? (globalModeTitle || `All ${discordTag} Systems`)
    : `Systems in ${regionName}`

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">
              {displayTitle}
            </h2>
            <p className="text-sm text-gray-400">
              {pagination.total} systems total &bull; Page {page} of {pagination.pages || 1}
            </p>
          </div>
          {/* 3D Region Map button - only show when viewing a specific region */}
          {!globalMode && region && (
            <a
              href={`/map/region?rx=${region.region_x}&ry=${region.region_y}&rz=${region.region_z}`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-2 bg-cyan-600 hover:bg-cyan-500 rounded-lg text-white text-sm font-medium transition-colors flex items-center gap-1.5"
              title="View region in 3D map"
            >
              <GlobeAltIcon className="w-4 h-4" />
              <span className="hidden sm:inline">3D Map</span>
            </a>
          )}
        </div>

        {/* Pagination controls */}
        {totalPages > 1 && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={!canPrevPage}
              className={`p-2 rounded ${canPrevPage ? 'bg-gray-700 hover:bg-gray-600' : 'bg-gray-800 text-gray-600 cursor-not-allowed'}`}
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </button>
            {/* Page numbers */}
            {pageNumbers.map((pageNum, idx) => (
              pageNum === '...' ? (
                <span key={`ellipsis-${idx}`} className="px-2 text-gray-500">...</span>
              ) : (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={`px-3 py-1 rounded text-sm ${
                    page === pageNum
                      ? 'bg-cyan-600 text-white font-medium'
                      : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                  }`}
                >
                  {pageNum}
                </button>
              )
            ))}
            <button
              onClick={() => setPage(p => Math.min(pagination.pages, p + 1))}
              disabled={!canNextPage}
              className={`p-2 rounded ${canNextPage ? 'bg-gray-700 hover:bg-gray-600' : 'bg-gray-800 text-gray-600 cursor-not-allowed'}`}
            >
              <ChevronRightIcon className="w-5 h-5" />
            </button>
          </div>
        )}
      </div>

      {loading && (
        <div className="text-center py-2 text-cyan-400 text-sm">
          <ArrowPathIcon className="w-4 h-4 animate-spin inline mr-2" />
          Updating...
        </div>
      )}

      <div className="space-y-2">
        {systems.map(system => {
          const starColor = starColors[system.star_type] || 'text-gray-400'
          const economyColor = economyColors[system.economy_type] || 'bg-gray-600'

          return (
            <Link
              key={system.id}
              to={`/systems/${system.id}`}
              className="block p-4 bg-gray-800 border border-gray-700 rounded-lg hover:border-cyan-500 hover:bg-gray-750 transition-all group"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 min-w-0 flex-1">
                  {/* Star icon */}
                  <div className="shrink-0 mt-1">
                    {system.star_type ? (
                      <StarIconSolid className={`w-6 h-6 ${starColor}`} />
                    ) : (
                      <StarIcon className="w-6 h-6 text-gray-500" />
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-white group-hover:text-cyan-400 transition-colors truncate">
                        {system.name || 'Unnamed System'}
                      </h3>
                      {getDiscordTagBadge(system.discord_tag)}
                      {(() => {
                        const grade = gradeConfig[system.completeness_grade] || gradeConfig['C']
                        const score = system.completeness_score || 0
                        return (
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded border font-bold ${grade.color}`}
                            title={`${grade.tip} (${score}%)`}
                          >
                            {grade.label}
                          </span>
                        )
                      })()}
                    </div>

                    {/* Glyph code */}
                    {system.glyph_code && (
                      <p className="text-xs font-mono text-gray-500 mt-0.5">
                        {system.glyph_code}
                      </p>
                    )}

                    {/* System properties */}
                    <div className="flex items-center gap-2 mt-2 flex-wrap">
                      {system.star_type && (
                        <span className={`text-xs px-2 py-0.5 rounded bg-gray-700 ${starColor}`}>
                          {system.star_type}
                        </span>
                      )}
                      {system.economy_type && (
                        <span className={`text-xs px-2 py-0.5 rounded ${economyColor} text-white`}>
                          {system.economy_type}
                        </span>
                      )}
                      {system.conflict_level && (
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          system.conflict_level === 'High' ? 'bg-red-600' :
                          system.conflict_level === 'Medium' ? 'bg-yellow-600' : 'bg-green-600'
                        } text-white`}>
                          {system.conflict_level} Conflict
                        </span>
                      )}
                      {system.dominant_lifeform && (
                        <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">
                          {system.dominant_lifeform}
                        </span>
                      )}
                      {system.stellar_classification && (
                        <span className={`text-xs px-2 py-0.5 rounded bg-gray-700 font-mono ${getStellarClassColor(system.stellar_classification)}`}>
                          {system.stellar_classification}
                        </span>
                      )}
                    </div>

                    {/* Uploader info */}
                    {system.discovered_by && (
                      <p className="text-xs text-gray-500 mt-1.5">
                        Uploaded by <span className="text-gray-400">{system.discovered_by}</span>
                        {system.discovered_at && (() => {
                          try {
                            const d = new Date(system.discovered_at)
                            if (!isNaN(d.getTime())) {
                              return <span> · {d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                            }
                          } catch {}
                          return null
                        })()}
                      </p>
                    )}
                  </div>
                </div>

                {/* 3D System Map button */}
                <a
                  href={`/map/system/${system.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="shrink-0 px-3 py-2 rounded bg-cyan-600 hover:bg-cyan-500 transition-colors text-white text-xs font-medium"
                  title="View system in 3D"
                >
                  View
                </a>
              </div>
            </Link>
          )
        })}
      </div>

      {/* Bottom pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-1 pt-4 flex-wrap">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={!canPrevPage}
            className={`px-3 py-2 rounded ${canPrevPage ? 'bg-gray-700 hover:bg-gray-600' : 'bg-gray-800 text-gray-600 cursor-not-allowed'}`}
          >
            Previous
          </button>
          {/* Page numbers */}
          {pageNumbers.map((pageNum, idx) => (
            pageNum === '...' ? (
              <span key={`ellipsis-bottom-${idx}`} className="px-2 text-gray-500">...</span>
            ) : (
              <button
                key={`bottom-${pageNum}`}
                onClick={() => setPage(pageNum)}
                className={`px-3 py-2 rounded text-sm ${
                  page === pageNum
                    ? 'bg-cyan-600 text-white font-medium'
                    : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                }`}
              >
                {pageNum}
              </button>
            )
          ))}
          <button
            onClick={() => setPage(p => Math.min(pagination.pages, p + 1))}
            disabled={!canNextPage}
            className={`px-3 py-2 rounded ${canNextPage ? 'bg-gray-700 hover:bg-gray-600' : 'bg-gray-800 text-gray-600 cursor-not-allowed'}`}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
