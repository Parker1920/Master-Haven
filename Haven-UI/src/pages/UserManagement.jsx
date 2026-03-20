import React, { useState, useEffect, useContext } from 'react'
import axios from 'axios'
import Card from '../components/Card'
import { AuthContext, FEATURES } from '../utils/AuthContext'

const TIER_LABELS = { 1: 'Super Admin', 2: 'Partner', 3: 'Sub-Admin', 4: 'Member', 5: 'Read-Only' }
const TIER_COLORS = { 1: 'bg-yellow-500', 2: 'bg-blue-500', 3: 'bg-teal-500', 4: 'bg-green-500', 5: 'bg-gray-500' }

const PARTNER_FEATURES = [
  { key: 'system_create', label: 'Create Systems' },
  { key: 'system_edit', label: 'Edit Systems' },
  { key: 'approvals', label: 'Approvals' },
  { key: 'batch_approvals', label: 'Batch Approvals' },
  { key: 'stats', label: 'View Statistics' },
  { key: 'settings', label: 'Theme Settings' },
  { key: 'csv_import', label: 'CSV Import' },
  { key: 'war_room', label: 'War Room' },
]

const SUB_ADMIN_FEATURES = [
  { key: 'system_create', label: 'Create Systems' },
  { key: 'system_edit', label: 'Edit Systems' },
  { key: 'approvals', label: 'Approvals' },
  { key: 'batch_approvals', label: 'Batch Approvals' },
  { key: 'stats', label: 'View Statistics' },
  { key: 'settings', label: 'Theme Settings' },
]

