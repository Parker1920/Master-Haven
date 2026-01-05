import React, { useEffect, useContext } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Systems from './pages/Systems'
import SystemDetail from './pages/SystemDetail'
import RegionDetail from './pages/RegionDetail'
import Wizard from './pages/Wizard'
import RTAI from './pages/RTAI'
import Settings from './pages/Settings'
import Discoveries from './pages/Discoveries'
import Tests from './pages/Tests'
import DBStats from './pages/DBStats'
import PendingApprovals from './pages/PendingApprovals'
import ApiKeys from './pages/ApiKeys'
import PartnerManagement from './pages/PartnerManagement'
import SubAdminManagement from './pages/SubAdminManagement'
import ApprovalAudit from './pages/ApprovalAudit'
import CsvImport from './pages/CsvImport'
import DataRestrictions from './pages/DataRestrictions'
import Navbar from './components/Navbar'
import InactivityOverlay from './components/InactivityOverlay'
import { AuthProvider, AuthContext, FEATURES } from './utils/AuthContext'

// Requires any logged-in admin (super admin or partner)
function RequireAdmin({ children }) {
  const auth = useContext(AuthContext)
  if (auth.loading) return <div className="flex items-center justify-center min-h-64"><div className="text-lg text-gray-400">Loading...</div></div>
  if (!auth.isAdmin) return <Navigate to='/' replace />
  return children
}

// Requires super admin specifically
function RequireSuperAdmin({ children }) {
  const auth = useContext(AuthContext)
  if (auth.loading) return <div className="flex items-center justify-center min-h-64"><div className="text-lg text-gray-400">Loading...</div></div>
  if (!auth.isSuperAdmin) return <Navigate to='/' replace />
  return children
}

// Requires admin with specific feature access
function RequireFeature({ feature, children }) {
  const auth = useContext(AuthContext)
  if (auth.loading) return <div className="flex items-center justify-center min-h-64"><div className="text-lg text-gray-400">Loading...</div></div>
  if (!auth.isAdmin) return <Navigate to='/' replace />
  if (!auth.canAccess(feature)) return <Navigate to='/' replace />
  return children
}

export default function App() {
  useEffect(() => {
    // Fetch server settings and apply server-side theme (if present)
    fetch('/api/settings')
      .then(res => res.json())
      .then(settings => {
        if (!settings) return
        const theme = settings.theme || {}
        // Apply background and text color if provided
        if (theme.bg) document.documentElement.style.setProperty('--app-bg', theme.bg)
        if (theme.text) document.documentElement.style.setProperty('--app-text', theme.text)
        if (theme.card) document.documentElement.style.setProperty('--app-card', theme.card)
        if (theme.primary) document.documentElement.style.setProperty('--app-primary', theme.primary)
      })
      .catch(() => {})
  }, [])

  return (
    <AuthProvider>
      <div className="min-h-screen" style={{ backgroundColor: 'var(--app-bg, #f8fafc)', color: 'var(--app-text, #111827)' }}>
        <Navbar />
        <main className="container mx-auto p-6">
          <Routes>
            {/* Public routes */}
            <Route path="/" element={<Dashboard />} />
            <Route path="/systems" element={<Systems />} />
            <Route path="/systems/:id" element={<SystemDetail />} />
            <Route path="/regions/:rx/:ry/:rz" element={<RegionDetail />} />
            <Route path="/create" element={<Wizard />} />
            <Route path="/wizard" element={<Wizard />} />
            <Route path="/discoveries" element={<Discoveries />} />
            <Route path="/db_stats" element={<DBStats />} />

            {/* Super admin only routes */}
            <Route path="/rtai" element={<RequireSuperAdmin><RTAI /></RequireSuperAdmin>} />
            <Route path="/api-keys" element={<RequireSuperAdmin><ApiKeys /></RequireSuperAdmin>} />
            <Route path="/tests" element={<RequireSuperAdmin><Tests /></RequireSuperAdmin>} />
            <Route path="/admin/partners" element={<RequireSuperAdmin><PartnerManagement /></RequireSuperAdmin>} />
            <Route path="/admin/partners/:partnerId/sub-admins" element={<RequireSuperAdmin><SubAdminManagement /></RequireSuperAdmin>} />
            <Route path="/admin/audit" element={<RequireSuperAdmin><ApprovalAudit /></RequireSuperAdmin>} />

            {/* Partners can manage their own sub-admins */}
            <Route path="/admin/sub-admins" element={<RequireAdmin><SubAdminManagement /></RequireAdmin>} />

            {/* Admin routes (super admin or partner with access) */}
            <Route path="/settings" element={<RequireFeature feature={FEATURES.SETTINGS}><Settings /></RequireFeature>} />
            <Route path="/pending-approvals" element={<RequireFeature feature={FEATURES.APPROVALS}><PendingApprovals /></RequireFeature>} />
            <Route path="/csv-import" element={<RequireFeature feature={FEATURES.CSV_IMPORT}><CsvImport /></RequireFeature>} />
            <Route path="/data-restrictions" element={<RequireAdmin><DataRestrictions /></RequireAdmin>} />
          </Routes>
        </main>
        <InactivityOverlay />
      </div>
    </AuthProvider>
  )
}
