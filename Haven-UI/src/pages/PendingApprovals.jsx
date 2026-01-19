import React, { useEffect, useState, useContext } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import Modal from '../components/Modal'
import { AuthContext, FEATURES } from '../utils/AuthContext'

export default function PendingApprovals() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const { isAdmin, isSuperAdmin, isHavenSubAdmin, user, loading: authLoading, canAccess } = auth || {}

  // Normalize Discord username by stripping #XXXX discriminator and lowercasing
  function normalizeDiscordUsername(username) {
    if (!username) return ''
    let normalized = username.toLowerCase().trim()
    // Strip Discord discriminator (#0000 to #9999)
    if (normalized.includes('#')) {
      normalized = normalized.split('#')[0]
    }
    return normalized
  }

  // Check if a submission was made by the current user (self-submission)
  function isSelfSubmission(submission) {
    if (!user) return false
    // Super admin can approve their own (trusted role)
    if (isSuperAdmin) return false
    // Check by account ID first (most reliable for logged-in submissions)
    if (submission.submitter_account_id && submission.submitter_account_type) {
      return user.type === submission.submitter_account_type &&
             user.accountId === submission.submitter_account_id
    }
    // Check by username against both submitted_by and personal_discord_username
    // Uses normalized comparison to handle Discord #XXXX discriminator (e.g., TurpitZz vs TurpitZz#9999)
    if (user.username) {
      const normalizedUser = normalizeDiscordUsername(user.username)
      // Check submitted_by
      if (submission.submitted_by && normalizeDiscordUsername(submission.submitted_by) === normalizedUser) {
        return true
      }
      // Check personal_discord_username (for personal uploads where user wasn't logged in)
      if (submission.personal_discord_username && normalizeDiscordUsername(submission.personal_discord_username) === normalizedUser) {
        return true
      }
    }
    return false
  }
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
      const [systemsResponse, regionsResponse, editRequestsResponse] = await Promise.all([
        axios.get('/api/pending_systems'),
        axios.get('/api/pending_region_names'),
        axios.get('/api/pending_edits')
      ])
      setSubmissions(systemsResponse.data.submissions || [])
      setRegionSubmissions(regionsResponse.data.pending || [])
      setEditRequests(editRequestsResponse.data.requests || [])
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
      .filter(s => !isSelfSubmission(s))
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

  if (authLoading || loading) {
    return (
      <div className="p-4">
        <Card>
          <p>Loading submissions...</p>
        </Card>
      </div>
    )
  }

  const pendingSubmissions = submissions.filter(s => s.status === 'pending')
  const reviewedSubmissions = submissions.filter(s => s.status !== 'pending')

  // Apply discord_tag filter for super admin
  const filteredPendingSubmissions = isSuperAdmin && filterTag !== 'all'
    ? pendingSubmissions.filter(s => {
        if (filterTag === 'untagged') return !s.discord_tag
        return s.discord_tag === filterTag
      })
    : pendingSubmissions

  const filteredReviewedSubmissions = isSuperAdmin && filterTag !== 'all'
    ? reviewedSubmissions.filter(s => {
        if (filterTag === 'untagged') return !s.discord_tag
        return s.discord_tag === filterTag
      })
    : reviewedSubmissions

  const pendingRegions = regionSubmissions.filter(r => r.status === 'pending')
  const pendingEdits = editRequests.filter(e => e.status === 'pending')

  // Helper to get discord tag badge color - each tag gets its own unique color
  function getDiscordTagBadge(tag, personalDiscordUsername = null) {
    if (!tag) {
      return (
        <span className="px-2 py-1 rounded text-xs font-semibold bg-gray-500 text-white">
          UNTAGGED
        </span>
      )
    }

    // Special handling for "personal" tag - magenta color
    // Show the discord username inside the badge if provided (super admin only)
    if (tag === 'personal') {
      return (
        <span className="px-2 py-1 rounded text-xs font-semibold bg-fuchsia-600 text-white">
          PERSONAL{personalDiscordUsername ? ` - ${personalDiscordUsername}` : ''}
        </span>
      )
    }

    // Predefined colors for known tags (actual partner discord tags)
    const tagColors = {
      'Haven': 'bg-cyan-500 text-white',
      'IEA': 'bg-green-500 text-white',
      'B.E.S': 'bg-orange-500 text-white',
      'ARCH': 'bg-purple-500 text-white',
      'TBH': 'bg-yellow-500 text-black',
      'EVRN': 'bg-pink-500 text-white',
    }

    // If tag has a predefined color, use it
    if (tagColors[tag]) {
      return (
        <span className={`px-2 py-1 rounded text-xs font-semibold ${tagColors[tag]}`}>
          {tag}
        </span>
      )
    }

    // For unknown tags, generate a color based on the tag name hash
    const colorPalette = [
      'bg-indigo-500 text-white',
      'bg-violet-500 text-white',
      'bg-fuchsia-500 text-white',
      'bg-amber-500 text-black',
      'bg-lime-500 text-black',
      'bg-teal-500 text-white',
      'bg-sky-500 text-white',
      'bg-rose-500 text-white',
    ]

    // Simple hash to get consistent color per tag
    let hash = 0
    for (let i = 0; i < tag.length; i++) {
      hash = tag.charCodeAt(i) + ((hash << 5) - hash)
    }
    const colorIndex = Math.abs(hash) % colorPalette.length

    return (
      <span className={`px-2 py-1 rounded text-xs font-semibold ${colorPalette[colorIndex]}`}>
        {tag}
      </span>
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
                  {selectedIds.size}/{filteredPendingSubmissions.filter(s => !isSelfSubmission(s)).length} selected
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
            {isSuperAdmin && filterTag !== 'all' && ` of ${pendingSubmissions.length}`})
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
                          disabled={isSelfSubmission(submission)}
                          className="w-5 h-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                          title={isSelfSubmission(submission) ? 'Cannot select your own submission' : ''}
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
                        {isSelfSubmission(submission) && (
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
              {isSuperAdmin && filterTag !== 'all' && ` of ${reviewedSubmissions.length}`})
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

        {/* View/Review Modal */}
        {viewModalOpen && selectedSubmission && (
          <Modal
            title={`Review: ${selectedSubmission.system_name}`}
            onClose={() => {
              setViewModalOpen(false)
              setSelectedSubmission(null)
            }}
          >
            <div className="space-y-4">
              {/* System Details */}
              <div className="border-b pb-3">
                <h4 className="font-semibold mb-2">System Information</h4>
                <div className="text-sm space-y-1">
                  <p><strong>Name:</strong> {selectedSubmission.system_data?.name}</p>
                  <p><strong>Galaxy:</strong> {selectedSubmission.system_data?.galaxy || 'Euclid'}</p>
                  <p><strong>Reality:</strong> <span className={selectedSubmission.system_data?.reality === 'Permadeath' ? 'text-red-400' : 'text-green-400'}>{selectedSubmission.system_data?.reality || 'Normal'}</span></p>
                  {selectedSubmission.glyph_code && (
                    <p><strong>Glyph Code:</strong> <span className="font-mono">{selectedSubmission.glyph_code}</span></p>
                  )}
                  {selectedSubmission.system_data?.region_x !== null && (
                    <p><strong>Region:</strong> [{selectedSubmission.system_data.region_x}, {selectedSubmission.system_data.region_y}, {selectedSubmission.system_data.region_z}]</p>
                  )}
                  <p><strong>Coordinates:</strong> ({selectedSubmission.system_data?.x || 0}, {selectedSubmission.system_data?.y || 0}, {selectedSubmission.system_data?.z || 0})</p>
                  {/* Extractor-specific system properties */}
                  {selectedSubmission.system_data?.star_type && selectedSubmission.system_data.star_type !== 'Unknown' && (
                    <p><strong>Star Type:</strong> <span className={
                      selectedSubmission.system_data.star_type === 'Yellow' ? 'text-yellow-400' :
                      selectedSubmission.system_data.star_type === 'Red' ? 'text-red-400' :
                      selectedSubmission.system_data.star_type === 'Green' ? 'text-green-400' :
                      selectedSubmission.system_data.star_type === 'Blue' ? 'text-blue-400' : ''
                    }>{selectedSubmission.system_data.star_type}</span></p>
                  )}
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
                  <p><strong>Description:</strong> {selectedSubmission.system_data?.description || 'None'}</p>
                </div>
              </div>

              {/* Planets */}
              {selectedSubmission.system_data?.planets && selectedSubmission.system_data.planets.length > 0 && (
                <div className="border-b pb-3">
                  <h4 className="font-semibold mb-2">Planets ({selectedSubmission.system_data.planets.length})</h4>
                  <div className="space-y-3">
                    {selectedSubmission.system_data.planets.map((planet, i) => (
                      <div key={i} className="text-sm bg-cyan-700 p-3 rounded">
                        <div className="flex items-start gap-3">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <p className="font-semibold text-base">{planet.name}</p>
                              {/* Planet size badge */}
                              {planet.planet_size && planet.planet_size !== 'Unknown' && (
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                  planet.planet_size === 'Large' ? 'bg-purple-600 text-white' :
                                  planet.planet_size === 'Medium' ? 'bg-blue-600 text-white' :
                                  planet.planet_size === 'Small' ? 'bg-green-600 text-white' :
                                  'bg-gray-600 text-white'
                                }`}>{planet.planet_size}</span>
                              )}
                            </div>
                            {/* Biome info (from extractor) */}
                            {(planet.biome || planet.biome_subtype) && (
                              <div className="mb-2 text-gray-300">
                                {planet.biome && planet.biome !== 'Unknown' && (
                                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium mr-2 ${
                                    planet.biome === 'Lush' ? 'bg-green-700' :
                                    planet.biome === 'Toxic' ? 'bg-yellow-700' :
                                    planet.biome === 'Scorched' ? 'bg-orange-700' :
                                    planet.biome === 'Radioactive' ? 'bg-lime-700' :
                                    planet.biome === 'Frozen' ? 'bg-cyan-700' :
                                    planet.biome === 'Barren' ? 'bg-stone-700' :
                                    planet.biome === 'Dead' ? 'bg-gray-700' :
                                    planet.biome === 'Weird' ? 'bg-purple-700' :
                                    planet.biome === 'Swamp' ? 'bg-emerald-800' :
                                    planet.biome === 'Lava' ? 'bg-red-700' :
                                    'bg-gray-600'
                                  }`}>{planet.biome}</span>
                                )}
                                {planet.biome_subtype && planet.biome_subtype !== 'Unknown' && planet.biome_subtype !== 'None' && (
                                  <span className="text-xs text-gray-400">({planet.biome_subtype})</span>
                                )}
                              </div>
                            )}
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-gray-300">
                              <div><span className="text-gray-400">Sentinel:</span> {planet.sentinel || planet.sentinels || 'None'}</div>
                              <div><span className="text-gray-400">Fauna:</span> {planet.fauna || 'N/A'}{planet.fauna_count > 0 && ` (${planet.fauna_count})`}</div>
                              <div><span className="text-gray-400">Flora:</span> {planet.flora || 'N/A'}{planet.flora_count > 0 && ` (${planet.flora_count})`}</div>
                              {(planet.climate || planet.weather) && <div><span className="text-gray-400">Weather:</span> {planet.climate || planet.weather}</div>}
                              {planet.has_water === 1 && <div><span className="text-cyan-300">Has Water</span></div>}
                            </div>
                          </div>
                        </div>
                        {/* Resources/Materials */}
                        {(planet.materials || (planet.resources && planet.resources.length > 0)) && (
                          <div className="mt-2 text-gray-300">
                            <span className="text-gray-400">Resources:</span> {planet.materials || planet.resources?.join(', ')}
                          </div>
                        )}
                        {planet.base_location && (
                          <div className="mt-1 text-gray-300">
                            <span className="text-gray-400">Base Location:</span> {planet.base_location}
                          </div>
                        )}
                        {planet.description && (
                          <div className="mt-1 text-gray-300">
                            <span className="text-gray-400">Description:</span> {planet.description}
                          </div>
                        )}
                        {planet.notes && (
                          <div className="mt-1 text-gray-300">
                            <span className="text-gray-400">Notes:</span> {planet.notes}
                          </div>
                        )}
                        {planet.photo && (
                          <div className="mt-2">
                            <span className="text-gray-400">Photo:</span> <span className="text-cyan-300">{planet.photo}</span>
                          </div>
                        )}
                        {planet.moons && planet.moons.length > 0 && (
                          <div className="mt-2 ml-3 border-l-2 border-cyan-500 pl-3">
                            <p className="text-gray-400 text-xs mb-1">Moons ({planet.moons.length}):</p>
                            {planet.moons.map((moon, j) => (
                              <div key={j} className="mb-2 text-xs">
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
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Moons (top-level from extractor - separate from planet.moons) */}
              {selectedSubmission.system_data?.moons && selectedSubmission.system_data.moons.length > 0 && (
                <div className="border-b pb-3">
                  <h4 className="font-semibold mb-2">Moons ({selectedSubmission.system_data.moons.length})</h4>
                  <div className="space-y-2">
                    {selectedSubmission.system_data.moons.map((moon, i) => (
                      <div key={i} className="text-sm bg-gray-700 p-3 rounded">
                        <div className="flex items-center gap-2 mb-2">
                          <p className="font-semibold">{moon.name}</p>
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-500 text-white">Moon</span>
                          {moon.biome && moon.biome !== 'Unknown' && (
                            <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-600">{moon.biome}</span>
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
                      </div>
                    ))}
                  </div>
                </div>
              )}

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
                  {isSelfSubmission(selectedSubmission) && (
                    <div className="mb-3 p-3 bg-amber-900/50 border border-amber-500 rounded">
                      <p className="text-amber-300 text-sm">
                        <strong>You submitted this system.</strong> Another admin must review and approve it to prevent conflicts of interest.
                      </p>
                    </div>
                  )}
                  <div className="flex flex-col sm:flex-row gap-2">
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
      </Card>
    </div>
  )
}
