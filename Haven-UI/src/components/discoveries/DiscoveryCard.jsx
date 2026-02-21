import React from 'react'
import { StarIcon } from '@heroicons/react/24/solid'

/**
 * DiscoveryCard - Photo-focused showcase card for discoveries
 *
 * Features:
 * - Large 16:9 image with lazy loading
 * - Type badge overlay
 * - Featured star badge
 * - Discoverer credit
 * - System/location info
 * - Hover zoom effect
 */

// Normalize photo URLs for display
function getPhotoUrl(photo) {
  if (!photo) return null
  if (photo.startsWith('http')) return photo
  // Normalize backslashes to forward slashes
  const normalized = photo.replace(/\\/g, '/')
  const parts = normalized.split('/')
  const filename = parts[parts.length - 1]
  return `/haven-ui-photos/${encodeURIComponent(filename)}`
}

// Placeholder gradient backgrounds when no photo
const TYPE_PLACEHOLDERS = {
  fauna: 'bg-gradient-to-br from-green-900 to-green-950',
  flora: 'bg-gradient-to-br from-emerald-900 to-emerald-950',
  mineral: 'bg-gradient-to-br from-purple-900 to-purple-950',
  ancient: 'bg-gradient-to-br from-yellow-900 to-amber-950',
  history: 'bg-gradient-to-br from-amber-900 to-orange-950',
  bones: 'bg-gradient-to-br from-stone-800 to-stone-900',
  alien: 'bg-gradient-to-br from-cyan-900 to-cyan-950',
  starship: 'bg-gradient-to-br from-blue-900 to-blue-950',
  multitool: 'bg-gradient-to-br from-orange-900 to-orange-950',
  lore: 'bg-gradient-to-br from-indigo-900 to-indigo-950',
  base: 'bg-gradient-to-br from-teal-900 to-teal-950',
  other: 'bg-gradient-to-br from-gray-800 to-gray-900',
}

export default function DiscoveryCard({
  discovery,
  onClick,
  className = ''
}) {
  const {
    id,
    discovery_name,
    discovery_type,
    type_slug,
    type_info,
    photo_url,
    discovered_by,
    system_name,
    system_galaxy,
    planet_name,
    moon_name,
    system_is_stub,
    location_type,
    is_featured,
  } = discovery

  const slug = type_slug || 'other'
  const photoSrc = getPhotoUrl(photo_url)
  const placeholderBg = TYPE_PLACEHOLDERS[slug] || TYPE_PLACEHOLDERS.other
  const emoji = type_info?.emoji || discovery_type || '?'
  const typeLabel = type_info?.label || slug

  return (
    <div
      onClick={() => onClick?.(discovery)}
      className={`
        group relative rounded-xl overflow-hidden
        bg-gray-800 border border-gray-700
        cursor-pointer
        transform transition-all duration-300
        hover:border-gray-500 hover:shadow-xl hover:shadow-black/30
        ${className}
      `}
    >
      {/* Image container - 16:9 aspect ratio */}
      <div className={`relative aspect-video overflow-hidden ${!photoSrc ? placeholderBg : ''}`}>
        {photoSrc ? (
          <img
            src={photoSrc}
            alt={discovery_name}
            loading="lazy"
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <span className="text-6xl opacity-30">{emoji}</span>
          </div>
        )}

        {/* Featured badge */}
        {is_featured ? (
          <div className="absolute top-3 right-3 flex items-center gap-1 px-2 py-1 rounded-full bg-yellow-500 text-yellow-900 text-xs font-bold shadow-lg">
            <StarIcon className="w-3 h-3" />
            Featured
          </div>
        ) : null}

        {/* Type badge */}
        <div className="absolute bottom-3 left-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-sm text-white text-sm">
          <span>{emoji}</span>
          <span className="font-medium">{typeLabel}</span>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Name */}
        <h3 className="text-white font-semibold text-lg truncate group-hover:text-cyan-400 transition-colors">
          {discovery_name || `Discovery #${id}`}
        </h3>

        {/* Location */}
        {(system_name || system_galaxy || planet_name || moon_name) && (
          <div className="mt-1 text-gray-400 text-sm truncate flex items-center gap-1">
            {system_name && <span>{system_name}</span>}
            {system_is_stub === 1 && (
              <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                Stub
              </span>
            )}
            {planet_name && <><span className="text-gray-600 mx-0.5">&rsaquo;</span><span>{planet_name}</span></>}
            {moon_name && <><span className="text-gray-600 mx-0.5">&rsaquo;</span><span>{moon_name}</span></>}
            {location_type === 'space' && !planet_name && !moon_name && <><span className="text-gray-600 mx-0.5">&rsaquo;</span><span className="text-cyan-400">Space</span></>}
            {system_galaxy && <><span className="mx-1">&bull;</span><span>{system_galaxy}</span></>}
          </div>
        )}

        {/* Discoverer */}
        <div className="mt-3 text-gray-500 text-sm">
          Discovered by <span className="text-gray-400">{discovered_by || 'Unknown'}</span>
        </div>
      </div>
    </div>
  )
}
