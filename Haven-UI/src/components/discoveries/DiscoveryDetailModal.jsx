import React, { useState, useEffect, useContext } from 'react'
import { Link } from 'react-router-dom'
import { XMarkIcon, StarIcon, MapPinIcon, CalendarIcon, UserIcon } from '@heroicons/react/24/outline'
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid'
import { AuthContext } from '../../utils/AuthContext'

/**
 * DiscoveryDetailModal - Enhanced modal for viewing discovery details
 *
 * Features:
 * - Full-width hero image
 * - Photo gallery with thumbnails
 * - Discovery info and description
 * - Location with system/planet links
 * - Evidence section
 * - Feature toggle for admins
 */

// Normalize photo URLs
function getPhotoUrl(photo) {
  if (!photo) return null
  if (photo.startsWith('http')) return photo
  const normalized = photo.replace(/\\/g, '/')
  const parts = normalized.split('/')
  const filename = parts[parts.length - 1]
  return `/haven-ui-photos/${encodeURIComponent(filename)}`
}

// Parse evidence URLs (comma-separated or array)
function parseEvidenceUrls(evidence) {
  if (!evidence) return []
  if (Array.isArray(evidence)) return evidence.map(u => getPhotoUrl(u) || u)
  if (typeof evidence === 'string') {
    return evidence.split(',').map(s => s.trim()).filter(Boolean).map(u => getPhotoUrl(u) || u)
  }
  return []
}

