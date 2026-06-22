import React, { useState, useMemo, useCallback } from 'react'
import axios from 'axios'
import Button from '../Button'
import Modal from '../Modal'
import { TYPE_INFO } from '../../data/discoveryTypes'
import { getPhotoUrl, getThumbnailUrl, batchApproveDiscoveries, batchRejectDiscoveries } from '../../utils/api'
import { formatCoords } from '../LatLngInput'
import { FEATURES } from '../../utils/AuthContext'

/**
 * DiscoveryApprovalTab - Discovery submission approval content
 *
 * Props:
 *   discoverySubmissions  - Array of discovery submissions
 *   isSuperAdmin          - Boolean
 *   isHavenSubAdmin       - Boolean
 *   user                  - Current user object
 *   filterTag             - Current discord tag filter value
 *   getDiscordTagBadge    - Function to render discord tag badge
 *   isSelfSubmission      - Function to check if submission is by current user
 *   loadSubmissions       - Function to reload all submissions
 */
export default function DiscoveryApprovalTab({
  discoverySubmissions,
  isSuperAdmin,
  isHavenSubAdmin,
  canAccess,
  user,
  filterTag,
  getDiscordTagBadge,
  isSelfSubmission,
  loadSubmissions,
}) {
  // Discovery modal state
  const [selectedDiscoveryApproval, setSelectedDiscoveryApproval] = useState(null)
  const [discoveryModalOpen, setDiscoveryModalOpen] = useState(false)
  const [discoveryRejectModalOpen, setDiscoveryRejectModalOpen] = useState(false)
  const [discoveryRejectionReason, setDiscoveryRejectionReason] = useState('')
  const [actionInProgress, setActionInProgress] = useState(false)
  // For EDIT submissions: the current live discovery, so we can show old → new.
  const [editOriginal, setEditOriginal] = useState(null)

  // Batch approval state (mirrors SystemApprovalTab; synchronous — no job polling)
  const [batchMode, setBatchMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [batchInProgress, setBatchInProgress] = useState(false)
  const [batchRejectModalOpen, setBatchRejectModalOpen] = useState(false)
  const [batchRejectionReason, setBatchRejectionReason] = useState('')
  const [batchResultsModalOpen, setBatchResultsModalOpen] = useState(false)
  const [batchResults, setBatchResults] = useState(null)
  const canBatch = !!(canAccess && canAccess(FEATURES.BATCH_APPROVALS))

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

  // Build a label-to-color lookup from the canonical TYPE_INFO
  const typeColorByLabel = useMemo(() => {
    const map = {}
    for (const [, info] of Object.entries(TYPE_INFO)) {
      map[info.label] = info.color
    }
    return map
  }, [])

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

  // --- Discovery approval handlers ---

  async function viewDiscoverySubmission(submission) {
    try {
      const response = await axios.get(`/api/pending_discoveries/${submission.id}`)
      setSelectedDiscoveryApproval(response.data)
      setEditOriginal(null)
      // If this is an EDIT, pull the current live discovery so we can show old → new.
      const editId = response.data.edit_discovery_id
      if (editId) {
        try {
          const orig = await axios.get(`/api/discoveries/${editId}`)
          setEditOriginal(orig.data)
        } catch {
          setEditOriginal(null)  // original may have been deleted
        }
      }
      setDiscoveryModalOpen(true)
    } catch (err) {
      alert('Failed to load discovery details: ' + (err.response?.data?.detail || err.message))
    }
  }

  // Build the old → new change list for an edit submission.
  const norm = (v) => (v == null ? '' : String(v)).trim()
  const prettyLabel = (k) => k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  const editDiff = useMemo(() => {
    const pending = selectedDiscoveryApproval
    if (!pending || !pending.edit_discovery_id || !editOriginal) return []
    const nd = pending.discovery_data || {}
    const newOf = (k) => (nd[k] !== undefined ? nd[k] : pending[k])
    const rows = []
    const simple = [
      ['discovery_name', 'Name'], ['discovery_type', 'Type'], ['description', 'Description'],
      ['significance', 'Significance'], ['location_type', 'Location Type'],
      ['planet_name', 'Planet'], ['moon_name', 'Moon'], ['location_name', 'Specific Location'],
      ['latitude', 'Latitude'], ['longitude', 'Longitude'],
    ]
    for (const [k, label] of simple) {
      const o = editOriginal[k]
      const n = newOf(k)
      if (norm(o) !== norm(n)) rows.push({ label, old: o, new: n })
    }
    const om = editOriginal.type_metadata && typeof editOriginal.type_metadata === 'object' ? editOriginal.type_metadata : {}
    let nm = nd.type_metadata
    if (typeof nm === 'string') { try { nm = JSON.parse(nm) } catch { nm = {} } }
    nm = nm && typeof nm === 'object' ? nm : {}
    for (const k of new Set([...Object.keys(om), ...Object.keys(nm)])) {
      if (norm(om[k]) !== norm(nm[k])) rows.push({ label: prettyLabel(k), old: om[k], new: nm[k] })
    }
    return rows
  }, [selectedDiscoveryApproval, editOriginal])

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

  // --- Batch handlers ---

  function toggleSelection(id) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function selectAllEligible() {
    const eligibleIds = filteredPendingDiscoveries
      .filter(s => !checkDiscoverySelfSubmission(s))
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
    if (!confirm(`Approve ${selectedIds.size} selected discovery(ies)?\n\nThis will add them to the main database.`)) {
      return
    }
    setBatchInProgress(true)
    try {
      const data = await batchApproveDiscoveries(Array.from(selectedIds))
      setBatchResults({ mode: 'approve', ...data })
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
      const data = await batchRejectDiscoveries(Array.from(selectedIds), batchRejectionReason)
      setBatchResults({ mode: 'reject', ...data })
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

  const eligibleCount = useMemo(
    () => filteredPendingDiscoveries.filter(s => !checkDiscoverySelfSubmission(s)).length,
    [filteredPendingDiscoveries, checkDiscoverySelfSubmission]
  )

  return (
    <>
      {/* Batch Mode Toggle */}
      {canBatch && filteredPendingDiscoveries.length > 0 && (
        <div className="flex justify-end mb-2">
          <Button
            className={`text-sm ${batchMode ? 'bg-amber-600 hover:bg-amber-700' : 'bg-indigo-600 hover:bg-indigo-700'}`}
            onClick={() => batchMode ? exitBatchMode() : setBatchMode(true)}
          >
            {batchMode ? 'Exit Batch' : 'Batch Mode'}
          </Button>
        </div>
      )}

      {/* Batch action bar */}
      {batchMode && (
        <div className="mb-3 p-3 rounded bg-indigo-900/40 border border-indigo-500/40 flex flex-wrap items-center gap-3">
          <span className="text-sm font-semibold">
            {selectedIds.size}/{eligibleCount} selected
          </span>
          <button onClick={selectAllEligible} className="text-sm text-indigo-300 hover:text-white underline">
            Select All
          </button>
          {selectedIds.size > 0 && (
            <button onClick={clearSelection} className="text-sm text-indigo-300 hover:text-white underline">
              Clear
            </button>
          )}
          {selectedIds.size > 0 && (
            <div className="flex gap-2 ml-auto">
              <Button
                className="bg-green-600 hover:bg-green-700 text-sm disabled:opacity-50"
                onClick={handleBatchApprove}
                disabled={batchInProgress}
              >
                {batchInProgress ? '...' : `Approve (${selectedIds.size})`}
              </Button>
              <Button
                className="bg-red-600 hover:bg-red-700 text-sm disabled:opacity-50"
                onClick={() => setBatchRejectModalOpen(true)}
                disabled={batchInProgress}
              >
                {batchInProgress ? '...' : `Reject (${selectedIds.size})`}
              </Button>
            </div>
          )}
        </div>
      )}

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
                className={`border rounded p-3 bg-cyan-700 hover:bg-cyan-600 ${
                  batchMode && selectedIds.has(submission.id) ? 'ring-2 ring-indigo-400' : ''
                }`}
              >
                <div className="flex items-start gap-3">
                  {/* Batch selection checkbox */}
                  {batchMode && (
                    <div className="flex-shrink-0 pt-1">
                      <input
                        type="checkbox"
                        className="w-5 h-5 accent-indigo-500 disabled:opacity-40"
                        checked={selectedIds.has(submission.id)}
                        disabled={checkDiscoverySelfSubmission(submission)}
                        title={checkDiscoverySelfSubmission(submission) ? 'You cannot approve your own submission' : ''}
                        onChange={() => toggleSelection(submission.id)}
                      />
                    </div>
                  )}
                  {/* Photo thumbnail */}
                  {submission.photo_url && (
                    <div className="flex-shrink-0 w-16 h-16 rounded overflow-hidden bg-gray-800">
                      <img
                        src={getThumbnailUrl(submission.photo_url)}
                        alt=""
                        className="w-full h-full object-cover"
                      />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold text-lg">{submission.discovery_name}</h4>
                    <div className="flex flex-wrap items-center gap-1.5 mt-1">
                      {getStatusBadge(submission.status)}
                      {/* New vs Edit badge */}
                      {submission.edit_discovery_id ? (
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-orange-500/30 text-orange-200 border border-orange-400/40">EDIT</span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-green-500/30 text-green-200 border border-green-400/40">NEW</span>
                      )}
                      {/* Type badge */}
                      {submission.type_info && (
                        <span className="px-2 py-0.5 rounded text-xs font-semibold" style={{ backgroundColor: (typeColorByLabel[submission.type_info.label] || '#6b7280') + '33', color: typeColorByLabel[submission.type_info.label] || '#6b7280' }}>
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
                    <span className="px-2 py-1 rounded text-xs font-semibold" style={{ backgroundColor: (typeColorByLabel[submission.type_info.label] || '#6b7280') + '33', color: typeColorByLabel[submission.type_info.label] || '#6b7280' }}>
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

      {/* Discovery Review Modal */}
      {discoveryModalOpen && selectedDiscoveryApproval && (
        <Modal
          title={`Review: ${selectedDiscoveryApproval.discovery_name}`}
          onClose={() => {
            setDiscoveryModalOpen(false)
            setSelectedDiscoveryApproval(null)
            setEditOriginal(null)
          }}
        >
          <div className="space-y-4">
            {/* Discovery Photo */}
            {selectedDiscoveryApproval.photo_url && (
              <div className="aspect-video rounded overflow-hidden bg-gray-800">
                <img
                  src={getPhotoUrl(selectedDiscoveryApproval.photo_url)}
                  alt={selectedDiscoveryApproval.discovery_name}
                  className="w-full h-full object-contain"
                />
              </div>
            )}

            {/* Edit diff (old → new) */}
            {selectedDiscoveryApproval.edit_discovery_id && (
              <div className="rounded p-3" style={{ backgroundColor: 'rgba(234,179,8,0.10)', border: '1px solid rgba(234,179,8,0.4)' }}>
                <h4 className="font-semibold mb-2 text-amber-300">
                  ✎ Edit of existing discovery #{selectedDiscoveryApproval.edit_discovery_id}
                </h4>
                {!editOriginal ? (
                  <p className="text-sm text-red-300">
                    The original discovery couldn't be loaded — it may have been deleted. Approving will fail; reject this instead.
                  </p>
                ) : editDiff.length === 0 ? (
                  <p className="text-sm text-gray-300">No field changes detected.</p>
                ) : (
                  <div className="text-sm space-y-1">
                    {editDiff.map((row, i) => (
                      <div key={i} className="grid grid-cols-[130px_1fr] gap-2">
                        <span className="text-gray-400">{row.label}</span>
                        <span>
                          <span className="line-through text-red-300/80">{norm(row.old) || '—'}</span>
                          <span className="mx-1 text-gray-500">→</span>
                          <span className="text-green-300 font-medium">{norm(row.new) || '—'}</span>
                        </span>
                      </div>
                    ))}
                  </div>
                )}
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
                {(selectedDiscoveryApproval.location_name || selectedDiscoveryApproval.discovery_data?.location_name) && (
                  <p><strong>Specific Location:</strong> {selectedDiscoveryApproval.location_name || selectedDiscoveryApproval.discovery_data?.location_name}</p>
                )}
                {(() => {
                  const coords = formatCoords(
                    selectedDiscoveryApproval.latitude ?? selectedDiscoveryApproval.discovery_data?.latitude,
                    selectedDiscoveryApproval.longitude ?? selectedDiscoveryApproval.discovery_data?.longitude,
                  )
                  return coords ? <p><strong>Surface Coords:</strong> <span className="font-mono">{coords}</span> <span className="text-gray-500">(lat, long)</span></p> : null
                })()}
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
                      setEditOriginal(null)
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
      {/* Batch Reject Modal */}
      {batchRejectModalOpen && (
        <Modal
          title={`Batch Reject ${selectedIds.size} Discovery(ies)`}
          onClose={() => {
            setBatchRejectModalOpen(false)
            setBatchRejectionReason('')
          }}
        >
          <div className="space-y-4">
            <p className="text-sm text-gray-700">
              Please provide a reason for rejecting these {selectedIds.size} discovery(ies). This reason will be applied to all selected items.
            </p>
            <div>
              <label className="block text-sm font-semibold mb-2">Rejection Reason</label>
              <textarea
                className="w-full border rounded p-2"
                rows="4"
                value={batchRejectionReason}
                onChange={(e) => setBatchRejectionReason(e.target.value)}
                placeholder="e.g., Duplicate discoveries, insufficient evidence..."
              />
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <Button
                className="bg-red-600 text-white hover:bg-red-700 text-sm w-full sm:w-auto disabled:opacity-50"
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
      {batchResultsModalOpen && batchResults && (() => {
        const succeeded = batchResults.mode === 'approve' ? (batchResults.approved || []) : (batchResults.rejected || [])
        const failed = batchResults.failed || []
        const skipped = batchResults.skipped || []
        const verb = batchResults.mode === 'approve' ? 'Approved' : 'Rejected'
        return (
          <Modal
            title="Batch Results"
            onClose={() => { setBatchResultsModalOpen(false); setBatchResults(null) }}
          >
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="p-3 rounded bg-green-900/40 border border-green-500/40">
                  <div className="text-2xl font-bold text-green-300">{succeeded.length}</div>
                  <div className="text-xs text-gray-300">{verb}</div>
                </div>
                <div className="p-3 rounded bg-red-900/40 border border-red-500/40">
                  <div className="text-2xl font-bold text-red-300">{failed.length}</div>
                  <div className="text-xs text-gray-300">Failed</div>
                </div>
                <div className="p-3 rounded bg-gray-700/60 border border-gray-500/40">
                  <div className="text-2xl font-bold text-gray-300">{skipped.length}</div>
                  <div className="text-xs text-gray-300">Skipped</div>
                </div>
              </div>

              {failed.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-red-300 mb-1">Failed</h4>
                  <ul className="text-xs space-y-1 max-h-40 overflow-y-auto">
                    {failed.map((item, i) => (
                      <li key={i} className="text-gray-300">
                        #{item.id}{item.name ? ` (${item.name})` : ''}: <span className="text-red-300">{item.error}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {skipped.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-300 mb-1">Skipped</h4>
                  <ul className="text-xs space-y-1 max-h-40 overflow-y-auto">
                    {skipped.map((item, i) => (
                      <li key={i} className="text-gray-300">
                        #{item.id}{item.name ? ` (${item.name})` : ''}: <span className="text-gray-400">{item.reason}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex justify-end">
                <Button
                  className="bg-indigo-600 hover:bg-indigo-700 text-sm"
                  onClick={() => { setBatchResultsModalOpen(false); setBatchResults(null) }}
                >
                  Done
                </Button>
              </div>
            </div>
          </Modal>
        )
      })()}
    </>
  )
}
