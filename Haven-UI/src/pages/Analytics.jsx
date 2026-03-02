import React, { useState, useEffect, useContext, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import DateRangePicker from '../components/DateRangePicker'
import LeaderboardTable from '../components/LeaderboardTable'
import SubmissionChart from '../components/SubmissionChart'
import CommunityPieChart from '../components/CommunityPieChart'
import StatCard from '../components/StatCard'
import { AuthContext } from '../utils/AuthContext'

export default function Analytics() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const { isSuperAdmin, isAdmin, user } = auth

  const [loading, setLoading] = useState(true)

  // Tab state
  const [activeTab, setActiveTab] = useState('manual')

  // Date range state
  const [dateRange, setDateRange] = useState({ startDate: null, endDate: null })
  const [period, setPeriod] = useState('month')

  // Data state
  const [leaderboard, setLeaderboard] = useState([])
  const [totals, setTotals] = useState({ total_submissions: 0, total_approved: 0, total_rejected: 0 })
  const [timeline, setTimeline] = useState([])
  const [communities, setCommunities] = useState([])
  const [selectedCommunity, setSelectedCommunity] = useState('')
  const [discordTags, setDiscordTags] = useState([])

  // Source breakdown (for overview bar + tab badges)
  const [sourceBreakdown, setSourceBreakdown] = useState([])

  // Extractor-specific data
  const [extractorSummary, setExtractorSummary] = useState(null)

  // Redirect if not admin
  useEffect(() => {
    if (!auth.loading && !isAdmin) {
      navigate('/')
    }
  }, [auth.loading, isAdmin, navigate])

  // Fetch discord tags
  useEffect(() => {
    const fetchTags = async () => {
      try {
        const res = await axios.get('/api/discord_tags')
        setDiscordTags(res.data.tags || [])
      } catch (err) {
        console.error('Failed to fetch discord tags:', err)
      }
    }
    if (isAdmin) {
      fetchTags()
    }
  }, [isAdmin])

  // Fetch data when filters or tab changes
  useEffect(() => {
    if (!isAdmin) return

    const fetchData = async () => {
      setLoading(true)
      try {
        const params = {}

        // Use period for quick filters, or dates for custom range
        if (dateRange.startDate && dateRange.endDate) {
          params.start_date = dateRange.startDate.toISOString().split('T')[0]
          params.end_date = dateRange.endDate.toISOString().split('T')[0]
        } else if (period) {
          params.period = period
        }

        if (selectedCommunity) {
          params.discord_tag = selectedCommunity
        }

        // Add source filter based on active tab
        const sourceParam = activeTab === 'manual' ? 'manual' : 'haven_extractor'

        // Fetch source-filtered data + source breakdown in parallel
        const requests = [
          // Source-filtered leaderboard
          axios.get('/api/analytics/submission-leaderboard', {
            params: { ...params, source: sourceParam },
            withCredentials: true
          }),
          // Source-filtered timeline
          axios.get('/api/analytics/submissions-timeline', {
            params: {
              ...params,
              source: sourceParam,
              granularity: period === 'year' ? 'month' : period === 'month' ? 'week' : 'day'
            },
            withCredentials: true
          }),
          // Source breakdown (unfiltered by source, for overview bar)
          axios.get('/api/analytics/source-breakdown', {
            params,
            withCredentials: true
          })
        ]

        // Community stats (super admin only)
        if (isSuperAdmin) {
          requests.push(
            axios.get('/api/analytics/community-stats', {
              params: { ...params, source: sourceParam },
              withCredentials: true
            })
          )
        }

        // Extractor summary (extractor tab only)
        if (activeTab === 'extractor') {
          requests.push(
            axios.get('/api/analytics/extractor-summary', {
              params: selectedCommunity ? { discord_tag: selectedCommunity } : {},
              withCredentials: true
            })
          )
        }

        const results = await Promise.all(requests)

        setLeaderboard(results[0].data.leaderboard || [])
        setTotals(results[0].data.totals || { total_submissions: 0, total_approved: 0, total_rejected: 0 })
        setTimeline(results[1].data.timeline || [])
        setSourceBreakdown(results[2].data.breakdown || [])

        if (isSuperAdmin) {
          setCommunities(results[3].data.communities || [])
          if (activeTab === 'extractor' && results[4]) {
            setExtractorSummary(results[4].data)
          }
        } else if (activeTab === 'extractor' && results[3]) {
          setExtractorSummary(results[3].data)
        }

      } catch (err) {
        console.error('Failed to fetch analytics:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [dateRange, period, selectedCommunity, isSuperAdmin, isAdmin, activeTab])

  const handleDateChange = ({ startDate, endDate }) => {
    setDateRange({ startDate, endDate })
    if (startDate || endDate) {
      setPeriod('') // Clear period when using custom dates
    }
  }

  const handlePeriodChange = (newPeriod) => {
    setPeriod(newPeriod)
    setDateRange({ startDate: null, endDate: null }) // Clear custom dates
  }

  // Show loading while auth is loading
  if (auth.loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-400">Loading...</div>
      </div>
    )
  }

  if (!isAdmin) {
    return null
  }

  // Derive counts from source breakdown for tab badges and overview bar
  const manualData = sourceBreakdown.find(s => s.source_type === 'manual') || { total: 0, approved: 0, rejected: 0, pending: 0 }
  const extractorData = sourceBreakdown.find(s => s.source_type === 'haven_extractor') || { total: 0, approved: 0, rejected: 0, pending: 0 }
  const grandTotal = manualData.total + extractorData.total
  const manualPct = grandTotal > 0 ? Math.round((manualData.total / grandTotal) * 100) : 0
  const extractorPct = grandTotal > 0 ? 100 - manualPct : 0

  // Memoize approval rate calculation
  const approvalRate = useMemo(() => {
    return totals.total_submissions > 0
      ? ((totals.total_approved / totals.total_submissions) * 100).toFixed(1)
      : 0
  }, [totals.total_submissions, totals.total_approved])

  const cardStyle = {
    background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
    border: '1px solid rgba(255,255,255,0.04)'
  }

  return (
    <div className="min-h-screen p-6" style={{ background: 'var(--app-bg)' }}>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>Analytics Dashboard</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
            Submission statistics and leaderboards
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

      {/* Source Overview Bar */}
      {grandTotal > 0 && (
        <div
          className="rounded-xl p-4 mb-6"
          style={cardStyle}
        >
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium" style={{ color: 'var(--app-text)', opacity: 0.7 }}>
              Submission Sources
            </h2>
            <div className="text-sm font-semibold" style={{ color: 'var(--app-text)' }}>
              {grandTotal.toLocaleString()} total
            </div>
          </div>
          {/* Proportional bar */}
          <div className="flex rounded-full overflow-hidden h-3 mb-3" style={{ background: 'rgba(255,255,255,0.05)' }}>
            {manualData.total > 0 && (
              <div
                className="transition-all duration-500"
                style={{ width: `${manualPct}%`, background: '#06b6d4' }}
                title={`Manual: ${manualData.total}`}
              />
            )}
            {extractorData.total > 0 && (
              <div
                className="transition-all duration-500"
                style={{ width: `${extractorPct}%`, background: '#a855f7' }}
                title={`Extractor: ${extractorData.total}`}
              />
            )}
          </div>
          {/* Legend */}
          <div className="flex items-center gap-6 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ background: '#06b6d4' }} />
              <span style={{ color: 'var(--app-text)' }}>
                Manual: <span className="font-semibold">{manualData.total.toLocaleString()}</span>
                <span style={{ opacity: 0.5 }}> ({manualPct}%)</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ background: '#a855f7' }} />
              <span style={{ color: 'var(--app-text)' }}>
                Extractor: <span className="font-semibold">{extractorData.total.toLocaleString()}</span>
                <span style={{ opacity: 0.5 }}> ({extractorPct}%)</span>
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Tab Switcher */}
      <div className="flex border-b mb-6" style={{ borderColor: 'rgba(255,255,255,0.1)' }}>
        <button
          className="px-5 py-3 text-sm font-medium border-b-2 transition-colors"
          style={{
            borderColor: activeTab === 'manual' ? '#06b6d4' : 'transparent',
            color: activeTab === 'manual' ? '#06b6d4' : 'var(--app-text)',
            opacity: activeTab === 'manual' ? 1 : 0.6
          }}
          onClick={() => setActiveTab('manual')}
        >
          Manual Submissions
          {manualData.total > 0 && (
            <span
              className="ml-2 px-2 py-0.5 text-xs rounded-full font-semibold"
              style={{ background: 'rgba(6, 182, 212, 0.15)', color: '#06b6d4' }}
            >
              {manualData.total.toLocaleString()}
            </span>
          )}
        </button>
        <button
          className="px-5 py-3 text-sm font-medium border-b-2 transition-colors"
          style={{
            borderColor: activeTab === 'extractor' ? '#a855f7' : 'transparent',
            color: activeTab === 'extractor' ? '#a855f7' : 'var(--app-text)',
            opacity: activeTab === 'extractor' ? 1 : 0.6
          }}
          onClick={() => setActiveTab('extractor')}
        >
          Haven Extractor
          {extractorData.total > 0 && (
            <span
              className="ml-2 px-2 py-0.5 text-xs rounded-full font-semibold"
              style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#a855f7' }}
            >
              {extractorData.total.toLocaleString()}
            </span>
          )}
        </button>
      </div>

      {/* === MANUAL TAB === */}
      {activeTab === 'manual' && (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard
              title="Manual Submissions"
              value={totals.total_submissions.toLocaleString()}
              subtitle={period === 'all' ? 'All time' : `This ${period}`}
            />
            <StatCard
              title="Approved"
              value={totals.total_approved.toLocaleString()}
              subtitle={`${((totals.total_approved / (totals.total_submissions || 1)) * 100).toFixed(1)}% of total`}
            />
            <StatCard
              title="Rejected"
              value={totals.total_rejected.toLocaleString()}
              subtitle={`${((totals.total_rejected / (totals.total_submissions || 1)) * 100).toFixed(1)}% of total`}
            />
            <StatCard
              title="Approval Rate"
              value={`${approvalRate}%`}
              subtitle={totals.total_submissions > 0 ? `${totals.total_approved} approved` : 'No submissions'}
            />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <div className="rounded-xl p-4" style={cardStyle}>
              <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
                Manual Submissions Over Time
              </h2>
              <SubmissionChart data={timeline} loading={loading} height={280} />
            </div>

            {isSuperAdmin && (
              <div className="rounded-xl p-4" style={cardStyle}>
                <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
                  Community Breakdown
                </h2>
                <CommunityPieChart data={communities} loading={loading} height={280} />
              </div>
            )}

            {!isSuperAdmin && (
              <div className="rounded-xl p-4" style={cardStyle}>
                <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
                  Your Community Stats
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg" style={{ background: 'rgba(0, 194, 179, 0.1)' }}>
                    <div className="text-3xl font-bold" style={{ color: 'var(--app-primary)' }}>
                      {leaderboard.length}
                    </div>
                    <div className="text-sm mt-1" style={{ color: 'var(--app-text)', opacity: 0.7 }}>
                      Active Submitters
                    </div>
                  </div>
                  <div className="p-4 rounded-lg" style={{ background: 'rgba(34, 197, 94, 0.1)' }}>
                    <div className="text-3xl font-bold" style={{ color: '#22c55e' }}>
                      {approvalRate}%
                    </div>
                    <div className="text-sm mt-1" style={{ color: 'var(--app-text)', opacity: 0.7 }}>
                      Approval Rate
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Leaderboard */}
          <div className="rounded-xl p-4" style={cardStyle}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold" style={{ color: 'var(--app-text)' }}>
                Manual Submission Leaderboard
              </h2>
              <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
                Top {leaderboard.length} submitters
              </div>
            </div>
            <LeaderboardTable
              data={leaderboard}
              showCommunity={isSuperAdmin && !selectedCommunity}
              loading={loading}
            />
          </div>
        </>
      )}

      {/* === EXTRACTOR TAB === */}
      {activeTab === 'extractor' && (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard
              title="Extractor Submissions"
              value={totals.total_submissions.toLocaleString()}
              subtitle={period === 'all' ? 'All time' : `This ${period}`}
            />
            <StatCard
              title="Registered Users"
              value={(extractorSummary?.registered_users || 0).toLocaleString()}
              subtitle={`${extractorSummary?.active_users_7d || 0} active this week`}
            />
            <StatCard
              title="Avg Per User"
              value={(extractorSummary?.avg_per_user || 0).toLocaleString()}
              subtitle="submissions per user"
            />
            <StatCard
              title="Approval Rate"
              value={`${approvalRate}%`}
              subtitle={totals.total_submissions > 0 ? `${totals.total_approved} approved` : 'No submissions'}
            />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <div className="rounded-xl p-4" style={cardStyle}>
              <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
                Extractor Submissions Over Time
              </h2>
              <SubmissionChart data={timeline} loading={loading} height={280} />
            </div>

            {isSuperAdmin && (
              <div className="rounded-xl p-4" style={cardStyle}>
                <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
                  Community Breakdown
                </h2>
                <CommunityPieChart data={communities} loading={loading} height={280} />
              </div>
            )}

            {!isSuperAdmin && (
              <div className="rounded-xl p-4" style={cardStyle}>
                <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
                  Extractor Overview
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg" style={{ background: 'rgba(168, 85, 247, 0.1)' }}>
                    <div className="text-3xl font-bold" style={{ color: '#a855f7' }}>
                      {extractorSummary?.registered_users || 0}
                    </div>
                    <div className="text-sm mt-1" style={{ color: 'var(--app-text)', opacity: 0.7 }}>
                      Registered Users
                    </div>
                  </div>
                  <div className="p-4 rounded-lg" style={{ background: 'rgba(168, 85, 247, 0.1)' }}>
                    <div className="text-3xl font-bold" style={{ color: '#a855f7' }}>
                      {extractorSummary?.active_users_7d || 0}
                    </div>
                    <div className="text-sm mt-1" style={{ color: 'var(--app-text)', opacity: 0.7 }}>
                      Active This Week
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Leaderboard */}
          <div className="rounded-xl p-4" style={cardStyle}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold" style={{ color: 'var(--app-text)' }}>
                Extractor Submission Leaderboard
              </h2>
              <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
                Top {leaderboard.length} submitters
              </div>
            </div>
            <LeaderboardTable
              data={leaderboard}
              showCommunity={isSuperAdmin && !selectedCommunity}
              loading={loading}
            />
          </div>
        </>
      )}
    </div>
  )
}