export default function UserManagement() {
  const auth = useContext(AuthContext)
  const { isSuperAdmin, isPartner, user } = auth
  const [profiles, setProfiles] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [tierFilter, setTierFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [partners, setPartners] = useState([]) // For sub-admin parent dropdown

  // Edit modal
  const [editProfile, setEditProfile] = useState(null) // full profile detail
  const [editForm, setEditForm] = useState({})
  const [editSaving, setEditSaving] = useState(false)

  // Elevate modal
  const [elevateProfile, setElevateProfile] = useState(null)
  const [elevateForm, setElevateForm] = useState({ tier: 2, partner_discord_tag: '', enabled_features: [], parent_profile_id: null, additional_discord_tags: [], can_approve_personal_uploads: false })
  const [elevating, setElevating] = useState(false)

  // Reset password
  const [resetProfile, setResetProfile] = useState(null)
  const [resetPassword, setResetPassword] = useState('')
  const [resetting, setResetting] = useState(false)

  useEffect(() => { fetchProfiles() }, [page, search, tierFilter])
  useEffect(() => {
    if (isSuperAdmin) {
      // Fetch partner list for sub-admin parent dropdown
      axios.get('/api/admin/profiles', { params: { tier: 2, per_page: 100 } })
        .then(r => setPartners(r.data.profiles || []))
        .catch(() => {})
    }
  }, [isSuperAdmin])

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
    } finally {
      setLoading(false)
    }
  }

  async function openEditModal(profile) {
    try {
      const r = await axios.get(`/api/admin/profiles/${profile.id}`)
      const detail = r.data
      setEditProfile(detail)
      setEditForm({
        display_name: detail.display_name || '',
        enabled_features: detail.enabled_features || [],
        additional_discord_tags: detail.additional_discord_tags || [],
        can_approve_personal_uploads: detail.can_approve_personal_uploads || false,
        partner_discord_tag: detail.partner_discord_tag || '',
        parent_profile_id: detail.parent_profile_id || null,
      })
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to load profile')
    }
  }

  async function saveEdit() {
    if (!editProfile) return
    setEditSaving(true)
    try {
      const body = { ...editForm }

      // If changing tier, use the tier endpoint
      if (editProfile.tier === 2 || editProfile.tier === 3) {
        // Update features and settings via the edit endpoint
        await axios.put(`/api/admin/profiles/${editProfile.id}`, {
          display_name: body.display_name,
          enabled_features: body.enabled_features,
          additional_discord_tags: body.additional_discord_tags,
          can_approve_personal_uploads: body.can_approve_personal_uploads,
        })
      }

      setEditProfile(null)
      fetchProfiles()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to save')
    } finally {
      setEditSaving(false)
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

  async function handleResetPassword() {
    if (!resetProfile || resetPassword.length < 4) return
    setResetting(true)
    try {
      await axios.post(`/api/admin/profiles/${resetProfile.id}/reset-password`, { new_password: resetPassword })
      setResetProfile(null)
      setResetPassword('')
      alert('Password reset successfully')
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to reset password')
    } finally {
      setResetting(false)
    }
  }

  function toggleFeature(key) {
    setEditForm(f => ({
      ...f,
      enabled_features: f.enabled_features.includes(key)
        ? f.enabled_features.filter(k => k !== key)
        : [...f.enabled_features, key]
    }))
  }

  function toggleElevateFeature(key) {
    setElevateForm(f => ({
      ...f,
      enabled_features: f.enabled_features.includes(key)
        ? f.enabled_features.filter(k => k !== key)
        : [...f.enabled_features, key]
    }))
  }

  const totalPages = Math.ceil(total / 25)
  const canManage = isSuperAdmin || isPartner

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
            <option value="2">Partners</option>
            <option value="3">Sub-Admins</option>
            <option value="4">Members</option>
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
                  {canManage && <th className="pb-2">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {profiles.map(p => (
                  <tr key={p.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="py-2 pr-4">
                      <div className="font-medium">{p.username}</div>
                      {p.display_name && p.display_name !== p.username && (
                        <div className="text-xs text-gray-500">{p.display_name}</div>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      <span className={`px-2 py-0.5 rounded text-xs text-white ${TIER_COLORS[p.tier] || 'bg-gray-600'}`}>
                        {TIER_LABELS[p.tier] || `Tier ${p.tier}`}
                      </span>
                    </td>
                    <td className="py-2 pr-4">
                      {p.partner_discord_tag ? (
                        <span className="text-cyan-400">{p.partner_discord_tag}</span>
                      ) : p.default_civ_tag ? (
                        <span className="text-gray-400">{p.default_civ_tag}</span>
                      ) : (
                        <span className="text-gray-600">-</span>
                      )}
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
                    {canManage && (
                      <td className="py-2">
                        <div className="flex gap-1 flex-wrap">
                          {/* Edit button - for partners and sub-admins */}
                          {(p.tier === 2 || p.tier === 3) && (isSuperAdmin || (isPartner && p.tier === 3)) && (
                            <button
                              onClick={() => openEditModal(p)}
                              className="px-2 py-1 bg-gray-600 hover:bg-gray-500 text-white text-xs rounded"
                            >
                              Edit
                            </button>
                          )}
                          {/* Elevate - super admin only, for users with passwords */}
                          {isSuperAdmin && p.tier > 2 && p.has_password && (
                            <button
                              onClick={() => {
                                setElevateProfile(p)
                                setElevateForm({ tier: p.tier <= 3 ? p.tier : 3, partner_discord_tag: '', enabled_features: [], parent_profile_id: null, additional_discord_tags: [], can_approve_personal_uploads: false })
                              }}
                              className="px-2 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded"
                            >
                              Elevate
                            </button>
                          )}
                          {/* Demote - super admin only, for partners/sub-admins */}
                          {isSuperAdmin && p.tier >= 2 && p.tier <= 3 && (
                            <button
                              onClick={() => {
                                if (confirm(`Demote ${p.username} to Member?`)) {
                                  axios.put(`/api/admin/profiles/${p.id}/tier`, { tier: 4 })
                                    .then(() => fetchProfiles())
                                    .catch(err => alert(err.response?.data?.detail || 'Failed'))
                                }
                              }}
                              className="px-2 py-1 bg-orange-600 hover:bg-orange-500 text-white text-xs rounded"
                            >
                              Demote
                            </button>
                          )}
                          {/* Reset Password */}
                          {(isSuperAdmin || (isPartner && p.tier === 3)) && p.tier > 1 && (
                            <button
                              onClick={() => { setResetProfile(p); setResetPassword('') }}
                              className="px-2 py-1 bg-yellow-700 hover:bg-yellow-600 text-white text-xs rounded"
                            >
                              Reset PW
                            </button>
                          )}
                          {/* Activate/Deactivate */}
                          {(isSuperAdmin || (isPartner && p.tier === 3)) && p.tier > 1 && (
                            <button
                              onClick={() => toggleActive(p)}
                              className={`px-2 py-1 text-xs rounded ${p.is_active ? 'bg-red-600 hover:bg-red-500' : 'bg-green-600 hover:bg-green-500'} text-white`}
                            >
                              {p.is_active ? 'Deactivate' : 'Activate'}
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
                {profiles.length === 0 && (
                  <tr><td colSpan={7} className="py-8 text-center text-gray-500">No profiles found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex justify-center gap-2 mt-4">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn text-sm">Prev</button>
            <span className="text-gray-400 text-sm py-1">Page {page} of {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn text-sm">Next</button>
          </div>
        )}
      </Card>

      {/* ========== EDIT MODAL ========== */}
      {editProfile && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 overflow-y-auto" onClick={() => setEditProfile(null)}>
          <div className="bg-gray-800 rounded-lg p-6 max-w-lg w-full mx-4 my-8" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-1">Edit {editProfile.username}</h2>
            <div className="text-sm text-gray-400 mb-4">
              <span className={`px-2 py-0.5 rounded text-xs text-white ${TIER_COLORS[editProfile.tier]}`}>
                {TIER_LABELS[editProfile.tier]}
              </span>
              {editProfile.partner_discord_tag && (
                <span className="ml-2 text-cyan-400">{editProfile.partner_discord_tag}</span>
              )}
              {editProfile.parent_info && (
                <span className="ml-2">under {editProfile.parent_info.username} ({editProfile.parent_info.partner_discord_tag})</span>
              )}
            </div>

            <div className="space-y-4">
              {/* Display Name */}
              <div>
                <label className="block text-sm text-gray-400 mb-1">Display Name</label>
                <input
                  value={editForm.display_name}
                  onChange={e => setEditForm({ ...editForm, display_name: e.target.value })}
                  className="w-full p-2 bg-gray-700 rounded text-white"
                />
              </div>

              {/* Feature permissions */}
              <div>
                <label className="block text-sm text-gray-400 mb-2">Permissions</label>
                <div className="grid grid-cols-2 gap-2">
                  {(editProfile.tier === 2 ? PARTNER_FEATURES : SUB_ADMIN_FEATURES).map(f => (
                    <label key={f.key} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-700/50 p-1 rounded">
                      <input
                        type="checkbox"
                        checked={editForm.enabled_features.includes(f.key)}
                        onChange={() => toggleFeature(f.key)}
                        className="rounded"
                      />
                      <span>{f.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Sub-admin specific: additional discord tags */}
              {editProfile.tier === 3 && !editProfile.parent_profile_id && (
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Additional Community Tags (Haven sub-admins)</label>
                  <p className="text-xs text-gray-500 mb-2">Tags this sub-admin can see pending approvals for, in addition to Haven.</p>
                  <div className="flex flex-wrap gap-2">
                    {partners.map(p => p.partner_discord_tag && (
                      <label key={p.id} className="flex items-center gap-1 text-xs cursor-pointer bg-gray-700 px-2 py-1 rounded">
                        <input
                          type="checkbox"
                          checked={editForm.additional_discord_tags.includes(p.partner_discord_tag)}
                          onChange={() => {
                            const tags = editForm.additional_discord_tags
                            setEditForm({
                              ...editForm,
                              additional_discord_tags: tags.includes(p.partner_discord_tag)
                                ? tags.filter(t => t !== p.partner_discord_tag)
                                : [...tags, p.partner_discord_tag]
                            })
                          }}
                        />
                        <span className="text-cyan-400">{p.partner_discord_tag}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Sub-admin specific: can_approve_personal_uploads */}
              {editProfile.tier === 3 && !editProfile.parent_profile_id && (
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editForm.can_approve_personal_uploads}
                    onChange={e => setEditForm({ ...editForm, can_approve_personal_uploads: e.target.checked })}
                  />
                  <span>Can approve personal uploads</span>
                </label>
              )}

              {/* Stats */}
              {editProfile.stats && (
                <div className="text-xs text-gray-500 pt-2 border-t border-gray-700">
                  {editProfile.stats.systems} systems, {editProfile.stats.discoveries} discoveries
                  {editProfile.created_at && <span className="ml-3">Member since {new Date(editProfile.created_at).toLocaleDateString()}</span>}
                </div>
              )}

              <div className="flex gap-2 pt-2">
                <button onClick={saveEdit} disabled={editSaving} className="btn flex-1">
                  {editSaving ? 'Saving...' : 'Save Changes'}
                </button>
                <button onClick={() => setEditProfile(null)} className="btn bg-gray-600">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========== ELEVATE MODAL ========== */}
      {elevateProfile && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 overflow-y-auto" onClick={() => setElevateProfile(null)}>
          <div className="bg-gray-800 rounded-lg p-6 max-w-lg w-full mx-4 my-8" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-4">Elevate {elevateProfile.username}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">New Tier</label>
                <select
                  value={elevateForm.tier}
                  onChange={e => setElevateForm({ ...elevateForm, tier: parseInt(e.target.value), enabled_features: [] })}
                  className="w-full p-2 bg-gray-700 rounded text-white"
                >
                  <option value={2}>Partner (Community Leader)</option>
                  <option value={3}>Sub-Admin (Community Moderator)</option>
                  <option value={4}>Member</option>
                  <option value={5}>Read-Only</option>
                </select>
              </div>

              {/* Partner: discord tag */}
              {elevateForm.tier === 2 && (
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Community Tag (required)</label>
                  <input
                    value={elevateForm.partner_discord_tag}
                    onChange={e => setElevateForm({ ...elevateForm, partner_discord_tag: e.target.value })}
                    className="w-full p-2 bg-gray-700 rounded text-white"
                    placeholder="e.g., Haven, IEA, B.E.S"
                  />
                </div>
              )}

              {/* Sub-admin: parent partner */}
              {elevateForm.tier === 3 && (
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Parent Partner (optional - leave blank for Haven sub-admin)</label>
                  <select
                    value={elevateForm.parent_profile_id || ''}
                    onChange={e => setElevateForm({ ...elevateForm, parent_profile_id: e.target.value ? parseInt(e.target.value) : null })}
                    className="w-full p-2 bg-gray-700 rounded text-white"
                  >
                    <option value="">Haven (no parent)</option>
                    {partners.map(p => (
                      <option key={p.id} value={p.id}>{p.username} ({p.partner_discord_tag})</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Feature permissions for Partner/Sub-Admin */}
              {(elevateForm.tier === 2 || elevateForm.tier === 3) && (
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Permissions</label>
                  <div className="grid grid-cols-2 gap-2">
                    {(elevateForm.tier === 2 ? PARTNER_FEATURES : SUB_ADMIN_FEATURES).map(f => (
                      <label key={f.key} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-700/50 p-1 rounded">
                        <input
                          type="checkbox"
                          checked={elevateForm.enabled_features.includes(f.key)}
                          onChange={() => toggleElevateFeature(f.key)}
                          className="rounded"
                        />
                        <span>{f.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex gap-2 pt-2">
                <button
                  onClick={handleElevate}
                  disabled={elevating || (elevateForm.tier === 2 && !elevateForm.partner_discord_tag.trim())}
                  className="btn flex-1"
                >
                  {elevating ? 'Saving...' : 'Confirm Elevation'}
                </button>
                <button onClick={() => setElevateProfile(null)} className="btn bg-gray-600">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========== RESET PASSWORD MODAL ========== */}
      {resetProfile && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setResetProfile(null)}>
          <div className="bg-gray-800 rounded-lg p-6 max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-4">Reset Password for {resetProfile.username}</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-400 mb-1">New Password</label>
                <input
                  type="password"
                  value={resetPassword}
                  onChange={e => setResetPassword(e.target.value)}
                  placeholder="At least 4 characters"
                  className="w-full p-2 bg-gray-700 rounded text-white"
                />
              </div>
              <div className="flex gap-2">
                <button onClick={handleResetPassword} disabled={resetting || resetPassword.length < 4} className="btn flex-1">
                  {resetting ? 'Resetting...' : 'Reset Password'}
                </button>
                <button onClick={() => setResetProfile(null)} className="btn bg-gray-600">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
