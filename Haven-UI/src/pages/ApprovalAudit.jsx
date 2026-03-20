import React, { useEffect, useState, useContext } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import { AuthContext } from '../utils/AuthContext'
import DateRangePicker from '../components/DateRangePicker'
import { format } from 'date-fns'

/**
 * Approval Audit Log — Route: /admin/audit
 * Auth: Super admin only; redirects to /systems otherwise.
 *
 * Paginated, filterable log of all approval/rejection actions.
 * Supports CSV and JSON export of filtered results.
 *
 * API endpoints:
 *   GET /api/approval_audit         — paginated audit entries with filters
 *   GET /api/approval_audit/export  — download filtered results as CSV or JSON
 *   GET /api/discord_tags           — community list for filter dropdown
 */
export default function ApprovalAudit() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const limit = 50

  // Filters
  const [filterApprover, setFilterApprover] = useState('')
  const [filterSubmitter, setFilterSubmitter] = useState('')
  const [filterDiscordTag, setFilterDiscordTag] = useState('')
  const [filterAction, setFilterAction] = useState('')
  const [filterSubmissionType, setFilterSubmissionType] = useState('')
  const [searchNotes, setSearchNotes] = useState('')
  const [filterSource, setFilterSource] = useState('')
  const [dateRange, setDateRange] = useState({ startDate: null, endDate: null })
  const [discordTags, setDiscordTags] = useState([])
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    if (!auth.isSuperAdmin) {
      alert('Super admin access required')
      navigate('/systems')
      return
    }
    loadDiscordTags()
    loadAuditLog()
  }, [auth.isSuperAdmin, navigate])

  useEffect(() => {
    loadAuditLog()
  }, [page, filterApprover, filterSubmitter, filterDiscordTag, filterAction, filterSubmissionType, searchNotes, filterSource, dateRange])

  async function loadDiscordTags() {
    try {
      const response = await axios.get('/api/discord_tags')
      setDiscordTags(response.data.tags || [])
    } catch (err) {
      console.error('Failed to load discord tags:', err)
    }
  }

  async function loadAuditLog() {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      params.append('limit', limit)
      params.append('offset', page * limit)
      if (filterApprover) params.append('approver', filterApprover)
      if (filterSubmitter) params.append('submitter', filterSubmitter)
      if (filterDiscordTag) params.append('discord_tag', filterDiscordTag)
      if (filterAction) params.append('action', filterAction)
      if (filterSubmissionType) params.append('submission_type', filterSubmissionType)
      if (searchNotes) params.append('search', searchNotes)
      if (filterSource) params.append('source', filterSource)
      if (dateRange.startDate) params.append('start_date', format(dateRange.startDate, 'yyyy-MM-dd'))
      if (dateRange.endDate) params.append('end_date', format(dateRange.endDate, 'yyyy-MM-dd'))

      const response = await axios.get(`/api/approval_audit?${params.toString()}`)
      setEntries(response.data.entries || [])
      setTotal(response.data.total || 0)
    } catch (err) {
      alert('Failed to load audit log: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  async function handleExport(exportFormat) {
    setExporting(true)
    try {
      const params = new URLSearchParams()
      params.append('format', exportFormat)
      if (filterApprover) params.append('approver', filterApprover)
      if (filterSubmitter) params.append('submitter', filterSubmitter)
      if (filterDiscordTag) params.append('discord_tag', filterDiscordTag)
      if (filterAction) params.append('action', filterAction)
      if (dateRange.startDate) params.append('start_date', format(dateRange.startDate, 'yyyy-MM-dd'))
      if (dateRange.endDate) params.append('end_date', format(dateRange.endDate, 'yyyy-MM-dd'))

      const response = await axios.get(`/api/approval_audit/export?${params.toString()}`, {
        responseType: exportFormat === 'csv' ? 'blob' : 'json'
      })

      if (exportFormat === 'csv') {
        const blob = new Blob([response.data], { type: 'text/csv' })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `approval_audit_${format(new Date(), 'yyyy-MM-dd')}.csv`
        a.click()
        window.URL.revokeObjectURL(url)
      } else {
        const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `approval_audit_${format(new Date(), 'yyyy-MM-dd')}.json`
        a.click()
        window.URL.revokeObjectURL(url)
      }
    } catch (err) {
      alert('Failed to export: ' + (err.response?.data?.detail || err.message))
    } finally {
      setExporting(false)
    }
  }

  function clearFilters() {
    setFilterApprover('')
    setFilterSubmitter('')
    setFilterDiscordTag('')
    setFilterAction('')
    setFilterSubmissionType('')
    setSearchNotes('')
    setFilterSource('')
    setDateRange({ startDate: null, endDate: null })
    setPage(0)
  }

  function getActionBadge(action) {
    const colors = {
      approved: 'bg-green-500 text-white',
      rejected: 'bg-red-500 text-white',
      direct_edit: 'bg-blue-500 text-white',
      direct_add: 'bg-purple-500 text-white',
      edit_pending: 'bg-yellow-500 text-black',
      tier_change: 'bg-orange-500 text-white',
      permission_change: 'bg-teal-500 text-white',
      activated: 'bg-green-600 text-white',
      deactivated: 'bg-red-600 text-white',
      password_reset: 'bg-amber-500 text-black'
    }
    const labels = {
      approved: 'APPROVED',
      rejected: 'REJECTED',
      direct_edit: 'EDITED',
      direct_add: 'ADDED',
      edit_pending: 'EDIT PENDING',
      tier_change: 'TIER CHANGE',
      permission_change: 'PERMS CHANGED',
      activated: 'ACTIVATED',
      deactivated: 'DEACTIVATED',
      password_reset: 'PW RESET'
    }
    return (
      <span className={`px-2 py-1 rounded text-xs font-semibold ${colors[action] || 'bg-gray-500 text-white'}`}>
        {labels[action] || action.toUpperCase()}
      </span>
    )
  }

  function getSourceBadge(source) {
    if (!source) return null
    if (source === 'haven_extractor') return <span className="px-1.5 py-0.5 rounded text-xs bg-purple-600 text-white ml-1">Extractor</span>
    if (source === 'companion_app') return <span className="px-1.5 py-0.5 rounded text-xs bg-cyan-600 text-white ml-1">Companion</span>
    return null
  }

  function getApproverTypeBadge(type) {
    const colors = {
      super_admin: 'bg-purple-500 text-white',
      partner: 'bg-cyan-500 text-white',
      sub_admin: 'bg-amber-500 text-black'
    }
    const labels = {
      super_admin: 'Super Admin',
      partner: 'Partner',
      sub_admin: 'Sub-Admin'
    }
    return (
      <span className={`px-2 py-1 rounded text-xs ${colors[type] || 'bg-gray-500 text-white'}`}>
        {labels[type] || type}
      </span>
    )
  }

  const activeFilterCount = [
    filterApprover,
    filterSubmitter,
    filterDiscordTag,
    filterAction,
    filterSubmissionType,
    searchNotes,
    filterSource,
    dateRange.startDate
  ].filter(Boolean).length

  const totalPages = Math.ceil(total / limit)

  if (!auth.isSuperAdmin) {
    return null
  }

  return (
    <div className="p-4 md:p-6 w-full">
      <Card className="w-full">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6">
          <div>
            <h2 className="text-xl sm:text-2xl font-bold">Approval Audit Log</h2>
            <p className="text-sm text-gray-400 mt-1 hidden sm:block">
              Track all approval and rejection actions across the system.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <button
                className="flex items-center gap-2 px-3 py-2 rounded text-sm font-medium bg-gray-700 text-white hover:bg-gray-600 transition-colors"
                onClick={() => document.getElementById('export-menu').classList.toggle('hidden')}
                disabled={exporting}
              >
                {exporting ? (
                  <span className="animate-spin">⏳</span>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                )}
                Export
              </button>
              <div id="export-menu" className="hidden absolute right-0 mt-1 w-32 bg-gray-700 rounded shadow-lg z-10">
                <button
                  className="w-full px-4 py-2 text-left text-sm text-white hover:bg-gray-600"
                  onClick={() => {
                    document.getElementById('export-menu').classList.add('hidden')
                    handleExport('csv')
                  }}
                >
                  Export CSV
                </button>
                <button
                  className="w-full px-4 py-2 text-left text-sm text-white hover:bg-gray-600"
                  onClick={() => {
                    document.getElementById('export-menu').classList.add('hidden')
                    handleExport('json')
                  }}
                >
                  Export JSON
                </button>
              </div>
            </div>
            <Button className="bg-gray-200 text-gray-800 text-sm" onClick={() => navigate(-1)}>
              Back
            </Button>
          </div>
        </div>

        {/* Enhanced Filters */}
        <div className="mb-6 p-4 bg-gray-700 rounded-lg">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-300">Filters</h3>
            {activeFilterCount > 0 && (
              <button
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                onClick={clearFilters}
              >
                Clear {activeFilterCount} filter{activeFilterCount > 1 ? 's' : ''}
                <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-4">
            {/* Date Range */}
            <div className="sm:col-span-2 md:col-span-1">
              <label className="block text-xs text-gray-400 mb-1">Date Range</label>
              <DateRangePicker
                startDate={dateRange.startDate}
                endDate={dateRange.endDate}
                onChange={({ startDate, endDate }) => {
                  setDateRange({ startDate, endDate })
                  setPage(0)
                }}
              />
            </div>

            {/* Action */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Action</label>
              <select
                className="w-full border rounded p-2 bg-gray-600 text-white text-sm"
                value={filterAction}
                onChange={(e) => {
                  setFilterAction(e.target.value)
                  setPage(0)
                }}
              >
                <option value="">All</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="direct_edit">Direct Edit</option>
                <option value="direct_add">Direct Add</option>
                <option value="edit_pending">Edit Pending</option>
                <option value="tier_change">Tier Change</option>
                <option value="permission_change">Permission Change</option>
                <option value="activated">Activated</option>
                <option value="deactivated">Deactivated</option>
                <option value="password_reset">Password Reset</option>
              </select>
            </div>

            {/* Submission Type */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Type</label>
              <select
                className="w-full border rounded p-2 bg-gray-600 text-white text-sm"
                value={filterSubmissionType}
                onChange={(e) => {
                  setFilterSubmissionType(e.target.value)
                  setPage(0)
                }}
              >
                <option value="">All</option>
                <option value="system">System</option>
                <option value="discovery">Discovery</option>
                <option value="region">Region</option>
                <option value="profile">Profile</option>
              </select>
            </div>

            {/* Source */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Source</label>
              <select
                className="w-full border rounded p-2 bg-gray-600 text-white text-sm"
                value={filterSource}
                onChange={(e) => {
                  setFilterSource(e.target.value)
                  setPage(0)
                }}
              >
                <option value="">All</option>
                <option value="manual">Manual</option>
                <option value="haven_extractor">Extractor</option>
                <option value="companion_app">Companion App</option>
              </select>
            </div>

            {/* Community */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Community</label>
              <select
                className="w-full border rounded p-2 bg-gray-600 text-white text-sm"
                value={filterDiscordTag}
                onChange={(e) => {
                  setFilterDiscordTag(e.target.value)
                  setPage(0)
                }}
              >
                <option value="">All</option>
                {discordTags.map(t => (
                  <option key={t.tag} value={t.tag}>{t.name}</option>
                ))}
              </select>
            </div>

            {/* Approver */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Approver</label>
              <input
                type="text"
                className="w-full border rounded p-2 bg-gray-600 text-white text-sm"
                placeholder="Username..."
                value={filterApprover}
                onChange={(e) => {
                  setFilterApprover(e.target.value)
                  setPage(0)
                }}
              />
            </div>

            {/* Submitter */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Submitter</label>
              <input
                type="text"
                className="w-full border rounded p-2 bg-gray-600 text-white text-sm"
                placeholder="Username..."
                value={filterSubmitter}
                onChange={(e) => {
                  setFilterSubmitter(e.target.value)
                  setPage(0)
                }}
              />
            </div>

            {/* Search Notes */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Search</label>
              <input
                type="text"
                className="w-full border rounded p-2 bg-gray-600 text-white text-sm"
                placeholder="Notes..."
                value={searchNotes}
                onChange={(e) => {
                  setSearchNotes(e.target.value)
                  setPage(0)
                }}
              />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500"></div>
          </div>
        ) : entries.length === 0 ? (
          <div className="text-gray-400 italic p-4 bg-gray-700 rounded text-center">
            No audit entries found matching your filters.
          </div>
        ) : (
          <>
            {/* Mobile Card Layout */}
            <div className="md:hidden space-y-3">
              {entries.map(entry => (
                <div key={entry.id} className="bg-gray-700 rounded-lg p-3">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="font-semibold">{entry.submission_name || 'Unknown'}</div>
                    {getActionBadge(entry.action)}
                  </div>
                  <div className="text-xs text-gray-400 mb-2 flex items-center gap-1">
                    {entry.submission_type} {entry.submission_id === 0 ? '(Direct)' : `#${entry.submission_id}`}
                    {getSourceBadge(entry.source)}
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <div className="text-xs text-gray-400">Approver</div>
                      <div className="text-gray-200">{entry.approver_username}</div>
                      <div className="mt-1">{getApproverTypeBadge(entry.approver_type)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-400">Submitter</div>
                      <div className="text-gray-200">{entry.submitter_username || 'Unknown'}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-400">Community</div>
                      {entry.submission_discord_tag ? (
                        <span className="px-2 py-0.5 rounded text-xs bg-cyan-600 text-white">
                          {entry.submission_discord_tag}
                        </span>
                      ) : (
                        <span className="text-gray-500 text-xs">Untagged</span>
                      )}
                    </div>
                    <div>
                      <div className="text-xs text-gray-400">Date</div>
                      <div className="text-gray-300 text-xs">{new Date(entry.timestamp).toLocaleDateString()}</div>
                    </div>
                  </div>
                  {entry.notes && (
                    <div className="mt-2 pt-2 border-t border-gray-600">
                      <div className="text-xs text-gray-400">Notes</div>
                      <div className="text-xs text-gray-300 line-clamp-2">{entry.notes}</div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Desktop Table Layout */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm table-fixed">
                <thead className="bg-gray-700">
                  <tr>
                    <th className="px-4 py-3 text-left w-[160px]">Timestamp</th>
                    <th className="px-4 py-3 text-left w-[100px]">Action</th>
                    <th className="px-4 py-3 text-left w-[200px]">Submission</th>
                    <th className="px-4 py-3 text-left w-[160px]">Approver</th>
                    <th className="px-4 py-3 text-left w-[140px]">Submitter</th>
                    <th className="px-4 py-3 text-left w-[120px]">Community</th>
                    <th className="px-4 py-3 text-left">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map(entry => (
                    <tr key={entry.id} className="border-b border-gray-600 hover:bg-gray-700/50">
                      <td className="px-4 py-3 text-gray-300 whitespace-nowrap">
                        {new Date(entry.timestamp).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        {getActionBadge(entry.action)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold truncate" title={entry.submission_name || 'Unknown'}>
                          {entry.submission_name || 'Unknown'}
                        </div>
                        <div className="text-xs text-gray-400 mt-1 flex items-center gap-1">
                          {entry.submission_type} {entry.submission_id === 0 ? '(Direct)' : `#${entry.submission_id}`}
                          {getSourceBadge(entry.source)}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold truncate" title={entry.approver_username}>
                          {entry.approver_username}
                        </div>
                        <div className="mt-1">{getApproverTypeBadge(entry.approver_type)}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-300">
                        <div className="truncate" title={entry.submitter_username || 'Unknown'}>
                          {entry.submitter_username || 'Unknown'}
                        </div>
                        {entry.submitter_type && (
                          <div className="text-xs text-gray-400 mt-1">{entry.submitter_type}</div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {entry.submission_discord_tag ? (
                          <span className="px-2 py-1 rounded text-xs bg-cyan-600 text-white">
                            {entry.submission_discord_tag}
                          </span>
                        ) : (
                          <span className="text-gray-500 text-xs">Untagged</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-300 text-sm">
                        {entry.notes ? (
                          <span className="block truncate" title={entry.notes}>
                            {entry.notes}
                          </span>
                        ) : (
                          <span className="text-gray-500">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mt-6 pt-4 border-t border-gray-600">
              <p className="text-xs sm:text-sm text-gray-400 text-center sm:text-left">
                {page * limit + 1}-{Math.min((page + 1) * limit, total)} of {total}
              </p>
              <div className="flex justify-center gap-2">
                <Button
                  className="bg-gray-600 text-white text-sm px-3 py-1"
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  Prev
                </Button>
                <span className="text-sm text-gray-400 flex items-center px-2">
                  {page + 1}/{totalPages || 1}
                </span>
                <Button
                  className="bg-gray-600 text-white text-sm px-3 py-1"
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= totalPages - 1}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
