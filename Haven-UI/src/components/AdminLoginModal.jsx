import React, { useState, useContext } from 'react'
import Modal from './Modal'
import AuthContext from '../utils/AuthContext'
import axios from 'axios'

export default function AdminLoginModal({ open, onClose }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [loginType, setLoginType] = useState('admin') // 'admin' or 'correspondent'
  const auth = useContext(AuthContext)

  if (!open) return null

  async function submit(e) {
    e?.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (loginType === 'correspondent') {
        // Use correspondent login endpoint
        const response = await axios.post('/api/warroom/correspondents/login', {
          username,
          password
        })
        // Refresh auth state after correspondent login
        await auth.refreshAuth()
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
              onClick={() => setLoginType('correspondent')}
              className={`flex-1 py-2 rounded text-sm font-medium transition-colors ${
                loginType === 'correspondent'
                  ? 'bg-red-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              War Correspondent
            </button>
          </div>

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
            <label className="block text-sm font-medium mb-1">Password</label>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={handleKeyDown}
              type="password"
              className="w-full p-2 border rounded bg-gray-700 text-white placeholder-gray-400"
              placeholder="Enter password"
              disabled={loading}
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              className="btn flex-1"
              disabled={loading || !username.trim() || !password}
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
