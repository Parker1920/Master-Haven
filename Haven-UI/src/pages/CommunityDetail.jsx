import React, { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import StatCard from '../components/StatCard'
import { getTagColorStyle as getTagColors } from '../utils/tagColors'
import { normalizeUsernameForUrl } from '../posters/_shared/identity'

/**
 * Community Detail — Route: /community-stats/:tag
 * Auth: Public (no login required).
 *
 * Drill-down page for a single community. Shows stat cards, two ranked
 * contributor tables (manual vs extractor), and an expandable region list
 * where each region reveals its systems with star type dots and grade badges.
 * Clicking a system navigates to /systems/:id.
 *
 * API endpoints:
 *   GET /api/public/community-overview   — find this community's stats from the overview list
 *   GET /api/public/contributors?community=TAG — ranked contributors for this community
 *   GET /api/public/community-regions?community=TAG — regions with nested system lists
 */

// Rank badge styles
const rankStyles = {
  1: { bg: 'rgba(255, 215, 0, 0.15)', border: 'rgba(255, 215, 0, 0.3)', text: '#FFD700' },
  2: { bg: 'rgba(192, 192, 192, 0.15)', border: 'rgba(192, 192, 192, 0.3)', text: '#C0C0C0' },
  3: { bg: 'rgba(205, 127, 50, 0.15)', border: 'rgba(205, 127, 50, 0.3)', text: '#CD7F32' },
}

// Star type colors
const starTypeColors = {
  'Yellow': '#facc15', 'Red': '#ef4444', 'Green': '#22c55e',
  'Blue': '#3b82f6', 'Purple': '#a855f7', 'Unknown': '#6b7280',
}

// Grade badge colors
const gradeColors = {
  'S': { bg: 'rgba(255, 215, 0, 0.2)', text: '#FFD700' },
  'A': { bg: 'rgba(34, 197, 94, 0.2)', text: '#22c55e' },
  'B': { bg: 'rgba(59, 130, 246, 0.2)', text: '#3b82f6' },
  'C': { bg: 'rgba(107, 114, 128, 0.2)', text: '#6b7280' },
}

export default function CommunityDetail() {
  const { tag } = useParams()
  const [loading, setLoading] = useState(true)
  const [community, setCommunity] = useState(null)
  const [contributors, setContributors] = useState([])
  const [totalContributors, setTotalContributors] = useState(0)
  const [regions, setRegions] = useState([])
  const [expandedRegions, setExpandedRegions] = useState({})

  const colors = getTagColors(tag)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      fetch('/api/public/community-overview').then(r => r.json()),
      fetch(`/api/public/contributors?community=${encodeURIComponent(tag)}`).then(r => r.json()),
      fetch(`/api/public/community-regions?community=${encodeURIComponent(tag)}`).then(r => r.json()),
    ])
      .then(([overviewData, contribData, regionsData]) => {
        const match = (overviewData.communities || []).find(c => c.discord_tag === tag)
        setCommunity(match || { discord_tag: tag, display_name: tag, total_systems: 0, total_discoveries: 0, unique_contributors: 0, manual_systems: 0, extractor_systems: 0 })
        setContributors(contribData.contributors || [])
        setTotalContributors(contribData.total_contributors || 0)
        setRegions(regionsData.regions || [])
      })
      .catch(err => console.error('Failed to load community detail:', err))
      .finally(() => setLoading(false))
  }, [tag])

  const toggleRegion = (key) => {
    setExpandedRegions(prev => ({ ...prev, [key]: !prev[key] }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg" style={{ color: 'var(--app-text)', opacity: 0.5 }}>Loading...</div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Back link */}
      <Link
        to="/community-stats"
        className="inline-flex items-center gap-1 text-sm mb-6 hover:underline"
        style={{ color: colors.text }}
      >
        &larr; Back to Community Stats
      </Link>

      {/* Community Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <span className="inline-block w-4 h-4 rounded-full" style={{ background: colors.text }} />
          <h1 className="text-3xl font-bold" style={{ color: 'var(--app-text)' }}>
            {community.display_name}
          </h1>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="Systems Mapped" value={(community.total_systems || 0).toLocaleString()} />
          <StatCard title="Discoveries" value={(community.total_discoveries || 0).toLocaleString()} />
          <StatCard title="Members" value={community.unique_contributors || 0} />
          <StatCard
            title="Upload Split"
            value={`${community.manual_systems || 0} / ${community.extractor_systems || 0}`}
            subtitle="Manual / Extractor"
          />
        </div>
      </div>

      {/* Members Section — Two Side-by-Side Lists (manual vs extractor) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Manual Submissions List — filter to manual-only, sort by count, assign ranks */}
        {(() => {
          const manualList = contributors
            .filter(c => (c.manual_count || 0) > 0)
            .sort((a, b) => (b.manual_count || 0) - (a.manual_count || 0))
            .map((c, i) => ({ ...c, _rank: i + 1 }))
          return (
            <div
              className="rounded-xl p-4"
              style={{
                background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
                border: '1px solid rgba(6, 182, 212, 0.15)'
              }}
            >
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--app-text)' }}>
                <span className="inline-block w-3 h-3 rounded-full" style={{ background: '#06b6d4' }} />
                Manual Submissions
                <span className="text-sm font-normal" style={{ opacity: 0.5 }}>({manualList.length})</span>
              </h2>
              {manualList.length === 0 ? (
                <div className="text-center py-8" style={{ color: 'var(--app-text)', opacity: 0.5 }}>No manual submissions</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                        <th className="text-left py-2 px-2 font-medium" style={{ color: 'var(--app-text)', opacity: 0.6, width: '3rem' }}>#</th>
                        <th className="text-left py-2 px-2 font-medium" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Name</th>
                        <th className="text-right py-2 px-2 font-medium" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Systems</th>
                      </tr>
                    </thead>
                    <tbody>
                      {manualList.map((c) => {
                        const rs = rankStyles[c._rank]
                        return (
                          <tr
                            key={c.username}
                            style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                          >
                            <td className="py-2.5 px-2">
                              {rs ? (
                                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold"
                                  style={{ background: rs.bg, border: `1px solid ${rs.border}`, color: rs.text }}>{c._rank}</span>
                              ) : (
                                <span className="text-xs font-medium pl-1.5" style={{ color: 'var(--app-text)', opacity: 0.4 }}>{c._rank}</span>
                              )}
                            </td>
                            <td className="py-2.5 px-2 font-medium" style={{ color: 'var(--app-text)' }}>
                              <Link to={`/voyager/${normalizeUsernameForUrl(c.username)}`}
                                className="hover:underline hover:text-cyan-400 transition-colors">
                                {c.username}
                              </Link>
                            </td>
                            <td className="py-2.5 px-2 text-right font-semibold" style={{ color: '#06b6d4' }}>{c.manual_count}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )
        })()}

        {/* Extractor Submissions List */}
        {(() => {
          const extractorList = contributors
            .filter(c => (c.extractor_count || 0) > 0)
            .sort((a, b) => (b.extractor_count || 0) - (a.extractor_count || 0))
            .map((c, i) => ({ ...c, _rank: i + 1 }))
          return (
            <div
              className="rounded-xl p-4"
              style={{
                background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
                border: '1px solid rgba(168, 85, 247, 0.15)'
              }}
            >
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--app-text)' }}>
                <span className="inline-block w-3 h-3 rounded-full" style={{ background: '#a855f7' }} />
                Extractor Submissions
                <span className="text-sm font-normal" style={{ opacity: 0.5 }}>({extractorList.length})</span>
              </h2>
              {extractorList.length === 0 ? (
                <div className="text-center py-8" style={{ color: 'var(--app-text)', opacity: 0.5 }}>No extractor submissions</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                        <th className="text-left py-2 px-2 font-medium" style={{ color: 'var(--app-text)', opacity: 0.6, width: '3rem' }}>#</th>
                        <th className="text-left py-2 px-2 font-medium" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Name</th>
                        <th className="text-right py-2 px-2 font-medium" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Systems</th>
                      </tr>
                    </thead>
                    <tbody>
                      {extractorList.map((c) => {
                        const rs = rankStyles[c._rank]
                        return (
                          <tr
                            key={c.username}
                            style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                          >
                            <td className="py-2.5 px-2">
                              {rs ? (
                                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold"
                                  style={{ background: rs.bg, border: `1px solid ${rs.border}`, color: rs.text }}>{c._rank}</span>
                              ) : (
                                <span className="text-xs font-medium pl-1.5" style={{ color: 'var(--app-text)', opacity: 0.4 }}>{c._rank}</span>
                              )}
                            </td>
                            <td className="py-2.5 px-2 font-medium" style={{ color: 'var(--app-text)' }}>
                              <Link to={`/voyager/${normalizeUsernameForUrl(c.username)}`}
                                className="hover:underline hover:text-cyan-400 transition-colors">
                                {c.username}
                              </Link>
                            </td>
                            <td className="py-2.5 px-2 text-right font-semibold" style={{ color: '#a855f7' }}>{c.extractor_count}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )
        })()}
      </div>

      {/* Regions Section */}
      <div
        className="rounded-xl p-4"
        style={{
          background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
          border: '1px solid rgba(255,255,255,0.04)'
        }}
      >
        <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
          Regions
          <span className="text-sm font-normal ml-2" style={{ opacity: 0.5 }}>({regions.length})</span>
        </h2>

        {regions.length === 0 ? (
          <div className="text-center py-8" style={{ color: 'var(--app-text)', opacity: 0.5 }}>
            No regions found
          </div>
        ) : (
          <div className="space-y-1">
            {regions.map((region) => {
              // Use coordinate triple as unique key since unnamed regions have no id
              const key = `${region.region_x},${region.region_y},${region.region_z}`
              const isExpanded = !!expandedRegions[key]

              return (
                <div key={key}>
                  {/* Region row */}
                  <button
                    onClick={() => toggleRegion(key)}
                    className="w-full flex items-center justify-between px-4 py-3 rounded-lg transition-colors text-left"
                    style={{
                      background: isExpanded ? 'rgba(255,255,255,0.04)' : 'transparent',
                    }}
                    onMouseEnter={e => { if (!isExpanded) e.currentTarget.style.background = 'rgba(255,255,255,0.02)' }}
                    onMouseLeave={e => { if (!isExpanded) e.currentTarget.style.background = 'transparent' }}
                  >
                    <div className="flex items-center gap-3">
                      {/* Expand arrow */}
                      <span
                        className="text-xs transition-transform"
                        style={{
                          color: 'var(--app-text)', opacity: 0.4,
                          transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                          display: 'inline-block',
                        }}
                      >
                        &#9654;
                      </span>
                      {/* Region name */}
                      <span className="font-medium" style={{ color: region.custom_name ? 'var(--app-text)' : 'var(--app-text)', opacity: region.custom_name ? 1 : 0.6 }}>
                        {region.display_name}
                      </span>
                    </div>
                    {/* System count */}
                    <span className="text-sm px-2 py-0.5 rounded-full" style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--app-text)', opacity: 0.6 }}>
                      {region.system_count} {region.system_count === 1 ? 'system' : 'systems'}
                    </span>
                  </button>

                  {/* Expanded system list */}
                  {isExpanded && (
                    <div className="ml-10 mr-4 mb-2 mt-1 space-y-0.5">
                      {region.systems.map((sys) => {
                        const gc = gradeColors[sys.completeness_grade] || gradeColors['C']
                        const starColor = starTypeColors[sys.star_type] || starTypeColors['Unknown']

                        return (
                          <Link
                            key={sys.id}
                            to={`/systems/${sys.id}`}
                            className="flex items-center justify-between px-3 py-2 rounded-lg transition-colors"
                            style={{ color: 'var(--app-text)' }}
                            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.04)'}
                            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                          >
                            <div className="flex items-center gap-2">
                              {/* Star type dot */}
                              <span
                                className="inline-block w-2.5 h-2.5 rounded-full"
                                style={{ background: starColor }}
                                title={sys.star_type}
                              />
                              {/* System name */}
                              <span className="text-sm hover:underline">{sys.name}</span>
                            </div>
                            {/* Grade badge */}
                            <span
                              className="text-xs font-bold px-1.5 py-0.5 rounded"
                              style={{ background: gc.bg, color: gc.text }}
                            >
                              {sys.completeness_grade}
                            </span>
                          </Link>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
