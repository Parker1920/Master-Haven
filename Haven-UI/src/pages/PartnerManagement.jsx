import React, { useEffect, useState, useContext } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import Modal from '../components/Modal'
import { AuthContext } from '../utils/AuthContext'

// Available features that can be toggled for partners
const AVAILABLE_FEATURES = [
  { id: 'system_create', label: 'Create Systems', description: 'Can create new star systems' },
  { id: 'system_edit', label: 'Edit Systems', description: 'Can edit systems tagged with their Discord' },
  { id: 'approvals', label: 'View Approvals', description: 'Can approve/reject pending submissions for their Discord' },
  { id: 'stats', label: 'View Statistics', description: 'Can view database statistics for their Discord' },
  { id: 'settings', label: 'Theme Settings', description: 'Can customize their theme colors' }
]

export default function PartnerManagement() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [partners, setPartners] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionInProgress, setActionInProgress] = useState(false)

  // Modal states
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [resetPasswordModalOpen, setResetPasswordModalOpen] = useState(false)
  const [selectedPartner, setSelectedPartner] = useState(null)

  // Form state
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    discord_tag: '',
    display_name: '',
    enabled_features: []
  })

  useEffect(() => {
    // Check if super admin
    if (!auth.isSuperAdmin) {
      alert('Super admin access required')
      navigate('/systems')
      return
    }
    loadPartners()
  }, [auth.isSuperAdmin, navigate])

  async function loadPartners() {
    setLoading(true)
    try {
      const response = await axios.get('/api/partners')
      setPartners(response.data.partners || [])
    } catch (err) {
      alert('Failed to load partners: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  function resetForm() {
    setFormData({
      username: '',
      password: '',
      discord_tag: '',
      display_name: '',
      enabled_features: []
    })
  }

  async function createPartner() {
    if (!formData.username.trim() || formData.username.length < 3) {
      alert('Username must be at least 3 characters')
      return
    }
    if (!formData.password || formData.password.length < 4) {
      alert('Password must be at least 4 characters')
      return
    }

    setActionInProgress(true)
    try {
      await axios.post('/api/partners', {
        username: formData.username.trim(),
        password: formData.password,
        discord_tag: formData.discord_tag.trim() || null,
        display_name: formData.display_name.trim() || formData.username.trim(),
        enabled_features: formData.enabled_features
      })
      alert('Partner account created successfully!')
      setCreateModalOpen(false)
      resetForm()
      loadPartners()
    } catch (err) {
      alert('Failed to create partner: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function updatePartner() {
    setActionInProgress(true)
    try {
      await axios.put(`/api/partners/${selectedPartner.id}`, {
        discord_tag: formData.discord_tag.trim() || null,
        display_name: formData.display_name.trim(),
        enabled_features: formData.enabled_features
      })
      alert('Partner updated successfully!')
      setEditModalOpen(false)
      loadPartners()
    } catch (err) {
      alert('Failed to update partner: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function resetPassword() {
    if (!formData.password || formData.password.length < 4) {
      alert('Password must be at least 4 characters')
      return
    }

    setActionInProgress(true)
    try {
      await axios.post(`/api/partners/${selectedPartner.id}/reset_password`, {
        password: formData.password
      })
      alert('Password reset successfully!')
      setResetPasswordModalOpen(false)
      resetForm()
    } catch (err) {
      alert('Failed to reset password: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function toggleActive(partner) {
    const action = partner.is_active ? 'deactivate' : 'activate'
    if (partner.is_active && !confirm(`Deactivate partner "${partner.display_name || partner.username}"?\n\nThey will not be able to log in until reactivated.`)) {
      return
    }

    setActionInProgress(true)
    try {
      if (partner.is_active) {
        await axios.delete(`/api/partners/${partner.id}`)
      } else {
        await axios.post(`/api/partners/${partner.id}/activate`)
      }
      loadPartners()
    } catch (err) {
      alert(`Failed to ${action} partner: ` + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  function openEditModal(partner) {
    setSelectedPartner(partner)
    setFormData({
      username: partner.username,
      password: '',
      discord_tag: partner.discord_tag || '',
      display_name: partner.display_name || '',
      enabled_features: partner.enabled_features || []
    })
    setEditModalOpen(true)
  }

  function openResetPasswordModal(partner) {
    setSelectedPartner(partner)
    setFormData({ ...formData, password: '' })
    setResetPasswordModalOpen(true)
  }

  function toggleFeature(featureId) {
    setFormData(prev => ({
      ...prev,
      enabled_features: prev.enabled_features.includes(featureId)
        ? prev.enabled_features.filter(f => f !== featureId)
        : [...prev.enabled_features, featureId]
    }))
  }

  function formatDate(isoString) {
    if (!isoString) return 'Never'
    return new Date(isoString).toLocaleString()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-400">Loading partners...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-cyan-400">Partner Management</h1>
          <p className="text-gray-400 mt-1">
            Create and manage login accounts for partner Discord servers
          </p>
        </div>
        <Button onClick={() => { resetForm(); setCreateModalOpen(true) }} disabled={actionInProgress}>
          + Add Partner
        </Button>
      </div>

      {/* Info Card */}
      <Card className="bg-gray-800/50 border border-cyan-900/50">
        <div className="p-4">
          <h3 className="text-cyan-400 font-semibold mb-2">About Partner Accounts</h3>
          <ul className="text-gray-300 text-sm space-y-1 list-disc list-inside">
            <li>Each partner account is tied to a Discord server via a short tag (e.g., "GHDF", "NMSHub")</li>
            <li>Partners can only edit systems/regions tagged with their Discord</li>
            <li>When partners edit untagged systems, it requires your approval</li>
            <li>You control which features each partner has access to</li>
            <li>Multiple admins from the same Discord can share one login</li>
          </ul>
        </div>
      </Card>

      {/* Partners List */}
      {partners.length === 0 ? (
        <Card className="bg-gray-800/50">
          <div className="p-8 text-center text-gray-400">
            <p className="text-lg mb-2">No partner accounts yet</p>
            <p className="text-sm">Create a partner account to give other Discord servers their own space.</p>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {partners.map(partner => (
            <Card key={partner.id} className={`bg-gray-800/50 border ${partner.is_active ? 'border-gray-700' : 'border-red-900/50'}`}>
              <div className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-white">
                        {partner.display_name || partner.username}
                      </h3>
                      <span className="text-sm text-gray-400">@{partner.username}</span>
                      {partner.is_active ? (
                        <span className="px-2 py-0.5 text-xs rounded-full bg-green-900/50 text-green-400 border border-green-700">
                          Active
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 text-xs rounded-full bg-red-900/50 text-red-400 border border-red-700">
                          Inactive
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-3">
                      <div>
                        <span className="text-gray-500">Discord Tag:</span>
                        <p className="text-cyan-400 font-mono">{partner.discord_tag || 'Not set'}</p>
                      </div>
                      <div>
                        <span className="text-gray-500">Created:</span>
                        <p className="text-gray-300">{formatDate(partner.created_at)}</p>
                      </div>
                      <div>
                        <span className="text-gray-500">Last Login:</span>
                        <p className="text-gray-300">{formatDate(partner.last_login_at)}</p>
                      </div>
                    </div>

                    <div>
                      <span className="text-gray-500 text-sm">Enabled Features: </span>
                      <span className="text-gray-400 text-sm">
                        {(partner.enabled_features || []).length > 0
                          ? partner.enabled_features.map(f => {
                              const feat = AVAILABLE_FEATURES.find(af => af.id === f)
                              return feat ? feat.label : f
                            }).join(', ')
                          : 'None'}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col gap-2 ml-4">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => openEditModal(partner)}
                      disabled={actionInProgress}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => openResetPasswordModal(partner)}
                      disabled={actionInProgress}
                    >
                      Reset Password
                    </Button>
                    <Button
                      variant={partner.is_active ? 'danger' : 'primary'}
                      size="sm"
                      onClick={() => toggleActive(partner)}
                      disabled={actionInProgress}
                    >
                      {partner.is_active ? 'Deactivate' : 'Activate'}
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create Partner Modal */}
      <Modal isOpen={createModalOpen} onClose={() => setCreateModalOpen(false)} title="Create Partner Account">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Username *
            </label>
            <input
              type="text"
              value={formData.username}
              onChange={(e) => setFormData({...formData, username: e.target.value})}
              placeholder="e.g., GHDFAdmin"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <p className="text-gray-500 text-xs mt-1">Login username (min 3 characters)</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Password *
            </label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({...formData, password: e.target.value})}
              placeholder="Enter password"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <p className="text-gray-500 text-xs mt-1">Min 4 characters</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Discord Tag
            </label>
            <input
              type="text"
              value={formData.discord_tag}
              onChange={(e) => setFormData({...formData, discord_tag: e.target.value})}
              placeholder="e.g., GHDF"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <p className="text-gray-500 text-xs mt-1">Short identifier for their Discord server. Systems/regions with this tag belong to them.</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Display Name
            </label>
            <input
              type="text"
              value={formData.display_name}
              onChange={(e) => setFormData({...formData, display_name: e.target.value})}
              placeholder="e.g., Galactic Hub Defense Force"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <p className="text-gray-500 text-xs mt-1">Friendly name shown in the UI</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Enabled Features
            </label>
            <div className="space-y-2 bg-gray-800 p-3 rounded border border-gray-700">
              {AVAILABLE_FEATURES.map(feature => (
                <label key={feature.id} className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.enabled_features.includes(feature.id)}
                    onChange={() => toggleFeature(feature.id)}
                    className="mt-1"
                  />
                  <div>
                    <span className="text-white">{feature.label}</span>
                    <p className="text-gray-500 text-xs">{feature.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button variant="secondary" onClick={() => setCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={createPartner} disabled={actionInProgress || !formData.username.trim() || !formData.password}>
              {actionInProgress ? 'Creating...' : 'Create Partner'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Edit Partner Modal */}
      <Modal isOpen={editModalOpen} onClose={() => setEditModalOpen(false)} title={`Edit ${selectedPartner?.display_name || selectedPartner?.username || 'Partner'}`}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Discord Tag
            </label>
            <input
              type="text"
              value={formData.discord_tag}
              onChange={(e) => setFormData({...formData, discord_tag: e.target.value})}
              placeholder="e.g., GHDF"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Display Name
            </label>
            <input
              type="text"
              value={formData.display_name}
              onChange={(e) => setFormData({...formData, display_name: e.target.value})}
              placeholder="e.g., Galactic Hub Defense Force"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Enabled Features
            </label>
            <div className="space-y-2 bg-gray-800 p-3 rounded border border-gray-700">
              {AVAILABLE_FEATURES.map(feature => (
                <label key={feature.id} className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.enabled_features.includes(feature.id)}
                    onChange={() => toggleFeature(feature.id)}
                    className="mt-1"
                  />
                  <div>
                    <span className="text-white">{feature.label}</span>
                    <p className="text-gray-500 text-xs">{feature.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button variant="secondary" onClick={() => setEditModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={updatePartner} disabled={actionInProgress}>
              {actionInProgress ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Reset Password Modal */}
      <Modal isOpen={resetPasswordModalOpen} onClose={() => setResetPasswordModalOpen(false)} title={`Reset Password for ${selectedPartner?.display_name || selectedPartner?.username || 'Partner'}`}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              New Password *
            </label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({...formData, password: e.target.value})}
              placeholder="Enter new password"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <p className="text-gray-500 text-xs mt-1">Min 4 characters</p>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button variant="secondary" onClick={() => setResetPasswordModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={resetPassword} disabled={actionInProgress || !formData.password || formData.password.length < 4}>
              {actionInProgress ? 'Resetting...' : 'Reset Password'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
