import React, { useState, useContext } from 'react'
import Modal from './Modal'
import AuthContext from '../utils/AuthContext'
import axios from 'axios'

/** Renders a login modal with tab toggle between Admin/Partner, Member, and War Correspondent modes. Props: open, onClose. */
export default function AdminLoginModal({ open, onClose }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [loginType, setLoginType] = useState('admin') // 'admin', 'member', or 'correspondent'
  const auth = useContext(AuthContext)

  if (!open) return null

  async function submit(e) {
    e?.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (loginType === 'correspondent') {
        // Correspondent login uses a separate endpoint; refreshAuth() picks up the session cookie
        await axios.post('/api/warroom/correspondents/login', { username, password })
        await auth.refreshAuth()
        setUsername('')
        setPassword('')
        onClose()
      } else if (loginType === 'member') {
        // Member login - username only (readonly) or username + password (full member)
        await auth.memberLogin(username, password || undefined)
        setUsername('')
        setPassword('')
        onClose()
      } else {
        await auth.login(username, password)
        setUsername('')
        setPassword('')
        onClose()
      }
    } catch (e) {
      const message = e.response?.data?.detail || e.message || 'Login failed'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      submit()
    }
  }

  const passwordRequired = loginType !== 'member'

  return (
    <Modal title="Login" onClose={onClose}>
      <form onSubmit={submit}>
        <div className="space-y-4">
          {/* Login type selector */}
          <div className="flex gap-2 mb-2">
            <button
              type="button"
              onClick={() => setLoginType('admin')}
              className={`flex-1 py-2 rounded text-sm font-medium transition-colors ${
                loginType === 'admin'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              Admin / Partner
            </button>
            <button
              type="button"
              onClick={() => setLoginType('member')}
              className={`flex-1 py-2 rounded text-sm font-medium transition-colors ${
                loginType === 'member'
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              Member
            </button>
            <button
              type="button"
              onClick={() => setLoginType('correspondent')}
              className={`flex-1 py-2 rounded text-sm font-medium transition-colors ${
                loginType === 'correspondent'
                  ? 'bg-red-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              Correspondent
            </button>
          </div>

          {loginType === 'member' && (
            <div className="text-xs text-gray-400 bg-gray-800 rounded p-2">
              Login with your username to view your submission history and stats.
              Password is optional — set one on your profile page to edit your defaults.
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1">Username</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={handleKeyDown}
              type="text"
              className="w-full p-2 border rounded bg-gray-700 text-white placeholder-gray-400"
              placeholder="Enter username"
              autoFocus
              disabled={loading}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Password {loginType === 'member' && <span className="text-gray-500">(optional)</span>}
            </label>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={handleKeyDown}
              type="password"
              className="w-full p-2 border rounded bg-gray-700 text-white placeholder-gray-400"
              placeholder={loginType === 'member' ? 'Optional - leave blank for read-only' : 'Enter password'}
              disabled={loading}
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              className="btn flex-1"
              disabled={loading || !username.trim() || (passwordRequired && !password)}
            >
              {loading ? 'Logging in...' : 'Login'}
            </button>
            <button
              type="button"
              className="btn"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
          </div>
          {error && <div className="text-red-500 mt-2 text-sm">{error}</div>}
        </div>
      </form>
    </Modal>
  )
}
