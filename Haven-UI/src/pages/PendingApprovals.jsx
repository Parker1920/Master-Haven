import React, { useEffect, useState, useContext, useMemo, useCallback } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import Modal from '../components/Modal'
import GlyphDisplay from '../components/GlyphDisplay'
import { AuthContext, FEATURES } from '../utils/AuthContext'
import { usePersonalColor } from '../utils/usePersonalColor'

export default function PendingApprovals() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const { isAdmin, isSuperAdmin, isHavenSubAdmin, user, loading: authLoading, canAccess } = auth || {}

  // State declarations first
  const [loading, setLoading] = useState(true)
  const [submissions, setSubmissions] = useState([])
  const [regionSubmissions, setRegionSubmissions] = useState([])
  const [editRequests, setEditRequests] = useState([])
  const [selectedSubmission, setSelectedSubmission] = useState(null)
  const [selectedRegion, setSelectedRegion] = useState(null)
  const [selectedEditRequest, setSelectedEditRequest] = useState(null)
  const [viewModalOpen, setViewModalOpen] = useState(false)
  const [regionModalOpen, setRegionModalOpen] = useState(false)
  const [editRequestModalOpen, setEditRequestModalOpen] = useState(false)
  const [rejectModalOpen, setRejectModalOpen] = useState(false)
  const [rejectionReason, setRejectionReason] = useState('')
  const [actionInProgress, setActionInProgress] = useState(false)
  // Batch approval state
  const [batchMode, setBatchMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [batchInProgress, setBatchInProgress] = useState(false)
  const [batchRejectModalOpen, setBatchRejectModalOpen] = useState(false)
  const [batchRejectionReason, setBatchRejectionReason] = useState('')
  const [batchResultsModalOpen, setBatchResultsModalOpen] = useState(false)
  const [batchResults, setBatchResults] = useState(null)
  // Discord tag filtering (super admin only)
  const [discordTags, setDiscordTags] = useState([])
  const [filterTag, setFilterTag] = useState('all') // 'all', 'untagged', or specific tag
  // Discoveries tab state
  const [activeTab, setActiveTab] = useState('systems')
  const [discoverySubmissions, setDiscoverySubmissions] = useState([])
  const [selectedDiscoveryApproval, setSelectedDiscoveryApproval] = useState(null)
  const [discoveryModalOpen, setDiscoveryModalOpen] = useState(false)
  const [discoveryRejectModalOpen, setDiscoveryRejectModalOpen] = useState(false)
  const [discoveryRejectionReason, setDiscoveryRejectionReason] = useState('')
  // Edit mode state (super admin only)
  const [editMode, setEditMode] = useState(false)
  const [editData, setEditData] = useState(null)
  const [editSaving, setEditSaving] = useState(false)

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

  // Check if a submission was made by the current user (self-submission) - memoized
  const isSelfSubmission = useCallback((submission) => {
    if (!user) return false
    if (isSuperAdmin) return false
    if (submission.submitter_account_id && submission.submitter_account_type) {
      return user.type === submission.submitter_account_type &&
             user.accountId === submission.submitter_account_id
    }
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

  // Pre-compute self-submission status for all submissions (O(n) once instead of O(n*k) per render)
  const selfSubmissionMap = useMemo(() => {
    const map = new Map()
    for (const submission of submissions) {
      map.set(submission.id, isSelfSubmission(submission))
    }
    return map
  }, [submissions, isSelfSubmission])

  // Helper to check self-submission using cached map
  const checkSelfSubmission = useCallback((submission) => {
    return selfSubmissionMap.get(submission.id) || false
  }, [selfSubmissionMap])

  // Pre-compute self-submission status for discovery submissions
  const discoverySelfSubmissionMap = useMemo(() => {
    const map = new Map()
    for (const submission of discoverySubmissions) {
      map.set(submission.id, isSelfSubmission(submission))
    }
    return map
  }, [discoverySubmissions, isSelfSubmission])

  const checkDiscoverySelfSubmission = useCallback((submission) => {
    return discoverySelfSubmissionMap.get(submission.id) || false
  }, [discoverySelfSubmissionMap])

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

  async function viewSubmission(submission) {
    try {
      const response = await axios.get(`/api/pending_systems/${submission.id}`)
      setSelectedSubmission(response.data)
      setViewModalOpen(true)
    } catch (err) {
      alert('Failed to load submission details: ' + (err.response?.data?.detail || err.message))
    }
  }

  async function approveSubmission(submissionId, systemName) {
    if (!confirm(`Approve system "${systemName}"?\n\nThis will add it to the main database.`)) {
      return
    }

    setActionInProgress(true)
    try {
      const response = await axios.post(`/api/approve_system/${submissionId}`)
      alert(`System "${systemName}" approved successfully!\n\nSystem ID: ${response.data.system_id}`)
      setViewModalOpen(false)
      setSelectedSubmission(null)
      loadSubmissions()
    } catch (err) {
      alert('Approval failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  function openRejectModal(submission) {
    setSelectedSubmission(submission)
    setRejectionReason('')
    setRejectModalOpen(true)
  }

  async function rejectSubmission() {
    if (!rejectionReason.trim()) {
      alert('Please provide a rejection reason')
      return
    }

    setActionInProgress(true)
    try {
      await axios.post(`/api/reject_system/${selectedSubmission.id}`, {
        reason: rejectionReason
      })
      alert(`System "${selectedSubmission.system_name}" rejected`)
      setRejectModalOpen(false)
      setViewModalOpen(false)
      setSelectedSubmission(null)
      setRejectionReason('')
      loadSubmissions()
    } catch (err) {
      alert('Rejection failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  // Edit pending submission functions (super admin only)
  function enterEditMode() {
    if (!selectedSubmission?.system_data) return
    setEditData(JSON.parse(JSON.stringify(selectedSubmission.system_data)))
    setEditMode(true)
  }

  function cancelEdit() {
    setEditMode(false)
    setEditData(null)
  }

  function updateEditField(path, value) {
    setEditData(prev => {
      const copy = JSON.parse(JSON.stringify(prev))
      const keys = path.split('.')
      let obj = copy
      for (let i = 0; i < keys.length - 1; i++) {
        const k = isNaN(keys[i]) ? keys[i] : parseInt(keys[i])
        obj = obj[k]
      }
      const lastKey = isNaN(keys[keys.length - 1]) ? keys[keys.length - 1] : parseInt(keys[keys.length - 1])
      obj[lastKey] = value
      return copy
    })
  }

  async function saveEdits() {
    if (!editData || !selectedSubmission) return
    setEditSaving(true)
    try {
      await axios.put(`/api/pending_systems/${selectedSubmission.id}`, {
        system_data: editData
      })
      // Refresh the submission detail
      const res = await axios.get(`/api/pending_systems/${selectedSubmission.id}`)
      setSelectedSubmission(res.data)
      setEditMode(false)
      setEditData(null)
      loadSubmissions()
    } catch (err) {
      alert('Save failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setEditSaving(false)
    }
  }

  // Region name approval functions
  function viewRegion(region) {
    setSelectedRegion(region)
    setRegionModalOpen(true)
  }

  async function approveRegion(region) {
    if (!confirm(`Approve region name "${region.proposed_name}" for coordinates [${region.region_x}, ${region.region_y}, ${region.region_z}]?`)) {
      return
    }

    setActionInProgress(true)
    try {
      await axios.post(`/api/pending_region_names/${region.id}/approve`)
      alert(`Region name "${region.proposed_name}" approved!`)
      setRegionModalOpen(false)
      setSelectedRegion(null)
      loadSubmissions()
    } catch (err) {
      alert('Approval failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function rejectRegion() {
    if (!rejectionReason.trim()) {
      alert('Please provide a rejection reason')
      return
    }

    setActionInProgress(true)
    try {
      await axios.post(`/api/pending_region_names/${selectedRegion.id}/reject`, {
        reason: rejectionReason
      })
      alert(`Region name "${selectedRegion.proposed_name}" rejected`)
      setRejectModalOpen(false)
      setRegionModalOpen(false)
      setSelectedRegion(null)
      setRejectionReason('')
      loadSubmissions()
    } catch (err) {
      alert('Rejection failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  // Edit request functions (for partner edits to untagged systems)
  function viewEditRequest(request) {
    setSelectedEditRequest(request)
    setEditRequestModalOpen(true)
  }

  async function approveEditRequest(request) {
    if (!confirm(`Approve edit request for system "${request.system_name}"?\n\nThis will apply the partner's changes to the system.`)) {
      return
    }

    setActionInProgress(true)
    try {
      await axios.post(`/api/pending_edits/${request.id}/approve`)
      alert(`Edit request approved! Changes have been applied to "${request.system_name}".`)
      setEditRequestModalOpen(false)
      setSelectedEditRequest(null)
      loadSubmissions()
    } catch (err) {
      alert('Approval failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function rejectEditRequest() {
    if (!rejectionReason.trim()) {
      alert('Please provide a rejection reason')
      return
    }

    setActionInProgress(true)
    try {
      await axios.post(`/api/pending_edits/${selectedEditRequest.id}/reject`, {
        notes: rejectionReason
      })
      alert(`Edit request rejected`)
      setRejectModalOpen(false)
      setEditRequestModalOpen(false)
      setSelectedEditRequest(null)
      setRejectionReason('')
      loadSubmissions()
    } catch (err) {
      alert('Rejection failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  // Batch approval functions
  function toggleSelection(id) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  function selectAllEligible() {
    const eligibleIds = filteredPendingSubmissions
      .filter(s => !checkSelfSubmission(s))
      .map(s => s.id)
    setSelectedIds(new Set(eligibleIds))
  }

  function clearSelection() {
    setSelectedIds(new Set())
  }

  function exitBatchMode() {
    setBatchMode(false)
    setSelectedIds(new Set())
  }

  async function handleBatchApprove() {
    if (selectedIds.size === 0) return
    if (!confirm(`Approve ${selectedIds.size} selected system(s)?\n\nThis will add them to the main database.`)) {
      return
    }

    setBatchInProgress(true)
    try {
      const response = await axios.post('/api/approve_systems/batch', {
        submission_ids: Array.from(selectedIds)
      })
      setBatchResults(response.data)
      setBatchResultsModalOpen(true)
      setSelectedIds(new Set())
      loadSubmissions()
    } catch (err) {
      alert('Batch approval failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setBatchInProgress(false)
    }
  }

  async function handleBatchReject() {
    if (!batchRejectionReason.trim()) {
      alert('Please provide a rejection reason')
      return
    }

    setBatchInProgress(true)
    try {
      const response = await axios.post('/api/reject_systems/batch', {
        submission_ids: Array.from(selectedIds),
        reason: batchRejectionReason
      })
      setBatchResults(response.data)
      setBatchRejectModalOpen(false)
      setBatchRejectionReason('')
      setBatchResultsModalOpen(true)
      setSelectedIds(new Set())
      loadSubmissions()
    } catch (err) {
      alert('Batch rejection failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setBatchInProgress(false)
    }
  }

  // Discovery approval functions
  async function viewDiscoverySubmission(submission) {
    try {
      const response = await axios.get(`/api/pending_discoveries/${submission.id}`)
      setSelectedDiscoveryApproval(response.data)
      setDiscoveryModalOpen(true)
    } catch (err) {
      alert('Failed to load discovery details: ' + (err.response?.data?.detail || err.message))
    }
  }

  async function approveDiscoverySubmission(submissionId, discoveryName) {
    if (!confirm(`Approve discovery "${discoveryName}"?\n\nThis will add it to the main database.`)) {
      return
    }

    setActionInProgress(true)
    try {
      await axios.post(`/api/approve_discovery/${submissionId}`)
      alert(`Discovery "${discoveryName}" approved successfully!`)
      setDiscoveryModalOpen(false)
      setSelectedDiscoveryApproval(null)
      loadSubmissions()
    } catch (err) {
      alert('Approval failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  function openDiscoveryRejectModal(submission) {
    setSelectedDiscoveryApproval(submission)
    setDiscoveryRejectionReason('')
    setDiscoveryRejectModalOpen(true)
  }

  async function rejectDiscoverySubmission() {
    if (!discoveryRejectionReason.trim()) {
      alert('Please provide a rejection reason')
      return
    }

    setActionInProgress(true)
    try {
      await axios.post(`/api/reject_discovery/${selectedDiscoveryApproval.id}`, {
        reason: discoveryRejectionReason
      })
      alert(`Discovery "${selectedDiscoveryApproval.discovery_name}" rejected`)
      setDiscoveryRejectModalOpen(false)
      setDiscoveryModalOpen(false)
      setSelectedDiscoveryApproval(null)
      setDiscoveryRejectionReason('')
      loadSubmissions()
    } catch (err) {
      alert('Rejection failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  // Single-pass filtering - categorize and filter in one iteration (O(n) instead of O(4n))
  // MUST be before any early returns to satisfy React's rules of hooks
  const { filteredPendingSubmissions, filteredReviewedSubmissions, pendingSubmissionsCount, reviewedSubmissionsCount } = useMemo(() => {
    const pending = []
    const reviewed = []
    let pendingCount = 0
    let reviewedCount = 0

    for (const s of submissions) {
      const isPending = s.status === 'pending'

      // Apply discord_tag filter for super admin
      let passesFilter = true
      if (isSuperAdmin && filterTag !== 'all') {
        if (filterTag === 'untagged') {
          passesFilter = !s.discord_tag
        } else {
          passesFilter = s.discord_tag === filterTag
        }
      }

      if (isPending) {
        pendingCount++
        if (passesFilter) pending.push(s)
      } else {
        reviewedCount++
        if (passesFilter) reviewed.push(s)
      }
    }

    return {
      filteredPendingSubmissions: pending,
      filteredReviewedSubmissions: reviewed,
      pendingSubmissionsCount: pendingCount,
      reviewedSubmissionsCount: reviewedCount
    }
  }, [submissions, isSuperAdmin, filterTag])

  const pendingRegions = useMemo(() => regionSubmissions.filter(r => r.status === 'pending'), [regionSubmissions])
  const pendingEdits = useMemo(() => editRequests.filter(e => e.status === 'pending'), [editRequests])

  // Filter discovery submissions
  const { filteredPendingDiscoveries, filteredReviewedDiscoveries } = useMemo(() => {
    const pending = []
    const reviewed = []
    for (const s of discoverySubmissions) {
      const isPending = s.status === 'pending'
      let passesFilter = true
      if (isSuperAdmin && filterTag !== 'all') {
        if (filterTag === 'untagged') {
          passesFilter = !s.discord_tag
        } else {
          passesFilter = s.discord_tag === filterTag
        }
      }
      if (isPending) {
        if (passesFilter) pending.push(s)
      } else {
        if (passesFilter) reviewed.push(s)
      }
    }
    return { filteredPendingDiscoveries: pending, filteredReviewedDiscoveries: reviewed }
  }, [discoverySubmissions, isSuperAdmin, filterTag])

  function getStatusBadge(status) {
    const colors = {
      pending: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-green-100 text-green-800',
      rejected: 'bg-red-100 text-red-800'
    }
    return (
      <span className={`px-2 py-1 rounded text-xs font-semibold ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
        {status.toUpperCase()}
      </span>
    )
  }

  // Pre-computed color palette for unknown tags
  const colorPalette = useMemo(() => [
    'bg-indigo-500 text-white',
    'bg-violet-500 text-white',
    'bg-fuchsia-500 text-white',
    'bg-amber-500 text-black',
    'bg-lime-500 text-black',
    'bg-teal-500 text-white',
    'bg-sky-500 text-white',
    'bg-rose-500 text-white',
  ], [])

  // Pre-defined colors for known tags
  const knownTagColors = useMemo(() => ({
    'Haven': 'bg-cyan-500 text-white',
    'IEA': 'bg-green-500 text-white',
    'B.E.S': 'bg-orange-500 text-white',
    'ARCH': 'bg-purple-500 text-white',
    'TBH': 'bg-yellow-500 text-black',
    'EVRN': 'bg-pink-500 text-white',
  }), [])

  // Cache for hash-based colors - computed once per unique tag
  const tagColorCache = useMemo(() => new Map(), [])

  // Helper to get tag color class - O(1) with caching instead of O(n) hash per render
  const getTagColorClass = useCallback((tag) => {
    if (knownTagColors[tag]) return knownTagColors[tag]

    if (tagColorCache.has(tag)) return tagColorCache.get(tag)

    // Compute hash once and cache
    let hash = 0
    for (let i = 0; i < tag.length; i++) {
      hash = tag.charCodeAt(i) + ((hash << 5) - hash)
    }
    const colorClass = colorPalette[Math.abs(hash) % colorPalette.length]
    tagColorCache.set(tag, colorClass)
    return colorClass
  }, [knownTagColors, colorPalette, tagColorCache])

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

    const colorClass = getTagColorClass(tag)
    return (
      <span className={`px-2 py-1 rounded text-xs font-semibold ${colorClass}`}>
        {tag}
      </span>
    )
  }, [getTagColorClass, personalColor])

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
              {/* Batch Mode Toggle - Requires batch_approvals feature */}
              {canAccess && canAccess(FEATURES.BATCH_APPROVALS) && filteredPendingSubmissions.length > 0 && (
                <Button
                  className={`text-sm ${batchMode ? 'bg-amber-600 hover:bg-amber-700' : 'bg-indigo-600 hover:bg-indigo-700'}`}
                  onClick={() => batchMode ? exitBatchMode() : setBatchMode(true)}
                >
                  {batchMode ? 'Exit Batch' : 'Batch Mode'}
                </Button>
              )}
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
            {filteredPendingSubmissions.length > 0 && (
              <span className="ml-2 px-1.5 py-0.5 text-xs rounded-full bg-cyan-600 text-white">
                {filteredPendingSubmissions.length}
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
            {filteredPendingDiscoveries.length > 0 && (
              <span className="ml-2 px-1.5 py-0.5 text-xs rounded-full bg-cyan-600 text-white">
                {filteredPendingDiscoveries.length}
              </span>
            )}
          </button>
        </div>

        {/* ===== SYSTEMS TAB ===== */}
        {activeTab === 'systems' && (<>

        {/* Pending Region Names */}
        {pendingRegions.length > 0 && (
          <div className="mb-6">
            <h3 className="text-xl font-semibold mb-3">
              Pending Region Names ({pendingRegions.length})
            </h3>
            <div className="space-y-2">
              {pendingRegions.map(region => (
                <div
                  key={`region-${region.id}`}
                  className="border rounded p-3 bg-purple-700 hover:bg-purple-600"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <h4 className="font-semibold text-lg">{region.proposed_name}</h4>
                      <div className="flex flex-wrap items-center gap-1.5 mt-1">
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-purple-200 text-purple-800">
                          REGION
                        </span>
                        {getStatusBadge(region.status)}
                        {/* Discord Tag Badge */}
                        {(isSuperAdmin || isHavenSubAdmin) && region.discord_tag && getDiscordTagBadge(region.discord_tag, isSuperAdmin ? region.personal_discord_username : null)}
                      </div>
                      <div className="text-sm text-gray-300 mt-1">
                        <span>Coords: [{region.region_x}, {region.region_y}, {region.region_z}]</span>
                        <span className="mx-2">•</span>
                        <span>By: {region.personal_discord_username || region.submitted_by || 'Anonymous'}</span>
                        <span className="mx-2">•</span>
                        <span>{new Date(region.submission_date).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => viewRegion(region)}
                      className="flex-shrink-0 px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                    >
                      Review
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Pending Edit Requests (Partner edits to untagged systems) */}
        {isSuperAdmin && pendingEdits.length > 0 && (
          <div className="mb-6">
            <h3 className="text-xl font-semibold mb-3">
              Pending Edit Requests ({pendingEdits.length})
            </h3>
            <div className="space-y-2">
              {pendingEdits.map(request => (
                <div
                  key={`edit-${request.id}`}
                  className="border rounded p-3 bg-orange-700 hover:bg-orange-600"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <h4 className="font-semibold text-lg">{request.system_name || 'Unknown System'}</h4>
                      <div className="flex flex-wrap items-center gap-1.5 mt-1">
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-orange-200 text-orange-800">
                          EDIT
                        </span>
                        {getStatusBadge(request.status)}
                      </div>
                      <div className="text-sm text-gray-300 mt-1">
                        <span>Partner: {request.partner_username || 'Unknown'}</span>
                        {request.partner_discord_tag && (
                          <>
                            <span className="mx-2">•</span>
                            <span className="text-cyan-300">{request.partner_discord_tag}</span>
                          </>
                        )}
                        <span className="mx-2">•</span>
                        <span>{new Date(request.submitted_at).toLocaleDateString()}</span>
                      </div>
                      {request.explanation && (
                        <div className="text-sm text-yellow-300 mt-1 line-clamp-1">
                          <span className="font-medium">Reason:</span> {request.explanation}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => viewEditRequest(request)}
                      className="flex-shrink-0 px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                    >
                      Review
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Batch Action Bar */}
        {batchMode && (
          <div className="mb-4 p-3 bg-indigo-900 border border-indigo-500 rounded">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2 sm:gap-4">
                <span className="text-white font-semibold text-sm">
                  {selectedIds.size}/{filteredPendingSubmissions.filter(s => !checkSelfSubmission(s)).length} selected
                </span>
                <button
                  onClick={selectAllEligible}
                  className="text-sm text-indigo-300 hover:text-white underline"
                >
                  Select All
                </button>
                {selectedIds.size > 0 && (
                  <button
                    onClick={clearSelection}
                    className="text-sm text-indigo-300 hover:text-white underline"
                  >
                    Clear
                  </button>
                )}
              </div>
              {selectedIds.size > 0 && (
                <div className="flex gap-2">
                  <Button
                    className="bg-green-600 hover:bg-green-700 text-white text-sm flex-1 sm:flex-initial"
                    onClick={handleBatchApprove}
                    disabled={batchInProgress}
                  >
                    {batchInProgress ? '...' : `Approve (${selectedIds.size})`}
                  </Button>
                  <Button
                    className="bg-red-600 hover:bg-red-700 text-white text-sm flex-1 sm:flex-initial"
                    onClick={() => setBatchRejectModalOpen(true)}
                    disabled={batchInProgress}
                  >
                    {batchInProgress ? '...' : `Reject (${selectedIds.size})`}
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Pending System Submissions */}
        <div className="mb-6">
          <h3 className="text-xl font-semibold mb-3">
            Pending Systems ({filteredPendingSubmissions.length}
            {isSuperAdmin && filterTag !== 'all' && ` of ${pendingSubmissionsCount}`})
          </h3>

          {filteredPendingSubmissions.length === 0 ? (
            <div className="text-gray-300 italic p-4 bg-cyan-700 rounded">
              {filterTag !== 'all' ? 'No pending submissions match the selected filter' : 'No pending system submissions'}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredPendingSubmissions.map(submission => (
                <div
                  key={submission.id}
                  className={`border rounded p-3 bg-cyan-700 hover:bg-cyan-600 ${
                    batchMode && selectedIds.has(submission.id) ? 'ring-2 ring-indigo-400' : ''
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {/* Batch mode checkbox */}
                    {batchMode && (
                      <div className="flex-shrink-0 pt-1">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(submission.id)}
                          onChange={() => toggleSelection(submission.id)}
                          disabled={checkSelfSubmission(submission)}
                          className="w-5 h-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                          title={checkSelfSubmission(submission) ? 'Cannot select your own submission' : ''}
                        />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <h4 className="font-semibold text-lg">{submission.system_name}</h4>
                      <div className="flex flex-wrap items-center gap-1.5 mt-1">
                        {getStatusBadge(submission.status)}
                        {/* Edit badge - shows when this is an edit of existing system */}
                        {submission.edit_system_id && (
                          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-orange-500 text-white">
                            EDIT
                          </span>
                        )}
                        {/* New badge - shows when this is a new system */}
                        {!submission.edit_system_id && (
                          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-green-500 text-white">
                            NEW
                          </span>
                        )}
                        {/* Self-submission badge - user cannot approve their own */}
                        {checkSelfSubmission(submission) && (
                          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-500 text-black">
                            YOURS
                          </span>
                        )}
                        {/* Discord Tag Badge - shows tag type without personal info */}
                        {(isSuperAdmin || isHavenSubAdmin) && submission.discord_tag && getDiscordTagBadge(submission.discord_tag, isSuperAdmin ? submission.personal_discord_username : null)}
                        {submission.source === 'companion_app' && submission.api_key_name && (
                          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-cyan-200 text-cyan-800">
                            {submission.api_key_name}
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-gray-300 mt-1">
                        <span>Galaxy: {submission.system_galaxy || 'Euclid'}</span>
                        <span className="mx-2">•</span>
                        <span className={submission.system_data?.reality === 'Permadeath' ? 'text-red-400' : 'text-green-400'}>
                          {submission.system_data?.reality || 'Normal'}
                        </span>
                        <span className="mx-2">•</span>
                        <span>Submitted by: {submission.personal_discord_username || submission.submitted_by || 'Anonymous'}</span>
                        <span className="mx-2">•</span>
                        <span>Date: {new Date(submission.submission_date).toLocaleString()}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => viewSubmission(submission)}
                      className="flex-shrink-0 px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                    >
                      Review
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Reviewed Submissions */}
        {filteredReviewedSubmissions.length > 0 && (
          <div>
            <h3 className="text-xl font-semibold mb-3">
              Recently Reviewed ({filteredReviewedSubmissions.length}
              {isSuperAdmin && filterTag !== 'all' && ` of ${reviewedSubmissionsCount}`})
            </h3>
            <div className="space-y-2">
              {filteredReviewedSubmissions.slice(0, 10).map(submission => (
                <div
                  key={submission.id}
                  className="border rounded p-3 bg-cyan-700"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="font-semibold">{submission.system_name}</h4>
                    {getStatusBadge(submission.status)}
                    {/* Edit badge - shows when this was an edit of existing system */}
                    {submission.edit_system_id && (
                      <span className="px-2 py-1 rounded text-xs font-semibold bg-orange-500 text-white">
                        EDIT
                      </span>
                    )}
                    {/* New badge - shows when this was a new system */}
                    {!submission.edit_system_id && (
                      <span className="px-2 py-1 rounded text-xs font-semibold bg-green-500 text-white">
                        NEW
                      </span>
                    )}
                    {/* Discord Tag Badge - shows tag type without personal info */}
                    {(isSuperAdmin || isHavenSubAdmin) && submission.discord_tag && getDiscordTagBadge(submission.discord_tag, isSuperAdmin ? submission.personal_discord_username : null)}
                  </div>
                  <div className="text-sm text-gray-300 mt-1">
                    <span>By: {submission.reviewed_by || 'Unknown'}</span>
                    <span className="mx-2">•</span>
                    <span>{submission.review_date ? new Date(submission.review_date).toLocaleDateString() : 'Unknown'}</span>
                    {submission.rejection_reason && (
                      <div className="text-red-300 mt-1 line-clamp-1">
                        Reason: {submission.rejection_reason}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        </>)}

        {/* ===== DISCOVERIES TAB ===== */}
        {activeTab === 'discoveries' && (<>
          {/* Pending Discoveries */}
          <div className="mb-6">
            <h3 className="text-xl font-semibold mb-3">
              Pending Discoveries ({filteredPendingDiscoveries.length})
            </h3>

            {filteredPendingDiscoveries.length === 0 ? (
              <div className="text-gray-300 italic p-4 bg-cyan-700 rounded">
                {filterTag !== 'all' ? 'No pending discoveries match the selected filter' : 'No pending discovery submissions'}
              </div>
            ) : (
              <div className="space-y-2">
                {filteredPendingDiscoveries.map(submission => (
                  <div
                    key={submission.id}
                    className="border rounded p-3 bg-cyan-700 hover:bg-cyan-600"
                  >
                    <div className="flex items-start gap-3">
                      {/* Photo thumbnail */}
                      {submission.photo_url && (
                        <div className="flex-shrink-0 w-16 h-16 rounded overflow-hidden bg-gray-800">
                          <img
                            src={submission.photo_url.startsWith('http') ? submission.photo_url : `/haven-ui-photos/${encodeURIComponent(submission.photo_url.split(/[/\\]/).pop())}`}
                            alt=""
                            className="w-full h-full object-cover"
                          />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <h4 className="font-semibold text-lg">{submission.discovery_name}</h4>
                        <div className="flex flex-wrap items-center gap-1.5 mt-1">
                          {getStatusBadge(submission.status)}
                          {/* Type badge */}
                          {submission.type_info && (
                            <span className="px-2 py-0.5 rounded text-xs font-semibold" style={{ backgroundColor: submission.type_info.color + '33', color: submission.type_info.color }}>
                              {submission.type_info.emoji} {submission.type_info.label}
                            </span>
                          )}
                          {/* Self-submission badge */}
                          {checkDiscoverySelfSubmission(submission) && (
                            <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-500 text-black">
                              YOURS
                            </span>
                          )}
                          {/* Discord Tag Badge */}
                          {(isSuperAdmin || isHavenSubAdmin) && submission.discord_tag && getDiscordTagBadge(submission.discord_tag)}
                        </div>
                        <div className="text-sm text-gray-300 mt-1">
                          {submission.system_name && (
                            <>
                              <span>System: {submission.system_name}</span>
                              <span className="mx-2">&bull;</span>
                            </>
                          )}
                          {submission.planet_name && (
                            <>
                              <span>{submission.planet_name}</span>
                              <span className="mx-2">&bull;</span>
                            </>
                          )}
                          {submission.moon_name && (
                            <>
                              <span>{submission.moon_name}</span>
                              <span className="mx-2">&bull;</span>
                            </>
                          )}
                          {submission.location_type === 'space' && (
                            <>
                              <span className="text-cyan-300">Space</span>
                              <span className="mx-2">&bull;</span>
                            </>
                          )}
                          <span>By: {submission.submitted_by || 'Anonymous'}</span>
                          <span className="mx-2">&bull;</span>
                          <span>{new Date(submission.submission_date).toLocaleDateString()}</span>
                        </div>
                      </div>
                      <button
                        onClick={() => viewDiscoverySubmission(submission)}
                        className="flex-shrink-0 px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                      >
                        Review
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Reviewed Discoveries */}
          {filteredReviewedDiscoveries.length > 0 && (
            <div>
              <h3 className="text-xl font-semibold mb-3">
                Recently Reviewed ({filteredReviewedDiscoveries.length})
              </h3>
              <div className="space-y-2">
                {filteredReviewedDiscoveries.slice(0, 10).map(submission => (
                  <div
                    key={submission.id}
                    className="border rounded p-3 bg-cyan-700"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="font-semibold">{submission.discovery_name}</h4>
                      {getStatusBadge(submission.status)}
                      {submission.type_info && (
                        <span className="px-2 py-1 rounded text-xs font-semibold" style={{ backgroundColor: submission.type_info.color + '33', color: submission.type_info.color }}>
                          {submission.type_info.emoji} {submission.type_info.label}
                        </span>
                      )}
                      {(isSuperAdmin || isHavenSubAdmin) && submission.discord_tag && getDiscordTagBadge(submission.discord_tag)}
                    </div>
                    <div className="text-sm text-gray-300 mt-1">
                      <span>By: {submission.reviewed_by || 'Unknown'}</span>
                      <span className="mx-2">&bull;</span>
                      <span>{submission.review_date ? new Date(submission.review_date).toLocaleDateString() : 'Unknown'}</span>
                      {submission.rejection_reason && (
                        <div className="text-red-300 mt-1 line-clamp-1">
                          Reason: {submission.rejection_reason}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>)}

        {/* View/Review Modal */}
        {viewModalOpen && selectedSubmission && (
          <Modal
            title={editMode ? `Editing: ${selectedSubmission.system_name}` : `Review: ${selectedSubmission.system_name}`}
            onClose={() => {
              setViewModalOpen(false)
              setSelectedSubmission(null)
              setEditMode(false)
              setEditData(null)
            }}
          >
            <div className="space-y-4">
              {/* System Details */}
              <div className="border-b pb-3">
                <h4 className="font-semibold mb-2">System Information {editMode && <span className="text-yellow-400 text-xs ml-2">(Editing)</span>}</h4>
                {editMode && editData ? (
                  <div className="text-sm space-y-2">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      <label className="block"><span className="text-gray-400">Name:</span>
                        <input type="text" value={editData.name || ''} onChange={e => updateEditField('name', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm" />
                      </label>
                      <label className="block"><span className="text-gray-400">Galaxy:</span>
                        <select value={editData.galaxy || 'Euclid'} onChange={e => updateEditField('galaxy', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm">
                          {['Euclid','Hilbert Dimension','Calypso','Hesperius Dimension','Hyades','Ickjamatew','Budullangr','Kikolgallr','Eltiensleen','Eissentam'].map(g => <option key={g} value={g}>{g}</option>)}
                        </select>
                      </label>
                      <label className="block"><span className="text-gray-400">Reality:</span>
                        <select value={editData.reality || 'Normal'} onChange={e => updateEditField('reality', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm">
                          <option value="Normal">Normal</option>
                          <option value="Permadeath">Permadeath</option>
                        </select>
                      </label>
                      <label className="block"><span className="text-gray-400">Star Color:</span>
                        <select value={editData.star_color || editData.star_type || ''} onChange={e => { updateEditField('star_color', e.target.value); updateEditField('star_type', e.target.value); }} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm">
                          <option value="">Unknown</option>
                          <option value="Yellow">Yellow</option>
                          <option value="Red">Red</option>
                          <option value="Green">Green</option>
                          <option value="Blue">Blue</option>
                        </select>
                      </label>
                      <label className="block"><span className="text-gray-400">Economy Type:</span>
                        <select value={editData.economy_type || ''} onChange={e => updateEditField('economy_type', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm">
                          <option value="">Unknown</option>
                          {['Trading','Scientific','Industrial','Technology','Mining','Power Generation','Manufacturing','None'].map(v => <option key={v} value={v}>{v}</option>)}
                        </select>
                      </label>
                      <label className="block"><span className="text-gray-400">Economy Level:</span>
                        <select value={editData.economy_level || ''} onChange={e => updateEditField('economy_level', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm">
                          <option value="">Unknown</option>
                          <option value="Low">Low</option>
                          <option value="Medium">Medium</option>
                          <option value="High">High</option>
                          <option value="None">None</option>
                        </select>
                      </label>
                      <label className="block"><span className="text-gray-400">Conflict Level:</span>
                        <select value={editData.conflict_level || ''} onChange={e => updateEditField('conflict_level', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm">
                          <option value="">Unknown</option>
                          <option value="Low">Low</option>
                          <option value="Medium">Medium</option>
                          <option value="High">High</option>
                          <option value="None">None</option>
                        </select>
                      </label>
                      <label className="block"><span className="text-gray-400">Dominant Lifeform:</span>
                        <select value={editData.dominant_lifeform || ''} onChange={e => updateEditField('dominant_lifeform', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm">
                          <option value="">Unknown</option>
                          <option value="Gek">Gek</option>
                          <option value="Vy'keen">Vy'keen</option>
                          <option value="Korvax">Korvax</option>
                          <option value="None">None</option>
                        </select>
                      </label>
                      <label className="block"><span className="text-gray-400">Spectral Class:</span>
                        <input type="text" value={editData.stellar_classification || ''} onChange={e => updateEditField('stellar_classification', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm" />
                      </label>
                      <label className="block"><span className="text-gray-400">Description:</span>
                        <input type="text" value={editData.description || ''} onChange={e => updateEditField('description', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm" />
                      </label>
                    </div>
                    {selectedSubmission.glyph_code && (
                      <div className="mt-2">
                        <strong className="text-gray-400">Glyph Code:</strong>
                        <div className="mt-1 flex items-center gap-2">
                          <GlyphDisplay glyphCode={selectedSubmission.glyph_code} size="medium" />
                          <span className="font-mono text-xs text-gray-400">({selectedSubmission.glyph_code})</span>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-sm space-y-1">
                    <p><strong>Name:</strong> {selectedSubmission.system_data?.name}</p>
                    <p><strong>Galaxy:</strong> {selectedSubmission.system_data?.galaxy || 'Euclid'}</p>
                    <p><strong>Reality:</strong> <span className={selectedSubmission.system_data?.reality === 'Permadeath' ? 'text-red-400' : 'text-green-400'}>{selectedSubmission.system_data?.reality || 'Normal'}</span></p>
                    {selectedSubmission.glyph_code && (
                      <div className="mb-2">
                        <strong>Glyph Code:</strong>
                        <div className="mt-1 flex items-center gap-2">
                          <GlyphDisplay glyphCode={selectedSubmission.glyph_code} size="medium" />
                          <span className="font-mono text-xs text-gray-400">({selectedSubmission.glyph_code})</span>
                        </div>
                      </div>
                    )}
                    {(selectedSubmission.system_data?.region_x !== undefined && selectedSubmission.system_data?.region_x !== null) && (
                      <p><strong>Region:</strong> [{selectedSubmission.system_data.region_x}, {selectedSubmission.system_data.region_y}, {selectedSubmission.system_data.region_z}]</p>
                    )}
                    <p><strong>Coordinates:</strong> ({selectedSubmission.system_data?.x || 0}, {selectedSubmission.system_data?.y || 0}, {selectedSubmission.system_data?.z || 0})</p>
                    {(() => {
                      const starColor = selectedSubmission.system_data?.star_color || selectedSubmission.system_data?.star_type;
                      if (starColor && starColor !== 'Unknown') {
                        return (
                          <p><strong>Star Color:</strong> <span className={
                            starColor === 'Yellow' ? 'text-yellow-400' :
                            starColor === 'Red' ? 'text-red-400' :
                            starColor === 'Green' ? 'text-green-400' :
                            starColor === 'Blue' ? 'text-blue-400' : ''
                          }>{starColor}</span></p>
                        );
                      }
                      return null;
                    })()}
                    {selectedSubmission.system_data?.economy_type && selectedSubmission.system_data.economy_type !== 'Unknown' && (
                      <p><strong>Economy:</strong> {selectedSubmission.system_data.economy_type} {selectedSubmission.system_data.economy_level && selectedSubmission.system_data.economy_level !== 'Unknown' && `(${selectedSubmission.system_data.economy_level})`}</p>
                    )}
                    {selectedSubmission.system_data?.conflict_level && selectedSubmission.system_data.conflict_level !== 'Unknown' && (
                      <p><strong>Conflict:</strong> <span className={
                        selectedSubmission.system_data.conflict_level === 'High' ? 'text-red-400' :
                        selectedSubmission.system_data.conflict_level === 'Low' ? 'text-green-400' : 'text-yellow-400'
                      }>{selectedSubmission.system_data.conflict_level}</span></p>
                    )}
                    {selectedSubmission.system_data?.dominant_lifeform && selectedSubmission.system_data.dominant_lifeform !== 'Unknown' && (
                      <p><strong>Dominant Lifeform:</strong> {selectedSubmission.system_data.dominant_lifeform}</p>
                    )}
                    {selectedSubmission.system_data?.stellar_classification && (
                      <p><strong>Spectral Class:</strong> <span className={`font-mono ${
                        (() => {
                          const firstChar = selectedSubmission.system_data.stellar_classification[0]?.toUpperCase();
                          switch(firstChar) {
                            case 'O': case 'B': return 'text-blue-300';
                            case 'F': case 'G': return 'text-yellow-300';
                            case 'K': case 'M': return 'text-red-400';
                            case 'E': return 'text-green-400';
                            case 'X': case 'Y': return 'text-purple-400';
                            default: return 'text-gray-300';
                          }
                        })()
                      }`}>{selectedSubmission.system_data.stellar_classification}</span></p>
                    )}
                    <p><strong>Description:</strong> {selectedSubmission.system_data?.description || 'None'}</p>
                  </div>
                )}
              </div>

              {/* Planets */}
              {(() => {
                const planetsData = editMode && editData ? editData.planets : selectedSubmission.system_data?.planets;
                if (!planetsData || planetsData.length === 0) return null;
                const biomeOptions = ['Lush','Toxic','Scorched','Radioactive','Frozen','Barren','Dead','Weird','Swamp','Lava'];
                const sizeOptions = ['Large','Medium','Small'];
                const inputCls = "w-full px-1.5 py-0.5 bg-gray-700 border border-gray-600 rounded text-white text-xs";
                const selectCls = "px-1.5 py-0.5 bg-gray-700 border border-gray-600 rounded text-white text-xs";
                const checkCls = "mr-1 accent-yellow-500";

                const renderBodyFields = (body, prefix, isMoon) => {
                  if (editMode && editData) {
                    return (
                      <div className="space-y-2">
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                          <label className="block"><span className="text-gray-400 text-xs">Name:</span>
                            <input type="text" value={body.name || ''} onChange={e => updateEditField(`${prefix}.name`, e.target.value)} className={inputCls} />
                          </label>
                          <label className="block"><span className="text-gray-400 text-xs">Size:</span>
                            <select value={body.planet_size || ''} onChange={e => updateEditField(`${prefix}.planet_size`, e.target.value)} className={`w-full ${selectCls}`}>
                              <option value="">Unknown</option>
                              {sizeOptions.map(s => <option key={s} value={s}>{s}</option>)}
                            </select>
                          </label>
                          <label className="block"><span className="text-gray-400 text-xs">Biome:</span>
                            <select value={body.biome || ''} onChange={e => updateEditField(`${prefix}.biome`, e.target.value)} className={`w-full ${selectCls}`}>
                              <option value="">Unknown</option>
                              {biomeOptions.map(b => <option key={b} value={b}>{b}</option>)}
                            </select>
                          </label>
                          <label className="block"><span className="text-gray-400 text-xs">Biome Subtype:</span>
                            <input type="text" value={body.biome_subtype || ''} onChange={e => updateEditField(`${prefix}.biome_subtype`, e.target.value)} className={inputCls} />
                          </label>
                          <label className="block"><span className="text-gray-400 text-xs">Weather:</span>
                            <input type="text" value={body.weather || body.climate || ''} onChange={e => updateEditField(`${prefix}.weather`, e.target.value)} className={inputCls} />
                          </label>
                          <label className="block"><span className="text-gray-400 text-xs">Sentinel:</span>
                            <input type="text" value={body.sentinel || body.sentinels || ''} onChange={e => updateEditField(`${prefix}.sentinel`, e.target.value)} className={inputCls} />
                          </label>
                          <label className="block"><span className="text-gray-400 text-xs">Fauna:</span>
                            <input type="text" value={body.fauna || ''} onChange={e => updateEditField(`${prefix}.fauna`, e.target.value)} className={inputCls} />
                          </label>
                          <label className="block"><span className="text-gray-400 text-xs">Flora:</span>
                            <input type="text" value={body.flora || ''} onChange={e => updateEditField(`${prefix}.flora`, e.target.value)} className={inputCls} />
                          </label>
                          <label className="block"><span className="text-gray-400 text-xs">Resources:</span>
                            <input type="text" value={body.materials || (body.resources && Array.isArray(body.resources) ? body.resources.join(', ') : body.resources) || ''} onChange={e => updateEditField(`${prefix}.materials`, e.target.value)} className={inputCls} />
                          </label>
                        </div>
                        <div className="flex flex-wrap gap-3 text-xs">
                          <label className="flex items-center"><input type="checkbox" checked={!!body.has_water} onChange={e => updateEditField(`${prefix}.has_water`, e.target.checked ? 1 : 0)} className={checkCls} />Water</label>
                          <label className="flex items-center"><input type="checkbox" checked={!!body.ancient_bones} onChange={e => updateEditField(`${prefix}.ancient_bones`, e.target.checked ? 1 : 0)} className={checkCls} />Ancient Bones</label>
                          <label className="flex items-center"><input type="checkbox" checked={!!body.vile_brood} onChange={e => updateEditField(`${prefix}.vile_brood`, e.target.checked ? 1 : 0)} className={checkCls} />Vile Brood</label>
                          <label className="flex items-center"><input type="checkbox" checked={!!body.salvageable_scrap} onChange={e => updateEditField(`${prefix}.salvageable_scrap`, e.target.checked ? 1 : 0)} className={checkCls} />Salvageable Scrap</label>
                          <label className="flex items-center"><input type="checkbox" checked={!!body.storm_crystals} onChange={e => updateEditField(`${prefix}.storm_crystals`, e.target.checked ? 1 : 0)} className={checkCls} />Storm Crystals</label>
                          <label className="flex items-center"><input type="checkbox" checked={!!body.gravitino_balls} onChange={e => updateEditField(`${prefix}.gravitino_balls`, e.target.checked ? 1 : 0)} className={checkCls} />Gravitino Balls</label>
                          <label className="flex items-center"><input type="checkbox" checked={!!body.is_infested} onChange={e => updateEditField(`${prefix}.is_infested`, e.target.checked ? 1 : 0)} className={checkCls} />Infested</label>
                          <label className="flex items-center"><input type="checkbox" checked={!!body.is_dissonant} onChange={e => updateEditField(`${prefix}.is_dissonant`, e.target.checked ? 1 : 0)} className={checkCls} />Dissonant</label>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          <label className="block"><span className="text-gray-400 text-xs">Base Location:</span>
                            <input type="text" value={body.base_location || ''} onChange={e => updateEditField(`${prefix}.base_location`, e.target.value)} className={inputCls} />
                          </label>
                          <label className="block"><span className="text-gray-400 text-xs">Notes:</span>
                            <input type="text" value={body.notes || ''} onChange={e => updateEditField(`${prefix}.notes`, e.target.value)} className={inputCls} />
                          </label>
                        </div>
                      </div>
                    );
                  }
                  // View mode
                  return (
                    <>
                      <div className="flex items-start gap-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <p className="font-semibold text-base">{body.name}</p>
                            {body.planet_size && body.planet_size !== 'Unknown' && (
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                body.planet_size === 'Large' ? 'bg-purple-600 text-white' :
                                body.planet_size === 'Medium' ? 'bg-blue-600 text-white' :
                                body.planet_size === 'Small' ? 'bg-green-600 text-white' :
                                'bg-gray-600 text-white'
                              }`}>{body.planet_size}</span>
                            )}
                          </div>
                          {(body.biome || body.biome_subtype) && (
                            <div className="mb-2 text-gray-300">
                              {body.biome && body.biome !== 'Unknown' && (
                                <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium mr-2 ${
                                  body.biome === 'Lush' ? 'bg-green-700' :
                                  body.biome === 'Toxic' ? 'bg-yellow-700' :
                                  body.biome === 'Scorched' ? 'bg-orange-700' :
                                  body.biome === 'Radioactive' ? 'bg-lime-700' :
                                  body.biome === 'Frozen' ? 'bg-cyan-700' :
                                  body.biome === 'Barren' ? 'bg-stone-700' :
                                  body.biome === 'Dead' ? 'bg-gray-700' :
                                  body.biome === 'Weird' ? 'bg-purple-700' :
                                  body.biome === 'Swamp' ? 'bg-emerald-800' :
                                  body.biome === 'Lava' ? 'bg-red-700' :
                                  'bg-gray-600'
                                }`}>{body.biome}</span>
                              )}
                              {body.biome_subtype && body.biome_subtype !== 'Unknown' && body.biome_subtype !== 'None' && (
                                <span className="text-xs text-gray-400">({body.biome_subtype})</span>
                              )}
                            </div>
                          )}
                          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-gray-300">
                            <div><span className="text-gray-400">Sentinel:</span> {body.sentinel || body.sentinels || 'None'}</div>
                            <div><span className="text-gray-400">Fauna:</span> {body.fauna || 'N/A'}{body.fauna_count > 0 && ` (${body.fauna_count})`}</div>
                            <div><span className="text-gray-400">Flora:</span> {body.flora || 'N/A'}{body.flora_count > 0 && ` (${body.flora_count})`}</div>
                            {(body.climate || body.weather) && <div><span className="text-gray-400">Weather:</span> {body.climate || body.weather}</div>}
                            {body.has_water === 1 && <div><span className="text-cyan-300">Has Water</span></div>}
                          </div>
                        </div>
                      </div>
                      {(body.materials || (body.resources && body.resources.length > 0)) && (
                        <div className="mt-2 text-gray-300">
                          <span className="text-gray-400">Resources:</span> {body.materials || body.resources?.join(', ')}
                        </div>
                      )}
                      {(body.ancient_bones || body.vile_brood || body.salvageable_scrap || body.storm_crystals || body.gravitino_balls || body.is_infested || body.is_dissonant) && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {body.ancient_bones ? <span className="text-xs px-1.5 py-0.5 rounded bg-amber-800/60 text-amber-300">Ancient Bones</span> : null}
                          {body.vile_brood ? <span className="text-xs px-1.5 py-0.5 rounded bg-red-800/60 text-red-300">Vile Brood</span> : null}
                          {body.salvageable_scrap ? <span className="text-xs px-1.5 py-0.5 rounded bg-orange-800/60 text-orange-300">Salvageable Scrap</span> : null}
                          {body.storm_crystals ? <span className="text-xs px-1.5 py-0.5 rounded bg-cyan-800/60 text-cyan-300">Storm Crystals</span> : null}
                          {body.gravitino_balls ? <span className="text-xs px-1.5 py-0.5 rounded bg-purple-800/60 text-purple-300">Gravitino Balls</span> : null}
                          {body.is_infested ? <span className="text-xs px-1.5 py-0.5 rounded bg-red-900/60 text-red-400">Infested</span> : null}
                          {body.is_dissonant ? <span className="text-xs px-1.5 py-0.5 rounded bg-violet-800/60 text-violet-300">Dissonant</span> : null}
                        </div>
                      )}
                      {body.base_location && (
                        <div className="mt-1 text-gray-300"><span className="text-gray-400">Base Location:</span> {body.base_location}</div>
                      )}
                      {body.description && (
                        <div className="mt-1 text-gray-300"><span className="text-gray-400">Description:</span> {body.description}</div>
                      )}
                      {body.notes && (
                        <div className="mt-1 text-gray-300"><span className="text-gray-400">Notes:</span> {body.notes}</div>
                      )}
                      {body.photo && (
                        <div className="mt-2"><span className="text-gray-400">Photo:</span> <span className="text-cyan-300">{body.photo}</span></div>
                      )}
                    </>
                  );
                };

                return (
                  <div className="border-b pb-3">
                    <h4 className="font-semibold mb-2">Planets ({planetsData.length})</h4>
                    <div className="space-y-3">
                      {planetsData.map((planet, i) => (
                        <div key={i} className="text-sm bg-cyan-700 p-3 rounded">
                          {renderBodyFields(planet, `planets.${i}`, false)}
                          {/* Moons nested under planet */}
                          {planet.moons && planet.moons.length > 0 && (
                            <div className="mt-2 ml-3 border-l-2 border-cyan-500 pl-3">
                              <p className="text-gray-400 text-xs mb-1">Moons ({planet.moons.length}):</p>
                              {planet.moons.map((moon, j) => (
                                <div key={j} className={`mb-2 ${editMode ? 'text-sm bg-gray-700/50 p-2 rounded' : 'text-xs'}`}>
                                  {editMode && editData ? (
                                    renderBodyFields(moon, `planets.${i}.moons.${j}`, true)
                                  ) : (
                                    <>
                                      <p className="font-medium">{moon.name}</p>
                                      <div className="grid grid-cols-2 gap-1 mt-1 text-gray-300">
                                        {moon.biome && moon.biome !== 'Unknown' && <div>Biome: {moon.biome}</div>}
                                        <div>Sentinel: {moon.sentinel || moon.sentinels || 'None'}</div>
                                        <div>Fauna: {moon.fauna || 'N/A'}</div>
                                        <div>Flora: {moon.flora || 'N/A'}</div>
                                        {(moon.materials || (moon.resources && moon.resources.length > 0)) && (
                                          <div className="col-span-2">Resources: {moon.materials || moon.resources?.join(', ')}</div>
                                        )}
                                      </div>
                                    </>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}

              {/* Moons (top-level from extractor - shown indented under planets) */}
              {(() => {
                const moonsData = editMode && editData ? editData.moons : selectedSubmission.system_data?.moons;
                if (!moonsData || moonsData.length === 0) return null;
                const biomeOptions = ['Lush','Toxic','Scorched','Radioactive','Frozen','Barren','Dead','Weird','Swamp','Lava'];
                const sizeOptions = ['Large','Medium','Small'];
                const inputCls = "w-full px-1.5 py-0.5 bg-gray-700 border border-gray-600 rounded text-white text-xs";
                const selectCls = "px-1.5 py-0.5 bg-gray-700 border border-gray-600 rounded text-white text-xs";
                const checkCls = "mr-1 accent-yellow-500";
                return (
                  <div className="border-b pb-3 ml-4 border-l-2 border-gray-600 pl-4">
                    <h4 className="font-semibold mb-2 text-gray-300">
                      <span className="text-gray-500">↳</span> System Moons ({moonsData.length})
                    </h4>
                    <div className="space-y-2">
                      {moonsData.map((moon, i) => (
                        <div key={i} className="text-sm bg-gray-700/70 p-3 rounded">
                          {editMode && editData ? (
                            <div className="space-y-2">
                              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                                <label className="block"><span className="text-gray-400 text-xs">Name:</span>
                                  <input type="text" value={moon.name || ''} onChange={e => updateEditField(`moons.${i}.name`, e.target.value)} className={inputCls} />
                                </label>
                                <label className="block"><span className="text-gray-400 text-xs">Size:</span>
                                  <select value={moon.planet_size || ''} onChange={e => updateEditField(`moons.${i}.planet_size`, e.target.value)} className={`w-full ${selectCls}`}>
                                    <option value="">Unknown</option>
                                    {sizeOptions.map(s => <option key={s} value={s}>{s}</option>)}
                                  </select>
                                </label>
                                <label className="block"><span className="text-gray-400 text-xs">Biome:</span>
                                  <select value={moon.biome || ''} onChange={e => updateEditField(`moons.${i}.biome`, e.target.value)} className={`w-full ${selectCls}`}>
                                    <option value="">Unknown</option>
                                    {biomeOptions.map(b => <option key={b} value={b}>{b}</option>)}
                                  </select>
                                </label>
                                <label className="block"><span className="text-gray-400 text-xs">Weather:</span>
                                  <input type="text" value={moon.weather || moon.climate || ''} onChange={e => updateEditField(`moons.${i}.weather`, e.target.value)} className={inputCls} />
                                </label>
                                <label className="block"><span className="text-gray-400 text-xs">Sentinel:</span>
                                  <input type="text" value={moon.sentinel || moon.sentinels || ''} onChange={e => updateEditField(`moons.${i}.sentinel`, e.target.value)} className={inputCls} />
                                </label>
                                <label className="block"><span className="text-gray-400 text-xs">Fauna:</span>
                                  <input type="text" value={moon.fauna || ''} onChange={e => updateEditField(`moons.${i}.fauna`, e.target.value)} className={inputCls} />
                                </label>
                                <label className="block"><span className="text-gray-400 text-xs">Flora:</span>
                                  <input type="text" value={moon.flora || ''} onChange={e => updateEditField(`moons.${i}.flora`, e.target.value)} className={inputCls} />
                                </label>
                                <label className="block"><span className="text-gray-400 text-xs">Resources:</span>
                                  <input type="text" value={moon.materials || (moon.resources && Array.isArray(moon.resources) ? moon.resources.join(', ') : moon.resources) || ''} onChange={e => updateEditField(`moons.${i}.materials`, e.target.value)} className={inputCls} />
                                </label>
                              </div>
                              <div className="flex flex-wrap gap-3 text-xs">
                                <label className="flex items-center"><input type="checkbox" checked={!!moon.has_water} onChange={e => updateEditField(`moons.${i}.has_water`, e.target.checked ? 1 : 0)} className={checkCls} />Water</label>
                                <label className="flex items-center"><input type="checkbox" checked={!!moon.ancient_bones} onChange={e => updateEditField(`moons.${i}.ancient_bones`, e.target.checked ? 1 : 0)} className={checkCls} />Ancient Bones</label>
                                <label className="flex items-center"><input type="checkbox" checked={!!moon.vile_brood} onChange={e => updateEditField(`moons.${i}.vile_brood`, e.target.checked ? 1 : 0)} className={checkCls} />Vile Brood</label>
                                <label className="flex items-center"><input type="checkbox" checked={!!moon.salvageable_scrap} onChange={e => updateEditField(`moons.${i}.salvageable_scrap`, e.target.checked ? 1 : 0)} className={checkCls} />Salvageable Scrap</label>
                                <label className="flex items-center"><input type="checkbox" checked={!!moon.storm_crystals} onChange={e => updateEditField(`moons.${i}.storm_crystals`, e.target.checked ? 1 : 0)} className={checkCls} />Storm Crystals</label>
                                <label className="flex items-center"><input type="checkbox" checked={!!moon.gravitino_balls} onChange={e => updateEditField(`moons.${i}.gravitino_balls`, e.target.checked ? 1 : 0)} className={checkCls} />Gravitino Balls</label>
                                <label className="flex items-center"><input type="checkbox" checked={!!moon.is_infested} onChange={e => updateEditField(`moons.${i}.is_infested`, e.target.checked ? 1 : 0)} className={checkCls} />Infested</label>
                                <label className="flex items-center"><input type="checkbox" checked={!!moon.is_dissonant} onChange={e => updateEditField(`moons.${i}.is_dissonant`, e.target.checked ? 1 : 0)} className={checkCls} />Dissonant</label>
                              </div>
                            </div>
                          ) : (
                            <>
                              <div className="flex items-center gap-2 mb-2">
                                <p className="font-semibold">{moon.name}</p>
                                <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-500 text-white">Moon</span>
                                {moon.planet_size && moon.planet_size !== 'Unknown' && (
                                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-600">{moon.planet_size}</span>
                                )}
                                {moon.biome && moon.biome !== 'Unknown' && (
                                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                    moon.biome === 'Lush' ? 'bg-green-700' :
                                    moon.biome === 'Toxic' ? 'bg-yellow-700' :
                                    moon.biome === 'Scorched' ? 'bg-orange-700' :
                                    moon.biome === 'Radioactive' ? 'bg-lime-700' :
                                    moon.biome === 'Frozen' ? 'bg-cyan-700' :
                                    moon.biome === 'Barren' ? 'bg-stone-700' :
                                    moon.biome === 'Dead' ? 'bg-gray-700' :
                                    moon.biome === 'Weird' ? 'bg-purple-700' :
                                    'bg-gray-600'
                                  }`}>{moon.biome}</span>
                                )}
                              </div>
                              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-gray-300">
                                <div><span className="text-gray-400">Sentinel:</span> {moon.sentinel || moon.sentinels || 'None'}</div>
                                <div><span className="text-gray-400">Fauna:</span> {moon.fauna || 'N/A'}</div>
                                <div><span className="text-gray-400">Flora:</span> {moon.flora || 'N/A'}</div>
                                {(moon.climate || moon.weather) && <div><span className="text-gray-400">Weather:</span> {moon.climate || moon.weather}</div>}
                              </div>
                              {(moon.materials || (moon.resources && moon.resources.length > 0)) && (
                                <div className="mt-2 text-gray-300">
                                  <span className="text-gray-400">Resources:</span> {moon.materials || moon.resources?.join(', ')}
                                </div>
                              )}
                              {(moon.ancient_bones || moon.vile_brood || moon.salvageable_scrap || moon.storm_crystals || moon.gravitino_balls || moon.is_infested || moon.is_dissonant) && (
                                <div className="mt-1 flex flex-wrap gap-1">
                                  {moon.ancient_bones ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-amber-800/60 text-amber-200 border border-amber-700/50">Ancient Bones</span> : null}
                                  {moon.vile_brood ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-red-800/60 text-red-200 border border-red-700/50">Vile Brood</span> : null}
                                  {moon.salvageable_scrap ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-orange-800/60 text-orange-200 border border-orange-700/50">Salvageable Scrap</span> : null}
                                  {moon.storm_crystals ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-cyan-800/60 text-cyan-200 border border-cyan-700/50">Storm Crystals</span> : null}
                                  {moon.gravitino_balls ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-purple-800/60 text-purple-200 border border-purple-700/50">Gravitino Balls</span> : null}
                                  {moon.is_infested ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-red-900/60 text-red-200 border border-red-800/50">Infested</span> : null}
                                  {moon.is_dissonant ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-violet-800/60 text-violet-200 border border-violet-700/50">Dissonant</span> : null}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}

              {/* Space Station */}
              {selectedSubmission.system_data?.space_station && (
                <div className="border-b pb-3">
                  <h4 className="font-semibold mb-2">Space Station</h4>
                  <div className="text-sm">
                    <p><strong>Name:</strong> {selectedSubmission.system_data.space_station.name}</p>
                    <p><strong>Race:</strong> {selectedSubmission.system_data.space_station.race}</p>
                    <p><strong>Position:</strong> ({selectedSubmission.system_data.space_station.x}, {selectedSubmission.system_data.space_station.y}, {selectedSubmission.system_data.space_station.z})</p>
                  </div>
                </div>
              )}

              {/* Submission Metadata */}
              <div className="text-sm text-gray-600">
                <p><strong>Submitted by:</strong> {selectedSubmission.personal_discord_username || selectedSubmission.submitted_by || 'Anonymous'}</p>
                {/* Personal ID (Discord snowflake) - super admin only */}
                {isSuperAdmin && selectedSubmission.personal_id && (
                  <p><strong>Discord ID:</strong> <span className="font-mono text-xs">{selectedSubmission.personal_id}</span></p>
                )}
                <p><strong>Submission Date:</strong> {new Date(selectedSubmission.submission_date).toLocaleString()}</p>
                {/* Source indicator */}
                {selectedSubmission.source && (
                  <p><strong>Source:</strong> <span className={`px-2 py-0.5 rounded text-xs ${
                    selectedSubmission.source === 'haven_extractor' ? 'bg-purple-600 text-white' :
                    selectedSubmission.source === 'companion_app' ? 'bg-cyan-600 text-white' :
                    'bg-gray-600 text-white'
                  }`}>{selectedSubmission.source === 'haven_extractor' ? 'Haven Extractor' : selectedSubmission.source}</span></p>
                )}
                {/* API key name if applicable */}
                {selectedSubmission.api_key_name && (
                  <p><strong>API Key:</strong> {selectedSubmission.api_key_name}</p>
                )}
                {/* IP Address only visible to super admin for security */}
                {isSuperAdmin && selectedSubmission.submitted_by_ip && (
                  <p><strong>IP Address:</strong> {selectedSubmission.submitted_by_ip}</p>
                )}
                {/* Discord info - shows tag type without personal info */}
                {(isSuperAdmin || isHavenSubAdmin) && selectedSubmission.discord_tag && (
                  <p className="mt-2">
                    <strong>Discord Community:</strong>{' '}
                    {getDiscordTagBadge(selectedSubmission.discord_tag, isSuperAdmin ? selectedSubmission.personal_discord_username : null)}
                  </p>
                )}
              </div>

              {/* Actions */}
              {selectedSubmission.status === 'pending' && (
                <div className="pt-3 border-t">
                  {/* Self-submission warning */}
                  {!editMode && isSelfSubmission(selectedSubmission) && (
                    <div className="mb-3 p-3 bg-amber-900/50 border border-amber-500 rounded">
                      <p className="text-amber-300 text-sm">
                        <strong>You submitted this system.</strong> Another admin must review and approve it to prevent conflicts of interest.
                      </p>
                    </div>
                  )}
                  {editMode ? (
                    <div className="flex flex-col sm:flex-row gap-2">
                      <Button
                        className="btn-primary bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm w-full sm:w-auto"
                        onClick={saveEdits}
                        disabled={editSaving}
                      >
                        {editSaving ? 'Saving...' : 'Save Changes'}
                      </Button>
                      <Button
                        className="bg-gray-500 text-white hover:bg-gray-600 text-sm w-full sm:w-auto"
                        onClick={cancelEdit}
                        disabled={editSaving}
                      >
                        Cancel Edit
                      </Button>
                    </div>
                  ) : (
                    <div className="flex flex-col sm:flex-row gap-2">
                      {isSuperAdmin && (
                        <Button
                          className="bg-yellow-600 text-white hover:bg-yellow-700 text-sm w-full sm:w-auto"
                          onClick={enterEditMode}
                          disabled={actionInProgress}
                        >
                          Edit
                        </Button>
                      )}
                      <Button
                        className="btn-primary bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm w-full sm:w-auto"
                        onClick={() => approveSubmission(selectedSubmission.id, selectedSubmission.system_name)}
                        disabled={actionInProgress || isSelfSubmission(selectedSubmission)}
                        title={isSelfSubmission(selectedSubmission) ? 'You cannot approve your own submission' : ''}
                      >
                        {isSelfSubmission(selectedSubmission) ? 'Cannot Self-Approve' : (actionInProgress ? 'Approving...' : 'Approve')}
                      </Button>
                      <Button
                        className="bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm w-full sm:w-auto"
                        onClick={() => {
                          setViewModalOpen(false)
                          openRejectModal(selectedSubmission)
                        }}
                        disabled={actionInProgress || isSelfSubmission(selectedSubmission)}
                        title={isSelfSubmission(selectedSubmission) ? 'You cannot reject your own submission' : ''}
                      >
                        {isSelfSubmission(selectedSubmission) ? 'Cannot Reject' : 'Reject'}
                      </Button>
                      <Button
                        className="bg-gray-200 text-gray-800 text-sm w-full sm:w-auto"
                        onClick={() => {
                          setViewModalOpen(false)
                          setSelectedSubmission(null)
                        }}
                        disabled={actionInProgress}
                      >
                        Close
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </Modal>
        )}

        {/* Reject System Modal */}
        {rejectModalOpen && selectedSubmission && (
          <Modal
            title={`Reject: ${selectedSubmission.system_name}`}
            onClose={() => {
              setRejectModalOpen(false)
              setSelectedSubmission(null)
              setRejectionReason('')
            }}
          >
            <div className="space-y-4">
              <p className="text-sm text-gray-700">
                Please provide a reason for rejecting this submission. This will help the submitter understand why their system was not approved.
              </p>

              <div>
                <label className="block text-sm font-semibold mb-2">Rejection Reason</label>
                <textarea
                  className="w-full border rounded p-2"
                  rows="4"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="e.g., Duplicate system, incomplete information, violates naming guidelines..."
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-2">
                <Button
                  className="bg-red-600 text-white hover:bg-red-700 text-sm w-full sm:w-auto"
                  onClick={rejectSubmission}
                  disabled={actionInProgress || !rejectionReason.trim()}
                >
                  {actionInProgress ? 'Rejecting...' : 'Confirm Rejection'}
                </Button>
                <Button
                  className="bg-gray-200 text-gray-800 text-sm w-full sm:w-auto"
                  onClick={() => {
                    setRejectModalOpen(false)
                    setRejectionReason('')
                    setViewModalOpen(true)
                  }}
                  disabled={actionInProgress}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </Modal>
        )}

        {/* Region Name Review Modal */}
        {regionModalOpen && selectedRegion && (
          <Modal
            title={`Review Region Name: ${selectedRegion.proposed_name}`}
            onClose={() => {
              setRegionModalOpen(false)
              setSelectedRegion(null)
            }}
          >
            <div className="space-y-4">
              <div className="border-b pb-3">
                <h4 className="font-semibold mb-2">Region Name Submission</h4>
                <div className="text-sm space-y-1">
                  <p><strong>Proposed Name:</strong> {selectedRegion.proposed_name}</p>
                  <p><strong>Region Coordinates:</strong> [{selectedRegion.region_x}, {selectedRegion.region_y}, {selectedRegion.region_z}]</p>
                </div>
              </div>

              <div className="text-sm text-gray-600">
                <p><strong>Submitted by:</strong> {selectedRegion.personal_discord_username || selectedRegion.submitted_by || 'Anonymous'}</p>
                <p><strong>Submission Date:</strong> {new Date(selectedRegion.submission_date).toLocaleString()}</p>
                {/* IP Address only visible to super admin for security */}
                {isSuperAdmin && selectedRegion.submitted_by_ip && (
                  <p><strong>IP Address:</strong> {selectedRegion.submitted_by_ip}</p>
                )}
                {/* Discord info */}
                {(isSuperAdmin || isHavenSubAdmin) && selectedRegion.discord_tag && (
                  <p className="mt-2">
                    <strong>Discord Community:</strong>{' '}
                    {getDiscordTagBadge(selectedRegion.discord_tag, isSuperAdmin ? selectedRegion.personal_discord_username : null)}
                  </p>
                )}
              </div>

              {selectedRegion.status === 'pending' && (
                <div className="flex flex-col sm:flex-row gap-2 pt-3 border-t">
                  <Button
                    className="btn-primary bg-green-600 hover:bg-green-700 text-sm w-full sm:w-auto"
                    onClick={() => approveRegion(selectedRegion)}
                    disabled={actionInProgress}
                  >
                    {actionInProgress ? 'Approving...' : 'Approve'}
                  </Button>
                  <Button
                    className="bg-red-600 text-white hover:bg-red-700 text-sm w-full sm:w-auto"
                    onClick={() => {
                      setRegionModalOpen(false)
                      setRejectionReason('')
                      setRejectModalOpen(true)
                    }}
                    disabled={actionInProgress}
                  >
                    Reject
                  </Button>
                  <Button
                    className="bg-gray-200 text-gray-800 text-sm w-full sm:w-auto"
                    onClick={() => {
                      setRegionModalOpen(false)
                      setSelectedRegion(null)
                    }}
                    disabled={actionInProgress}
                  >
                    Close
                  </Button>
                </div>
              )}
            </div>
          </Modal>
        )}

        {/* Reject Region Modal */}
        {rejectModalOpen && selectedRegion && (
          <Modal
            title={`Reject: ${selectedRegion.proposed_name}`}
            onClose={() => {
              setRejectModalOpen(false)
              setSelectedRegion(null)
              setRejectionReason('')
            }}
          >
            <div className="space-y-4">
              <p className="text-sm text-gray-700">
                Please provide a reason for rejecting this region name submission.
              </p>

              <div>
                <label className="block text-sm font-semibold mb-2">Rejection Reason</label>
                <textarea
                  className="w-full border rounded p-2"
                  rows="4"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="e.g., Name already in use, inappropriate name, etc..."
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-2">
                <Button
                  className="bg-red-600 text-white hover:bg-red-700 text-sm w-full sm:w-auto"
                  onClick={rejectRegion}
                  disabled={actionInProgress || !rejectionReason.trim()}
                >
                  {actionInProgress ? 'Rejecting...' : 'Confirm Rejection'}
                </Button>
                <Button
                  className="bg-gray-200 text-gray-800 text-sm w-full sm:w-auto"
                  onClick={() => {
                    setRejectModalOpen(false)
                    setRejectionReason('')
                    setRegionModalOpen(true)
                  }}
                  disabled={actionInProgress}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </Modal>
        )}

        {/* Edit Request Review Modal */}
        {editRequestModalOpen && selectedEditRequest && (
          <Modal
            title={`Review Edit Request: ${selectedEditRequest.system_name || 'Unknown System'}`}
            onClose={() => {
              setEditRequestModalOpen(false)
              setSelectedEditRequest(null)
            }}
          >
            <div className="space-y-4">
              {/* Partner Info */}
              <div className="border-b pb-3">
                <h4 className="font-semibold mb-2">Submitted By</h4>
                <div className="text-sm space-y-1">
                  <p><strong>Partner:</strong> {selectedEditRequest.partner_username || 'Unknown'}</p>
                  {selectedEditRequest.partner_discord_tag && (
                    <p><strong>Discord Tag:</strong> <span className="text-cyan-400">{selectedEditRequest.partner_discord_tag}</span></p>
                  )}
                  <p><strong>Submitted:</strong> {new Date(selectedEditRequest.submitted_at).toLocaleString()}</p>
                </div>
              </div>

              {/* Explanation */}
              <div className="border-b pb-3">
                <h4 className="font-semibold mb-2">Reason for Edit</h4>
                <div className="bg-yellow-900/30 border border-yellow-700 rounded p-3 text-yellow-200">
                  {selectedEditRequest.explanation || 'No explanation provided'}
                </div>
              </div>

              {/* Edit Data Summary */}
              <div className="border-b pb-3">
                <h4 className="font-semibold mb-2">Proposed Changes</h4>
                <div className="text-sm bg-gray-700 p-3 rounded max-h-64 overflow-y-auto">
                  {selectedEditRequest.edit_data ? (
                    <div className="space-y-1">
                      <p><strong>System Name:</strong> {selectedEditRequest.edit_data.name}</p>
                      <p><strong>Galaxy:</strong> {selectedEditRequest.edit_data.galaxy || 'Euclid'}</p>
                      <p><strong>Reality:</strong> <span className={selectedEditRequest.edit_data.reality === 'Permadeath' ? 'text-red-400' : 'text-green-400'}>{selectedEditRequest.edit_data.reality || 'Normal'}</span></p>
                      {selectedEditRequest.edit_data.description && (
                        <p><strong>Description:</strong> {selectedEditRequest.edit_data.description}</p>
                      )}
                      {selectedEditRequest.edit_data.planets && (
                        <p><strong>Planets:</strong> {selectedEditRequest.edit_data.planets.length}</p>
                      )}
                      {selectedEditRequest.edit_data.discord_tag && (
                        <p><strong>New Discord Tag:</strong> <span className="text-cyan-400">{selectedEditRequest.edit_data.discord_tag}</span></p>
                      )}
                    </div>
                  ) : (
                    <p className="text-gray-400">No edit data available</p>
                  )}
                </div>
              </div>

              {/* Actions */}
              {selectedEditRequest.status === 'pending' && (
                <div className="flex flex-col sm:flex-row gap-2 pt-3 border-t">
                  <Button
                    className="btn-primary bg-green-600 hover:bg-green-700 text-sm w-full sm:w-auto"
                    onClick={() => approveEditRequest(selectedEditRequest)}
                    disabled={actionInProgress}
                  >
                    {actionInProgress ? 'Approving...' : 'Approve'}
                  </Button>
                  <Button
                    className="bg-red-600 text-white hover:bg-red-700 text-sm w-full sm:w-auto"
                    onClick={() => {
                      setEditRequestModalOpen(false)
                      setRejectionReason('')
                      setRejectModalOpen(true)
                    }}
                    disabled={actionInProgress}
                  >
                    Reject
                  </Button>
                  <Button
                    className="bg-gray-200 text-gray-800 text-sm w-full sm:w-auto"
                    onClick={() => {
                      setEditRequestModalOpen(false)
                      setSelectedEditRequest(null)
                    }}
                    disabled={actionInProgress}
                  >
                    Close
                  </Button>
                </div>
              )}
            </div>
          </Modal>
        )}

        {/* Reject Edit Request Modal */}
        {rejectModalOpen && selectedEditRequest && (
          <Modal
            title={`Reject Edit: ${selectedEditRequest.system_name || 'Unknown System'}`}
            onClose={() => {
              setRejectModalOpen(false)
              setSelectedEditRequest(null)
              setRejectionReason('')
            }}
          >
            <div className="space-y-4">
              <p className="text-sm text-gray-700">
                Please provide a reason for rejecting this edit request. This will be visible to the partner.
              </p>

              <div>
                <label className="block text-sm font-semibold mb-2">Rejection Reason</label>
                <textarea
                  className="w-full border rounded p-2"
                  rows="4"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="e.g., Edit not appropriate, system belongs to another community, etc..."
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-2">
                <Button
                  className="bg-red-600 text-white hover:bg-red-700 text-sm w-full sm:w-auto"
                  onClick={rejectEditRequest}
                  disabled={actionInProgress || !rejectionReason.trim()}
                >
                  {actionInProgress ? 'Rejecting...' : 'Confirm Rejection'}
                </Button>
                <Button
                  className="bg-gray-200 text-gray-800 text-sm w-full sm:w-auto"
                  onClick={() => {
                    setRejectModalOpen(false)
                    setRejectionReason('')
                    setEditRequestModalOpen(true)
                  }}
                  disabled={actionInProgress}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </Modal>
        )}

        {/* Batch Rejection Reason Modal */}
        {batchRejectModalOpen && (
          <Modal
            title={`Batch Reject ${selectedIds.size} Submission(s)`}
            onClose={() => {
              setBatchRejectModalOpen(false)
              setBatchRejectionReason('')
            }}
          >
            <div className="space-y-4">
              <p className="text-sm text-gray-700">
                Please provide a reason for rejecting these {selectedIds.size} submission(s). This reason will be applied to all selected items.
              </p>

              <div>
                <label className="block text-sm font-semibold mb-2">Rejection Reason</label>
                <textarea
                  className="w-full border rounded p-2"
                  rows="4"
                  value={batchRejectionReason}
                  onChange={(e) => setBatchRejectionReason(e.target.value)}
                  placeholder="e.g., Duplicate systems, incomplete information, violates naming guidelines..."
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-2">
                <Button
                  className="bg-red-600 text-white hover:bg-red-700 text-sm w-full sm:w-auto"
                  onClick={handleBatchReject}
                  disabled={batchInProgress || !batchRejectionReason.trim()}
                >
                  {batchInProgress ? 'Rejecting...' : `Reject ${selectedIds.size}`}
                </Button>
                <Button
                  className="bg-gray-200 text-gray-800 text-sm w-full sm:w-auto"
                  onClick={() => {
                    setBatchRejectModalOpen(false)
                    setBatchRejectionReason('')
                  }}
                  disabled={batchInProgress}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </Modal>
        )}

        {/* Batch Results Modal */}
        {batchResultsModalOpen && batchResults && (
          <Modal
            title="Batch Operation Results"
            onClose={() => {
              setBatchResultsModalOpen(false)
              setBatchResults(null)
            }}
          >
            <div className="space-y-4">
              {/* Summary */}
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-3 bg-green-900/50 border border-green-500 rounded">
                  <div className="text-2xl font-bold text-green-400">
                    {batchResults.summary?.approved || batchResults.summary?.rejected || 0}
                  </div>
                  <div className="text-sm text-green-300">
                    {batchResults.results?.approved ? 'Approved' : 'Rejected'}
                  </div>
                </div>
                <div className="p-3 bg-red-900/50 border border-red-500 rounded">
                  <div className="text-2xl font-bold text-red-400">
                    {batchResults.summary?.failed || 0}
                  </div>
                  <div className="text-sm text-red-300">Failed</div>
                </div>
                <div className="p-3 bg-amber-900/50 border border-amber-500 rounded">
                  <div className="text-2xl font-bold text-amber-400">
                    {batchResults.summary?.skipped || 0}
                  </div>
                  <div className="text-sm text-amber-300">Skipped</div>
                </div>
              </div>

              {/* Details */}
              <div className="max-h-64 overflow-y-auto space-y-3">
                {/* Approved/Rejected */}
                {(batchResults.results?.approved?.length > 0 || batchResults.results?.rejected?.length > 0) && (
                  <div>
                    <h4 className="font-semibold text-green-400 mb-1">
                      {batchResults.results?.approved ? 'Approved' : 'Rejected'}:
                    </h4>
                    <ul className="text-sm space-y-1">
                      {(batchResults.results?.approved || batchResults.results?.rejected || []).map(item => (
                        <li key={item.id} className="text-gray-300">
                          {item.name || `ID: ${item.id}`}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Failed */}
                {batchResults.results?.failed?.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-red-400 mb-1">Failed:</h4>
                    <ul className="text-sm space-y-1">
                      {batchResults.results.failed.map(item => (
                        <li key={item.id} className="text-red-300">
                          {item.name || `ID: ${item.id}`}: {item.error}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Skipped */}
                {batchResults.results?.skipped?.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-amber-400 mb-1">Skipped:</h4>
                    <ul className="text-sm space-y-1">
                      {batchResults.results.skipped.map(item => (
                        <li key={item.id} className="text-amber-300">
                          {item.name || `ID: ${item.id}`}: {item.reason}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <div className="pt-3 border-t">
                <Button
                  className="bg-gray-200 text-gray-800"
                  onClick={() => {
                    setBatchResultsModalOpen(false)
                    setBatchResults(null)
                  }}
                >
                  Close
                </Button>
              </div>
            </div>
          </Modal>
        )}
        {/* Discovery Review Modal */}
        {discoveryModalOpen && selectedDiscoveryApproval && (
          <Modal
            title={`Review: ${selectedDiscoveryApproval.discovery_name}`}
            onClose={() => {
              setDiscoveryModalOpen(false)
              setSelectedDiscoveryApproval(null)
            }}
          >
            <div className="space-y-4">
              {/* Discovery Photo */}
              {selectedDiscoveryApproval.photo_url && (
                <div className="aspect-video rounded overflow-hidden bg-gray-800">
                  <img
                    src={selectedDiscoveryApproval.photo_url.startsWith('http') ? selectedDiscoveryApproval.photo_url : `/haven-ui-photos/${encodeURIComponent(selectedDiscoveryApproval.photo_url.split(/[/\\]/).pop())}`}
                    alt={selectedDiscoveryApproval.discovery_name}
                    className="w-full h-full object-contain"
                  />
                </div>
              )}

              {/* Discovery Info */}
              <div className="border-b pb-3">
                <h4 className="font-semibold mb-2">Discovery Information</h4>
                <div className="text-sm space-y-1">
                  <p><strong>Name:</strong> {selectedDiscoveryApproval.discovery_name}</p>
                  <p><strong>Type:</strong> {selectedDiscoveryApproval.type_info?.emoji} {selectedDiscoveryApproval.type_info?.label || selectedDiscoveryApproval.discovery_type}</p>
                  {selectedDiscoveryApproval.description && (
                    <p><strong>Description:</strong> {selectedDiscoveryApproval.description}</p>
                  )}
                </div>
              </div>

              {/* Location */}
              <div className="border-b pb-3">
                <h4 className="font-semibold mb-2">Location</h4>
                <div className="text-sm space-y-1">
                  <p><strong>System:</strong> {selectedDiscoveryApproval.system_name || 'Unknown'}</p>
                  {selectedDiscoveryApproval.location_type && (
                    <p><strong>Location Type:</strong> {selectedDiscoveryApproval.location_type === 'space' ? 'Space' : selectedDiscoveryApproval.location_type === 'moon' ? 'Moon' : 'Planet'}</p>
                  )}
                  {selectedDiscoveryApproval.planet_name && (
                    <p><strong>Planet:</strong> {selectedDiscoveryApproval.planet_name}</p>
                  )}
                  {selectedDiscoveryApproval.moon_name && (
                    <p><strong>Moon:</strong> {selectedDiscoveryApproval.moon_name}</p>
                  )}
                </div>
              </div>

              {/* Type Metadata */}
              {selectedDiscoveryApproval.discovery_data?.type_metadata && Object.keys(selectedDiscoveryApproval.discovery_data.type_metadata).length > 0 && (
                <div className="border-b pb-3">
                  <h4 className="font-semibold mb-2">Details</h4>
                  <div className="text-sm space-y-1">
                    {Object.entries(selectedDiscoveryApproval.discovery_data.type_metadata).map(([key, value]) => (
                      value && (
                        <p key={key}>
                          <strong>{key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}:</strong> {value}
                        </p>
                      )
                    ))}
                  </div>
                </div>
              )}

              {/* Submission Metadata */}
              <div className="text-sm text-gray-600">
                <p><strong>Submitted by:</strong> {selectedDiscoveryApproval.submitted_by || 'Anonymous'}</p>
                <p><strong>Submission Date:</strong> {new Date(selectedDiscoveryApproval.submission_date).toLocaleString()}</p>
                {isSuperAdmin && selectedDiscoveryApproval.submitted_by_ip && (
                  <p><strong>IP Address:</strong> {selectedDiscoveryApproval.submitted_by_ip}</p>
                )}
                {(isSuperAdmin || isHavenSubAdmin) && selectedDiscoveryApproval.discord_tag && (
                  <p className="mt-2">
                    <strong>Discord Community:</strong>{' '}
                    {getDiscordTagBadge(selectedDiscoveryApproval.discord_tag)}
                  </p>
                )}
              </div>

              {/* Actions */}
              {selectedDiscoveryApproval.status === 'pending' && (
                <div className="pt-3 border-t">
                  {checkDiscoverySelfSubmission(selectedDiscoveryApproval) && (
                    <div className="mb-3 p-3 bg-amber-900/50 border border-amber-500 rounded">
                      <p className="text-amber-300 text-sm">
                        <strong>You submitted this discovery.</strong> Another admin must review and approve it.
                      </p>
                    </div>
                  )}
                  <div className="flex flex-col sm:flex-row gap-2">
                    <Button
                      className="btn-primary bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm w-full sm:w-auto"
                      onClick={() => approveDiscoverySubmission(selectedDiscoveryApproval.id, selectedDiscoveryApproval.discovery_name)}
                      disabled={actionInProgress || checkDiscoverySelfSubmission(selectedDiscoveryApproval)}
                      title={checkDiscoverySelfSubmission(selectedDiscoveryApproval) ? 'You cannot approve your own submission' : ''}
                    >
                      {checkDiscoverySelfSubmission(selectedDiscoveryApproval) ? 'Cannot Self-Approve' : (actionInProgress ? 'Approving...' : 'Approve')}
                    </Button>
                    <Button
                      className="bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm w-full sm:w-auto"
                      onClick={() => {
                        setDiscoveryModalOpen(false)
                        openDiscoveryRejectModal(selectedDiscoveryApproval)
                      }}
                      disabled={actionInProgress || checkDiscoverySelfSubmission(selectedDiscoveryApproval)}
                      title={checkDiscoverySelfSubmission(selectedDiscoveryApproval) ? 'You cannot reject your own submission' : ''}
                    >
                      {checkDiscoverySelfSubmission(selectedDiscoveryApproval) ? 'Cannot Reject' : 'Reject'}
                    </Button>
                    <Button
                      className="bg-gray-200 text-gray-800 text-sm w-full sm:w-auto"
                      onClick={() => {
                        setDiscoveryModalOpen(false)
                        setSelectedDiscoveryApproval(null)
                      }}
                      disabled={actionInProgress}
                    >
                      Close
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </Modal>
        )}

        {/* Discovery Reject Modal */}
        {discoveryRejectModalOpen && selectedDiscoveryApproval && (
          <Modal
            title={`Reject: ${selectedDiscoveryApproval.discovery_name}`}
            onClose={() => {
              setDiscoveryRejectModalOpen(false)
              setSelectedDiscoveryApproval(null)
              setDiscoveryRejectionReason('')
            }}
          >
            <div className="space-y-4">
              <p className="text-sm text-gray-700">
                Please provide a reason for rejecting this discovery submission.
              </p>

              <div>
                <label className="block text-sm font-semibold mb-2">Rejection Reason</label>
                <textarea
                  className="w-full border rounded p-2"
                  rows="4"
                  value={discoveryRejectionReason}
                  onChange={(e) => setDiscoveryRejectionReason(e.target.value)}
                  placeholder="e.g., Duplicate discovery, incorrect type, needs more evidence..."
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-2">
                <Button
                  className="bg-red-600 text-white hover:bg-red-700 text-sm w-full sm:w-auto"
                  onClick={rejectDiscoverySubmission}
                  disabled={actionInProgress || !discoveryRejectionReason.trim()}
                >
                  {actionInProgress ? 'Rejecting...' : 'Confirm Rejection'}
                </Button>
                <Button
                  className="bg-gray-200 text-gray-800 text-sm w-full sm:w-auto"
                  onClick={() => {
                    setDiscoveryRejectModalOpen(false)
                    setDiscoveryRejectionReason('')
                    setDiscoveryModalOpen(true)
                  }}
                  disabled={actionInProgress}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </Modal>
        )}

      </Card>
    </div>
  )
}
