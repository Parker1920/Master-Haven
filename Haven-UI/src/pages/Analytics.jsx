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

  // Fetch data when filters change
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

        // Fetch leaderboard
        const leaderboardRes = await axios.get('/api/analytics/submission-leaderboard', {
          params,
          withCredentials: true
        })
        setLeaderboard(leaderboardRes.data.leaderboard || [])
        setTotals(leaderboardRes.data.totals || { total_submissions: 0, total_approved: 0, total_rejected: 0 })

        // Fetch timeline
        const timelineRes = await axios.get('/api/analytics/submissions-timeline', {
          params: {
            ...params,
            granularity: period === 'year' ? 'month' : period === 'month' ? 'week' : 'day'
          },
          withCredentials: true
        })
        setTimeline(timelineRes.data.timeline || [])

        // Fetch community stats (super admin only)
        if (isSuperAdmin) {
          const communityRes = await axios.get('/api/analytics/community-stats', {
            params,
            withCredentials: true
          })
          setCommunities(communityRes.data.communities || [])
        }

      } catch (err) {
        console.error('Failed to fetch analytics:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [dateRange, period, selectedCommunity, isSuperAdmin, isAdmin])

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

  // Memoize approval rate calculation to avoid recalculating on every render
  const approvalRate = useMemo(() => {
    return totals.total_submissions > 0
      ? ((totals.total_approved / totals.total_submissions) * 100).toFixed(1)
      : 0
  }, [totals.total_submissions, totals.total_approved])

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

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          title="Total Submissions"
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
        {/* Timeline Chart */}
        <div
          className="rounded-xl p-4"
          style={{
            background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
            border: '1px solid rgba(255,255,255,0.04)'
          }}
        >
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
            Submissions Over Time
          </h2>
          <SubmissionChart data={timeline} loading={loading} height={280} />
        </div>

        {/* Community Breakdown (Super Admin Only) */}
        {isSuperAdmin && (
          <div
            className="rounded-xl p-4"
            style={{
              background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
              border: '1px solid rgba(255,255,255,0.04)'
            }}
          >
            <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text)' }}>
              Community Breakdown
            </h2>
            <CommunityPieChart data={communities} loading={loading} height={280} />
          </div>
        )}

        {/* If not super admin, show a larger timeline */}
        {!isSuperAdmin && (
          <div
            className="rounded-xl p-4"
            style={{
              background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
              border: '1px solid rgba(255,255,255,0.04)'
            }}
          >
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
      <div
        className="rounded-xl p-4"
        style={{
          background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
          border: '1px solid rgba(255,255,255,0.04)'
        }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--app-text)' }}>
            Submission Leaderboard
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
    </div>
  )
}
