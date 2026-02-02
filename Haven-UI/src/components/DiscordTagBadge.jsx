import React from 'react'
import { usePersonalColor } from '../utils/usePersonalColor'

const tagColors = {
  'Haven': 'bg-cyan-500 text-white',
  'IEA': 'bg-green-500 text-white',
  'B.E.S': 'bg-orange-500 text-white',
  'ARCH': 'bg-purple-500 text-white',
  'TBH': 'bg-yellow-500 text-black',
  'EVRN': 'bg-pink-500 text-white',
}

export default function DiscordTagBadge({ tag, className = '' }) {
  const { personalColor } = usePersonalColor()

  if (!tag) return null

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
