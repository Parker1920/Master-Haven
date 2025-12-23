import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import Modal from '../components/Modal'
import { adminStatus } from '../utils/api'

export default function ApiKeys() {
  const navigate = useNavigate()
  const [isAdmin, setIsAdmin] = useState(false)
  const [loading, setLoading] = useState(true)
  const [keys, setKeys] = useState([])
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [viewKeyModalOpen, setViewKeyModalOpen] = useState(false)
  const [newKeyData, setNewKeyData] = useState(null)
  const [actionInProgress, setActionInProgress] = useState(false)

  // Form state for creating a new key
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyRateLimit, setNewKeyRateLimit] = useState(200)

  useEffect(() => {
    adminStatus().then(r => {
      setIsAdmin(r.logged_in)
      if (!r.logged_in) {
        alert('Admin authentication required')
        navigate('/systems')
      } else {
        loadKeys()
      }
    }).catch(() => {
      alert('Failed to verify admin status')
      navigate('/systems')
    })
  }, [navigate])

  async function loadKeys() {
    setLoading(true)
    try {
      const response = await axios.get('/api/keys')
      setKeys(response.data.keys || [])
    } catch (err) {
      alert('Failed to load API keys: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  async function createKey() {
    if (!newKeyName.trim()) {
      alert('Please enter a name for the API key')
      return
    }

    setActionInProgress(true)
    try {
      const response = await axios.post('/api/keys', {
        name: newKeyName.trim(),
        rate_limit: newKeyRateLimit,
        permissions: ['submit', 'check_duplicate']
      })

      // Store the new key data to show in the modal
      setNewKeyData(response.data)
      setCreateModalOpen(false)
      setViewKeyModalOpen(true)

      // Reset form
      setNewKeyName('')
      setNewKeyRateLimit(200)

      // Reload keys list
      loadKeys()
    } catch (err) {
      alert('Failed to create API key: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function revokeKey(keyId, keyName) {
    if (!confirm(`Revoke API key "${keyName}"?\n\nThis will immediately invalidate the key. Any companion apps using it will stop working.`)) {
      return
    }

    setActionInProgress(true)
    try {
      await axios.delete(`/api/keys/${keyId}`)
      alert(`API key "${keyName}" has been revoked.`)
      loadKeys()
    } catch (err) {
      alert('Failed to revoke API key: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function reactivateKey(keyId, keyName) {
    setActionInProgress(true)
    try {
      await axios.put(`/api/keys/${keyId}`, { is_active: true })
      alert(`API key "${keyName}" has been reactivated.`)
      loadKeys()
    } catch (err) {
      alert('Failed to reactivate API key: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
      alert('API key copied to clipboard!')
    }).catch(() => {
      alert('Failed to copy to clipboard. Please copy manually.')
    })
  }

  function formatDate(isoString) {
    if (!isoString) return 'Never'
    const date = new Date(isoString)
    return date.toLocaleString()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-400">Loading API keys...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-cyan-400">API Keys</h1>
          <p className="text-gray-400 mt-1">
            Manage API keys for the NMS Save Watcher companion app and other integrations
          </p>
        </div>
        <Button onClick={() => setCreateModalOpen(true)} disabled={actionInProgress}>
          + Create New Key
        </Button>
      </div>

      {/* Info Card */}
      <Card className="bg-gray-800/50 border border-cyan-900/50">
        <div className="p-4">
          <h3 className="text-cyan-400 font-semibold mb-2">About API Keys</h3>
          <ul className="text-gray-300 text-sm space-y-1 list-disc list-inside">
            <li>API keys allow external applications to submit systems to Voyagers Haven</li>
            <li>Submissions via API key go to the pending approval queue (same as manual submissions)</li>
            <li>Each key has its own rate limit (default: 200 requests/hour)</li>
            <li>Keys are shown only once when created - save them securely!</li>
            <li>Revoked keys can be reactivated if needed</li>
          </ul>
        </div>
      </Card>

      {/* Keys List */}
      {keys.length === 0 ? (
        <Card className="bg-gray-800/50">
          <div className="p-8 text-center text-gray-400">
            <p className="text-lg mb-2">No API keys yet</p>
            <p className="text-sm">Create an API key to allow the NMS Save Watcher companion app to submit discoveries.</p>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {keys.map(key => (
            <Card key={key.id} className={`bg-gray-800/50 border ${key.is_active ? 'border-gray-700' : 'border-red-900/50'}`}>
              <div className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-white">{key.name}</h3>
                      {key.is_active ? (
                        <span className="px-2 py-0.5 text-xs rounded-full bg-green-900/50 text-green-400 border border-green-700">
                          Active
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 text-xs rounded-full bg-red-900/50 text-red-400 border border-red-700">
                          Revoked
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">Key Prefix:</span>
                        <p className="text-gray-300 font-mono">{key.key_prefix}...</p>
                      </div>
                      <div>
                        <span className="text-gray-500">Rate Limit:</span>
                        <p className="text-gray-300">{key.rate_limit}/hour</p>
                      </div>
                      <div>
                        <span className="text-gray-500">Created:</span>
                        <p className="text-gray-300">{formatDate(key.created_at)}</p>
                      </div>
                      <div>
                        <span className="text-gray-500">Last Used:</span>
                        <p className="text-gray-300">{formatDate(key.last_used_at)}</p>
                      </div>
                    </div>

                    <div className="mt-2">
                      <span className="text-gray-500 text-sm">Permissions: </span>
                      <span className="text-gray-400 text-sm">
                        {(key.permissions || []).join(', ') || 'None'}
                      </span>
                    </div>
                  </div>

                  <div className="flex gap-2 ml-4">
                    {key.is_active ? (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => revokeKey(key.id, key.name)}
                        disabled={actionInProgress}
                      >
                        Revoke
                      </Button>
                    ) : (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => reactivateKey(key.id, key.name)}
                        disabled={actionInProgress}
                      >
                        Reactivate
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create Key Modal */}
      <Modal isOpen={createModalOpen} onClose={() => setCreateModalOpen(false)} title="Create API Key">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Key Name *
            </label>
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="e.g., Parker's Companion App"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <p className="text-gray-500 text-xs mt-1">A descriptive name to identify this key</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Rate Limit (requests/hour)
            </label>
            <input
              type="number"
              value={newKeyRateLimit}
              onChange={(e) => setNewKeyRateLimit(parseInt(e.target.value) || 200)}
              min="1"
              max="1000"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <p className="text-gray-500 text-xs mt-1">Maximum submissions per hour (default: 200)</p>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button variant="secondary" onClick={() => setCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={createKey} disabled={actionInProgress || !newKeyName.trim()}>
              {actionInProgress ? 'Creating...' : 'Create Key'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* View New Key Modal */}
      <Modal isOpen={viewKeyModalOpen} onClose={() => setViewKeyModalOpen(false)} title="API Key Created">
        {newKeyData && (
          <div className="space-y-4">
            <div className="bg-yellow-900/30 border border-yellow-700 rounded p-4">
              <div className="flex items-start gap-2">
                <span className="text-yellow-500 text-xl">⚠️</span>
                <div>
                  <p className="text-yellow-400 font-semibold">Save this key now!</p>
                  <p className="text-yellow-300 text-sm">
                    This is the only time the full key will be shown. Store it securely.
                  </p>
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Your API Key
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newKeyData.key}
                  readOnly
                  className="flex-1 px-3 py-2 bg-gray-900 border border-gray-600 rounded text-cyan-400 font-mono text-sm"
                />
                <Button onClick={() => copyToClipboard(newKeyData.key)}>
                  Copy
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Name:</span>
                <p className="text-white">{newKeyData.name}</p>
              </div>
              <div>
                <span className="text-gray-500">Rate Limit:</span>
                <p className="text-white">{newKeyData.rate_limit}/hour</p>
              </div>
            </div>

            <div className="bg-gray-800 rounded p-4 text-sm">
              <p className="text-gray-400 mb-2">To use this key with the NMS Save Watcher companion app:</p>
              <ol className="list-decimal list-inside text-gray-300 space-y-1">
                <li>Open the companion app's web dashboard</li>
                <li>Go to Settings</li>
                <li>Paste this API key in the API Key field</li>
                <li>Save your settings</li>
              </ol>
            </div>

            <div className="flex justify-end pt-4 border-t border-gray-700">
              <Button onClick={() => setViewKeyModalOpen(false)}>
                I've Saved the Key
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
