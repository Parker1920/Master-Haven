import React from 'react'
import { usePersonalColor } from '../utils/usePersonalColor'
import { tagColors } from '../utils/tagColors'

/** Renders a small colored badge for a community discord tag. Props: tag, className. */

export default function DiscordTagBadge({ tag, className = '' }) {
  const { personalColor } = usePersonalColor()

  if (!tag) return null

  // "personal" tags use the user's chosen personal color from context
  if (tag === 'personal') {
    return (
      <span
        className={`text-xs text-white px-1.5 py-0.5 rounded ${className}`}
        style={{ backgroundColor: personalColor }}
      >
        Personal
      </span>
    )
  }

  const colorClass = tagColors[tag] || 'bg-indigo-500 text-white'
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded ${colorClass} ${className}`}>
      {tag}
    </span>
  )
}
