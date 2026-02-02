import React from 'react'
import { Link } from 'react-router-dom'

/**
 * TypeCard - Landing page card for each discovery type
 *
 * Displays a large visual card with emoji, label, count, and gradient background.
 * Links to the type-specific discovery page.
 */

// Color gradients for each discovery type
const TYPE_GRADIENTS = {
  fauna: 'from-green-600 to-green-800',
  flora: 'from-emerald-600 to-emerald-800',
  mineral: 'from-purple-600 to-purple-800',
  ancient: 'from-yellow-600 to-amber-800',
  history: 'from-amber-600 to-orange-800',
  bones: 'from-stone-500 to-stone-700',
  alien: 'from-cyan-600 to-cyan-800',
  starship: 'from-blue-600 to-blue-800',
  multitool: 'from-orange-600 to-orange-800',
  lore: 'from-indigo-600 to-indigo-800',
  base: 'from-teal-600 to-teal-800',
  other: 'from-gray-600 to-gray-800',
}

// Hover glow colors
const TYPE_GLOWS = {
  fauna: 'hover:shadow-green-500/30',
  flora: 'hover:shadow-emerald-500/30',
  mineral: 'hover:shadow-purple-500/30',
  ancient: 'hover:shadow-yellow-500/30',
  history: 'hover:shadow-amber-500/30',
  bones: 'hover:shadow-stone-400/30',
  alien: 'hover:shadow-cyan-500/30',
  starship: 'hover:shadow-blue-500/30',
  multitool: 'hover:shadow-orange-500/30',
  lore: 'hover:shadow-indigo-500/30',
  base: 'hover:shadow-teal-500/30',
  other: 'hover:shadow-gray-500/30',
}

export default function TypeCard({ slug, emoji, label, count = 0, className = '' }) {
  const gradient = TYPE_GRADIENTS[slug] || TYPE_GRADIENTS.other
  const glow = TYPE_GLOWS[slug] || TYPE_GLOWS.other

  return (
    <Link
      to={`/discoveries/${slug}`}
      className={`
        block rounded-xl overflow-hidden
        bg-gradient-to-br ${gradient}
        transform transition-all duration-300
        hover:scale-105 hover:shadow-xl ${glow}
        cursor-pointer
        ${className}
      `}
    >
      <div className="p-6 flex flex-col items-center justify-center min-h-[140px]">
        {/* Emoji */}
        <div className="text-5xl mb-2 drop-shadow-lg">
          {emoji}
        </div>

        {/* Label */}
        <div className="text-white font-semibold text-lg">
          {label}
        </div>

        {/* Count badge */}
        <div className="mt-2 px-3 py-1 rounded-full bg-black/30 text-white/90 text-sm font-medium">
          {count.toLocaleString()} {count === 1 ? 'discovery' : 'discoveries'}
        </div>
      </div>
    </Link>
  )
}
