/**
 * RealitySelector — Level 1 of the Systems v2.0 hierarchy.
 *
 * Hits /api/realities/summary for system + galaxy counts per reality, then
 * folds them into a fixed 4-up grid (Normal / Custom / Permadeath / Creative).
 * If the API returns realities we don't have a preset for, they render as
 * generic cards at the end. If a preset reality has zero systems, it still
 * renders — discoverability beats hiding empty modes.
 *
 * Per dispatch task list: the legacy v1 RealitySelector.jsx is replaced by
 * this implementation.
 */

import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useSystems } from '../contexts/SystemsContext'
import LoadingSkeleton from './LoadingSkeleton'

// Only Normal and Permadeath are surfaced — Custom and Creative were in the
// original spec but Parker cut them since they're not used in this community.
// If a reality outside this list shows up in the data, it still renders via
// the `extras` branch below.
const PRESETS = [
  {
    key: 'Normal',
    title: 'Normal',
    blurb: 'Standard mode — most explored, all communities active',
    badge: { label: 'Default', cls: 'pill-teal' },
    iconBg: 'var(--app-primary-dim)',
    iconColor: 'var(--app-primary)',
    icon: (
      <>
        <circle cx="12" cy="12" r="10" />
        <path strokeLinecap="round" d="M12 6v6l4 2" />
      </>
    ),
  },
  {
    key: 'Permadeath',
    title: 'Permadeath',
    blurb: 'One life — death wipes the save permanently',
    badge: { label: 'Hardcore', cls: 'pill-red' },
    iconBg: 'rgba(239, 68, 68, 0.15)',
    iconColor: '#fca5a5',
    icon: <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />,
  },
]

export default function RealitySelector() {
  const { selectReality } = useSystems()
  const [counts, setCounts] = useState({})
  const [total, setTotal] = useState({ systems: 0, regions: 0 })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      axios.get('/api/realities/summary').then((r) => r.data),
      axios.get('/api/stats').then((r) => r.data).catch(() => ({})),
    ])
      .then(([reality, stats]) => {
        if (cancelled) return
        const byReality = {}
        for (const r of reality.realities || []) byReality[r.reality] = r
        setCounts(byReality)
        setTotal({
          systems: stats.system_count || 0,
          regions: stats.named_regions || stats.regions || 0,
        })
      })
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])

  if (loading) return <LoadingSkeleton variant="reality" count={4} />

  const presetKeys = new Set(PRESETS.map((p) => p.key))
  const extras = Object.keys(counts).filter((k) => !presetKeys.has(k))

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--app-text)' }}>Choose a reality</h2>
        <div className="text-xs mono" style={{ color: 'var(--muted)' }}>
          {total.systems.toLocaleString()} systems
          {total.regions ? ` · ${total.regions.toLocaleString()} regions` : ''}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {PRESETS.map((p) => {
          const c = counts[p.key]
          return (
            <button
              key={p.key}
              type="button"
              onClick={() => selectReality(p.key)}
              className="haven-card haven-card-hover p-5 text-left"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: p.iconBg }}>
                  <svg className="w-5 h-5" style={{ color: p.iconColor }} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    {p.icon}
                  </svg>
                </div>
                <span className={`pill ${p.badge.cls} text-[10px]`}>{p.badge.label}</span>
              </div>
              <h3 className="text-lg font-semibold mb-1">{p.title}</h3>
              <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>{p.blurb}</p>
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-bold">{(c?.system_count || 0).toLocaleString()}</span>
                <span className="text-xs" style={{ color: 'var(--muted)' }}>systems</span>
              </div>
              <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
                {c?.galaxy_count ? `${c.galaxy_count} galaxies` : 'No data yet'}
              </div>
            </button>
          )
        })}

        {extras.map((key) => {
          const c = counts[key]
          return (
            <button
              key={key}
              type="button"
              onClick={() => selectReality(key)}
              className="haven-card haven-card-hover p-5 text-left"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'rgba(255,255,255,0.05)' }}>
                  <svg className="w-5 h-5" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="9" />
                  </svg>
                </div>
              </div>
              <h3 className="text-lg font-semibold mb-1">{key}</h3>
              <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>Reality discovered in submissions</p>
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-bold">{(c?.system_count || 0).toLocaleString()}</span>
                <span className="text-xs" style={{ color: 'var(--muted)' }}>systems</span>
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}
