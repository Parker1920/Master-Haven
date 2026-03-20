import React, { useState } from 'react'
import Modal from './Modal'

/**
 * Modal shown during first-time submission when profile lookup returns suggestions or not_found.
 * Props:
 *   status: 'suggestions' | 'not_found' | 'created'
 *   suggestions: array of {id, username, display_name, default_civ_tag, distance}
 *   username: the username they entered
 *   onUse: (profileId) => void  -- user claims an existing profile
 *   onCreate: (profileData) => void  -- user creates a new profile
 *   onClose: () => void
 */
export default function ProfileClaimModal({ status, suggestions = [], username, onUse, onCreate, onContinue, onClose }) {
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [defaultCivTag, setDefaultCivTag] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleUse(profileId) {
    setLoading(true)
    try {
      await onUse(profileId)
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate() {
    setLoading(true)
    try {
      await onCreate({
        username,
        password: password || undefined,
        default_civ_tag: defaultCivTag || undefined
      })
    } finally {
      setLoading(false)
    }
  }

  if (status === 'created') {
    return (
      <Modal title="Profile Created" onClose={onClose}>
        <div className="space-y-4">
          <div className="text-center">
            <div className="text-green-400 text-lg font-semibold mb-2">Welcome to Haven!</div>
            <p className="text-gray-300">
              A profile has been created for <strong className="text-white">{username}</strong>.
            </p>
            <p className="text-gray-400 text-sm mt-2">
              You can now log in with your username to view your submission history. Set a password on your profile page to edit your defaults.
            </p>
          </div>
          <button
            onClick={onContinue || onClose}
            className="btn w-full"
            disabled={loading}
          >
            Continue with Submission
          </button>
        </div>
      </Modal>
    )
  }

  if (status === 'suggestions') {
    return (
      <Modal title="Is this you?" onClose={onClose}>
        <div className="space-y-4">
          <p className="text-gray-300 text-sm">
            We found similar usernames. Is one of these your profile?
          </p>
          <div className="space-y-2">
            {suggestions.map(s => (
              <button
                key={s.id}
                onClick={() => handleUse(s.id)}
                disabled={loading}
                className="w-full flex items-center justify-between p-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors text-left"
              >
                <div>
                  <div className="text-white font-medium">{s.username}</div>
                  {s.default_civ_tag && (
                    <div className="text-xs text-cyan-400">{s.default_civ_tag}</div>
                  )}
                </div>
                <span className="text-sm text-green-400">That's me</span>
              </button>
            ))}
          </div>
          <div className="border-t border-gray-700 pt-3">
            <button
              onClick={handleCreate}
              disabled={loading}
              className="w-full py-2 bg-gray-800 hover:bg-gray-700 rounded text-gray-300 text-sm transition-colors"
            >
              None of these — create a new profile for "{username}"
            </button>
          </div>
        </div>
      </Modal>
    )
  }

  // status === 'not_found'
  return (
    <Modal title="New Profile" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-gray-300 text-sm">
          No profile found for <strong className="text-white">{username}</strong>.
          We'll create one so you can track your contributions.
        </p>

        <div>
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="text-sm text-cyan-400 hover:text-cyan-300 mb-2"
          >
            {showPassword ? 'Hide password options' : 'Want to set a password? (optional)'}
          </button>
          {showPassword && (
            <div className="space-y-2">
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Password (4+ characters, optional)"
                className="w-full p-2 rounded bg-gray-700 text-white placeholder-gray-400 text-sm"
              />
              <p className="text-xs text-gray-500">
                Setting a password lets you log in and edit your default community, reality, and galaxy.
              </p>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleCreate}
            disabled={loading || (password && password.length < 4)}
            className="btn flex-1"
          >
            {loading ? 'Creating...' : 'Create Profile & Submit'}
          </button>
          <button onClick={onClose} className="btn" disabled={loading}>Cancel</button>
        </div>
      </div>
    </Modal>
  )
}
