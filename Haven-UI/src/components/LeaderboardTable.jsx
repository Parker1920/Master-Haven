import React, { useState, useMemo } from 'react'

const rankColors = {
  1: { bg: 'rgba(255, 215, 0, 0.15)', border: 'rgba(255, 215, 0, 0.3)', text: '#FFD700' },
  2: { bg: 'rgba(192, 192, 192, 0.15)', border: 'rgba(192, 192, 192, 0.3)', text: '#C0C0C0' },
  3: { bg: 'rgba(205, 127, 50, 0.15)', border: 'rgba(205, 127, 50, 0.3)', text: '#CD7F32' },
}

const tagColors = {
  'Haven': 'bg-cyan-500',
  'IEA': 'bg-green-500',
  'B.E.S': 'bg-orange-500',
  'ARCH': 'bg-purple-500',
  'TBH': 'bg-yellow-500',
  'EVRN': 'bg-pink-500',
  'Personal': 'bg-gray-500',
}

const hashColorPalette = ['bg-indigo-500', 'bg-violet-500', 'bg-rose-500', 'bg-emerald-500', 'bg-amber-500', 'bg-sky-500']

// Module-level cache for hash-computed colors - persists across renders
const tagColorCache = new Map()

function getTagColor(tag) {
  if (tagColors[tag]) return tagColors[tag]

  // Check cache first
  if (tagColorCache.has(tag)) return tagColorCache.get(tag)

  // Hash-based color for unknown tags - compute once and cache
  let hash = 0
  for (let i = 0; i < (tag || '').length; i++) {
    hash = tag.charCodeAt(i) + ((hash << 5) - hash)
  }
  const color = hashColorPalette[Math.abs(hash) % hashColorPalette.length]
  tagColorCache.set(tag, color)
  return color
}

