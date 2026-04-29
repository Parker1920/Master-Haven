import React, { useEffect, useContext, lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'

// Eagerly load components needed for initial render (Dashboard is the landing page)
import Dashboard from './pages/Dashboard'
import Navbar from './components/Navbar'
import { AuthProvider, AuthContext, FEATURES } from './utils/AuthContext'

// Poster routes are chrome-less (no navbar, no container) so they're rendered
// outside the main app shell. Lazy-loaded.
const VoyagerPoster = lazy(() => import('./posters/VoyagerPoster'))
const GalaxyAtlas = lazy(() => import('./posters/GalaxyAtlas'))
const PosterRoute = lazy(() => import('./pages/PosterRoute'))

// Lazy load all other pages - they're only loaded when the user navigates to them
// This reduces initial bundle size from 2.3MB to ~500KB for first paint
const Systems = lazy(() => import('./pages/Systems'))
const SystemDetail = lazy(() => import('./pages/SystemDetail'))
const RegionDetail = lazy(() => import('./pages/RegionDetail'))
const Wizard = lazy(() => import('./pages/Wizard'))
const Settings = lazy(() => import('./pages/Settings'))
const Discoveries = lazy(() => import('./pages/Discoveries'))
const DiscoveryType = lazy(() => import('./pages/DiscoveryType'))
const DBStats = lazy(() => import('./pages/DBStats'))
const PendingApprovals = lazy(() => import('./pages/PendingApprovals'))
const ApiKeys = lazy(() => import('./pages/ApiKeys'))
const PartnerManagement = lazy(() => import('./pages/PartnerManagement'))
const SubAdminManagement = lazy(() => import('./pages/SubAdminManagement'))
const ApprovalAudit = lazy(() => import('./pages/ApprovalAudit'))
const Analytics = lazy(() => import('./pages/Analytics'))
const PartnerAnalytics = lazy(() => import('./pages/PartnerAnalytics'))
const Events = lazy(() => import('./pages/Events'))
const CsvImport = lazy(() => import('./pages/CsvImport'))
const DataRestrictions = lazy(() => import('./pages/DataRestrictions'))
const ExtractorUsers = lazy(() => import('./pages/ExtractorUsers'))
const CommunityStats = lazy(() => import('./pages/CommunityStats'))
const CommunityDetail = lazy(() => import('./pages/CommunityDetail'))
const Profile = lazy(() => import('./pages/Profile'))
const UserManagement = lazy(() => import('./pages/UserManagement'))
const Changelog = lazy(() => import('./pages/Changelog'))

// Heavy components with Three.js - load separately for better code splitting
const WarRoom = lazy(() => import('./pages/WarRoom'))
const WarRoomAdmin = lazy(() => import('./pages/WarRoomAdmin'))

// Loading fallback component
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-64">
      <div className="text-lg text-gray-400">Loading...</div>
    </div>
  )
}

/** Route guard: requires any logged-in admin role (super admin, partner, or sub-admin). Redirects unauthenticated users to /. */
function RequireAdmin({ children }) {
  const auth = useContext(AuthContext)
  if (auth.loading) return <div className="flex items-center justify-center min-h-64"><div className="text-lg text-gray-400">Loading...</div></div>
  if (!auth.isAdmin) return <Navigate to='/' replace />
  return children
}

/** Route guard: requires super admin role specifically. Partners and sub-admins are redirected. */
function RequireSuperAdmin({ children }) {
  const auth = useContext(AuthContext)
  if (auth.loading) return <div className="flex items-center justify-center min-h-64"><div className="text-lg text-gray-400">Loading...</div></div>
  if (!auth.isSuperAdmin) return <Navigate to='/' replace />
  return children
}

/** Route guard: requires admin with a specific FEATURES flag (e.g., APPROVALS, SETTINGS, CSV_IMPORT). Checks both auth and feature access. */
function RequireFeature({ feature, children }) {
  const auth = useContext(AuthContext)
  if (auth.loading) return <div className="flex items-center justify-center min-h-64"><div className="text-lg text-gray-400">Loading...</div></div>
  if (!auth.isAdmin) return <Navigate to='/' replace />
  if (!auth.canAccess(feature)) return <Navigate to='/' replace />
  return children
}

/** Route guard: War Room access - allows war correspondents (non-admin role), super admin, or any admin with WAR_ROOM feature enabled. */
function RequireWarRoomAccess({ children }) {
  const auth = useContext(AuthContext)
  if (auth.loading) return <div className="flex items-center justify-center min-h-64"><div className="text-lg text-gray-400">Loading...</div></div>
  // Allow correspondents without normal admin check
  if (auth.user?.type === 'correspondent') return children
  // Allow super admin
  if (auth.isSuperAdmin) return children
  // Allow enrolled partners/sub-admins with war_room feature
  if (auth.isAdmin && auth.canAccess(FEATURES.WAR_ROOM)) return children
  return <Navigate to='/' replace />
}