export default function DiscoveryDetailModal({
  discovery,
  isOpen,
  onClose,
  onFeatureToggle
}) {
  const auth = useContext(AuthContext)
  const session = auth.user
  const [selectedImage, setSelectedImage] = useState(null)
  const [isFeatureLoading, setIsFeatureLoading] = useState(false)

  // Reset selected image when discovery changes
  useEffect(() => {
    if (discovery?.photo_url) {
      setSelectedImage(getPhotoUrl(discovery.photo_url))
    } else {
      setSelectedImage(null)
    }
  }, [discovery])

  // Increment view count
  useEffect(() => {
    if (isOpen && discovery?.id) {
      fetch(`/api/discoveries/${discovery.id}/view`, { method: 'POST' }).catch(() => {})
    }
  }, [isOpen, discovery?.id])

  if (!isOpen || !discovery) return null

  const {
    id,
    discovery_name,
    discovery_type,
    type_info,
    description,
    photo_url,
    evidence_url,
    discovered_by,
    discord_user_id,
    submission_timestamp,
    created_at,
    system_id,
    system_name,
    system_galaxy,
    planet_name,
    moon_name,
    system_is_stub,
    location_type,
    location_name,
    type_metadata,
    is_featured,
    view_count,
  } = discovery

  const mainPhoto = getPhotoUrl(photo_url)
  const evidencePhotos = parseEvidenceUrls(evidence_url)
  const allPhotos = [mainPhoto, ...evidencePhotos].filter(Boolean)
  const displayDate = submission_timestamp || created_at
  const emoji = type_info?.emoji || discovery_type || '?'
  const typeLabel = type_info?.label || 'Discovery'

  const canFeature = auth.isSuperAdmin || auth.isPartner || auth.isSubAdmin

  async function handleFeatureToggle() {
    if (!canFeature || isFeatureLoading) return
    setIsFeatureLoading(true)
    try {
      const res = await fetch(`/api/discoveries/${id}/feature`, {
        method: 'POST',
        credentials: 'include'
      })
      if (res.ok) {
        const data = await res.json()
        onFeatureToggle?.(id, data.is_featured)
      }
    } catch (err) {
      console.error('Failed to toggle featured:', err)
    } finally {
      setIsFeatureLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-xl"
        style={{ backgroundColor: 'var(--app-card)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-10 p-2 rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors"
        >
          <XMarkIcon className="w-6 h-6" />
        </button>

        {/* Hero image */}
        {selectedImage ? (
          <div className="relative aspect-video bg-black">
            <img
              src={selectedImage}
              alt={discovery_name}
              className="w-full h-full object-contain"
            />
          </div>
        ) : (
          <div className="aspect-video bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center">
            <span className="text-8xl opacity-30">{emoji}</span>
          </div>
        )}

        {/* Photo gallery thumbnails */}
        {allPhotos.length > 1 && (
          <div className="flex gap-2 p-4 overflow-x-auto bg-black/30">
            {allPhotos.map((photo, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedImage(photo)}
                className={`
                  flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden border-2 transition-all
                  ${selectedImage === photo ? 'border-cyan-500' : 'border-transparent opacity-60 hover:opacity-100'}
                `}
              >
                <img src={photo} alt={`Photo ${idx + 1}`} className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        )}

        {/* Content */}
        <div className="p-6">
          {/* Header */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">{emoji}</span>
                <span className="text-gray-400">{typeLabel}</span>
                {is_featured && (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-yellow-500 text-yellow-900 text-xs font-bold">
                    <StarIconSolid className="w-3 h-3" />
                    Featured
                  </span>
                )}
              </div>
              <h2 className="text-2xl font-bold text-white">
                {discovery_name || `Discovery #${id}`}
              </h2>
            </div>

            {/* Feature toggle button for admins */}
            {canFeature && (
              <button
                onClick={handleFeatureToggle}
                disabled={isFeatureLoading}
                className={`
                  flex items-center gap-2 px-4 py-2 rounded-lg transition-colors
                  ${is_featured
                    ? 'bg-yellow-500 text-yellow-900 hover:bg-yellow-400'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }
                  ${isFeatureLoading ? 'opacity-50 cursor-not-allowed' : ''}
                `}
              >
                {is_featured ? (
                  <>
                    <StarIconSolid className="w-4 h-4" />
                    Unfeature
                  </>
                ) : (
                  <>
                    <StarIcon className="w-4 h-4" />
                    Feature
                  </>
                )}
              </button>
            )}
          </div>

          {/* Description */}
          {description && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">Description</h3>
              <p className="text-gray-300 whitespace-pre-wrap">{description}</p>
            </div>
          )}

          {/* Location */}
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">Location</h3>
            <div className="flex flex-wrap items-center gap-2 text-gray-300">
              {system_id && system_name && (
                <Link
                  to={`/systems/${system_id}`}
                  className="flex items-center gap-2 hover:text-cyan-400 transition-colors"
                >
                  <MapPinIcon className="w-4 h-4" />
                  {system_name}
                  {system_galaxy && <span className="text-gray-500">({system_galaxy})</span>}
                </Link>
              )}
              {system_is_stub === 1 && (
                <span className="px-2 py-0.5 rounded text-xs font-semibold bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                  Stub - Needs Update
                </span>
              )}
              {planet_name && (
                <span className="flex items-center gap-1 text-gray-300">
                  <span className="text-gray-600">&rsaquo;</span>
                  {planet_name}
                </span>
              )}
              {moon_name && (
                <span className="flex items-center gap-1 text-gray-300">
                  <span className="text-gray-600">&rsaquo;</span>
                  {moon_name}
                </span>
              )}
              {location_type === 'space' && !planet_name && !moon_name && (
                <span className="flex items-center gap-1 text-cyan-400">
                  <span className="text-gray-600">&rsaquo;</span>
                  Space
                </span>
              )}
              {location_name && !planet_name && !moon_name && location_type !== 'space' && (
                <span className="flex items-center gap-2 text-gray-400">
                  <span className="text-gray-600">&bull;</span>
                  {location_name}
                </span>
              )}
            </div>
          </div>

          {/* Type Details (metadata) */}
          {type_metadata && typeof type_metadata === 'object' && Object.keys(type_metadata).length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">Details</h3>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                {Object.entries(type_metadata).map(([key, value]) => (
                  value && (
                    <div key={key} className="text-sm">
                      <span className="text-gray-500">{key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}:</span>{' '}
                      <span className="text-gray-300">{value}</span>
                    </div>
                  )
                ))}
              </div>
            </div>
          )}

          {/* Metadata */}
          <div className="mt-6 pt-6 border-t border-gray-700 flex flex-wrap items-center gap-6 text-sm">
            {/* Discoverer */}
            <div className="flex items-center gap-2 text-gray-400">
              <UserIcon className="w-4 h-4" />
              <span>Discovered by</span>
              <span className="text-gray-300">{discovered_by || discord_user_id || 'Unknown'}</span>
            </div>

            {/* Date */}
            {displayDate && (
              <div className="flex items-center gap-2 text-gray-400">
                <CalendarIcon className="w-4 h-4" />
                <span>{new Date(displayDate).toLocaleDateString()}</span>
              </div>
            )}

            {/* View count */}
            {view_count > 0 && (
              <div className="text-gray-500">
                {view_count.toLocaleString()} {view_count === 1 ? 'view' : 'views'}
              </div>
            )}
          </div>

          {/* External evidence links */}
          {evidencePhotos.some(url => url.startsWith('http') && !url.includes('haven-ui-photos')) && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">External Links</h3>
              <div className="space-y-1">
                {evidencePhotos
                  .filter(url => url.startsWith('http') && !url.includes('haven-ui-photos'))
                  .map((url, idx) => (
                    <a
                      key={idx}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block text-cyan-400 hover:text-cyan-300 truncate"
                    >
                      {url}
                    </a>
                  ))
                }
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
