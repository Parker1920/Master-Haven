import React, { useState, useEffect, useContext, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import DateRangePicker from '../components/DateRangePicker'
import LeaderboardTable from '../components/LeaderboardTable'
import SubmissionChart from '../components/SubmissionChart'
import StatCard from '../components/StatCard'
import { AuthContext } from '../utils/AuthContext'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, BarChart, Bar, Cell
} from 'recharts'
import { format, parseISO } from 'date-fns'

// Discovery type display info
const TYPE_INFO = {
  fauna: { label: 'Fauna', emoji: '🦗', color: '#22c55e' },
  flora: { label: 'Flora', emoji: '🌿', color: '#10b981' },
  mineral: { label: 'Mineral', emoji: '💎', color: '#6366f1' },
  ancient: { label: 'Ancient', emoji: '🏛️', color: '#f59e0b' },
  history: { label: 'History', emoji: '📜', color: '#eab308' },
  bones: { label: 'Bones', emoji: '🦴', color: '#a3a3a3' },
  alien: { label: 'Alien', emoji: '👽', color: '#8b5cf6' },
  starship: { label: 'Starship', emoji: '🚀', color: '#3b82f6' },
  multitool: { label: 'Multi-tool', emoji: '⚙️', color: '#64748b' },
  lore: { label: 'Lore', emoji: '📖', color: '#d946ef' },
  base: { label: 'Base', emoji: '🏠', color: '#f97316' },
  other: { label: 'Other', emoji: '🆕', color: '#737373' }
}

// Custom tooltip for charts
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

// Rank display colors
const rankColors = {
  1: { bg: 'rgba(255, 215, 0, 0.15)', border: 'rgba(255, 215, 0, 0.3)', text: '#FFD700' },
  2: { bg: 'rgba(192, 192, 192, 0.15)', border: 'rgba(192, 192, 192, 0.3)', text: '#C0C0C0' },
  3: { bg: 'rgba(205, 127, 50, 0.15)', border: 'rgba(205, 127, 50, 0.3)', text: '#CD7F32' },
}

