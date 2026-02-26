import React, { useEffect, useState, useContext } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import Modal from '../components/Modal'
import StatCard from '../components/StatCard'
import { AuthContext } from '../utils/AuthContext'

export default function ExtractorUsers() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionInProgress, setActionInProgress] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  // Edit modal
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState(null)
  const [editRateLimit, setEditRateLimit] = useState(100)

  useEffect(() => {
    if (!auth.isAdmin) {
      navigate('/')
      return
    }
    loadUsers()
  }, [auth.isAdmin])

  async function loadUsers() {
    try {
      setLoading(true)
      const res = await axios.get('/api/extractor/users')
      setUsers(res.data.users || [])
    } catch (err) {
      console.error('Failed to load extractor users:', err)
    } finally {
      setLoading(false)
    }
  }

  // Stats
  const totalUsers = users.length
  const activeUsers = users.filter(u => u.is_active).length
  const totalSubmissions = users.reduce((sum, u) => sum + (u.total_submissions || 0), 0)
  const recentlyActive = users.filter(u => {
    if (!u.last_submission_at) return false
    const diff = Date.now() - new Date(u.last_submission_at).getTime()
    return diff < 7 * 24 * 60 * 60 * 1000
  }).length

  // Filtered users
  const filteredUsers = users.filter(u => {
    if (search) {
      const q = search.toLowerCase()
      if (!(u.discord_username || '').toLowerCase().includes(q) &&
          !(u.key_prefix || '').toLowerCase().includes(q)) {
        return false
      }
    }
    if (statusFilter === 'active' && !u.is_active) return false
    if (statusFilter === 'suspended' && u.is_active) return false
    return true
  })

  function openEditModal(user) {
    setSelectedUser(user)
    setEditRateLimit(user.rate_limit || 100)
    setEditModalOpen(true)
  }

  async function saveEdit() {
    if (!selectedUser) return
    setActionInProgress(true)
    try {
      await axios.put(`/api/extractor/users/${selectedUser.id}`, {
        rate_limit: editRateLimit
      })
      setEditModalOpen(false)
      loadUsers()
    } catch (err) {
      alert('Failed to update: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function toggleActive(user) {
    setActionInProgress(true)
    try {
      await axios.put(`/api/extractor/users/${user.id}`, {
        is_active: !user.is_active
      })
      loadUsers()
    } catch (err) {
      alert('Failed to update: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  function formatDate(dateStr) {
    if (!dateStr) return 'Never'
    try {
      const d = new Date(dateStr)
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    } catch {
      return dateStr
    }
  }

  function timeAgo(dateStr) {
    if (!dateStr) return 'Never'
    try {
      const diff = Date.now() - new Date(dateStr).getTime()
      const mins = Math.floor(diff / 60000)
      if (mins < 60) return `${mins}m ago`
      const hours = Math.floor(mins / 60)
      if (hours < 24) return `${hours}h ago`
      const days = Math.floor(hours / 24)
      if (days < 30) return `${days}d ago`
      return formatDate(dateStr)
    } catch {
      return dateStr
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-gray-400">Loading extractor users...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-cyan-400">Extractor Users</h1>
        <p className="text-gray-400 mt-1">
          {auth.isSuperAdmin
            ? 'Manage Haven Extractor users and their API access'
            : `Haven Extractor users submitting to ${auth.user?.displayName || auth.user?.discordTag || 'your community'}`
          }
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Registered Users" value={totalUsers} subtitle={`${activeUsers} active`} />
        <StatCard title="Active (7 days)" value={recentlyActive} subtitle="with recent submissions" />
        <StatCard title="Total Submissions" value={totalSubmissions.toLocaleString()} subtitle="across all users" />
        <StatCard title="Avg Rate Limit" value={users.length ? Math.round(users.reduce((s, u) => s + (u.rate_limit || 0), 0) / users.length) : 0} subtitle="requests/hour" />
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap gap-3 items-center">
        <input
          type="text"
          placeholder="Search by username or key prefix..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="px-3 py-2 rounded-lg text-sm text-white placeholder-gray-500 flex-1 min-w-[200px]"
          style={{ background: 'var(--app-card)', border: '1px solid rgba(255,255,255,0.1)' }}
        />
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="px-3 py-2 rounded-lg text-sm text-white"
          style={{ background: 'var(--app-card)', border: '1px solid rgba(255,255,255,0.1)' }}
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
        <span className="text-sm text-gray-400">{filteredUsers.length} user{filteredUsers.length !== 1 ? 's' : ''}</span>
      </div>

      {/* User Cards */}
      {filteredUsers.length === 0 ? (
        <Card className="bg-gray-800/50">
          <div className="p-8 text-center text-gray-400">
            <p className="text-lg mb-2">No extractor users found</p>
            <p className="text-sm">
              {search || statusFilter !== 'all'
                ? 'Try adjusting your filters'
                : 'Users will appear here after they register their Haven Extractor'}
            </p>
          </div>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredUsers.map(user => (
            <Card key={user.id} className={`bg-gray-800/50 border ${user.is_active ? 'border-gray-700' : 'border-red-900/50'}`}>
              <div className="p-4">
                <div className="flex items-start justify-between gap-4">
                  {/* Left: User info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2 flex-wrap">
                      <h3 className="text-lg font-semibold text-white">{user.discord_username || 'Unknown'}</h3>
                      {user.is_active ? (
                        <span className="px-2 py-0.5 text-xs rounded-full bg-green-900/50 text-green-400 border border-green-700">
                          Active
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 text-xs rounded-full bg-red-900/50 text-red-400 border border-red-700">
                          Suspended
                        </span>
                      )}
                    </div>

                    {/* Stats grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-1 text-sm mb-3">
                      <div>
                        <span className="text-gray-500">Submissions: </span>
                        <span className="text-white font-medium">{(user.total_submissions || 0).toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Rate Limit: </span>
                        <span className="text-white">{user.rate_limit}/hr</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Registered: </span>
                        <span className="text-gray-300">{formatDate(user.created_at)}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Last Active: </span>
                        <span className="text-gray-300">{timeAgo(user.last_submission_at)}</span>
                      </div>
                    </div>

                    {/* Key prefix */}
                    <div className="text-xs text-gray-500 mb-2">
                      Key: <code className="text-gray-400">{user.key_prefix}...</code>
                    </div>

                    {/* Communities used */}
                    {user.communities_used && user.communities_used.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {user.communities_used.map(c => (
                          <span
                            key={c.tag}
                            className="px-2 py-0.5 text-xs rounded-full border"
                            style={{
                              background: c.tag === 'personal' ? 'rgba(217, 70, 239, 0.15)' : 'rgba(6, 182, 212, 0.15)',
                              borderColor: c.tag === 'personal' ? 'rgba(217, 70, 239, 0.3)' : 'rgba(6, 182, 212, 0.3)',
                              color: c.tag === 'personal' ? '#d946ef' : '#06b6d4'
                            }}
                          >
                            {c.tag || 'personal'} ({c.count})
                            {c.approved > 0 && <span className="text-green-400 ml-1">{c.approved} approved</span>}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Right: Actions (super admin only) */}
                  {auth.isSuperAdmin && (
                    <div className="flex flex-col gap-2 shrink-0">
                      <Button
                        onClick={() => openEditModal(user)}
                        disabled={actionInProgress}
                        className="text-xs px-3 py-1.5 bg-cyan-700 hover:bg-cyan-600"
                      >
                        Edit
                      </Button>
                      <Button
                        onClick={() => toggleActive(user)}
                        disabled={actionInProgress}
                        className={`text-xs px-3 py-1.5 ${
                          user.is_active
                            ? 'bg-red-700 hover:bg-red-600'
                            : 'bg-green-700 hover:bg-green-600'
                        }`}
                      >
                        {user.is_active ? 'Suspend' : 'Reactivate'}
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Edit Modal */}
      {editModalOpen && selectedUser && (
        <Modal title={`Edit - ${selectedUser.discord_username}`} onClose={() => setEditModalOpen(false)}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Rate Limit (requests/hour)</label>
              <input
                type="number"
                value={editRateLimit}
                onChange={e => setEditRateLimit(parseInt(e.target.value) || 0)}
                min={1}
                max={10000}
                className="w-full px-3 py-2 rounded-lg text-white text-sm"
                style={{ background: 'var(--app-card)', border: '1px solid rgba(255,255,255,0.15)' }}
              />
              <p className="text-xs text-gray-500 mt-1">Default for extractor users is 100/hr. The shared key uses 1000/hr.</p>
            </div>

            <div className="bg-gray-800/50 rounded-lg p-3 text-sm space-y-1">
              <div><span className="text-gray-500">Username:</span> <span className="text-white">{selectedUser.discord_username}</span></div>
              <div><span className="text-gray-500">Key Prefix:</span> <code className="text-gray-400">{selectedUser.key_prefix}...</code></div>
              <div><span className="text-gray-500">Registered:</span> <span className="text-gray-300">{formatDate(selectedUser.created_at)}</span></div>
              <div><span className="text-gray-500">Total Submissions:</span> <span className="text-white">{(selectedUser.total_submissions || 0).toLocaleString()}</span></div>
            </div>

            <div className="flex justify-end gap-3">
              <Button onClick={() => setEditModalOpen(false)} className="bg-gray-600 hover:bg-gray-500">
                Cancel
              </Button>
              <Button onClick={saveEdit} disabled={actionInProgress} className="bg-cyan-600 hover:bg-cyan-500">
                {actionInProgress ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
