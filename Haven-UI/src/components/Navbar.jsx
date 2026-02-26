import React, { useContext, useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { SparklesIcon, Bars3Icon, XMarkIcon, ChevronDownIcon } from '@heroicons/react/24/solid'
import AdminLoginModal from './AdminLoginModal'
import { AuthContext, FEATURES } from '../utils/AuthContext'
import { useInactivityAware } from '../hooks/useInactivityAware'
import axios from 'axios'

export default function Navbar() {
  const auth = useContext(AuthContext)
  const [showLogin, setShowLogin] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)
  const [activeConflictCount, setActiveConflictCount] = useState(0)
  const [openDropdown, setOpenDropdown] = useState(null)
  const intervalRef = useRef(null)
  const warIntervalRef = useRef(null)
  const dropdownRef = useRef(null)
  const { isDisconnected, registerConnection, unregisterConnection } = useInactivityAware()

  const { isAdmin, isSuperAdmin, isPartner, isSubAdmin, isCorrespondent, user, canAccess } = auth

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpenDropdown(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Fetch pending count every 60 seconds if admin
  useEffect(() => {
    if (!isAdmin) {
      setPendingCount(0)
      return
    }

    if (isDisconnected) return

    const fetchCount = async () => {
      try {
        const response = await axios.get('/api/pending_systems/count')
        setPendingCount(response.data.count || 0)
      } catch (err) {
        // Silent fail
      }
    }

    const startPolling = () => {
      intervalRef.current = setInterval(fetchCount, 60000)
    }

    fetchCount()
    startPolling()

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

  // Fetch active conflict count for War Room badge
  useEffect(() => {
    const hasWarRoomAccess = canAccess(FEATURES.WAR_ROOM) || isCorrespondent

    if (!hasWarRoomAccess) {
      setActiveConflictCount(0)
      return
    }

    if (isDisconnected) return

    const fetchConflictCount = async () => {
      try {
        const response = await axios.get('/api/warroom/conflicts/active')
        setActiveConflictCount(response.data?.length || 0)
      } catch (err) {
        // Silent fail
      }
    }

    fetchConflictCount()
    warIntervalRef.current = setInterval(fetchConflictCount, 60000)

    return () => {
      if (warIntervalRef.current) {
        clearInterval(warIntervalRef.current)
      }
    }
  }, [canAccess, isCorrespondent, isDisconnected])

  const closeMenu = () => setMobileMenuOpen(false)

  const toggleDropdown = (name) => {
    setOpenDropdown(prev => prev === name ? null : name)
  }

  const closeDropdown = () => setOpenDropdown(null)

  // Shared link styles
  const navLink = 'px-3 py-1 hover:underline whitespace-nowrap'
  const dropdownTrigger = 'px-3 py-1 hover:underline whitespace-nowrap flex items-center gap-1 cursor-pointer select-none'
  const dropdownPanel = 'absolute top-full left-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1 min-w-[180px] z-50'
  const dropdownItem = 'block w-full text-left px-4 py-2 hover:bg-gray-700 whitespace-nowrap'

  // Visibility helpers
  const showAnalyticsDropdown = isSuperAdmin || (isAdmin && !isCorrespondent)
  const showAdminDropdown = canAccess(FEATURES.APPROVALS) || canAccess(FEATURES.SETTINGS) || (isAdmin && !isCorrespondent)
  const showSuperAdminDropdown = isSuperAdmin

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
                    {isCorrespondent && <span className="ml-1 text-red-400">(War Correspondent)</span>}
                  </span>
                ) : 'Web'}
              </div>
            </div>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden lg:flex items-center space-x-1" aria-label="Primary" ref={dropdownRef}>
            {/* Public links */}
            <Link className={navLink} to="/">Dashboard</Link>
            <Link className={navLink} to="/systems">Systems</Link>
            <a className={navLink} href="/map/latest">Map</a>
            <Link className={navLink} to="/create">Create</Link>
            <Link className={navLink} to="/discoveries">Discoveries</Link>
            {isAdmin && !isCorrespondent && <Link className={navLink} to="/events">Events</Link>}
            {(canAccess(FEATURES.WAR_ROOM) || isCorrespondent) && (
              <Link className={`${navLink} text-red-400 font-bold relative`} to="/war-room">
                War Room
                {activeConflictCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-red-600 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center animate-pulse">
                    {activeConflictCount > 9 ? '9+' : activeConflictCount}
                  </span>
                )}
              </Link>
            )}

            {/* Analytics dropdown */}
            {showAnalyticsDropdown && (
              <div className="relative">
                <button className={dropdownTrigger} onClick={() => toggleDropdown('analytics')}>
                  Analytics <ChevronDownIcon className={`w-3 h-3 transition-transform ${openDropdown === 'analytics' ? 'rotate-180' : ''}`} />
                </button>
                {openDropdown === 'analytics' && (
                  <div className={dropdownPanel}>
                    {isSuperAdmin && <Link className={dropdownItem} to="/analytics" onClick={closeDropdown}>Analytics</Link>}
                    {isAdmin && !isCorrespondent && <Link className={dropdownItem} to="/partner-analytics" onClick={closeDropdown}>Partner Analytics</Link>}
                    <Link className={dropdownItem} to="/db_stats" onClick={closeDropdown}>DB Stats</Link>
                  </div>
                )}
              </div>
            )}
            {/* DB Stats visible to public when no analytics dropdown */}
            {!showAnalyticsDropdown && <Link className={navLink} to="/db_stats">DB Stats</Link>}

            {/* Admin dropdown */}
            {showAdminDropdown && (
              <div className="relative">
                <button className={`${dropdownTrigger} relative`} onClick={() => toggleDropdown('admin')}>
                  Admin
                  {pendingCount > 0 && canAccess(FEATURES.APPROVALS) && (
                    <span className="bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                      {pendingCount > 9 ? '9+' : pendingCount}
                    </span>
                  )}
                  <ChevronDownIcon className={`w-3 h-3 transition-transform ${openDropdown === 'admin' ? 'rotate-180' : ''}`} />
                </button>
                {openDropdown === 'admin' && (
                  <div className={dropdownPanel}>
                    {canAccess(FEATURES.APPROVALS) && (
                      <Link className={`${dropdownItem} flex justify-between items-center`} to="/pending-approvals" onClick={closeDropdown}>
                        <span>Approvals</span>
                        {pendingCount > 0 && (
                          <span className="bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center ml-2">
                            {pendingCount > 9 ? '9+' : pendingCount}
                          </span>
                        )}
                      </Link>
                    )}
                    {canAccess(FEATURES.SETTINGS) && <Link className={dropdownItem} to="/settings" onClick={closeDropdown}>Settings</Link>}
                    {isAdmin && !isCorrespondent && <Link className={dropdownItem} to="/admin/extractors" onClick={closeDropdown}>Extractors</Link>}
                    {(isSuperAdmin || isPartner) && <Link className={dropdownItem} to="/admin/sub-admins" onClick={closeDropdown}>Sub-Admins</Link>}
                    {canAccess(FEATURES.CSV_IMPORT) && <Link className={dropdownItem} to="/csv-import" onClick={closeDropdown}>CSV Import</Link>}
                    {isAdmin && !isCorrespondent && <Link className={dropdownItem} to="/data-restrictions" onClick={closeDropdown}>Data Restrictions</Link>}
                  </div>
                )}
              </div>
            )}

            {/* Super Admin dropdown */}
            {showSuperAdminDropdown && (
              <div className="relative">
                <button className={dropdownTrigger} onClick={() => toggleDropdown('superadmin')}>
                  Super Admin <ChevronDownIcon className={`w-3 h-3 transition-transform ${openDropdown === 'superadmin' ? 'rotate-180' : ''}`} />
                </button>
                {openDropdown === 'superadmin' && (
                  <div className={dropdownPanel}>
                    <Link className={dropdownItem} to="/api-keys" onClick={closeDropdown}>API Keys</Link>
                    <Link className={dropdownItem} to="/admin/partners" onClick={closeDropdown}>Partners</Link>
                    <Link className={dropdownItem} to="/admin/audit" onClick={closeDropdown}>Audit Log</Link>
                  </div>
                )}
              </div>
            )}

            {/* Auth button */}
            {!isAdmin ? (
              <button className="px-3 py-1 bg-blue-500 text-white rounded whitespace-nowrap" onClick={() => setShowLogin(true)}>Login</button>
            ) : (
              <button className="px-3 py-1 bg-red-500 text-white rounded whitespace-nowrap" onClick={() => auth.logout()}>Logout</button>
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
          <nav className="lg:hidden mt-4 flex flex-col space-y-1 pb-4" aria-label="Mobile">
            {/* Public */}
            <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/" onClick={closeMenu}>Dashboard</Link>
            <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/systems" onClick={closeMenu}>Systems</Link>
            <a className="px-3 py-2 hover:bg-gray-700 rounded" href="/map/latest" onClick={closeMenu}>Map</a>
            <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/create" onClick={closeMenu}>Create</Link>
            <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/discoveries" onClick={closeMenu}>Discoveries</Link>
            {isAdmin && !isCorrespondent && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/events" onClick={closeMenu}>Events</Link>}
            {(canAccess(FEATURES.WAR_ROOM) || isCorrespondent) && (
              <Link className="px-3 py-2 hover:bg-gray-700 rounded text-red-400 font-bold flex justify-between items-center" to="/war-room" onClick={closeMenu}>
                <span>War Room</span>
                {activeConflictCount > 0 && (
                  <span className="bg-red-600 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center animate-pulse">
                    {activeConflictCount > 9 ? '9+' : activeConflictCount}
                  </span>
                )}
              </Link>
            )}

            {/* Analytics section */}
            {showAnalyticsDropdown && (
              <>
                <div className="pt-2 mt-1 border-t border-gray-700">
                  <div className="px-3 py-1 text-xs text-gray-500 uppercase tracking-wider">Analytics</div>
                </div>
                {isSuperAdmin && <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5" to="/analytics" onClick={closeMenu}>Analytics</Link>}
                {isAdmin && !isCorrespondent && <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5" to="/partner-analytics" onClick={closeMenu}>Partner Analytics</Link>}
                <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5" to="/db_stats" onClick={closeMenu}>DB Stats</Link>
              </>
            )}
            {!showAnalyticsDropdown && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/db_stats" onClick={closeMenu}>DB Stats</Link>}

            {/* Admin section */}
            {showAdminDropdown && (
              <>
                <div className="pt-2 mt-1 border-t border-gray-700">
                  <div className="px-3 py-1 text-xs text-gray-500 uppercase tracking-wider">Admin</div>
                </div>
                {canAccess(FEATURES.APPROVALS) && (
                  <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5 flex justify-between items-center" to="/pending-approvals" onClick={closeMenu}>
                    <span>Approvals</span>
                    {pendingCount > 0 && (
                      <span className="bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                        {pendingCount > 9 ? '9+' : pendingCount}
                      </span>
                    )}
                  </Link>
                )}
                {canAccess(FEATURES.SETTINGS) && <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5" to="/settings" onClick={closeMenu}>Settings</Link>}
                {isAdmin && !isCorrespondent && <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5" to="/admin/extractors" onClick={closeMenu}>Extractors</Link>}
                {(isSuperAdmin || isPartner) && <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5" to="/admin/sub-admins" onClick={closeMenu}>Sub-Admins</Link>}
                {canAccess(FEATURES.CSV_IMPORT) && <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5" to="/csv-import" onClick={closeMenu}>CSV Import</Link>}
                {isAdmin && !isCorrespondent && <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5" to="/data-restrictions" onClick={closeMenu}>Data Restrictions</Link>}
              </>
            )}

            {/* Super Admin section */}
            {showSuperAdminDropdown && (
              <>
                <div className="pt-2 mt-1 border-t border-gray-700">
                  <div className="px-3 py-1 text-xs text-gray-500 uppercase tracking-wider">Super Admin</div>
                </div>
                <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5" to="/api-keys" onClick={closeMenu}>API Keys</Link>
                <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5" to="/admin/partners" onClick={closeMenu}>Partners</Link>
                <Link className="px-3 py-2 hover:bg-gray-700 rounded pl-5" to="/admin/audit" onClick={closeMenu}>Audit Log</Link>
              </>
            )}

            {/* Auth */}
            <div className="pt-2 border-t border-gray-700">
              {isAdmin && (
                <div className="px-3 py-2 text-sm text-gray-400 mb-2">
                  Logged in as: {user?.displayName || user?.username}
                  {isPartner && user?.discordTag && <span className="text-cyan-400"> ({user.discordTag})</span>}
                  {isSubAdmin && <span className="text-amber-400"> (Sub-Admin)</span>}
                  {isCorrespondent && <span className="text-yellow-400"> (War Correspondent)</span>}
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
