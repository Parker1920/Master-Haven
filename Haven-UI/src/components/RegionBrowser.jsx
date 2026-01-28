import React, { useEffect, useState, useContext } from 'react'
import axios from 'axios'
import Card from './Card'
import Modal from './Modal'
import Button from './Button'
import { MapPinIcon, ArrowPathIcon, ChevronLeftIcon, ChevronRightIcon, PencilIcon, StarIcon } from '@heroicons/react/24/outline'
import { AuthContext } from '../utils/AuthContext'

/**
 * Level 3 Hierarchy: Region Browser
 *
 * Shows a paginated list of regions within the selected galaxy.
 * Each region shows system count and custom name if available.
 * Includes the ability to set/edit region names.
 */
export default function RegionBrowser({ reality, galaxy, onSelect, selectedRegion, discordTag = 'all', onViewAllSystems }) {
  const auth = useContext(AuthContext)
  const [regions, setRegions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(0)
  const [totalRegions, setTotalRegions] = useState(0)
  const limit = 50 // Regions per page

  // Discord tags for region name submission
  const [discordTags, setDiscordTags] = useState([])

  // Edit region name modal state
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editingRegion, setEditingRegion] = useState(null)
  const [newRegionName, setNewRegionName] = useState('')
  const [newRegionDiscordTag, setNewRegionDiscordTag] = useState(null)
  const [submitterDiscordUsername, setSubmitterDiscordUsername] = useState('')
  const [submittingName, setSubmittingName] = useState(false)

  useEffect(() => {
    if (reality && galaxy) {
      loadRegions()
    }
  }, [reality, galaxy, page, discordTag])

  // Load discord tags for the modal dropdown
  useEffect(() => {
    axios.get('/api/discord_tags').then(r => {
      setDiscordTags(r.data.tags || [])
    }).catch(() => {})
  }, [])

  async function loadRegions() {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        reality,
        galaxy,
        include_systems: 'false',
        page: page.toString(),
        limit: limit.toString()
      })
      if (discordTag && discordTag !== 'all') {
        params.append('discord_tag', discordTag)
      }

      const res = await axios.get(`/api/regions/grouped?${params.toString()}`)
      setRegions(res.data.regions || [])
      setTotalRegions(res.data.total_regions || 0)
    } catch (err) {
      console.error('Failed to load regions:', err)
      setError('Failed to load region data')
      setRegions([])
    } finally {
      setLoading(false)
    }
  }

  // Open edit modal for a region
  function openEditModal(e, region) {
    e.stopPropagation() // Don't trigger region selection
    setEditingRegion(region)
    setNewRegionName(region.display_name || region.custom_name || '')
    setNewRegionDiscordTag(null)
    setSubmitterDiscordUsername('')
    setEditModalOpen(true)
  }

  // Submit region name
  async function handleSubmitName(e) {
    e.preventDefault()
    if (!newRegionName.trim() || !editingRegion) return

    // Check if user is logged in (partner/sub-admin) - use their session username
    const isLoggedIn = auth?.isAdmin && !auth?.isSuperAdmin
    const effectiveUsername = isLoggedIn ? auth?.user?.username : submitterDiscordUsername.trim()

    // Validation for non-super-admin users
    if (!auth?.isSuperAdmin) {
      if (!newRegionDiscordTag) {
        alert('Please select a Discord Community')
        return
      }
      // Only require manual Discord username for anonymous users
      if (!isLoggedIn && !submitterDiscordUsername.trim()) {
        alert('Please enter your Discord Username')
        return
      }
    }

    const { region_x, region_y, region_z } = editingRegion
    setSubmittingName(true)
    try {
      if (auth?.isSuperAdmin) {
        // Super admin can update directly
        await axios.put(`/api/regions/${region_x}/${region_y}/${region_z}`, { custom_name: newRegionName.trim() })
      } else {
        // Others submit for approval with Discord info
        await axios.post(`/api/regions/${region_x}/${region_y}/${region_z}/submit`, {
          proposed_name: newRegionName.trim(),
          discord_tag: newRegionDiscordTag,
          personal_discord_username: effectiveUsername
        })
      }
      setEditModalOpen(false)
      setEditingRegion(null)
      setNewRegionName('')
      setNewRegionDiscordTag(null)
      setSubmitterDiscordUsername('')
      loadRegions()
      alert(auth?.isSuperAdmin ? 'Region name updated!' : 'Name submitted for approval!')
    } catch (err) {
      alert('Failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setSubmittingName(false)
    }
  }

  // Pagination
  const totalPages = Math.ceil(totalRegions / limit)
  const canPrevPage = page > 0
  const canNextPage = page < totalPages - 1

  // Generate page numbers to display (show up to 7 pages with ellipsis)
  function getPageNumbers() {
    const pages = []
    const currentPage = page + 1 // Convert to 1-based for display

    if (totalPages <= 7) {
      // Show all pages if 7 or fewer
      for (let i = 1; i <= totalPages; i++) pages.push(i)
    } else {
      // Always show first page
      pages.push(1)

      if (currentPage > 3) {
        pages.push('...')
      }

      // Show pages around current
      const start = Math.max(2, currentPage - 1)
      const end = Math.min(totalPages - 1, currentPage + 1)

      for (let i = start; i <= end; i++) {
        if (!pages.includes(i)) pages.push(i)
      }

      if (currentPage < totalPages - 2) {
        pages.push('...')
      }

      // Always show last page
      if (!pages.includes(totalPages)) pages.push(totalPages)
    }

    return pages
  }

  // Check if a specific discord tag is selected (not 'all', 'untagged', 'personal')
  const isSpecificTagSelected = discordTag && !['all', 'untagged', 'personal'].includes(discordTag)

  // Format region key for selection
  function getRegionKey(r) {
    return `${r.region_x}-${r.region_y}-${r.region_z}`
  }

  // Check if a region is selected
  function isRegionSelected(r) {
    if (!selectedRegion) return false
    return selectedRegion.region_x === r.region_x &&
           selectedRegion.region_y === r.region_y &&
           selectedRegion.region_z === r.region_z
  }

  if (loading && regions.length === 0) {
    return (
      <Card>
        <div className="text-center py-8 text-gray-400">
          <ArrowPathIcon className="w-6 h-6 animate-spin mx-auto mb-2" />
          Loading regions in {galaxy}...
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
            onClick={loadRegions}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white"
          >
            Retry
          </button>
        </div>
      </Card>
    )
  }

  if (regions.length === 0) {
    return (
      <Card>
        <div className="text-center py-8 text-gray-400">
          <MapPinIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No regions found in {galaxy}.</p>
          <p className="text-sm mt-2">Systems need to be added to see regions here.</p>
        </div>
      </Card>
    )
  }

  // Total systems across all regions on current page
  const pageSystems = regions.reduce((sum, r) => sum + (r.system_count || 0), 0)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <MapPinIcon className="w-6 h-6 text-purple-400" />
            Regions in {galaxy}
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            {totalRegions} regions total • Showing {regions.length} ({pageSystems.toLocaleString()} systems)
          </p>
        </div>

        {/* Pagination controls */}
        {totalPages > 1 && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={!canPrevPage}
              className={`p-2 rounded ${canPrevPage ? 'bg-gray-700 hover:bg-gray-600' : 'bg-gray-800 text-gray-600 cursor-not-allowed'}`}
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </button>
            {/* Page numbers */}
            {getPageNumbers().map((pageNum, idx) => (
              pageNum === '...' ? (
                <span key={`ellipsis-${idx}`} className="px-2 text-gray-500">...</span>
              ) : (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum - 1)}
                  className={`px-3 py-1 rounded text-sm ${
                    page + 1 === pageNum
                      ? 'bg-purple-600 text-white font-medium'
                      : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                  }`}
                >
                  {pageNum}
                </button>
              )
            ))}
            <button
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
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

      {/* View All Systems button - shows when a specific discord tag is selected */}
      {isSpecificTagSelected && onViewAllSystems && (
        <div className="mb-4">
          <button
            onClick={onViewAllSystems}
            className="w-full p-4 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 rounded-xl text-white font-semibold transition-all flex items-center justify-center gap-2 shadow-lg hover:shadow-cyan-500/25"
          >
            <StarIcon className="w-5 h-5" />
            View All {discordTag} Systems ({totalRegions > 0 ? 'across all regions' : 'none found'})
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {regions.map(r => {
          const isSelected = isRegionSelected(r)
          const hasCustomName = r.display_name && r.display_name !== `Region (${r.region_x}, ${r.region_y}, ${r.region_z})`

          return (
            <div
              key={getRegionKey(r)}
              className={`
                relative overflow-hidden rounded-xl transition-all duration-300
                group
                ${isSelected
                  ? 'ring-2 ring-purple-400 ring-offset-2 ring-offset-gray-900 scale-[1.02]'
                  : 'hover:scale-[1.02] hover:shadow-lg hover:shadow-purple-500/10'
                }
              `}
            >
              {/* Gradient background */}
              <div className={`
                absolute inset-0 bg-gradient-to-br
                ${isSelected
                  ? 'from-purple-600 to-indigo-700'
                  : hasCustomName
                    ? 'from-purple-700/80 to-indigo-800/80'
                    : 'from-gray-700 to-gray-800'
                }
              `} />

              {/* Subtle pattern */}
              <div className="absolute inset-0 opacity-5" style={{
                backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)',
                backgroundSize: '12px 12px'
              }} />

              {/* Content */}
              <button
                onClick={() => onSelect(r)}
                className="relative p-4 w-full text-left"
              >
                {/* Header row */}
                <div className="flex items-start justify-between mb-2">
                  <div className={`
                    p-2 rounded-lg
                    ${isSelected ? 'bg-white/20' : hasCustomName ? 'bg-purple-500/30' : 'bg-gray-600/50'}
                  `}>
                    {hasCustomName ? (
                      <StarIcon className="w-5 h-5 text-yellow-400 fill-yellow-400" />
                    ) : (
                      <MapPinIcon className={`w-5 h-5 ${isSelected ? 'text-white' : 'text-purple-400'}`} />
                    )}
                  </div>

                  <div className="flex items-center gap-1">
                    {/* 3D Map button - always visible for mobile */}
                    <a
                      href={`/map/region?rx=${r.region_x}&ry=${r.region_y}&rz=${r.region_z}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className={`
                        px-2 py-1 rounded-lg text-xs font-medium transition-colors
                        ${isSelected ? 'bg-white/20 hover:bg-white/30 text-white' : 'bg-cyan-600/80 hover:bg-cyan-500 text-white'}
                      `}
                      title="View in 3D Map"
                    >
                      View
                    </a>
                    {/* Edit button */}
                    <button
                      onClick={(e) => openEditModal(e, r)}
                      className={`
                        p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity
                        ${isSelected ? 'bg-white/20 hover:bg-white/30' : 'bg-gray-600/50 hover:bg-gray-500/50'}
                      `}
                      title={hasCustomName ? 'Edit name' : 'Set name'}
                    >
                      <PencilIcon className="w-4 h-4 text-white" />
                    </button>
                  </div>
                </div>

                {/* Region name */}
                <h3 className="font-bold text-white truncate mb-1">
                  {hasCustomName ? (
                    <span className="text-purple-200">{r.display_name}</span>
                  ) : (
                    <span className="text-gray-300">Unnamed Region</span>
                  )}
                </h3>

                {/* Coordinates */}
                <p className="text-xs font-mono text-white/50 mb-3">
                  ({r.region_x}, {r.region_y}, {r.region_z})
                </p>

                {/* Stats row */}
                <div className={`
                  flex items-center justify-between pt-3 border-t
                  ${isSelected ? 'border-white/20' : 'border-white/10'}
                `}>
                  <div>
                    <span className="text-2xl font-bold text-white">
                      {r.system_count}
                    </span>
                    <span className="text-xs ml-1.5 text-white/60">
                      {r.system_count === 1 ? 'system' : 'systems'}
                    </span>
                  </div>

                  {hasCustomName && (
                    <span className="text-xs px-2 py-1 rounded-full bg-purple-500/30 text-purple-200">
                      Named
                    </span>
                  )}
                </div>

                {isSelected && (
                  <div className="absolute -top-1 -right-1">
                    <span className="bg-white text-purple-600 text-xs font-bold px-2 py-1 rounded-full shadow">
                      Selected
                    </span>
                  </div>
                )}
              </button>

              {/* Hover glow */}
              <div className={`
                absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300
                bg-gradient-to-t from-purple-500/20 to-transparent pointer-events-none
              `} />
            </div>
          )
        })}
      </div>

      {/* Bottom pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-1 pt-4 flex-wrap">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={!canPrevPage}
            className={`px-3 py-2 rounded ${canPrevPage ? 'bg-gray-700 hover:bg-gray-600' : 'bg-gray-800 text-gray-600 cursor-not-allowed'}`}
          >
            Previous
          </button>
          {/* Page numbers */}
          {getPageNumbers().map((pageNum, idx) => (
            pageNum === '...' ? (
              <span key={`ellipsis-bottom-${idx}`} className="px-2 text-gray-500">...</span>
            ) : (
              <button
                key={`bottom-${pageNum}`}
                onClick={() => setPage(pageNum - 1)}
                className={`px-3 py-2 rounded text-sm ${
                  page + 1 === pageNum
                    ? 'bg-purple-600 text-white font-medium'
                    : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                }`}
              >
                {pageNum}
              </button>
            )
          ))}
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={!canNextPage}
            className={`px-3 py-2 rounded ${canNextPage ? 'bg-gray-700 hover:bg-gray-600' : 'bg-gray-800 text-gray-600 cursor-not-allowed'}`}
          >
            Next
          </button>
        </div>
      )}

      {/* Edit Region Name Modal */}
      {editModalOpen && editingRegion && (
        <Modal
          title={editingRegion.display_name ? 'Edit Region Name' : 'Set Region Name'}
          onClose={() => setEditModalOpen(false)}
        >
          <form onSubmit={handleSubmitName} className="space-y-4">
            {/* Current coordinates display */}
            <div className="bg-gray-800 rounded-lg p-3 text-center">
              <span className="text-xs text-gray-400">Coordinates</span>
              <p className="font-mono text-purple-400">
                ({editingRegion.region_x}, {editingRegion.region_y}, {editingRegion.region_z})
              </p>
            </div>

            <div>
              <label className="block text-sm font-semibold mb-2">Region Name</label>
              <input
                type="text"
                value={newRegionName}
                onChange={e => setNewRegionName(e.target.value)}
                placeholder="Enter region name..."
                className="w-full px-3 py-2 rounded border border-gray-600 bg-gray-800 focus:border-purple-500 focus:outline-none"
                autoFocus
                maxLength={50}
              />
              {!auth?.isSuperAdmin && (
                <p className="text-xs text-gray-400 mt-1">
                  Your submission will be reviewed before approval.
                </p>
              )}
            </div>

            {/* Discord fields for non-super-admin users */}
            {!auth?.isSuperAdmin && (
              <>
                <div>
                  <label className="block text-sm font-semibold mb-2">
                    Discord Community <span className="text-red-400">*</span>
                  </label>
                  <select
                    className={`w-full px-3 py-2 rounded border bg-gray-800 focus:outline-none ${
                      !newRegionDiscordTag ? 'border-red-500/50' : 'border-gray-600 focus:border-purple-500'
                    }`}
                    value={newRegionDiscordTag || ''}
                    onChange={e => setNewRegionDiscordTag(e.target.value || null)}
                    required
                  >
                    <option value="">-- Select Community (Required) --</option>
                    {discordTags.map(t => (
                      <option key={t.tag} value={t.tag}>{t.name} ({t.tag})</option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    Which Discord community will review this region name?
                  </p>
                </div>

                {/* For logged-in users, show their username; for anonymous, show input field */}
                {auth?.isAdmin ? (
                  <div>
                    <label className="block text-sm font-semibold mb-2">Submitting As</label>
                    <div className="w-full px-3 py-2 rounded border border-gray-600 bg-gray-700 text-gray-300">
                      {auth?.user?.username || 'Unknown'}
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Your logged-in username will be used for tracking
                    </p>
                  </div>
                ) : (
                  <div>
                    <label className="block text-sm font-semibold mb-2">
                      Your Discord Username <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={submitterDiscordUsername}
                      onChange={e => setSubmitterDiscordUsername(e.target.value)}
                      placeholder="e.g., YourName#1234"
                      className={`w-full px-3 py-2 rounded border bg-gray-800 focus:outline-none ${
                        !submitterDiscordUsername.trim() ? 'border-red-500/50' : 'border-gray-600 focus:border-purple-500'
                      }`}
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      So we can contact you if needed
                    </p>
                  </div>
                )}
              </>
            )}

            <div className="flex gap-2 pt-2">
              <Button
                type="submit"
                className="flex-1 bg-purple-600 hover:bg-purple-700"
                disabled={submittingName || !newRegionName.trim()}
              >
                {submittingName ? 'Submitting...' : (auth?.isSuperAdmin ? 'Save' : 'Submit for Approval')}
              </Button>
              <Button
                type="button"
                className="bg-gray-600 hover:bg-gray-700"
                onClick={() => setEditModalOpen(false)}
                disabled={submittingName}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
