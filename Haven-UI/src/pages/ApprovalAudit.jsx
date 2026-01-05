import React, { useEffect, useState, useContext } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import { AuthContext } from '../utils/AuthContext'

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
  const [filterDiscordTag, setFilterDiscordTag] = useState('')
  const [discordTags, setDiscordTags] = useState([])

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
  }, [page, filterApprover, filterDiscordTag])

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
      if (filterDiscordTag) params.append('discord_tag', filterDiscordTag)

      const response = await axios.get(`/api/approval_audit?${params.toString()}`)
      setEntries(response.data.entries || [])
      setTotal(response.data.total || 0)
    } catch (err) {
      alert('Failed to load audit log: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  function getActionBadge(action) {
    const colors = {
      approved: 'bg-green-500 text-white',
      rejected: 'bg-red-500 text-white'
    }
    return (
      <span className={`px-2 py-1 rounded text-xs font-semibold ${colors[action] || 'bg-gray-500 text-white'}`}>
        {action.toUpperCase()}
      </span>
    )
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

  const totalPages = Math.ceil(total / limit)

  if (!auth.isSuperAdmin) {
    return null
  }

  return (
    <div className="p-4">
      <Card className="max-w-6xl">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-2xl font-bold">Approval Audit Log</h2>
            <p className="text-sm text-gray-400 mt-1">
              Track all approval and rejection actions across the system.
            </p>
          </div>
          <Button className="bg-gray-200 text-gray-800" onClick={() => navigate(-1)}>
            Back
          </Button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-4 p-3 bg-gray-700 rounded">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Approver</label>
            <input
              type="text"
              className="border rounded p-2 bg-gray-600 text-white text-sm"
              placeholder="Filter by username..."
              value={filterApprover}
              onChange={(e) => {
                setFilterApprover(e.target.value)
                setPage(0)
              }}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Community</label>
            <select
              className="border rounded p-2 bg-gray-600 text-white text-sm"
              value={filterDiscordTag}
              onChange={(e) => {
                setFilterDiscordTag(e.target.value)
                setPage(0)
              }}
            >
              <option value="">All Communities</option>
              {discordTags.map(t => (
                <option key={t.tag} value={t.tag}>{t.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <Button
              className="bg-gray-500 text-white text-sm"
              onClick={() => {
                setFilterApprover('')
                setFilterDiscordTag('')
                setPage(0)
              }}
            >
              Clear Filters
            </Button>
          </div>
        </div>

        {loading ? (
          <p className="text-gray-400">Loading audit log...</p>
        ) : entries.length === 0 ? (
          <div className="text-gray-400 italic p-4 bg-gray-700 rounded">
            No audit entries found. Approvals and rejections will appear here.
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-700">
                  <tr>
                    <th className="p-2 text-left">Timestamp</th>
                    <th className="p-2 text-left">Action</th>
                    <th className="p-2 text-left">Submission</th>
                    <th className="p-2 text-left">Approver</th>
                    <th className="p-2 text-left">Submitter</th>
                    <th className="p-2 text-left">Community</th>
                    <th className="p-2 text-left">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map(entry => (
                    <tr key={entry.id} className="border-b border-gray-600 hover:bg-gray-700">
                      <td className="p-2 text-gray-300 whitespace-nowrap">
                        {new Date(entry.timestamp).toLocaleString()}
                      </td>
                      <td className="p-2">
                        {getActionBadge(entry.action)}
                      </td>
                      <td className="p-2">
                        <div className="font-semibold">{entry.submission_name || 'Unknown'}</div>
                        <div className="text-xs text-gray-400">
                          {entry.submission_type} #{entry.submission_id}
                        </div>
                      </td>
                      <td className="p-2">
                        <div className="font-semibold">{entry.approver_username}</div>
                        <div className="mt-1">{getApproverTypeBadge(entry.approver_type)}</div>
                      </td>
                      <td className="p-2 text-gray-300">
                        {entry.submitter_username || 'Unknown'}
                        {entry.submitter_type && (
                          <div className="text-xs text-gray-400">{entry.submitter_type}</div>
                        )}
                      </td>
                      <td className="p-2">
                        {entry.submission_discord_tag ? (
                          <span className="px-2 py-1 rounded text-xs bg-cyan-600 text-white">
                            {entry.submission_discord_tag}
                          </span>
                        ) : (
                          <span className="text-gray-500 text-xs">Untagged</span>
                        )}
                      </td>
                      <td className="p-2 text-gray-300 text-xs max-w-xs truncate">
                        {entry.notes || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex justify-between items-center mt-4 pt-4 border-t border-gray-600">
              <p className="text-sm text-gray-400">
                Showing {page * limit + 1}-{Math.min((page + 1) * limit, total)} of {total} entries
              </p>
              <div className="flex gap-2">
                <Button
                  className="bg-gray-600 text-white text-sm px-3 py-1"
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  Previous
                </Button>
                <span className="text-sm text-gray-400 flex items-center px-2">
                  Page {page + 1} of {totalPages || 1}
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