export default function LeaderboardTable({ data, showCommunity = true, showRank = true, loading = false }) {
  const [expandedRows, setExpandedRows] = useState({})

  const toggleRow = (index) => {
    setExpandedRows(prev => ({
      ...prev,
      [index]: !prev[index]
    }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: 'var(--app-primary)' }}></div>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-12" style={{ color: 'var(--app-text)', opacity: 0.5 }}>
        No submission data found
      </div>
    )
  }

  // Count columns for colspan
  const colCount = (showRank ? 1 : 0) + 1 + (showCommunity ? 1 : 0) + 4

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
            {showRank && (
              <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--app-accent-3)' }}>
                Rank
              </th>
            )}
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--app-accent-3)' }}>
              Submitter
            </th>
            {showCommunity && (
              <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--app-accent-3)' }}>
                Source
              </th>
            )}
            <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--app-accent-3)' }}>
              Total
            </th>
            <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--app-accent-3)' }}>
              Approved
            </th>
            <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--app-accent-3)' }}>
              Rejected
            </th>
            <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--app-accent-3)' }}>
              Rate
            </th>
          </tr>
        </thead>
        <tbody>
          {data.map((entry, index) => {
            const rank = entry.rank || index + 1
            const rankStyle = rankColors[rank] || null
            const hasBreakdown = entry.tag_breakdown && entry.tag_breakdown.length > 1
            const isExpanded = expandedRows[index]

            return (
              <React.Fragment key={`${entry.username}-${index}`}>
                <tr
                  className={`transition-colors hover:bg-white/5 ${hasBreakdown ? 'cursor-pointer' : ''}`}
                  style={{
                    borderBottom: isExpanded ? 'none' : '1px solid rgba(255,255,255,0.05)',
                    ...(rankStyle && {
                      background: rankStyle.bg,
                    })
                  }}
                  onClick={hasBreakdown ? () => toggleRow(index) : undefined}
                >
                  {showRank && (
                    <td className="py-3 px-4">
                      <div
                        className="w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm"
                        style={{
                          background: rankStyle ? rankStyle.bg : 'rgba(255,255,255,0.05)',
                          border: rankStyle ? `2px solid ${rankStyle.border}` : '1px solid rgba(255,255,255,0.1)',
                          color: rankStyle ? rankStyle.text : 'var(--app-text)'
                        }}
                      >
                        {rank}
                      </div>
                    </td>
                  )}
                  <td className="py-3 px-4">
                    <div className="font-medium" style={{ color: 'var(--app-text)' }}>
                      {entry.username || 'Unknown'}
                    </div>
                    {entry.last_submission && (
                      <div className="text-xs mt-0.5" style={{ color: 'var(--app-text)', opacity: 0.5 }}>
                        Last: {new Date(entry.last_submission).toLocaleDateString()}
                      </div>
                    )}
                  </td>
                  {showCommunity && (
                    <td className="py-3 px-4">
                      {(entry.discord_tags || entry.discord_tag) ? (
                        <div className="flex flex-wrap items-center gap-1">
                          {(entry.discord_tags || entry.discord_tag || '').split(',').filter(Boolean).map((tag, i) => (
                            <span key={i} className={`px-2 py-0.5 rounded text-xs font-medium text-white ${getTagColor(tag.trim())}`}>
                              {tag.trim()}
                            </span>
                          ))}
                          {hasBreakdown && (
                            <span className="ml-1 text-xs" style={{ color: 'var(--app-primary)' }}>
                              {isExpanded ? '▲' : '▼'}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs" style={{ color: 'var(--app-text)', opacity: 0.5 }}>-</span>
                      )}
                    </td>
                  )}
                  <td className="py-3 px-4 text-right font-semibold" style={{ color: 'var(--app-text)' }}>
                    {entry.total_submissions}
                  </td>
                  <td className="py-3 px-4 text-right font-medium" style={{ color: '#22c55e' }}>
                    {entry.approved || 0}
                  </td>
                  <td className="py-3 px-4 text-right font-medium" style={{ color: '#ef4444' }}>
                    {entry.rejected || 0}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div
                        className="h-2 rounded-full overflow-hidden"
                        style={{
                          width: '60px',
                          background: 'rgba(255,255,255,0.1)'
                        }}
                      >
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${entry.approval_rate}%`,
                            background: entry.approval_rate >= 80 ? '#22c55e' : entry.approval_rate >= 50 ? '#f59e0b' : '#ef4444'
                          }}
                        />
                      </div>
                      <span
                        className="text-sm font-medium"
                        style={{
                          color: entry.approval_rate >= 80 ? '#22c55e' : entry.approval_rate >= 50 ? '#f59e0b' : '#ef4444'
                        }}
                      >
                        {entry.approval_rate}%
                      </span>
                    </div>
                  </td>
                </tr>

                {/* Expanded breakdown row */}
                {hasBreakdown && isExpanded && (
                  <tr>
                    <td colSpan={colCount} style={{ padding: 0 }}>
                      <div
                        className="mx-4 mb-3 rounded-lg overflow-hidden"
                        style={{
                          background: 'rgba(0, 0, 0, 0.3)',
                          border: '1px solid rgba(255,255,255,0.1)'
                        }}
                      >
                        <table className="w-full">
                          <thead>
                            <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                              <th className="text-left py-2 px-4 text-xs font-medium" style={{ color: 'var(--app-accent-3)' }}>
                                Community
                              </th>
                              <th className="text-right py-2 px-4 text-xs font-medium" style={{ color: 'var(--app-accent-3)' }}>
                                Total
                              </th>
                              <th className="text-right py-2 px-4 text-xs font-medium" style={{ color: 'var(--app-accent-3)' }}>
                                Approved
                              </th>
                              <th className="text-right py-2 px-4 text-xs font-medium" style={{ color: 'var(--app-accent-3)' }}>
                                Rejected
                              </th>
                              <th className="text-right py-2 px-4 text-xs font-medium" style={{ color: 'var(--app-accent-3)' }}>
                                Rate
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {entry.tag_breakdown.map((breakdown, bIndex) => {
                              const bRate = breakdown.total > 0
                                ? Math.round((breakdown.approved / breakdown.total) * 100)
                                : 0
                              return (
                                <tr
                                  key={bIndex}
                                  style={{ borderTop: bIndex > 0 ? '1px solid rgba(255,255,255,0.05)' : 'none' }}
                                >
                                  <td className="py-2 px-4">
                                    <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${getTagColor(breakdown.discord_tag)}`}>
                                      {breakdown.discord_tag || '-'}
                                    </span>
                                  </td>
                                  <td className="py-2 px-4 text-right text-sm" style={{ color: 'var(--app-text)' }}>
                                    {breakdown.total}
                                  </td>
                                  <td className="py-2 px-4 text-right text-sm" style={{ color: '#22c55e' }}>
                                    {breakdown.approved || 0}
                                  </td>
                                  <td className="py-2 px-4 text-right text-sm" style={{ color: '#ef4444' }}>
                                    {breakdown.rejected || 0}
                                  </td>
                                  <td className="py-2 px-4 text-right text-sm" style={{
                                    color: bRate >= 80 ? '#22c55e' : bRate >= 50 ? '#f59e0b' : '#ef4444'
                                  }}>
                                    {bRate}%
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
