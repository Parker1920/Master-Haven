import React, { useEffect, useState, useContext } from 'react'
import axios from 'axios'
import { useNavigate, useParams } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import Modal from '../components/Modal'
import { AuthContext } from '../utils/AuthContext'

// Available features that can be toggled for sub-admins (subset of parent's features)
const AVAILABLE_FEATURES = [
  { id: 'system_create', label: 'Create Systems', description: 'Can create new star systems' },
  { id: 'system_edit', label: 'Edit Systems', description: 'Can edit systems tagged with their Discord' },
  { id: 'approvals', label: 'Approvals', description: 'Can approve/reject pending submissions' },
  { id: 'batch_approvals', label: 'Batch Approvals', description: 'Can approve or reject multiple submissions at once' },
  { id: 'stats', label: 'View Statistics', description: 'Can view database statistics' },
  { id: 'settings', label: 'Theme Settings', description: 'Can customize theme colors' }
]

export default function SubAdminManagement() {
  const navigate = useNavigate()
  const { partnerId } = useParams() // Optional: for super admin managing specific partner's sub-admins
  const auth = useContext(AuthContext)
  const [subAdmins, setSubAdmins] = useState([])
  const [partners, setPartners] = useState([]) // For super admin to select partner
  const [loading, setLoading] = useState(true)
  const [actionInProgress, setActionInProgress] = useState(false)

  // Modal states
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [resetPasswordModalOpen, setResetPasswordModalOpen] = useState(false)
  const [selectedSubAdmin, setSelectedSubAdmin] = useState(null)

  // Form state
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    display_name: '',
    enabled_features: [],
    parent_partner_id: partnerId || ''
  })

  // For password reset
  const [newPassword, setNewPassword] = useState('')

  useEffect(() => {
    if (!auth.isAdmin) {
      alert('Admin access required')
      navigate('/systems')
      return
    }
    loadSubAdmins()
    if (auth.isSuperAdmin && !partnerId) {
      loadPartners()
    }
  }, [auth.isAdmin, auth.isSuperAdmin, navigate, partnerId])

  async function loadSubAdmins() {
    setLoading(true)
    try {
      const url = partnerId ? `/api/sub_admins?partner_id=${partnerId}` : '/api/sub_admins'
      const response = await axios.get(url)
      setSubAdmins(response.data.sub_admins || [])
    } catch (err) {
      alert('Failed to load sub-admins: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  async function loadPartners() {
    try {
      const response = await axios.get('/api/partners')
      setPartners(response.data.partners || [])
    } catch (err) {
      console.error('Failed to load partners:', err)
    }
  }

  function resetForm() {
    setFormData({
      username: '',
      password: '',
      display_name: '',
      enabled_features: [],
      // Default to 'haven' for super admin creating sub-admins
      parent_partner_id: partnerId || (auth.isSuperAdmin ? 'haven' : '')
    })
  }

  async function createSubAdmin() {
    if (!formData.username.trim() || formData.username.length < 3) {
      alert('Username must be at least 3 characters')
      return
    }
    if (!formData.password || formData.password.length < 4) {
      alert('Password must be at least 4 characters')
      return
    }
    // For super admin, parent_partner_id is optional (NULL = Haven sub-admin)
    // For partners, it's automatically set on the backend

    setActionInProgress(true)
    try {
      const payload = {
        username: formData.username.trim(),
        password: formData.password,
        display_name: formData.display_name.trim() || formData.username.trim(),
        enabled_features: formData.enabled_features
      }
      // Only include parent_partner_id if specified (for super admin creating under a partner)
      if (formData.parent_partner_id && formData.parent_partner_id !== 'haven') {
        payload.parent_partner_id = parseInt(formData.parent_partner_id)
      }
      await axios.post('/api/sub_admins', payload)
      alert('Sub-admin account created successfully!')
      setCreateModalOpen(false)
      resetForm()
      loadSubAdmins()
    } catch (err) {
      alert('Failed to create sub-admin: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  function openEditModal(subAdmin) {
    setSelectedSubAdmin(subAdmin)
    setFormData({
      username: subAdmin.username,
      password: '',
      display_name: subAdmin.display_name || '',
      enabled_features: subAdmin.enabled_features || [],
      parent_partner_id: subAdmin.parent_partner_id
    })
    setEditModalOpen(true)
  }

  async function updateSubAdmin() {
    setActionInProgress(true)
    try {
      await axios.put(`/api/sub_admins/${selectedSubAdmin.id}`, {
        display_name: formData.display_name.trim() || null,
        enabled_features: formData.enabled_features,
        is_active: selectedSubAdmin.is_active
      })
      alert('Sub-admin updated successfully!')
      setEditModalOpen(false)
      setSelectedSubAdmin(null)
      resetForm()
      loadSubAdmins()
    } catch (err) {
      alert('Failed to update sub-admin: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  function openResetPasswordModal(subAdmin) {
    setSelectedSubAdmin(subAdmin)
    setNewPassword('')
    setResetPasswordModalOpen(true)
  }

  async function resetPassword() {
    if (!newPassword || newPassword.length < 4) {
      alert('New password must be at least 4 characters')
      return
    }

    setActionInProgress(true)
    try {
      await axios.post(`/api/sub_admins/${selectedSubAdmin.id}/reset_password`, {
        new_password: newPassword
      })
      alert('Password reset successfully!')
      setResetPasswordModalOpen(false)
      setSelectedSubAdmin(null)
      setNewPassword('')
    } catch (err) {
      alert('Failed to reset password: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function toggleActive(subAdmin) {
    const action = subAdmin.is_active ? 'deactivate' : 'reactivate'
    if (!confirm(`Are you sure you want to ${action} "${subAdmin.username}"?`)) {
      return
    }

    setActionInProgress(true)
    try {
      if (subAdmin.is_active) {
        await axios.delete(`/api/sub_admins/${subAdmin.id}`)
      } else {
        await axios.put(`/api/sub_admins/${subAdmin.id}`, { is_active: true })
      }
      loadSubAdmins()
    } catch (err) {
      alert(`Failed to ${action} sub-admin: ` + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  function toggleFeature(featureId) {
    setFormData(prev => {
      const features = prev.enabled_features || []
      if (features.includes(featureId)) {
        return { ...prev, enabled_features: features.filter(f => f !== featureId) }
      } else {
        return { ...prev, enabled_features: [...features, featureId] }
      }
    })
  }

  if (loading) {
    return (
      <div className="p-4">
        <Card>
          <p>Loading sub-admins...</p>
        </Card>
      </div>
    )
  }

  return (
    <div className="p-4">
      <Card className="max-w-4xl">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-2xl font-bold">Sub-Admin Management</h2>
            <p className="text-sm text-gray-400 mt-1">
              Sub-admins can approve submissions (except their own) and manage content for their community.
            </p>
          </div>
          <div className="flex space-x-2">
            <Button
              className="bg-green-600 text-white hover:bg-green-700"
              onClick={() => {
                resetForm()
                setCreateModalOpen(true)
              }}
            >
              + Create Sub-Admin
            </Button>
            <Button className="bg-gray-200 text-gray-800" onClick={() => navigate(-1)}>
              Back
            </Button>
          </div>
        </div>

        {subAdmins.length === 0 ? (
          <div className="text-gray-400 italic p-4 bg-gray-700 rounded">
            No sub-admin accounts yet. Create one to allow community members to help with approvals.
          </div>
        ) : (
          <div className="space-y-3">
            {subAdmins.map(subAdmin => (
              <div
                key={subAdmin.id}
                className={`border rounded p-4 ${subAdmin.is_active ? 'bg-cyan-700' : 'bg-gray-600 opacity-75'}`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-semibold">{subAdmin.username}</h3>
                      {!subAdmin.is_active && (
                        <span className="px-2 py-0.5 rounded text-xs bg-red-500 text-white">INACTIVE</span>
                      )}
                    </div>
                    {subAdmin.display_name && (
                      <p className="text-sm text-gray-300">{subAdmin.display_name}</p>
                    )}
                    <p className="text-sm text-cyan-300 mt-1">
                      Parent: {subAdmin.parent_display_name || 'Haven'}
                      {subAdmin.parent_partner_id ? ` (${subAdmin.parent_discord_tag || 'No tag'})` : ' (Super Admin)'}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {(subAdmin.enabled_features || []).map(f => (
                        <span key={f} className="px-2 py-0.5 rounded text-xs bg-cyan-600 text-white">
                          {f}
                        </span>
                      ))}
                      {(!subAdmin.enabled_features || subAdmin.enabled_features.length === 0) && (
                        <span className="text-sm text-gray-400 italic">No features enabled</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-2">
                      Created: {new Date(subAdmin.created_at).toLocaleDateString()}
                      {subAdmin.last_login_at && (
                        <span> | Last login: {new Date(subAdmin.last_login_at).toLocaleDateString()}</span>
                      )}
                    </p>
                  </div>
                  <div className="flex flex-col gap-1">
                    <Button
                      className="bg-blue-600 text-white text-sm px-3 py-1"
                      onClick={() => openEditModal(subAdmin)}
                    >
                      Edit
                    </Button>
                    <Button
                      className="bg-yellow-600 text-white text-sm px-3 py-1"
                      onClick={() => openResetPasswordModal(subAdmin)}
                    >
                      Reset Password
                    </Button>
                    <Button
                      className={`text-sm px-3 py-1 ${subAdmin.is_active ? 'bg-red-600 text-white' : 'bg-green-600 text-white'}`}
                      onClick={() => toggleActive(subAdmin)}
                      disabled={actionInProgress}
                    >
                      {subAdmin.is_active ? 'Deactivate' : 'Reactivate'}
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Create Sub-Admin Modal */}
      {createModalOpen && (
        <Modal title="Create Sub-Admin" onClose={() => setCreateModalOpen(false)}>
          <div className="space-y-4">
            {auth.isSuperAdmin && !partnerId && (
              <div>
                <label className="block text-sm font-semibold mb-1">Parent</label>
                <select
                  className="w-full border rounded p-2 bg-gray-700 text-white"
                  value={formData.parent_partner_id}
                  onChange={(e) => setFormData({...formData, parent_partner_id: e.target.value})}
                >
                  <option value="haven">Haven (Super Admin)</option>
                  <optgroup label="Partners">
                    {partners.filter(p => p.is_active).map(p => (
                      <option key={p.id} value={p.id}>
                        {p.display_name || p.username} ({p.discord_tag || 'No tag'})
                      </option>
                    ))}
                  </optgroup>
                </select>
                <p className="text-xs text-gray-400 mt-1">
                  Haven sub-admins report directly to you (no community tag).
                </p>
              </div>
            )}
            <div>
              <label className="block text-sm font-semibold mb-1">Username *</label>
              <input
                type="text"
                className="w-full border rounded p-2 bg-gray-700 text-white"
                value={formData.username}
                onChange={(e) => setFormData({...formData, username: e.target.value})}
                placeholder="min 3 characters"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold mb-1">Password *</label>
              <input
                type="password"
                className="w-full border rounded p-2 bg-gray-700 text-white"
                value={formData.password}
                onChange={(e) => setFormData({...formData, password: e.target.value})}
                placeholder="min 4 characters"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold mb-1">Display Name</label>
              <input
                type="text"
                className="w-full border rounded p-2 bg-gray-700 text-white"
                value={formData.display_name}
                onChange={(e) => setFormData({...formData, display_name: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-sm font-semibold mb-1">Enabled Features</label>
              <div className="space-y-2">
                {AVAILABLE_FEATURES.map(f => (
                  <label key={f.id} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.enabled_features.includes(f.id)}
                      onChange={() => toggleFeature(f.id)}
                      className="rounded"
                    />
                    <span className="text-sm">{f.label}</span>
                    <span className="text-xs text-gray-400">- {f.description}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex space-x-2 pt-3">
              <Button
                className="bg-green-600 text-white"
                onClick={createSubAdmin}
                disabled={actionInProgress}
              >
                {actionInProgress ? 'Creating...' : 'Create Sub-Admin'}
              </Button>
              <Button
                className="bg-gray-200 text-gray-800"
                onClick={() => setCreateModalOpen(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Edit Sub-Admin Modal */}
      {editModalOpen && selectedSubAdmin && (
        <Modal title={`Edit: ${selectedSubAdmin.username}`} onClose={() => setEditModalOpen(false)}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-semibold mb-1">Display Name</label>
              <input
                type="text"
                className="w-full border rounded p-2 bg-gray-700 text-white"
                value={formData.display_name}
                onChange={(e) => setFormData({...formData, display_name: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-sm font-semibold mb-1">Enabled Features</label>
              <div className="space-y-2">
                {AVAILABLE_FEATURES.map(f => (
                  <label key={f.id} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.enabled_features.includes(f.id)}
                      onChange={() => toggleFeature(f.id)}
                      className="rounded"
                    />
                    <span className="text-sm">{f.label}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex space-x-2 pt-3">
              <Button
                className="bg-blue-600 text-white"
                onClick={updateSubAdmin}
                disabled={actionInProgress}
              >
                {actionInProgress ? 'Saving...' : 'Save Changes'}
              </Button>
              <Button
                className="bg-gray-200 text-gray-800"
                onClick={() => setEditModalOpen(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Reset Password Modal */}
      {resetPasswordModalOpen && selectedSubAdmin && (
        <Modal title={`Reset Password: ${selectedSubAdmin.username}`} onClose={() => setResetPasswordModalOpen(false)}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-semibold mb-1">New Password *</label>
              <input
                type="password"
                className="w-full border rounded p-2 bg-gray-700 text-white"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="min 4 characters"
              />
            </div>
            <div className="flex space-x-2 pt-3">
              <Button
                className="bg-yellow-600 text-white"
                onClick={resetPassword}
                disabled={actionInProgress}
              >
                {actionInProgress ? 'Resetting...' : 'Reset Password'}
              </Button>
              <Button
                className="bg-gray-200 text-gray-800"
                onClick={() => setResetPasswordModalOpen(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