export default function PartnerAnalytics() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const { isSuperAdmin, isAdmin, user } = auth

  const [loading, setLoading] = useState(true)

  // Date/period state
  const [dateRange, setDateRange] = useState({ startDate: null, endDate: null })
  const [period, setPeriod] = useState('month')

  // Community selector (super admin only)
  const [discordTags, setDiscordTags] = useState([])
  const [selectedCommunity, setSelectedCommunity] = useState('')

  // Data state
  const [overview, setOverview] = useState(null)
  const [subLeaderboard, setSubLeaderboard] = useState([])
  const [subTotals, setSubTotals] = useState({})
  const [discLeaderboard, setDiscLeaderboard] = useState([])
  const [discTotals, setDiscTotals] = useState({})
  const [subTimeline, setSubTimeline] = useState([])
  const [discTimeline, setDiscTimeline] = useState([])
  const [typeBreakdown, setTypeBreakdown] = useState([])

  // Redirect if not admin
  useEffect(() => {
    if (!auth.loading && !isAdmin) {
      navigate('/')
    }
  }, [auth.loading, isAdmin, navigate])

  // Fetch discord tags for super admin
  useEffect(() => {
    if (isSuperAdmin) {
      axios.get('/api/discord_tags').then(r => {
        setDiscordTags(r.data.tags || [])
      }).catch(() => {})
    }
  }, [isSuperAdmin])

  // Fetch all data when filters change
  useEffect(() => {
    if (!isAdmin) return

    const fetchData = async () => {
      setLoading(true)
      try {
        const params = {}
        if (dateRange.startDate && dateRange.endDate) {
          params.start_date = dateRange.startDate.toISOString().split('T')[0]
          params.end_date = dateRange.endDate.toISOString().split('T')[0]
        } else if (period) {
          params.period = period
        }
        if (selectedCommunity) {
          params.discord_tag = selectedCommunity
        }

        const opts = { params, withCredentials: true }

        // Fetch all data in parallel
        const [overviewRes, subLbRes, discLbRes, subTlRes, discTlRes, typesRes] = await Promise.all([
          axios.get('/api/analytics/partner-overview', opts),
          axios.get('/api/analytics/submission-leaderboard', opts),
          axios.get('/api/analytics/discovery-leaderboard', opts),
          axios.get('/api/analytics/submissions-timeline', {
            params: { ...params, granularity: period === 'year' ? 'month' : period === 'month' ? 'week' : 'day' },
            withCredentials: true
          }),
          axios.get('/api/analytics/discovery-timeline', {
            params: { ...params, granularity: period === 'year' ? 'month' : period === 'month' ? 'week' : 'day' },
            withCredentials: true
          }),
          axios.get('/api/analytics/discovery-type-breakdown', opts)
        ])

        setOverview(overviewRes.data)
        setSubLeaderboard(subLbRes.data.leaderboard || [])
        setSubTotals(subLbRes.data.totals || {})
        setDiscLeaderboard(discLbRes.data.leaderboard || [])
        setDiscTotals(discLbRes.data.totals || {})
        setSubTimeline(subTlRes.data.timeline || [])
        setDiscTimeline(discTlRes.data.timeline || [])
        setTypeBreakdown(typesRes.data.breakdown || [])
      } catch (err) {
        console.error('Failed to fetch partner analytics:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [dateRange, period, selectedCommunity, isSuperAdmin, isAdmin])

  const handleDateChange = ({ startDate, endDate }) => {
    setDateRange({ startDate, endDate })
    if (startDate || endDate) setPeriod('')
  }

  const handlePeriodChange = (newPeriod) => {
    setPeriod(newPeriod)
    setDateRange({ startDate: null, endDate: null })
  }

  // Format discovery timeline for chart
  const formattedDiscTimeline = useMemo(() => {
    return discTimeline.map(item => ({
      ...item,
      displayDate: item.date.includes('W')
        ? item.date
        : item.date.length === 7
          ? item.date
          : format(parseISO(item.date), 'MMM d')
    }))
  }, [discTimeline])

  // Format type breakdown for bar chart
  const formattedTypeBreakdown = useMemo(() => {
    return typeBreakdown.map(item => ({
      ...item,
      label: TYPE_INFO[item.type_slug]?.label || item.type_slug || 'Other',
      emoji: TYPE_INFO[item.type_slug]?.emoji || '',
      fill: TYPE_INFO[item.type_slug]?.color || '#737373'
    }))
  }, [typeBreakdown])

  // Community name display
  const communityName = useMemo(() => {
    if (selectedCommunity) {
      const tag = discordTags.find(t => t.tag === selectedCommunity)
      return tag?.name || selectedCommunity
    }
    if (!isSuperAdmin && user?.discord_tag) {
      return user.discord_tag
    }
    return 'All Communities'
  }, [selectedCommunity, discordTags, isSuperAdmin, user])

  if (auth.loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-400">Loading...</div>
      </div>
    )
  }

  if (!isAdmin) return null

  const subs = overview?.submissions || {}
  const discs = overview?.discoveries || {}
  const approvalRate = subs.total > 0
    ? ((subs.approved / subs.total) * 100).toFixed(1)
    : 0

  return (
    <div className="min-h-screen p-6" style={{ background: 'var(--app-bg)' }}>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>
            Partner Analytics
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
            {communityName} — Submissions & Discovery Statistics
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {/* Period quick filters */}
          <div className="flex items-center rounded-lg overflow-hidden" style={{ background: 'var(--app-card)', border: '1px solid rgba(255,255,255,0.1)' }}>
            {['week', 'month', 'year', 'all'].map((p) => (
              <button
                key={p}
                onClick={() => handlePeriodChange(p)}
                className="px-3 py-2 text-sm font-medium transition-colors"
                style={{
                  background: period === p ? 'var(--app-primary)' : 'transparent',
                  color: period === p ? '#000' : 'var(--app-text)'
                }}
              >
                {p === 'all' ? 'All Time' : p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
          <DateRangePicker
            startDate={dateRange.startDate}
            endDate={dateRange.endDate}
            onChange={handleDateChange}
          />
          {isSuperAdmin && (
            <select
              value={selectedCommunity}
              onChange={(e) => setSelectedCommunity(e.target.value)}
              className="px-3 py-2 rounded-lg text-sm"
              style={{
                background: 'var(--app-card)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'var(--app-text)'
              }}
            >
              <option value="">All Communities</option>
              {discordTags.map((tag) => (
                <option key={tag.tag} value={tag.tag}>{tag.name}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          title="System Submissions"
          value={(subs.total || 0).toLocaleString()}
          subtitle={`${subs.approved || 0} approved, ${subs.pending || 0} pending`}
          trend={overview?.activity_trend?.map(d => d.submissions)}
        />
        <StatCard
          title="Approval Rate"
          value={`${approvalRate}%`}
          subtitle={subs.total > 0 ? `${subs.rejected || 0} rejected` : 'No submissions'}
        />
        <StatCard
          title="Total Discoveries"
          value={(discs.total || 0).toLocaleString()}
          subtitle={`${discs.unique_types || 0} types discovered`}
          trend={overview?.activity_trend?.map(d => d.discoveries)}
        />
        <StatCard
          title="Active Members"
          value={((subs.active_submitters || 0) + (discs.active_discoverers || 0)).toLocaleString()}
          subtitle={`${subs.active_submitters || 0} submitters, ${discs.active_discoverers || 0} discoverers`}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Submission Timeline */}
        <div
          className="rounded-xl p-4"
          style={{
            background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
            border: '1px solid rgba(255,255,255,0.04)'
          }}
        >
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
            System Submissions Over Time
          </h2>
          <SubmissionChart data={subTimeline} loading={loading} height={280} />
        </div>

        {/* Discovery Timeline */}
        <div
          className="rounded-xl p-4"
          style={{
            background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
            border: '1px solid rgba(255,255,255,0.04)'
          }}
        >
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
            Discoveries Over Time
          </h2>
          {loading ? (
            <div className="flex items-center justify-center" style={{ height: 280 }}>
              <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: 'var(--app-primary)' }}></div>
            </div>
          ) : formattedDiscTimeline.length === 0 ? (
            <div className="flex items-center justify-center" style={{ height: 280, color: 'var(--app-text)', opacity: 0.5 }}>
              No discovery data available
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={formattedDiscTimeline} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorDiscoveries" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis
                  dataKey="displayDate"
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
                <Legend
                  wrapperStyle={{ paddingTop: '10px' }}
                  formatter={(value) => <span style={{ color: 'var(--app-text)', fontSize: '12px' }}>{value}</span>}
                />
                <Area
                  type="monotone"
                  dataKey="discoveries"
                  name="Discoveries"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  fill="url(#colorDiscoveries)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Discovery Type Breakdown */}
      <div
        className="rounded-xl p-4 mb-6"
        style={{
          background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
          border: '1px solid rgba(255,255,255,0.04)'
        }}
      >
        <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
          Discovery Type Breakdown
        </h2>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: 'var(--app-primary)' }}></div>
          </div>
        ) : formattedTypeBreakdown.length === 0 ? (
          <div className="text-center py-12" style={{ color: 'var(--app-text)', opacity: 0.5 }}>
            No discovery data available
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Bar chart */}
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

            {/* Grid of type cards */}
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
        )}
      </div>

      {/* Two Leaderboards Side-by-Side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Submission Leaderboard */}
        <div
          className="rounded-xl p-4"
          style={{
            background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
            border: '1px solid rgba(255,255,255,0.04)'
          }}
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold" style={{ color: 'var(--app-text)' }}>
              System Submission Leaderboard
            </h2>
            <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
              Top {subLeaderboard.length}
            </div>
          </div>
          <LeaderboardTable
            data={subLeaderboard}
            showCommunity={isSuperAdmin && !selectedCommunity}
            loading={loading}
          />
        </div>

        {/* Discovery Leaderboard */}
        <div
          className="rounded-xl p-4"
          style={{
            background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
            border: '1px solid rgba(255,255,255,0.04)'
          }}
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold" style={{ color: 'var(--app-text)' }}>
              Discovery Leaderboard
            </h2>
            <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
              {discTotals.total_discoveries || 0} discoveries by {discTotals.total_discoverers || 0} explorers
            </div>
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: 'var(--app-primary)' }}></div>
            </div>
          ) : discLeaderboard.length === 0 ? (
            <div className="text-center py-12" style={{ color: 'var(--app-text)', opacity: 0.5 }}>
              No discovery data found
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                    <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--app-accent-3)' }}>Rank</th>
                    <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--app-accent-3)' }}>Discoverer</th>
                    <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--app-accent-3)' }}>Discoveries</th>
                    <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--app-accent-3)' }}>Types</th>
                  </tr>
                </thead>
                <tbody>
                  {discLeaderboard.map((entry) => {
                    const rs = rankColors[entry.rank] || null
                    return (
                      <tr
                        key={entry.normalized_name}
                        className="transition-colors hover:bg-white/5"
                        style={{
                          borderBottom: '1px solid rgba(255,255,255,0.05)',
                          ...(rs && { background: rs.bg })
                        }}
                      >
                        <td className="py-3 px-4">
                          <div
                            className="w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm"
                            style={{
                              background: rs ? rs.bg : 'rgba(255,255,255,0.05)',
                              border: rs ? `2px solid ${rs.border}` : '1px solid rgba(255,255,255,0.1)',
                              color: rs ? rs.text : 'var(--app-text)'
                            }}
                          >
                            {entry.rank}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <div className="font-medium" style={{ color: 'var(--app-text)' }}>
                            {entry.discoverer || 'Unknown'}
                          </div>
                          {entry.last_discovery && (
                            <div className="text-xs mt-0.5" style={{ color: 'var(--app-text)', opacity: 0.5 }}>
                              Last: {new Date(entry.last_discovery).toLocaleDateString()}
                            </div>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right font-semibold" style={{ color: '#8b5cf6' }}>
                          {entry.total_discoveries}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-1 flex-wrap">
                            {(entry.type_slugs || []).slice(0, 5).map(slug => (
                              <span key={slug} title={TYPE_INFO[slug]?.label || slug} className="text-sm">
                                {TYPE_INFO[slug]?.emoji || slug}
                              </span>
                            ))}
                            {(entry.type_slugs || []).length > 5 && (
                              <span className="text-xs" style={{ color: 'var(--app-text)', opacity: 0.5 }}>
                                +{entry.type_slugs.length - 5}
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
