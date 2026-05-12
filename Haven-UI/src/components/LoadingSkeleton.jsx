/**
 * LoadingSkeleton — pulsing placeholder cards shown during level transitions.
 *
 * Renders `count` skeleton-card cells in the same responsive grid used by the
 * real card grids. Aspect-ratio prop picks the poster shape for the level:
 * 'square' (L2 galaxy), '2:1' (L3 region), '3:2' (L4 system), 'tile' (L1
 * reality).
 */

import React from 'react'

const ASPECT_CLASS = {
  square: 'aspect-square',
  '2:1': 'aspect-[2/1]',
  '3:2': 'aspect-[3/2]',
  tile: 'h-32',
}

const GRID_CLASS = {
  reality: 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4',
  galaxy: 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4',
  region: 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4',
  system: 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4',
}

export default function LoadingSkeleton({ variant = 'galaxy', count = 6 }) {
  const aspectKey = variant === 'reality' ? 'tile' : variant === 'galaxy' ? 'square' : variant === 'region' ? '2:1' : '3:2'
  const aspectCls = ASPECT_CLASS[aspectKey]
  const gridCls = GRID_CLASS[variant] || GRID_CLASS.galaxy

  return (
    <div className={gridCls} aria-busy="true" aria-live="polite">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton-card">
          <div className={aspectCls} style={{ background: 'rgba(255,255,255,0.04)' }} />
          <div className="p-4 space-y-2">
            <div className="skeleton-bar h-4 w-3/4" />
            <div className="skeleton-bar h-3 w-1/2" />
            <div className="skeleton-bar h-3 w-2/3 mt-3" />
          </div>
        </div>
      ))}
    </div>
  )
}
