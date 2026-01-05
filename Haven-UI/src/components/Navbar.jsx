import React, { useContext, useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { SparklesIcon, Bars3Icon, XMarkIcon } from '@heroicons/react/24/solid'
import AdminLoginModal from './AdminLoginModal'
import { AuthContext, FEATURES } from '../utils/AuthContext'
import { useInactivityAware } from '../hooks/useInactivityAware'
import axios from 'axios'

export default function Navbar() {
  const auth = useContext(AuthContext)
  const [showLogin, setShowLogin] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)
  const intervalRef = useRef(null)
  const { isDisconnected, registerConnection, unregisterConnection } = useInactivityAware()

  const { isAdmin, isSuperAdmin, isPartner, isSubAdmin, user, canAccess } = auth

  // Fetch pending count every 30 seconds if admin
  useEffect(() => {
    if (!isAdmin) {
      setPendingCount(0)
      return
    }

    // Don't start polling if disconnected due to inactivity
    if (isDisconnected) return

    const fetchCount = async () => {
      try {
        const response = await axios.get('/api/pending_systems/count')
        setPendingCount(response.data.count || 0)
      } catch (err) {
        // Silent fail - don't show errors in navbar
      }
    }

    const startPolling = () => {
      intervalRef.current = setInterval(fetchCount, 30000) // Update every 30 seconds
    }

    fetchCount()
    startPolling()

    // Register with inactivity system
    registerConnection('navbar-pending-polling', {
      cleanup: () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
      },
      restore: () => {
        fetchCount()
        startPolling()
      }
    })

    return () => {
      unregisterConnection('navbar-pending-polling')
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [isAdmin, isDisconnected, registerConnection, unregisterConnection])

  const closeMenu = () => setMobileMenuOpen(false)

  return (
    <header className="p-4 shadow" style={{ background: 'linear-gradient(90deg, var(--app-card), rgba(255,255,255,0.02))' }}>
      <div className="container mx-auto" role="navigation" aria-label="Main navigation">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div style={{ background: 'linear-gradient(135deg, var(--app-primary), var(--app-accent-2))' }} className="p-2 rounded-lg">
              <SparklesIcon className="w-7 h-7 text-white" />
            </div>
            <div>
              <div className="text-xl font-semibold" style={{ color: 'var(--app-text)' }}>Haven Control Room</div>
              <div className="text-sm muted" style={{ color: 'var(--app-accent-3)' }}>
                {isAdmin ? (
                  <span>
                    {user?.displayName || user?.username}
                    {isPartner && user?.discordTag && <span className="ml-1 text-cyan-400">({user.discordTag})</span>}
                    {isSuperAdmin && <span className="ml-1 text-yellow-400">(Super Admin)</span>}
                    {isSubAdmin && <span className="ml-1 text-amber-400">(Sub-Admin)</span>}
                  </span>
                ) : 'Web'}
              </div>
            </div>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden lg:flex space-x-2" aria-label="Primary">
            <Link className="px-3 py-1 hover:underline" to="/">Dashboard</Link>
            <Link className="px-3 py-1 hover:underline" to="/systems">Systems</Link>
            <a className="px-3 py-1 hover:underline" href="/map/latest">Map</a>
            <Link className="px-3 py-1 hover:underline" to="/create">Create</Link>
            {isSuperAdmin && <Link className="px-3 py-1 hover:underline" to="/rtai">RT-AI</Link>}
            {canAccess(FEATURES.SETTINGS) && <Link className="px-3 py-1 hover:underline" to="/settings">Settings</Link>}
            <Link className="px-3 py-1 hover:underline" to="/discoveries">Discoveries</Link>
            {isSuperAdmin && <Link className="px-3 py-1 hover:underline" to="/tests">Tests</Link>}
            <Link className="px-3 py-1 hover:underline" to="/db_stats">DB Stats</Link>
            {canAccess(FEATURES.APPROVALS) && (
              <Link className="px-3 py-1 hover:underline relative" to="/pending-approvals">
                Approvals
                {pendingCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                    {pendingCount > 9 ? '9+' : pendingCount}
                  </span>
                )}
              </Link>
            )}
            {isSuperAdmin && <Link className="px-3 py-1 hover:underline" to="/api-keys">API Keys</Link>}
            {isSuperAdmin && <Link className="px-3 py-1 hover:underline" to="/admin/partners">Partners</Link>}
            {isSuperAdmin && <Link className="px-3 py-1 hover:underline" to="/admin/audit">Audit Log</Link>}
            {(isSuperAdmin || isPartner) && <Link className="px-3 py-1 hover:underline" to="/admin/sub-admins">Sub-Admins</Link>}
            {canAccess(FEATURES.CSV_IMPORT) && <Link className="px-3 py-1 hover:underline" to="/csv-import">CSV Import</Link>}
            {isAdmin && <Link className="px-3 py-1 hover:underline" to="/data-restrictions">Restrictions</Link>}
            {!isAdmin ? (
              <button className="px-3 py-1 bg-blue-500 text-white rounded" onClick={() => setShowLogin(true)}>Login</button>
            ) : (
              <button className="px-3 py-1 bg-red-500 text-white rounded" onClick={() => auth.logout()}>Logout</button>
            )}
          </nav>

          {/* Mobile Menu Button */}
          <button
            className="lg:hidden p-2 text-white"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <XMarkIcon className="w-6 h-6" /> : <Bars3Icon className="w-6 h-6" />}
          </button>
        </div>

        {/* Mobile Navigation */}
        {mobileMenuOpen && (
          <nav className="lg:hidden mt-4 flex flex-col space-y-2 pb-4" aria-label="Mobile">
            <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/" onClick={closeMenu}>Dashboard</Link>
            <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/systems" onClick={closeMenu}>Systems</Link>
            <a className="px-3 py-2 hover:bg-gray-700 rounded" href="/map/latest" onClick={closeMenu}>Map</a>
            <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/create" onClick={closeMenu}>Create</Link>
            {isSuperAdmin && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/rtai" onClick={closeMenu}>RT-AI</Link>}
            {canAccess(FEATURES.SETTINGS) && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/settings" onClick={closeMenu}>Settings</Link>}
            <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/discoveries" onClick={closeMenu}>Discoveries</Link>
            {isSuperAdmin && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/tests" onClick={closeMenu}>Tests</Link>}
            <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/db_stats" onClick={closeMenu}>DB Stats</Link>
            {canAccess(FEATURES.APPROVALS) && (
              <Link className="px-3 py-2 hover:bg-gray-700 rounded flex justify-between items-center" to="/pending-approvals" onClick={closeMenu}>
                <span>Approvals</span>
                {pendingCount > 0 && (
                  <span className="bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                    {pendingCount > 9 ? '9+' : pendingCount}
                  </span>
                )}
              </Link>
            )}
            {isSuperAdmin && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/api-keys" onClick={closeMenu}>API Keys</Link>}
            {isSuperAdmin && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/admin/partners" onClick={closeMenu}>Partners</Link>}
            {isSuperAdmin && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/admin/audit" onClick={closeMenu}>Audit Log</Link>}
            {(isSuperAdmin || isPartner) && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/admin/sub-admins" onClick={closeMenu}>Sub-Admins</Link>}
            {canAccess(FEATURES.CSV_IMPORT) && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/csv-import" onClick={closeMenu}>CSV Import</Link>}
            {isAdmin && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/data-restrictions" onClick={closeMenu}>Data Restrictions</Link>}
            <div className="pt-2 border-t border-gray-700">
              {isAdmin && (
                <div className="px-3 py-2 text-sm text-gray-400 mb-2">
                  Logged in as: {user?.displayName || user?.username}
                  {isPartner && user?.discordTag && <span className="text-cyan-400"> ({user.discordTag})</span>}
                  {isSubAdmin && <span className="text-amber-400"> (Sub-Admin)</span>}
                </div>
              )}
              {!isAdmin ? (
                <button className="w-full px-3 py-2 bg-blue-500 text-white rounded" onClick={() => { setShowLogin(true); closeMenu(); }}>Login</button>
              ) : (
                <button className="w-full px-3 py-2 bg-red-500 text-white rounded" onClick={() => { auth.logout(); closeMenu(); }}>Logout</button>
              )}
            </div>
          </nav>
        )}
      </div>
      <AdminLoginModal open={showLogin} onClose={() => setShowLogin(false)} />
    </header>
  )
}
