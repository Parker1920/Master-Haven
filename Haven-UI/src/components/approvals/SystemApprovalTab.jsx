import React, { useState, useMemo, useCallback } from 'react'
import axios from 'axios'
import Button from '../Button'
import Modal from '../Modal'
import GlyphDisplay from '../GlyphDisplay'
import { FEATURES } from '../../utils/AuthContext'

/**
 * SystemApprovalTab - Systems/regions/edit request approval content
 *
 * Props:
 *   submissions           - Array of system submissions
 *   regionSubmissions     - Array of region name submissions
 *   editRequests          - Array of edit requests
 *   isSuperAdmin          - Boolean
 *   isHavenSubAdmin       - Boolean
 *   canAccess             - Feature access checker function
 *   user                  - Current user object
 *   filterTag             - Current discord tag filter value
 *   getDiscordTagBadge    - Function to render discord tag badge
 *   isSelfSubmission      - Function to check if submission is by current user
 *   personalColor         - Personal submission color
 *   loadSubmissions       - Function to reload all submissions
 */
export default function SystemApprovalTab({
  submissions,
  regionSubmissions,
  editRequests,
  isSuperAdmin,
  isHavenSubAdmin,
  canAccess,
  user,
  filterTag,
  getDiscordTagBadge,
  isSelfSubmission,
  personalColor,
  loadSubmissions,
}) {
  // System review modal state
  const [selectedSubmission, setSelectedSubmission] = useState(null)
  const [viewModalOpen, setViewModalOpen] = useState(false)
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

  // Batch region name state
  const [batchRegionMode, setBatchRegionMode] = useState(false)
  const [selectedRegionIds, setSelectedRegionIds] = useState(new Set())
  const [batchRegionInProgress, setBatchRegionInProgress] = useState(false)
  const [batchRegionRejectModalOpen, setBatchRegionRejectModalOpen] = useState(false)
  const [batchRegionRejectionReason, setBatchRegionRejectionReason] = useState('')

  // Region modal state
  const [selectedRegion, setSelectedRegion] = useState(null)
  const [regionModalOpen, setRegionModalOpen] = useState(false)

  // Edit request modal state
  const [selectedEditRequest, setSelectedEditRequest] = useState(null)
  const [editRequestModalOpen, setEditRequestModalOpen] = useState(false)

  // Edit mode state (super admin only)
  const [editMode, setEditMode] = useState(false)
  const [editData, setEditData] = useState(null)
  const [editSaving, setEditSaving] = useState(false)

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

  // Single-pass filtering - categorize and filter in one iteration (O(n) instead of O(4n))
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

  // --- System submission handlers ---

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

  // --- Edit pending submission functions (super admin only) ---

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

  // --- Region name approval functions ---

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

  // --- Batch region name functions ---

  function toggleRegionSelection(id) {
    setSelectedRegionIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function selectAllRegions() {
    const ids = new Set()
    pendingRegions.forEach(r => {
      if (!isSelfSubmission(r)) ids.add(r.id)
    })
    setSelectedRegionIds(ids)
  }

  function exitBatchRegionMode() {
    setBatchRegionMode(false)
    setSelectedRegionIds(new Set())
  }

  async function handleBatchRegionApprove() {
    if (selectedRegionIds.size === 0) return
    if (!confirm(`Approve ${selectedRegionIds.size} region name(s)?`)) return
    setBatchRegionInProgress(true)
    try {
      const response = await axios.post('/api/approve_region_names/batch', {
        submission_ids: Array.from(selectedRegionIds)
      })
      const data = response.data
      // Wrap in same format as system batch results for the shared modal
      setBatchResults({
        results: { approved: data.approved || [], failed: data.failed || [], skipped: data.skipped || [] },
        summary: {
          total: (data.approved?.length || 0) + (data.failed?.length || 0) + (data.skipped?.length || 0),
          approved: data.approved?.length || 0,
          failed: data.failed?.length || 0,
          skipped: data.skipped?.length || 0
        }
      })
      setBatchResultsModalOpen(true)
      exitBatchRegionMode()
      loadSubmissions()
    } catch (err) {
      alert('Batch approve failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setBatchRegionInProgress(false)
    }
  }

  async function handleBatchRegionReject() {
    if (selectedRegionIds.size === 0) return
    if (!batchRegionRejectionReason.trim()) {
      alert('Please provide a rejection reason')
      return
    }
    setBatchRegionInProgress(true)
    try {
      const response = await axios.post('/api/reject_region_names/batch', {
        submission_ids: Array.from(selectedRegionIds),
        reason: batchRegionRejectionReason
      })
      const data = response.data
      setBatchResults({
        results: { rejected: data.rejected || [], failed: data.failed || [], skipped: data.skipped || [] },
        summary: {
          total: (data.rejected?.length || 0) + (data.failed?.length || 0) + (data.skipped?.length || 0),
          rejected: data.rejected?.length || 0,
          failed: data.failed?.length || 0,
          skipped: data.skipped?.length || 0
        }
      })
      setBatchResultsModalOpen(true)
      exitBatchRegionMode()
      setBatchRegionRejectModalOpen(false)
      setBatchRegionRejectionReason('')
      loadSubmissions()
    } catch (err) {
      alert('Batch reject failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setBatchRegionInProgress(false)
    }
  }

  // --- Edit request functions ---

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

  // --- Batch approval functions ---

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

  return (
    <>
      {/* Batch Mode Toggle in header area */}
      <div className="flex justify-end mb-2">
        {canAccess && canAccess(FEATURES.BATCH_APPROVALS) && filteredPendingSubmissions.length > 0 && (
          <Button
            className={`text-sm ${batchMode ? 'bg-amber-600 hover:bg-amber-700' : 'bg-indigo-600 hover:bg-indigo-700'}`}
            onClick={() => batchMode ? exitBatchMode() : setBatchMode(true)}
          >
            {batchMode ? 'Exit Batch' : 'Batch Mode'}
          </Button>
        )}
      </div>

      {/* Pending Region Names */}
      {pendingRegions.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xl font-semibold">
              Pending Region Names ({pendingRegions.length})
            </h3>
            <div className="flex gap-2">
              {canAccess && canAccess(FEATURES.BATCH_APPROVALS) && pendingRegions.length > 0 && (
                <Button
                  className={`text-sm ${batchRegionMode ? 'bg-amber-600 hover:bg-amber-700' : 'bg-indigo-600 hover:bg-indigo-700'}`}
                  onClick={() => batchRegionMode ? exitBatchRegionMode() : setBatchRegionMode(true)}
                >
                  {batchRegionMode ? 'Exit Batch' : 'Batch Mode'}
                </Button>
              )}
            </div>
          </div>

          {/* Batch region actions bar */}
          {batchRegionMode && (
            <div className="mb-3 p-3 bg-indigo-900/40 border border-indigo-700 rounded flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-3">
                <span className="text-sm text-indigo-300">{selectedRegionIds.size} selected</span>
                <button onClick={selectAllRegions} className="text-sm text-indigo-300 hover:text-white underline">Select All</button>
                {selectedRegionIds.size > 0 && (
                  <button onClick={() => setSelectedRegionIds(new Set())} className="text-sm text-indigo-300 hover:text-white underline">Clear</button>
                )}
              </div>
              {selectedRegionIds.size > 0 && (
                <div className="flex gap-2">
                  <Button
                    className="bg-green-600 hover:bg-green-700 text-white text-sm"
                    onClick={handleBatchRegionApprove}
                    disabled={batchRegionInProgress}
                  >
                    {batchRegionInProgress ? '...' : `Approve (${selectedRegionIds.size})`}
                  </Button>
                  <Button
                    className="bg-red-600 hover:bg-red-700 text-white text-sm"
                    onClick={() => setBatchRegionRejectModalOpen(true)}
                    disabled={batchRegionInProgress}
                  >
                    {batchRegionInProgress ? '...' : `Reject (${selectedRegionIds.size})`}
                  </Button>
                </div>
              )}
            </div>
          )}

          <div className="space-y-2">
            {pendingRegions.map(region => (
              <div
                key={`region-${region.id}`}
                className="border rounded p-3 bg-purple-700 hover:bg-purple-600"
              >
                <div className="flex items-start gap-3">
                  {/* Batch mode checkbox */}
                  {batchRegionMode && (
                    <div className="flex-shrink-0 pt-1">
                      <input
                        type="checkbox"
                        checked={selectedRegionIds.has(region.id)}
                        onChange={() => toggleRegionSelection(region.id)}
                        disabled={isSelfSubmission(region)}
                        className="w-5 h-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                        title={isSelfSubmission(region) ? 'Cannot select your own submission' : ''}
                      />
                    </div>
                  )}
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
                  {!batchRegionMode && (
                    <button
                      onClick={() => viewRegion(region)}
                      className="flex-shrink-0 px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                    >
                      Review
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Batch Region Reject Modal */}
      {batchRegionRejectModalOpen && (
        <Modal title={`Reject ${selectedRegionIds.size} Region Name(s)`} onClose={() => setBatchRegionRejectModalOpen(false)}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Rejection Reason</label>
              <textarea
                value={batchRegionRejectionReason}
                onChange={e => setBatchRegionRejectionReason(e.target.value)}
                className="w-full p-2 border rounded bg-gray-700 border-gray-600 text-sm"
                rows={3}
                placeholder="Enter reason for rejection..."
              />
            </div>
            <div className="flex gap-2">
              <Button
                className="bg-red-600 hover:bg-red-700 text-white text-sm"
                onClick={handleBatchRegionReject}
                disabled={batchRegionInProgress}
              >
                {batchRegionInProgress ? 'Rejecting...' : 'Confirm Reject'}
              </Button>
              <Button
                className="bg-gray-600 hover:bg-gray-700 text-sm"
                onClick={() => setBatchRegionRejectModalOpen(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        </Modal>
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
                      {/* Mismatch warning badge - data differs from existing system */}
                      {submission.system_data?._mismatch_flags?.length > 0 && (
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-yellow-600 text-white" title={submission.system_data._mismatch_flags.join('; ')}>
                          DATA MISMATCH
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
                      <span>Galaxy: {submission.galaxy || submission.system_data?.galaxy || 'Euclid'}</span>
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
                  {!submission.edit_system_id && (
                    <span className="px-2 py-1 rounded text-xs font-semibold bg-green-500 text-white">
                      NEW
                    </span>
                  )}
                  {submission.system_data?._mismatch_flags?.length > 0 && (
                    <span className="px-2 py-1 rounded text-xs font-semibold bg-yellow-600 text-white" title={submission.system_data._mismatch_flags.join('; ')}>
                      DATA MISMATCH
                    </span>
                  )}
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
                        <option value="Purple">Purple</option>
                      </select>
                    </label>
                    <label className="block"><span className="text-gray-400">Economy Type:</span>
                      <select value={editData.economy_type || ''} onChange={e => updateEditField('economy_type', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm">
                        <option value="">Unknown</option>
                        {['Trading','Scientific','Mining','Technology','Manufacturing','Power Generation','Mass Production','Advanced Materials','Pirate','None','Abandoned'].map(v => <option key={v} value={v}>{v}</option>)}
                      </select>
                    </label>
                    <label className="block"><span className="text-gray-400">Economy Level:</span>
                      <select value={editData.economy_level || ''} onChange={e => updateEditField('economy_level', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm">
                        <option value="">Unknown</option>
                        <option value="T1">T1 (Low)</option>
                        <option value="T2">T2 (Medium)</option>
                        <option value="T3">T3 (High)</option>
                        <option value="T4">T4 (Pirate)</option>
                        <option value="None">None</option>
                      </select>
                    </label>
                    <label className="block"><span className="text-gray-400">Conflict Level:</span>
                      <select value={editData.conflict_level || ''} onChange={e => updateEditField('conflict_level', e.target.value)} className="w-full mt-0.5 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm">
                        <option value="">Unknown</option>
                        <option value="Low">Low</option>
                        <option value="Medium">Medium</option>
                        <option value="High">High</option>
                        <option value="Pirate">☠️ Pirate</option>
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
                  {selectedSubmission.system_data?._mismatch_flags?.length > 0 && (
                    <div className="mb-3 p-2 rounded border border-yellow-600 bg-yellow-600/10">
                      <p className="text-yellow-400 font-semibold text-xs mb-1">Data Mismatch — Review Carefully</p>
                      <ul className="text-xs text-yellow-300 list-disc list-inside space-y-0.5">
                        {selectedSubmission.system_data._mismatch_flags.map((flag, i) => (
                          <li key={i}>{flag}</li>
                        ))}
                      </ul>
                    </div>
                  )}
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
                          starColor === 'Blue' ? 'text-blue-400' :
                          starColor === 'Purple' ? 'text-purple-400' : ''
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
              const biomeOptions = ['Lush','Toxic','Scorched','Radioactive','Frozen','Barren','Dead','Weird','Swamp','Lava','Marsh','Volcanic','Infested','Desolate','Exotic','Airless','Gas Giant'];
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
                        <label className="flex items-center"><input type="checkbox" checked={!!body.is_bubble} onChange={e => updateEditField(`${prefix}.is_bubble`, e.target.checked ? 1 : 0)} className={checkCls} />Bubble Planet</label>
                        <label className="flex items-center"><input type="checkbox" checked={!!body.is_floating_islands} onChange={e => updateEditField(`${prefix}.is_floating_islands`, e.target.checked ? 1 : 0)} className={checkCls} />Floating Islands</label>
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
                    {(body.ancient_bones || body.vile_brood || body.salvageable_scrap || body.storm_crystals || body.gravitino_balls || body.is_infested || body.is_dissonant || body.is_bubble || body.is_floating_islands) && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {body.ancient_bones ? <span className="text-xs px-1.5 py-0.5 rounded bg-amber-800/60 text-amber-300">Ancient Bones</span> : null}
                        {body.vile_brood ? <span className="text-xs px-1.5 py-0.5 rounded bg-red-800/60 text-red-300">Vile Brood</span> : null}
                        {body.salvageable_scrap ? <span className="text-xs px-1.5 py-0.5 rounded bg-orange-800/60 text-orange-300">Salvageable Scrap</span> : null}
                        {body.storm_crystals ? <span className="text-xs px-1.5 py-0.5 rounded bg-cyan-800/60 text-cyan-300">Storm Crystals</span> : null}
                        {body.gravitino_balls ? <span className="text-xs px-1.5 py-0.5 rounded bg-purple-800/60 text-purple-300">Gravitino Balls</span> : null}
                        {body.is_infested ? <span className="text-xs px-1.5 py-0.5 rounded bg-red-900/60 text-red-400">Infested</span> : null}
                        {body.is_dissonant ? <span className="text-xs px-1.5 py-0.5 rounded bg-violet-800/60 text-violet-300">Dissonant</span> : null}
                        {body.is_bubble ? <span className="text-xs px-1.5 py-0.5 rounded bg-pink-800/60 text-pink-300">Bubble Planet</span> : null}
                        {body.is_floating_islands ? <span className="text-xs px-1.5 py-0.5 rounded bg-teal-800/60 text-teal-300">Floating Islands</span> : null}
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
              const biomeOptions = ['Lush','Toxic','Scorched','Radioactive','Frozen','Barren','Dead','Weird','Swamp','Lava','Marsh','Volcanic','Infested','Desolate','Exotic','Airless','Gas Giant'];
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
                              <label className="flex items-center"><input type="checkbox" checked={!!moon.is_bubble} onChange={e => updateEditField(`moons.${i}.is_bubble`, e.target.checked ? 1 : 0)} className={checkCls} />Bubble Planet</label>
                              <label className="flex items-center"><input type="checkbox" checked={!!moon.is_floating_islands} onChange={e => updateEditField(`moons.${i}.is_floating_islands`, e.target.checked ? 1 : 0)} className={checkCls} />Floating Islands</label>
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
                            {(moon.ancient_bones || moon.vile_brood || moon.salvageable_scrap || moon.storm_crystals || moon.gravitino_balls || moon.is_infested || moon.is_dissonant || moon.is_bubble || moon.is_floating_islands) && (
                              <div className="mt-1 flex flex-wrap gap-1">
                                {moon.ancient_bones ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-amber-800/60 text-amber-200 border border-amber-700/50">Ancient Bones</span> : null}
                                {moon.vile_brood ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-red-800/60 text-red-200 border border-red-700/50">Vile Brood</span> : null}
                                {moon.salvageable_scrap ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-orange-800/60 text-orange-200 border border-orange-700/50">Salvageable Scrap</span> : null}
                                {moon.storm_crystals ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-cyan-800/60 text-cyan-200 border border-cyan-700/50">Storm Crystals</span> : null}
                                {moon.gravitino_balls ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-purple-800/60 text-purple-200 border border-purple-700/50">Gravitino Balls</span> : null}
                                {moon.is_infested ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-red-900/60 text-red-200 border border-red-800/50">Infested</span> : null}
                                {moon.is_dissonant ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-violet-800/60 text-violet-200 border border-violet-700/50">Dissonant</span> : null}
                                {moon.is_bubble ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-pink-800/60 text-pink-200 border border-pink-700/50">Bubble Planet</span> : null}
                                {moon.is_floating_islands ? <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-teal-800/60 text-teal-200 border border-teal-700/50">Floating Islands</span> : null}
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
                  selectedSubmission.source === 'manual' ? 'bg-gray-600 text-white' :
                  'bg-blue-600 text-white'
                }`}>{selectedSubmission.source === 'haven_extractor' ? 'Haven Extractor' : selectedSubmission.source}</span></p>
              )}
              {/* Game mode indicator */}
              {selectedSubmission.game_mode && (
                <p><strong>Game Mode:</strong> <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                  selectedSubmission.game_mode === 'Normal' ? 'bg-gray-600 text-white' :
                  selectedSubmission.game_mode === 'Survival' ? 'bg-orange-600 text-white' :
                  selectedSubmission.game_mode === 'Permadeath' ? 'bg-red-600 text-white' :
                  selectedSubmission.game_mode === 'Creative' ? 'bg-cyan-600 text-white' :
                  selectedSubmission.game_mode === 'Relaxed' ? 'bg-green-600 text-white' :
                  'bg-purple-600 text-white'
                }`}>{selectedSubmission.game_mode}</span></p>
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
    </>
  )
}
