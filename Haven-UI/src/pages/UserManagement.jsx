import React, { useState, useEffect, useContext } from 'react'
import axios from 'axios'
import Card from '../components/Card'
import { AuthContext } from '../utils/AuthContext'

const TIER_LABELS = { 1: 'Super Admin', 2: 'Partner', 3: 'Sub-Admin', 4: 'Member', 5: 'Read-Only' }
const TIER_COLORS = { 1: 'bg-yellow-500', 2: 'bg-blue-500', 3: 'bg-teal-500', 4: 'bg-green-500', 5: 'bg-gray-500' }

export default function UserManagement() {
  const auth = useContext(AuthContext)
  const { isSuperAdmin } = auth
  const [profiles, setProfiles] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [tierFilter, setTierFilter] = useState('')
  const [loading, setLoading] = useState(true)
  // Elevation modal
  const [elevateProfile, setElevateProfile] = useState(null)
  const [elevateForm, setElevateForm] = useState({ tier: 2, partner_discord_tag: '', enabled_features: [] })
  const [elevating, setElevating] = useState(false)

  useEffect(() => { fetchProfiles() }, [page, search, tierFilter])

  async function fetchProfiles() {
    setLoading(true)
    try {
      const params = { page, per_page: 25 }
      if (search) params.search = search
      if (tierFilter) params.tier = tierFilter
      const r = await axios.get('/api/admin/profiles', { params })
      setProfiles(r.data.profiles || [])
      setTotal(r.data.total || 0)
    } catch {
      // Silent
    } finally {
      setLoading(false)
    }
  }

  async function handleElevate() {
    if (!elevateProfile) return
    setElevating(true)
    try {
      await axios.put(`/api/admin/profiles/${elevateProfile.id}/tier`, elevateForm)
      setElevateProfile(null)
      fetchProfiles()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to elevate')
    } finally {
      setElevating(false)
    }
  }

  async function toggleActive(profile) {
    try {
      await axios.put(`/api/admin/profiles/${profile.id}`, { is_active: !profile.is_active })
      fetchProfiles()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update')
    }
  }

  const totalPages = Math.ceil(total / 25)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">User Management</h1>
        <span className="text-gray-400 text-sm">{total} profiles</span>
      </div>

      {/* Filters */}
      <Card>
        <div className="flex gap-3 flex-wrap">
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            placeholder="Search username..."
            className="flex-1 min-w-48 p-2 bg-gray-700 rounded text-white placeholder-gray-400"
          />
          <select
            value={tierFilter}
            onChange={e => { setTierFilter(e.target.value); setPage(1) }}
            className="p-2 bg-gray-700 rounded text-white"
          >
            <option value="">All Tiers</option>
            <option value="1">Super Admin</option>
            <option value="2">Partner</option>
            <option value="3">Sub-Admin</option>
            <option value="4">Member</option>
            <option value="5">Read-Only</option>
          </select>
        </div>
      </Card>

      {/* Profiles table */}
      <Card>
        {loading ? (
          <div className="text-gray-400 text-center py-8">Loading...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="pb-2 pr-4">Username</th>
                  <th className="pb-2 pr-4">Tier</th>
                  <th className="pb-2 pr-4">Community</th>
                  <th className="pb-2 pr-4">Systems</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4">Last Login</th>
                  {isSuperAdmin && <th className="pb-2">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {profiles.map(p => (
                  <tr key={p.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="py-2 pr-4">
                      <div className="font-medium">{p.username}</div>
                      {p.display_name !== p.username && (
                        <div className="text-xs text-gray-500">{p.display_name}</div>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      <span className={`px-2 py-0.5 rounded text-xs text-white ${TIER_COLORS[p.tier] || 'bg-gray-600'}`}>
                        {TIER_LABELS[p.tier] || `Tier ${p.tier}`}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-gray-400">
                      {p.partner_discord_tag || p.default_civ_tag || '-'}
                    </td>
                    <td className="py-2 pr-4">{p.system_count}</td>
                    <td className="py-2 pr-4">
                      {p.is_active ? (
                        <span className="text-green-400 text-xs">Active</span>
                      ) : (
                        <span className="text-red-400 text-xs">Inactive</span>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-gray-500 text-xs">
                      {p.last_login_at ? new Date(p.last_login_at).toLocaleDateString() : 'Never'}
                    </td>
                    {isSuperAdmin && (
                      <td className="py-2">
                        <div className="flex gap-1">
                          {p.tier > 2 && p.has_password && (
                            <button
                              onClick={() => { setElevateProfile(p); setElevateForm({ tier: 2, partner_discord_tag: '', enabled_features: [] }) }}
                              className="px-2 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded"
                            >
                              Elevate
                            </button>
                          )}
                          <button
                            onClick={() => toggleActive(p)}
                            className={`px-2 py-1 text-xs rounded ${p.is_active ? 'bg-red-600 hover:bg-red-500' : 'bg-green-600 hover:bg-green-500'} text-white`}
                          >
                            {p.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex justify-center gap-2 mt-4">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn text-sm">Prev</button>
            <span className="text-gray-400 text-sm py-1">Page {page} of {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn text-sm">Next</button>
          </div>
        )}
      </Card>

      {/* Elevation modal */}
      {elevateProfile && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setElevateProfile(null)}>
          <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-4">Elevate {elevateProfile.username}</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-400 mb-1">New Tier</label>
                <select
                  value={elevateForm.tier}
                  onChange={e => setElevateForm({ ...elevateForm, tier: parseInt(e.target.value) })}
                  className="w-full p-2 bg-gray-700 rounded text-white"
                >
                  <option value={2}>Partner</option>
                  <option value={3}>Sub-Admin</option>
                  <option value={4}>Member</option>
                  <option value={5}>Read-Only</option>
                </select>
              </div>
              {elevateForm.tier === 2 && (
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Partner Discord Tag (required)</label>
                  <input
                    value={elevateForm.partner_discord_tag}
                    onChange={e => setElevateForm({ ...elevateForm, partner_discord_tag: e.target.value })}
                    className="w-full p-2 bg-gray-700 rounded text-white"
                    placeholder="e.g., Haven, IEA, B.E.S"
                  />
                </div>
              )}
              <div className="flex gap-2 pt-2">
                <button onClick={handleElevate} disabled={elevating || (elevateForm.tier === 2 && !elevateForm.partner_discord_tag.trim())} className="btn flex-1">
                  {elevating ? 'Saving...' : 'Confirm'}
                </button>
                <button onClick={() => setElevateProfile(null)} className="btn bg-gray-600">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
