// Authentication context providing session state, login/logout, and role-based access control.
// Polls /api/admin/status on mount to restore sessions across page reloads.
import React, { createContext, useState, useEffect, useMemo, useCallback } from 'react'

// Feature flags for permission checking via canAccess(feature).
// Super admins bypass all checks. Partners/sub-admins must have the feature in enabledFeatures[].
// Features marked "frontend-only" are checked in the UI but not yet enforced by backend middleware
// (tracked TODO for backend enforcement).
export const FEATURES = {
  API_KEYS: 'api_keys',                   // Manage extractor API keys
  BACKUP_RESTORE: 'backup_restore',       // Database backup/restore (frontend-only)
  PARTNER_MANAGEMENT: 'partner_management', // Create/edit partner accounts
  SYSTEM_CREATE: 'system_create',         // Create new systems directly (frontend-only)
  SYSTEM_EDIT: 'system_edit',             // Edit existing systems (frontend-only)
  APPROVALS: 'approvals',                 // Approve/reject pending submissions
  STATS: 'stats',                         // View analytics dashboard
  SETTINGS: 'settings',                   // Access admin settings page
  CSV_IMPORT: 'csv_import',              // Bulk CSV import tool
  BATCH_APPROVALS: 'batch_approvals',     // Approve multiple submissions at once (frontend-only)
  WAR_ROOM: 'war_room'                   // Territorial conflict system
}

export const AuthContext = createContext({
  isAdmin: false,
  isSuperAdmin: false,
  isPartner: false,
  isSubAdmin: false,
  isHavenSubAdmin: false,
  isCorrespondent: false,
  isMember: false,
  isReadOnly: false,
  user: null,
  loading: true,
  login: async () => {},
  memberLogin: async () => {},
  logout: async () => {},
  canAccess: () => false,
  refreshAuth: async () => {}
})

/** Build user object from API response data (shared between checkAuth, login, memberLogin) */
function buildUserFromData(data) {
  return {
    type: data.user_type,
    username: data.username,
    discordTag: data.discord_tag,
    displayName: data.display_name,
    enabledFeatures: data.enabled_features || [],
    accountId: data.account_id,
    profileId: data.profile_id || null,
    tier: data.tier || null,
    defaultCivTag: data.default_civ_tag || null,
    defaultReality: data.default_reality || null,
    defaultGalaxy: data.default_galaxy || null,
    parentDisplayName: data.parent_display_name,
    isHavenSubAdmin: data.is_haven_sub_admin || false
  }
}

/** Provides auth state to the app. Checks session on mount and exposes login/logout/canAccess. */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  async function checkAuth() {
    try {
      const r = await fetch('/api/admin/status', { credentials: 'include' })
      const data = await r.json()
      if (data.logged_in) {
        setUser(buildUserFromData(data))
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

  const isAdmin = !!user && !['member', 'member_readonly'].includes(user?.type)
  const isSuperAdmin = user?.type === 'super_admin'
  const isPartner = user?.type === 'partner'
  const isSubAdmin = user?.type === 'sub_admin'
  const isHavenSubAdmin = user?.isHavenSubAdmin || false
  const isCorrespondent = user?.type === 'correspondent'
  const isMember = user?.type === 'member' || user?.type === 'member_readonly'
  const isReadOnly = user?.type === 'member_readonly'

  /** Check if the current user can access a given FEATURES flag. Super admins always pass. */
  const canAccess = useCallback((feature) => {
    if (!user) return false
    if (isSuperAdmin) return true
    const enabled = user.enabledFeatures || []
    if (enabled.includes('all')) return true
    return enabled.includes(feature)
  }, [user, isSuperAdmin])

  /** Admin/Partner login with username + password */
  const login = useCallback(async (username, password) => {
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
    setUser(buildUserFromData(data))
    return data
  }, [])

  /** Member login - username only (readonly) or username + password (full member) */
  const memberLogin = useCallback(async (username, password) => {
    const body = { username }
    if (password) body.password = password
    const r = await fetch('/api/profile/login', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    if (!r.ok) {
      const data = await r.json().catch(() => ({}))
      throw new Error(data.detail || 'Login failed')
    }
    const data = await r.json()
    setUser(buildUserFromData(data))
    return data
  }, [])

  const logout = useCallback(async () => {
    await fetch('/api/admin/logout', { method: 'POST', credentials: 'include' })
    setUser(null)
  }, [])

  const refreshAuth = useCallback(async () => {
    await checkAuth()
  }, [])

  // Memoize context value to prevent unnecessary re-renders of all consumers
  const contextValue = useMemo(() => ({
    isAdmin,
    isSuperAdmin,
    isPartner,
    isSubAdmin,
    isHavenSubAdmin,
    isCorrespondent,
    isMember,
    isReadOnly,
    user,
    loading,
    login,
    memberLogin,
    logout,
    canAccess,
    refreshAuth
  }), [isAdmin, isSuperAdmin, isPartner, isSubAdmin, isHavenSubAdmin, isCorrespondent, isMember, isReadOnly, user, loading, login, memberLogin, logout, canAccess, refreshAuth])

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  )
}

export default AuthContext
