import React, { useEffect, useState, useContext, useMemo, useCallback } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import { AuthContext } from '../utils/AuthContext'
import { usePersonalColor } from '../utils/usePersonalColor'
import { tagColors } from '../utils/tagColors'
import SystemApprovalTab from '../components/approvals/SystemApprovalTab'
import DiscoveryApprovalTab from '../components/approvals/DiscoveryApprovalTab'

/**
 * Pending Approvals Queue
 * Route: /pending-approvals
 * Auth: Feature-gated (FEATURES.approvals). Admin role required.
 *
 * Two-tab interface for reviewing pending submissions:
 *   - Systems tab: system submissions, region name proposals, and edit requests
 *   - Discoveries tab: discovery submissions
 *
 * Self-approval prevention: sub-admins cannot approve their own submissions.
 * Determined via backend flag (is_self_submission), account ID matching, and
 * Discord username normalization (strips #discriminator, lowercases).
 * Super admins and partners are exempt from self-approval checks.
 *
 * Super admin can filter by discord_tag and enter edit mode on pending submissions.
 * Batch approval/rejection available for system submissions.
 *
 * Key APIs:
 *   GET  /api/pending_systems, /api/pending_region_names, /api/pending_edits, /api/pending_discoveries
 *   GET  /api/pending_systems/:id, /api/pending_discoveries/:id
 *   POST /api/approve_system/:id, /api/reject_system/:id
 *   POST /api/approve_systems/batch, /api/reject_systems/batch
 *   POST /api/approve_discovery/:id, /api/reject_discovery/:id
 *   PUT  /api/pending_systems/:id  (super admin edit mode)
 */
