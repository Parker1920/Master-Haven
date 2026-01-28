import React, { createContext, useState, useEffect } from 'react'

// Feature constants for permission checking
export const FEATURES = {
  API_KEYS: 'api_keys',
  BACKUP_RESTORE: 'backup_restore',
  PARTNER_MANAGEMENT: 'partner_management',
  SYSTEM_CREATE: 'system_create',
  SYSTEM_EDIT: 'system_edit',
  APPROVALS: 'approvals',
  STATS: 'stats',
  SETTINGS: 'settings',
  CSV_IMPORT: 'csv_import',
  BATCH_APPROVALS: 'batch_approvals',
  WAR_ROOM: 'war_room'
}

export const AuthContext = createContext({
  isAdmin: false,
  isSuperAdmin: false,
  isPartner: false,
  isSubAdmin: false,
  isHavenSubAdmin: false,
  isCorrespondent: false,
  user: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
  canAccess: () => false,
  refreshAuth: async () => {}
})

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  async function checkAuth() {
    try {
      const r = await fetch('/api/admin/status', { credentials: 'include' })
      const data = await r.json()
      if (data.logged_in) {
        setUser({
          type: data.user_type,
          username: data.username,
          discordTag: data.discord_tag,
          displayName: data.display_name,
          enabledFeatures: data.enabled_features || [],
          accountId: data.account_id,
          parentDisplayName: data.parent_display_name,  // For sub-admins
          isHavenSubAdmin: data.is_haven_sub_admin || false  // True if Haven sub-admin (no parent partner)
        })
      } else {
        setUser(null)
      }
    } catch (err) {
      console.error('Auth check failed:', err)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    checkAuth()
  }, [])

  const isAdmin = !!user
  const isSuperAdmin = user?.type === 'super_admin'
  const isPartner = user?.type === 'partner'
  const isSubAdmin = user?.type === 'sub_admin'
  const isHavenSubAdmin = user?.isHavenSubAdmin || false
  const isCorrespondent = user?.type === 'correspondent'

  function canAccess(feature) {
    if (!user) return false
    if (isSuperAdmin) return true
    const enabled = user.enabledFeatures || []
    if (enabled.includes('all')) return true
    return enabled.includes(feature)
  }

  async function login(username, password) {
    const r = await fetch('/api/admin/login', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    })
    if (!r.ok) {
      const data = await r.json().catch(() => ({}))
      throw new Error(data.detail || 'Login failed')
    }
    const data = await r.json()
    setUser({
      type: data.user_type,
      username: data.username,
      discordTag: data.discord_tag,
      displayName: data.display_name,
      enabledFeatures: data.enabled_features || [],
      accountId: data.account_id,
      parentDisplayName: data.parent_display_name,
      isHavenSubAdmin: data.is_haven_sub_admin || false
    })
    return data
  }

  async function logout() {
    await fetch('/api/admin/logout', { method: 'POST', credentials: 'include' })
    setUser(null)
  }

  async function refreshAuth() {
    await checkAuth()
  }

  return (
    <AuthContext.Provider value={{
      isAdmin,
      isSuperAdmin,
      isPartner,
      isSubAdmin,
      isHavenSubAdmin,
      isCorrespondent,
      user,
      loading,
      login,
      logout,
      canAccess,
      refreshAuth
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export default AuthContext