// Routes that render WITHOUT the navbar/container chrome — chrome-less poster
// surfaces meant to be screenshotted or shared as images.
const POSTER_ROUTE_PREFIXES = ['/voyager/', '/atlas/', '/poster/']

function isPosterRoute(pathname) {
  return POSTER_ROUTE_PREFIXES.some(prefix => pathname.startsWith(prefix))
}

function AppShell() {
  const location = useLocation()
  const chromeless = isPosterRoute(location.pathname)

  if (chromeless) {
    // Poster mode: no navbar, no container, just the poster filling viewport.
    // /poster/:type/:key is the registry-driven route opened by Playwright.
    // /voyager/:user and /atlas/:galaxy are friendly aliases for direct sharing.
    return (
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/voyager/:username" element={<VoyagerPoster />} />
          <Route path="/atlas/:galaxy" element={<GalaxyAtlas />} />
          <Route path="/poster/:type/:key" element={<PosterRoute />} />
        </Routes>
      </Suspense>
    )
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--app-bg, #f8fafc)', color: 'var(--app-text, #111827)' }}>
      <Navbar />
      <main className="container mx-auto p-6">
        <Suspense fallback={<PageLoader />}>
          <Routes>
              {/* Public routes */}
              <Route path="/" element={<Dashboard />} />
              <Route path="/systems" element={<Systems />} />
              <Route path="/systems/:id" element={<SystemDetail />} />
              <Route path="/regions/:rx/:ry/:rz" element={<RegionDetail />} />
              <Route path="/create" element={<Wizard />} />
              <Route path="/wizard" element={<Wizard />} />
              <Route path="/discoveries" element={<Discoveries />} />
              <Route path="/discoveries/:type" element={<DiscoveryType />} />
              <Route path="/db_stats" element={<DBStats />} />
              <Route path="/community-stats" element={<CommunityStats />} />
              <Route path="/community-stats/:tag" element={<CommunityDetail />} />
              <Route path="/changelog" element={<Changelog />} />
              <Route path="/profile" element={<Profile />} />

              {/* Super admin only routes */}
              <Route path="/api-keys" element={<RequireSuperAdmin><ApiKeys /></RequireSuperAdmin>} />
              <Route path="/admin/users" element={<RequireAdmin><UserManagement /></RequireAdmin>} />
              <Route path="/admin/partners" element={<RequireSuperAdmin><PartnerManagement /></RequireSuperAdmin>} />
              <Route path="/admin/partners/:partnerId/sub-admins" element={<RequireSuperAdmin><SubAdminManagement /></RequireSuperAdmin>} />
              <Route path="/admin/audit" element={<RequireSuperAdmin><ApprovalAudit /></RequireSuperAdmin>} />

              {/* Extractor user management (admin or partner) */}
              <Route path="/admin/extractors" element={<RequireAdmin><ExtractorUsers /></RequireAdmin>} />

              {/* Analytics (admin or partner) */}
              <Route path="/analytics" element={<RequireAdmin><Analytics /></RequireAdmin>} />
              <Route path="/partner-analytics" element={<RequireAdmin><PartnerAnalytics /></RequireAdmin>} />
              <Route path="/events" element={<RequireAdmin><Events /></RequireAdmin>} />

              {/* Partners can manage their own sub-admins */}
              <Route path="/admin/sub-admins" element={<RequireAdmin><SubAdminManagement /></RequireAdmin>} />

              {/* Admin routes (super admin or partner with access) */}
              <Route path="/settings" element={<RequireFeature feature={FEATURES.SETTINGS}><Settings /></RequireFeature>} />
              <Route path="/pending-approvals" element={<RequireFeature feature={FEATURES.APPROVALS}><PendingApprovals /></RequireFeature>} />
              <Route path="/csv-import" element={<RequireFeature feature={FEATURES.CSV_IMPORT}><CsvImport /></RequireFeature>} />
              <Route path="/data-restrictions" element={<RequireAdmin><DataRestrictions /></RequireAdmin>} />

              {/* War Room */}
              <Route path="/war-room" element={<RequireWarRoomAccess><WarRoom /></RequireWarRoomAccess>} />
              <Route path="/war-room/admin" element={<RequireSuperAdmin><WarRoomAdmin /></RequireSuperAdmin>} />
            </Routes>
          </Suspense>
        </main>
      </div>
  )
}

export default function App() {
  useEffect(() => {
    // Fetch server settings and apply server-side theme (if present)
    fetch('/api/settings')
      .then(res => res.json())
      .then(settings => {
        if (!settings) return
        const theme = settings.theme || {}
        if (theme.bg) document.documentElement.style.setProperty('--app-bg', theme.bg)
        if (theme.text) document.documentElement.style.setProperty('--app-text', theme.text)
        if (theme.card) document.documentElement.style.setProperty('--app-card', theme.card)
        if (theme.primary) document.documentElement.style.setProperty('--app-primary', theme.primary)
      })
      .catch(() => {})
  }, [])

  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  )
}
