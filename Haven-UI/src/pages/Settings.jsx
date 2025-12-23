import React, { useEffect, useState, useContext } from 'react'
import { AuthContext } from '../utils/AuthContext'
import Card from '../components/Card'
import Button from '../components/Button'

export default function Settings() {
  const auth = useContext(AuthContext)
  const { isAdmin, isSuperAdmin, isPartner, user, logout } = auth || {}

  const [settings, setSettings] = useState({})
  const [partnerTheme, setPartnerTheme] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    // Load global settings
    fetch('/api/settings', { credentials: 'include' })
      .then(r => r.json())
      .then(s => setSettings(s || {}))
      .catch(() => {})
      .finally(() => setLoading(false))

    // Load partner theme if partner
    if (isPartner) {
      fetch('/api/partner/theme', { credentials: 'include' })
        .then(r => r.json())
        .then(data => setPartnerTheme(data.theme || {}))
        .catch(() => {})
    }
  }, [isPartner])

  const updateTheme = (k, v) => {
    const theme = { ...(settings.theme || {}), [k]: v }
    setSettings({ ...settings, theme })
    // Apply immediately for preview
    if (k === 'bg') document.documentElement.style.setProperty('--app-bg', v)
    if (k === 'text') document.documentElement.style.setProperty('--app-text', v)
    if (k === 'card') document.documentElement.style.setProperty('--app-card', v)
    if (k === 'primary') document.documentElement.style.setProperty('--app-primary', v)
  }

  const updatePartnerTheme = (k, v) => {
    const theme = { ...partnerTheme, [k]: v }
    setPartnerTheme(theme)
    // Apply immediately for preview
    if (k === 'bg') document.documentElement.style.setProperty('--app-bg', v)
    if (k === 'text') document.documentElement.style.setProperty('--app-text', v)
    if (k === 'card') document.documentElement.style.setProperty('--app-card', v)
    if (k === 'primary') document.documentElement.style.setProperty('--app-primary', v)
  }

  const saveGlobalSettings = async () => {
    setSaving(true)
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      })
      if (!res.ok) throw new Error(await res.text())
      alert('Settings saved successfully!')
    } catch (e) {
      alert('Failed to save settings: ' + e)
    }
    setSaving(false)
  }

  const savePartnerTheme = async () => {
    setSaving(true)
    try {
      const res = await fetch('/api/partner/theme', {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme: partnerTheme })
      })
      if (!res.ok) throw new Error(await res.text())
      alert('Theme saved successfully!')
    } catch (e) {
      alert('Failed to save theme: ' + e)
    }
    setSaving(false)
  }

  const doBackup = async () => {
    try {
      const res = await fetch('/api/backup', { method: 'POST', credentials: 'include' })
      if (!res.ok) throw new Error(await res.text())
      const j = await res.json()
      alert('Backup created: ' + j.backup_path)
    } catch (e) {
      alert('Backup failed: ' + e)
    }
  }

  const onUploadDB = async (e) => {
    try {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch('/api/db_upload', { method: 'POST', credentials: 'include', body: fd })
      if (!res.ok) throw new Error(await res.text())
      const j = await res.json()
      alert('DB uploaded: ' + j.path)
    } catch (e) {
      alert('DB upload failed: ' + e)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-400">Loading settings...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-cyan-400">Settings</h1>

      {/* User Info */}
      <Card className="bg-gray-800/50">
        <div className="p-4">
          <h3 className="text-lg font-semibold text-white mb-2">Logged in as</h3>
          <div className="text-gray-300">
            <p><strong>{user?.displayName || user?.username}</strong></p>
            {isSuperAdmin && <p className="text-yellow-400 text-sm">Super Admin</p>}
            {isPartner && user?.discordTag && <p className="text-cyan-400 text-sm">Partner: {user.discordTag}</p>}
          </div>
          <Button className="mt-3" variant="danger" onClick={logout}>Logout</Button>
        </div>
      </Card>

      {/* Partner Theme Settings */}
      {isPartner && (
        <Card className="bg-gray-800/50">
          <div className="p-4">
            <h3 className="text-lg font-semibold text-white mb-2">Your Theme</h3>
            <p className="text-sm text-gray-400 mb-4">
              Customize your view of Haven Control Room. These settings only affect your session.
            </p>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm text-gray-300 mb-1">Background</label>
                <input
                  type="color"
                  value={partnerTheme.bg || '#1f2937'}
                  onChange={e => updatePartnerTheme('bg', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Text</label>
                <input
                  type="color"
                  value={partnerTheme.text || '#f3f4f6'}
                  onChange={e => updatePartnerTheme('text', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Card</label>
                <input
                  type="color"
                  value={partnerTheme.card || '#374151'}
                  onChange={e => updatePartnerTheme('card', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Primary</label>
                <input
                  type="color"
                  value={partnerTheme.primary || '#06b6d4'}
                  onChange={e => updatePartnerTheme('primary', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
            </div>

            <Button className="mt-4" onClick={savePartnerTheme} disabled={saving}>
              {saving ? 'Saving...' : 'Save Your Theme'}
            </Button>
          </div>
        </Card>
      )}

      {/* Super Admin: Global Theme Settings */}
      {isSuperAdmin && (
        <Card className="bg-gray-800/50">
          <div className="p-4">
            <h3 className="text-lg font-semibold text-white mb-2">Global Theme</h3>
            <p className="text-sm text-gray-400 mb-4">
              Server-side theme controls the color palette for all users (default).
            </p>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm text-gray-300 mb-1">Background</label>
                <input
                  type="color"
                  value={(settings.theme && settings.theme.bg) || '#1f2937'}
                  onChange={e => updateTheme('bg', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Text</label>
                <input
                  type="color"
                  value={(settings.theme && settings.theme.text) || '#f3f4f6'}
                  onChange={e => updateTheme('text', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Card</label>
                <input
                  type="color"
                  value={(settings.theme && settings.theme.card) || '#374151'}
                  onChange={e => updateTheme('card', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Primary</label>
                <input
                  type="color"
                  value={(settings.theme && settings.theme.primary) || '#06b6d4'}
                  onChange={e => updateTheme('primary', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
            </div>

            <Button className="mt-4" onClick={saveGlobalSettings} disabled={saving}>
              {saving ? 'Saving...' : 'Save Global Theme'}
            </Button>
          </div>
        </Card>
      )}

      {/* Super Admin: Database Management */}
      {isSuperAdmin && (
        <Card className="bg-gray-800/50">
          <div className="p-4">
            <h3 className="text-lg font-semibold text-white mb-2">Database Management</h3>
            <p className="text-sm text-gray-400 mb-4">
              Create backups or restore the database from a backup file.
            </p>

            <div className="flex flex-wrap gap-4">
              <div>
                <Button onClick={doBackup}>Create Backup</Button>
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Upload Database (.db file)</label>
                <input
                  type="file"
                  accept=".db"
                  onChange={onUploadDB}
                  className="text-sm text-gray-400"
                />
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
