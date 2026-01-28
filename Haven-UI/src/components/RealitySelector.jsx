import React, { useEffect, useState } from 'react'
import axios from 'axios'
import Card from './Card'
import { GlobeAltIcon, ShieldExclamationIcon } from '@heroicons/react/24/outline'

/**
 * Level 1 Hierarchy: Reality Selector
 *
 * Shows Normal vs Permadeath tabs/cards with system counts.
 * First step in the containerized Systems page drill-down.
 */
export default function RealitySelector({ onSelect, selectedReality }) {
  const [realities, setRealities] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadRealities()
  }, [])

  async function loadRealities() {
    setLoading(true)
    setError(null)
    try {
      const res = await axios.get('/api/realities/summary')
      setRealities(res.data.realities || [])
    } catch (err) {
      console.error('Failed to load realities:', err)
      setError('Failed to load reality data')
      // Fallback to default realities if API fails
      setRealities([
        { reality: 'Normal', galaxy_count: 0, system_count: 0 },
        { reality: 'Permadeath', galaxy_count: 0, system_count: 0 }
      ])
    } finally {
      setLoading(false)
    }
  }

  // Icons for each reality
  const realityIcons = {
    'Normal': GlobeAltIcon,
    'Permadeath': ShieldExclamationIcon
  }

  // Colors for each reality
  const realityColors = {
    'Normal': {
      bg: 'bg-cyan-600',
      hoverBg: 'hover:bg-cyan-500',
      border: 'border-cyan-500',
      text: 'text-cyan-400',
      ring: 'ring-cyan-500'
    },
    'Permadeath': {
      bg: 'bg-red-600',
      hoverBg: 'hover:bg-red-500',
      border: 'border-red-500',
      text: 'text-red-400',
      ring: 'ring-red-500'
    }
  }

  if (loading) {
    return (
      <Card>
        <div className="text-center py-8 text-gray-400">Loading realities...</div>
      </Card>
    )
  }

  // Ensure we have both realities even if one has no data
  const normalizedRealities = ['Normal', 'Permadeath'].map(r => {
    const found = realities.find(x => x.reality === r)
    return found || { reality: r, galaxy_count: 0, system_count: 0 }
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Select Reality</h2>
        {error && <span className="text-sm text-red-400">{error}</span>}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {normalizedRealities.map(r => {
          const Icon = realityIcons[r.reality] || GlobeAltIcon
          const colors = realityColors[r.reality] || realityColors['Normal']
          const isSelected = selectedReality === r.reality

          return (
            <button
              key={r.reality}
              onClick={() => onSelect(r.reality)}
              className={`
                relative p-6 rounded-lg border-2 transition-all duration-200
                text-left group
                ${isSelected
                  ? `${colors.bg} ${colors.border} text-white ring-2 ${colors.ring} ring-offset-2 ring-offset-gray-900`
                  : `bg-gray-800 border-gray-700 ${colors.hoverBg.replace('hover:', '')} hover:border-gray-600`
                }
              `}
            >
              <div className="flex items-start gap-4">
                <div className={`
                  p-3 rounded-lg transition-colors
                  ${isSelected ? 'bg-white/20' : 'bg-gray-700 group-hover:bg-gray-600'}
                `}>
                  <Icon className={`w-8 h-8 ${isSelected ? 'text-white' : colors.text}`} />
                </div>

                <div className="flex-1">
                  <h3 className={`text-xl font-bold ${isSelected ? 'text-white' : 'text-gray-100'}`}>
                    {r.reality}
                  </h3>
                  <p className={`text-sm mt-1 ${isSelected ? 'text-white/80' : 'text-gray-400'}`}>
                    {r.reality === 'Normal'
                      ? 'Standard survival mode'
                      : 'One life, permanent death'}
                  </p>
                </div>
              </div>

              <div className={`
                mt-4 pt-4 border-t flex justify-between
                ${isSelected ? 'border-white/20' : 'border-gray-700'}
              `}>
                <div>
                  <div className={`text-2xl font-bold ${isSelected ? 'text-white' : colors.text}`}>
                    {r.system_count.toLocaleString()}
                  </div>
                  <div className={`text-xs ${isSelected ? 'text-white/70' : 'text-gray-500'}`}>
                    Systems
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-2xl font-bold ${isSelected ? 'text-white' : colors.text}`}>
                    {r.galaxy_count}
                  </div>
                  <div className={`text-xs ${isSelected ? 'text-white/70' : 'text-gray-500'}`}>
                    Galaxies
                  </div>
                </div>
              </div>

              {isSelected && (
                <div className="absolute top-2 right-2">
                  <span className="bg-white text-gray-900 text-xs font-bold px-2 py-1 rounded">
                    Selected
                  </span>
                </div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
