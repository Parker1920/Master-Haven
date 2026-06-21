import React, { useState, useContext, lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AuthContext } from '../utils/AuthContext'

const UserManagement = lazy(() => import('./UserManagement'))
const SubAdminManagement = lazy(() => import('./SubAdminManagement'))
const ExtractorUsers = lazy(() => import('./ExtractorUsers'))
const ApiKeys = lazy(() => import('./ApiKeys'))

/**
 * Access Control Hub — Route: /admin/access
 *
 * Tabbed shell consolidating the four account-management pages into one
 * destination. Each tab mounts its corresponding existing page intact, so
 * this is additive — /admin/users, /admin/sub-admins, /admin/extractors,
 * /api-keys all stay live during the migration.
 *
 * Tabs:
 *   - Users          → UserManagement (all tiers, super admin + partner)
 *   - Sub-Admins     → SubAdminManagement (tier 3, feature-flag editor)
 *   - Extractor Users → ExtractorUsers (mod API users)
 *   - API Keys       → ApiKeys (integration tokens, super admin only)
 *
 * Active tab persists via ?tab= URL param for deep linking.
 */
export default function AccessControl() {
  const [searchParams, setSearchParams] = useSearchParams()
  const auth = useContext(AuthContext)
  const { isSuperAdmin, isAdmin } = auth

  // API Keys tab is super-admin only; filter it out for partners
  const TABS = [
    { key: 'users', label: 'Users', desc: 'All user accounts across all tiers', visible: true },
    { key: 'sub-admins', label: 'Sub-Admins', desc: 'Manage sub-admin permissions & access', visible: true },
    { key: 'extractors', label: 'Extractor Users', desc: 'Haven Extractor mod API users', visible: true },
    { key: 'api-keys', label: 'API Keys', desc: 'Integration tokens', visible: isSuperAdmin },
  ].filter(t => t.visible)

  const initialTab = searchParams.get('tab') || 'users'
  const [activeTab, setActiveTab] = useState(
    TABS.some(t => t.key === initialTab) ? initialTab : 'users'
  )

  const handleTab = (key) => {
    setActiveTab(key)
    setSearchParams({ tab: key }, { replace: true })
  }

  if (auth.loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-400">Loading...</div>
      </div>
    )
  }

  if (!isAdmin) return null

  return (
    <div className="-mx-3 sm:-mx-6 -mt-3 sm:-mt-6">
      {/* Hub header — negative margin scoped per breakpoint to match
          container padding on phones (avoids horizontal scroll). */}
      <div
        className="px-6 pt-4 pb-3 border-b"
        style={{
          background: 'linear-gradient(180deg, rgba(255,255,255,0.03), transparent)',
          borderColor: 'rgba(255,255,255,0.08)',
        }}
      >
        <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
          <div>
            <h1 className="text-xl font-bold" style={{ color: 'var(--app-text)' }}>Access Control</h1>
            <p className="text-xs" style={{ color: 'var(--app-text)', opacity: 0.55 }}>
              Unified hub for user accounts, sub-admins, extractor users, and API keys
            </p>
          </div>
        </div>
        {/* Tab strip */}
        <div className="flex items-center gap-1 flex-wrap">
          {TABS.map(t => {
            const active = activeTab === t.key
            return (
              <button
                key={t.key}
                onClick={() => handleTab(t.key)}
                className="px-4 py-2 rounded-t-lg text-sm font-medium transition-colors border-b-2"
                style={{
                  borderColor: active ? 'var(--app-primary)' : 'transparent',
                  color: active ? 'var(--app-primary)' : 'var(--app-text)',
                  background: active ? 'rgba(0, 194, 179, 0.08)' : 'transparent',
                  opacity: active ? 1 : 0.65,
                }}
                title={t.desc}
              >
                {t.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Tab body — each tab mounts an existing page in embedded mode so
          its own page title is skipped (no double chrome). */}
      <div className="p-6">
        <Suspense fallback={
          <div className="flex items-center justify-center min-h-64">
            <div className="text-lg text-gray-400">Loading tab...</div>
          </div>
        }>
          {activeTab === 'users' && <UserManagement embedded />}
          {activeTab === 'sub-admins' && <SubAdminManagement embedded />}
          {activeTab === 'extractors' && <ExtractorUsers embedded />}
          {activeTab === 'api-keys' && isSuperAdmin && <ApiKeys embedded />}
        </Suspense>
      </div>
    </div>
  )
}
