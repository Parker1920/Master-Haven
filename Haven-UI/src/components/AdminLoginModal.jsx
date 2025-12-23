import React, { useState, useContext } from 'react'
import Modal from './Modal'
import AuthContext from '../utils/AuthContext'

export default function AdminLoginModal({ open, onClose }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const auth = useContext(AuthContext)

  if (!open) return null

  async function submit(e) {
    e?.preventDefault()
    setError('')
    setLoading(true)
    try {
      await auth.login(username, password)
      setUsername('')
      setPassword('')
      onClose()
    } catch (e) {
      setError(e.message || 'Login failed')
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