export default function PendingApprovals() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const { isAdmin, isSuperAdmin, isHavenSubAdmin, user, loading: authLoading, canAccess } = auth || {}

  // Shared data state
  const [loading, setLoading] = useState(true)
  const [submissions, setSubmissions] = useState([])
  const [regionSubmissions, setRegionSubmissions] = useState([])
  const [editRequests, setEditRequests] = useState([])
  const [discoverySubmissions, setDiscoverySubmissions] = useState([])

  // Discord tag filtering (super admin only)
  const [discordTags, setDiscordTags] = useState([])
  const [filterTag, setFilterTag] = useState('all') // 'all', 'untagged', or specific tag

  // Tab switcher: 'systems' (system/region/edit submissions) vs 'discoveries' (discovery submissions)
  const [activeTab, setActiveTab] = useState('systems')

  // Get personal submission color from settings
  const { personalColor } = usePersonalColor()

  // Normalize Discord username by stripping #XXXX discriminator and lowercasing
  const normalizeDiscordUsername = useCallback((username) => {
    if (!username) return ''
    let normalized = username.toLowerCase().trim()
    if (normalized.includes('#')) {
      normalized = normalized.split('#')[0]
    }
    return normalized
  }, [])

  // Memoized normalized username for current user
  const normalizedCurrentUser = useMemo(() => {
    return user?.username ? normalizeDiscordUsername(user.username) : ''
  }, [user?.username, normalizeDiscordUsername])

  // Self-approval prevention: checks if the current user submitted this entry.
  // Super admins and partners are exempt (trusted). Sub-admins are blocked from
  // approving their own work. Uses three-tier matching: backend flag, account ID,
  // then normalized Discord username comparison.
  const isSelfSubmission = useCallback((submission) => {
    if (!user) return false
    if (isSuperAdmin) return false
    // Partners can self-approve (trusted community leaders)
    if (user.type === 'partner') return false
    // Primary: profile_id match (most reliable)
    if (user.profileId && submission.submitter_profile_id) {
      return user.profileId === submission.submitter_profile_id
    }
    // Use backend flag if available
    if (submission.is_self_submission) return true
    // Secondary: account_id match
    if (submission.submitter_account_id && submission.submitter_account_type) {
      return user.type === submission.submitter_account_type &&
             user.accountId === submission.submitter_account_id
    }
    // Tertiary: normalized username fallback
    if (normalizedCurrentUser) {
      if (submission.submitted_by && normalizeDiscordUsername(submission.submitted_by) === normalizedCurrentUser) {
        return true
      }
      if (submission.personal_discord_username && normalizeDiscordUsername(submission.personal_discord_username) === normalizedCurrentUser) {
        return true
      }
    }
    return false
  }, [user, isSuperAdmin, normalizedCurrentUser, normalizeDiscordUsername])

  // Helper to get discord tag badge color - each tag gets its own unique color
  const getDiscordTagBadge = useCallback((tag, personalDiscordUsername = null) => {
    if (!tag) {
      return (
        <span className="px-2 py-1 rounded text-xs font-semibold bg-gray-500 text-white">
          UNTAGGED
        </span>
      )
    }

    // Special handling for "personal" tag - configurable color
    // Show the discord username inside the badge if provided (super admin only)
    if (tag === 'personal') {
      return (
        <span
          className="px-2 py-1 rounded text-xs font-semibold text-white"
          style={{ backgroundColor: personalColor }}
        >
          PERSONAL{personalDiscordUsername ? ` - ${personalDiscordUsername}` : ''}
        </span>
      )
    }

    const colorClass = tagColors[tag] || 'bg-indigo-500 text-white'
    return (
      <span className={`px-2 py-1 rounded text-xs font-semibold ${colorClass}`}>
        {tag}
      </span>
    )
  }, [personalColor])

  // Fetch available discord tags for filter dropdown
  useEffect(() => {
    if (isSuperAdmin) {
      axios.get('/api/discord_tags').then(r => {
        setDiscordTags(r.data.tags || [])
      }).catch(() => {})
    }
  }, [isSuperAdmin])

  useEffect(() => {
    // Wait for auth to load, then check if user is admin
    if (authLoading) return

    if (!isAdmin) {
      alert('Admin authentication required')
      navigate('/systems')
    } else {
      loadSubmissions()
    }
  }, [authLoading, isAdmin, navigate])

  async function loadSubmissions() {
    setLoading(true)
    try {
      const [systemsResponse, regionsResponse, editRequestsResponse, discoveriesResponse] = await Promise.all([
        axios.get('/api/pending_systems'),
        axios.get('/api/pending_region_names'),
        axios.get('/api/pending_edits'),
        axios.get('/api/pending_discoveries')
      ])
      setSubmissions(systemsResponse.data.submissions || [])
      setRegionSubmissions(regionsResponse.data.pending || [])
      setEditRequests(editRequestsResponse.data.requests || [])
      setDiscoverySubmissions(discoveriesResponse.data.submissions || [])
    } catch (err) {
      alert('Failed to load submissions: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  // Compute pending counts for tab badges (must be before early returns for hooks rules)
  const pendingSystemsCount = useMemo(() => {
    return submissions.filter(s => {
      if (s.status !== 'pending') return false
      if (isSuperAdmin && filterTag !== 'all') {
        if (filterTag === 'untagged') return !s.discord_tag
        return s.discord_tag === filterTag
      }
      return true
    }).length
  }, [submissions, isSuperAdmin, filterTag])

  const pendingDiscoveriesCount = useMemo(() => {
    return discoverySubmissions.filter(s => {
      if (s.status !== 'pending') return false
      if (isSuperAdmin && filterTag !== 'all') {
        if (filterTag === 'untagged') return !s.discord_tag
        return s.discord_tag === filterTag
      }
      return true
    }).length
  }, [discoverySubmissions, isSuperAdmin, filterTag])

  // Early return for loading state - MUST be after all hooks
  if (authLoading || loading) {
    return (
      <div className="p-4">
        <Card>
          <p>Loading submissions...</p>
        </Card>
      </div>
    )
  }

  return (
    <div className="p-4">
      <Card className="max-w-6xl">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-4">
          <h2 className="text-xl sm:text-2xl font-bold">Approvals Queue</h2>
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
            {/* Discord Tag Filter - Super Admin Only */}
            {isSuperAdmin && (
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-300 hidden sm:inline">Filter:</label>
                <select
                  className="p-2 border rounded bg-gray-700 text-white text-sm flex-1 sm:flex-initial"
                  value={filterTag}
                  onChange={e => setFilterTag(e.target.value)}
                >
                  <option value="all">All Communities</option>
                  <option value="untagged">Untagged Only</option>
                  {discordTags.map(t => (
                    <option key={t.tag} value={t.tag}>{t.name} ({t.tag})</option>
                  ))}
                </select>
              </div>
            )}
            <div className="flex gap-2">
              <Button className="bg-gray-200 text-gray-800 text-sm" onClick={() => navigate('/systems')}>
                Back
              </Button>
            </div>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-gray-600 mb-6">
          <button
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'systems'
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
            onClick={() => setActiveTab('systems')}
          >
            Systems
            {pendingSystemsCount > 0 && (
              <span className="ml-2 px-1.5 py-0.5 text-xs rounded-full bg-cyan-600 text-white">
                {pendingSystemsCount}
              </span>
            )}
          </button>
          <button
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'discoveries'
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
            onClick={() => setActiveTab('discoveries')}
          >
            Discoveries
            {pendingDiscoveriesCount > 0 && (
              <span className="ml-2 px-1.5 py-0.5 text-xs rounded-full bg-cyan-600 text-white">
                {pendingDiscoveriesCount}
              </span>
            )}
          </button>
        </div>

        {/* ===== SYSTEMS TAB ===== */}
        {activeTab === 'systems' && (
          <SystemApprovalTab
            submissions={submissions}
            regionSubmissions={regionSubmissions}
            editRequests={editRequests}
            isSuperAdmin={isSuperAdmin}
            isHavenSubAdmin={isHavenSubAdmin}
            canAccess={canAccess}
            user={user}
            filterTag={filterTag}
            getDiscordTagBadge={getDiscordTagBadge}
            isSelfSubmission={isSelfSubmission}
            personalColor={personalColor}
            loadSubmissions={loadSubmissions}
          />
        )}

        {/* ===== DISCOVERIES TAB ===== */}
        {activeTab === 'discoveries' && (
          <DiscoveryApprovalTab
            discoverySubmissions={discoverySubmissions}
            isSuperAdmin={isSuperAdmin}
            isHavenSubAdmin={isHavenSubAdmin}
            user={user}
            filterTag={filterTag}
            getDiscordTagBadge={getDiscordTagBadge}
            isSelfSubmission={isSelfSubmission}
            loadSubmissions={loadSubmissions}
          />
        )}

      </Card>
    </div>
  )
}
