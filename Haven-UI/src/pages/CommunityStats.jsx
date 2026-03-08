import React, { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import StatCard from '../components/StatCard'
import { getTagColorStyle as getTagColors } from '../utils/tagColors'
import { TYPE_INFO } from '../data/discoveryTypes'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts'

/**
 * Community Stats Overview — Route: /community-stats
 * Auth: Public (no login required).
 *
 * Showcases all Discord communities' contributions. Sections:
 *   - Grand total stat cards (systems, discoveries, communities, contributors)
 *   - Clickable community cards with manual/extractor upload split bars
 *   - Activity timeline (area chart: manual, extractor, discoveries over time)
 *   - Discovery type breakdown (bar chart + type cards with percentages)
 *   - Side-by-side contributor leaderboards (manual vs extractor) with community tags
 *
 * API endpoints (all public, no auth):
 *   GET /api/public/community-overview     — per-community stats + grand totals
 *   GET /api/public/contributors           — ranked contributor list with upload method
 *   GET /api/public/activity-timeline      — combined systems + discoveries timeline
 *   GET /api/public/discovery-breakdown    — discovery counts by type
 */

// Rank badge colors
const rankStyles = {
  1: { bg: 'rgba(255, 215, 0, 0.15)', border: 'rgba(255, 215, 0, 0.3)', text: '#FFD700' },
  2: { bg: 'rgba(192, 192, 192, 0.15)', border: 'rgba(192, 192, 192, 0.3)', text: '#C0C0C0' },
  3: { bg: 'rgba(205, 127, 50, 0.15)', border: 'rgba(205, 127, 50, 0.3)', text: '#CD7F32' },
}

// Chart tooltip
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="rounded-lg p-3 shadow-xl" style={{ background: 'var(--app-card)', border: '1px solid rgba(255,255,255,0.1)' }}>
      <div className="text-xs font-medium mb-2" style={{ color: 'var(--app-text)' }}>{label}</div>
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center justify-between gap-4 text-sm">
          <span style={{ color: entry.color }}>{entry.name}:</span>
          <span className="font-semibold" style={{ color: 'var(--app-text)' }}>{entry.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function CommunityStats() {
  const [loading, setLoading] = useState(true)
  const [overview, setOverview] = useState(null)
  const [contributors, setContributors] = useState([])
  const [timeline, setTimeline] = useState([])
  const [typeBreakdown, setTypeBreakdown] = useState([])

  // Fetch all four data sources in parallel on mount.
  // safeFetch returns fallback on HTTP error or network failure, so one
  // broken endpoint doesn't prevent the rest of the page from rendering.
  useEffect(() => {
    const safeFetch = (url, fallback = {}) =>
      fetch(url).then(r => r.ok ? r.json() : fallback).catch(() => fallback)

    Promise.all([
      safeFetch('/api/public/community-overview', {}),
      safeFetch('/api/public/contributors', {}),
      safeFetch('/api/public/activity-timeline', {}),
      safeFetch('/api/public/discovery-breakdown', {}),
    ])
      .then(([overviewData, contribData, timelineData, breakdownData]) => {
        setOverview(overviewData)
        setContributors(contribData.contributors || [])
        setTimeline(timelineData.timeline || [])
        setTypeBreakdown(breakdownData.breakdown || [])
      })
      .finally(() => setLoading(false))
  }, [])

  // Format type breakdown for bar chart
  const formattedTypeBreakdown = useMemo(() => {
    return typeBreakdown.map(item => ({
      ...item,
      label: TYPE_INFO[item.type_slug]?.label || item.type_slug || 'Other',
      emoji: TYPE_INFO[item.type_slug]?.emoji || '',
      fill: TYPE_INFO[item.type_slug]?.color || '#737373'
    }))
  }, [typeBreakdown])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg" style={{ color: 'var(--app-text)', opacity: 0.5 }}>Loading community stats...</div>
      </div>
    )
  }

  const totals = overview?.totals || {}
  const communities = overview?.communities || []

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold" style={{ color: 'var(--app-text)' }}>Community Stats</h1>
        <p className="mt-2 text-sm" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
          Celebrating our community's contributions to mapping the universe
        </p>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard title="Systems Mapped" value={(totals.total_systems || 0).toLocaleString()} />
        <StatCard title="Discoveries" value={(totals.total_discoveries || 0).toLocaleString()} />
        <StatCard title="Communities" value={totals.total_communities || 0} />
        <StatCard title="Contributors" value={(totals.total_contributors || 0).toLocaleString()} />
      </div>

      {/* Community Cards Grid */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>Communities</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {communities.map(community => {
            const colors = getTagColors(community.discord_tag)
            const totalMethod = community.manual_systems + community.extractor_systems
            const manualPct = totalMethod > 0 ? Math.round((community.manual_systems / totalMethod) * 100) : 0
            const extractorPct = totalMethod > 0 ? 100 - manualPct : 0

            return (
              <Link
                key={community.discord_tag}
                to={`/community-stats/${encodeURIComponent(community.discord_tag)}`}
                className="rounded-xl p-5 block transition-all hover:scale-[1.02] hover:shadow-lg cursor-pointer"
                style={{ background: colors.bg, border: `1px solid ${colors.border}`, textDecoration: 'none' }}
              >
                {/* Community name */}
                <div className="flex items-center gap-2 mb-4">
                  <span
                    className="inline-block w-3 h-3 rounded-full"
                    style={{ background: colors.text }}
                  />
                  <span className="text-lg font-bold" style={{ color: colors.text }}>
                    {community.display_name}
                  </span>
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div>
                    <div className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>
                      {community.total_systems.toLocaleString()}
                    </div>
                    <div className="text-xs" style={{ color: 'var(--app-text)', opacity: 0.5 }}>Systems</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>
                      {community.total_discoveries.toLocaleString()}
                    </div>
                    <div className="text-xs" style={{ color: 'var(--app-text)', opacity: 0.5 }}>Discoveries</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>
                      {community.unique_contributors}
                    </div>
                    <div className="text-xs" style={{ color: 'var(--app-text)', opacity: 0.5 }}>Members</div>
                  </div>
                </div>

                {/* Upload method bar */}
                {totalMethod > 0 && (
                  <div>
                    <div className="flex items-center justify-between text-xs mb-1" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
                      <span>Manual: {community.manual_systems}</span>
                      <span>Extractor: {community.extractor_systems}</span>
                    </div>
                    <div className="w-full h-2 rounded-full overflow-hidden flex" style={{ background: 'rgba(255,255,255,0.05)' }}>
                      {manualPct > 0 && (
                        <div
                          className="h-full"
                          style={{ width: `${manualPct}%`, background: '#06b6d4' }}
                          title={`Manual: ${manualPct}%`}
                        />
                      )}
                      {extractorPct > 0 && (
                        <div
                          className="h-full"
                          style={{ width: `${extractorPct}%`, background: '#a855f7' }}
                          title={`Extractor: ${extractorPct}%`}
                        />
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1.5">
                      <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--app-text)', opacity: 0.5 }}>
                        <span className="inline-block w-2 h-2 rounded-full" style={{ background: '#06b6d4' }} /> Manual
                      </div>
                      <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--app-text)', opacity: 0.5 }}>
                        <span className="inline-block w-2 h-2 rounded-full" style={{ background: '#a855f7' }} /> Extractor
                      </div>
                    </div>
                  </div>
                )}
              </Link>
            )
          })}
        </div>
      </div>

      {/* Activity Timeline */}
      <div
        className="rounded-xl p-4 mb-8"
        style={{
          background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
          border: '1px solid rgba(255,255,255,0.04)'
        }}
      >
        <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>Activity Timeline</h2>
        {timeline.length === 0 ? (
          <div className="text-center py-12" style={{ color: 'var(--app-text)', opacity: 0.5 }}>
            No activity data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={timeline} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="manualGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="extractorGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="discoveriesGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis
                dataKey="date"
                tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }}
                axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                tickLine={{ stroke: 'rgba(255,255,255,0.1)' }}
              />
              <YAxis
                tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }}
                axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                tickLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                allowDecimals={false}
              />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="manual" name="Manual" stroke="#06b6d4" fill="url(#manualGrad)" strokeWidth={2} />
              <Area type="monotone" dataKey="extractor" name="Extractor" stroke="#a855f7" fill="url(#extractorGrad)" strokeWidth={2} />
              <Area type="monotone" dataKey="discoveries" name="Discoveries" stroke="#22c55e" fill="url(#discoveriesGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Discovery Type Breakdown */}
      {formattedTypeBreakdown.length > 0 && (
        <div
          className="rounded-xl p-4 mb-8"
          style={{
            background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
            border: '1px solid rgba(255,255,255,0.04)'
          }}
        >
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>Discovery Types</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={formattedTypeBreakdown} margin={{ top: 10, right: 10, left: 0, bottom: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  angle={-35}
                  textAnchor="end"
                />
                <YAxis
                  tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  allowDecimals={false}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="count" name="Discoveries" radius={[4, 4, 0, 0]}>
                  {formattedTypeBreakdown.map((entry, index) => (
                    <Cell key={index} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {formattedTypeBreakdown.map((item) => (
                <div
                  key={item.type_slug}
                  className="p-3 rounded-lg"
                  style={{ background: `${item.fill}15`, border: `1px solid ${item.fill}30` }}
                >
                  <div className="text-xl mb-1">{item.emoji}</div>
                  <div className="text-sm font-medium" style={{ color: item.fill }}>{item.label}</div>
                  <div className="text-2xl font-bold mt-1" style={{ color: 'var(--app-text)' }}>
                    {item.count}
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: 'var(--app-text)', opacity: 0.5 }}>
                    {item.percentage}% of total
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Contributors — Manual & Extractor Side-by-Side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Manual Submissions */}
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
                        <th className="text-left py-2 px-2 font-medium" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Community</th>
                        <th className="text-right py-2 px-2 font-medium" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Systems</th>
                      </tr>
                    </thead>
                    <tbody>
                      {manualList.map((c) => {
                        const rs = rankStyles[c._rank]
                        const tags = (c.discord_tags || '').split(',').filter(Boolean)
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
                            <td className="py-2.5 px-2 font-medium" style={{ color: 'var(--app-text)' }}>{c.username}</td>
                            <td className="py-2.5 px-2">
                              <div className="flex flex-wrap gap-1">
                                {tags.map(tag => {
                                  const tc = getTagColors(tag.trim())
                                  return (
                                    <span key={tag} className="px-1.5 py-0.5 rounded-full text-xs" style={{ background: tc.bg, border: `1px solid ${tc.border}`, color: tc.text }}>
                                      {tag.trim()}
                                    </span>
                                  )
                                })}
                              </div>
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

        {/* Extractor Submissions */}
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
                        <th className="text-left py-2 px-2 font-medium" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Community</th>
                        <th className="text-right py-2 px-2 font-medium" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Systems</th>
                      </tr>
                    </thead>
                    <tbody>
                      {extractorList.map((c) => {
                        const rs = rankStyles[c._rank]
                        const tags = (c.discord_tags || '').split(',').filter(Boolean)
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
                            <td className="py-2.5 px-2 font-medium" style={{ color: 'var(--app-text)' }}>{c.username}</td>
                            <td className="py-2.5 px-2">
                              <div className="flex flex-wrap gap-1">
                                {tags.map(tag => {
                                  const tc = getTagColors(tag.trim())
                                  return (
                                    <span key={tag} className="px-1.5 py-0.5 rounded-full text-xs" style={{ background: tc.bg, border: `1px solid ${tc.border}`, color: tc.text }}>
                                      {tag.trim()}
                                    </span>
                                  )
                                })}
                              </div>
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

    </div>
  )
}
