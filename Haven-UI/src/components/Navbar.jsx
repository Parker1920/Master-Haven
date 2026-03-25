import React, { useContext, useState, useEffect, useRef, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { SparklesIcon, Bars3Icon, XMarkIcon, ChevronDownIcon } from '@heroicons/react/24/solid'
import AdminLoginModal from './AdminLoginModal'
import { AuthContext, FEATURES } from '../utils/AuthContext'
import axios from 'axios'

/**
 * Top navigation bar with auth-aware links, pending count badges, and dropdown menus.
 *
 * NAV_LINKS and NAV_GROUPS define all navigation in one place.
 * Both desktop and mobile views render from the same data source,
 * eliminating the manual sync issue between the two layouts.
 */

// Badge component (shared between desktop and mobile)
function CountBadge({ count, className = '' }) {
  if (!count || count <= 0) return null
  return (
    <span className={`bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center ${className}`}>
      {count > 9 ? '9+' : count}
    </span>
  )
}

function ConflictBadge({ count, className = '' }) {
  if (!count || count <= 0) return null
  return (
    <span className={`bg-red-600 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center animate-pulse ${className}`}>
      {count > 9 ? '9+' : count}
    </span>
  )
}

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
  const { isAdmin, isSuperAdmin, isPartner, isSubAdmin, isCorrespondent, isMember, user, canAccess } = auth

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
    const fetchCount = async () => {
      try {
        const response = await axios.get('/api/pending_systems/count')
        setPendingCount(response.data.count || 0)
      } catch (err) { /* Silent fail */ }
    }
    fetchCount()
    intervalRef.current = setInterval(fetchCount, 60000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [isAdmin])

  // Fetch active conflict count for War Room badge
  useEffect(() => {
    const hasWarRoomAccess = canAccess(FEATURES.WAR_ROOM) || isCorrespondent
    if (!hasWarRoomAccess) {
      setActiveConflictCount(0)
      return
    }
    const fetchConflictCount = async () => {
      try {
        const response = await axios.get('/api/warroom/conflicts/active')
        setActiveConflictCount(response.data?.length || 0)
      } catch (err) { /* Silent fail */ }
    }
    fetchConflictCount()
    warIntervalRef.current = setInterval(fetchConflictCount, 60000)
    return () => { if (warIntervalRef.current) clearInterval(warIntervalRef.current) }
  }, [canAccess, isCorrespondent])

  const closeMenu = () => setMobileMenuOpen(false)
  const toggleDropdown = (name) => setOpenDropdown(prev => prev === name ? null : name)
  const closeDropdown = () => setOpenDropdown(null)

  // ============================================================================
  // NAV_LINKS: Single source of truth for all navigation items.
  // Add/remove links here — both desktop and mobile update automatically.
  // ============================================================================
  const showAnalyticsDropdown = isSuperAdmin || (isAdmin && !isCorrespondent)
  const showAdminDropdown = canAccess(FEATURES.APPROVALS) || canAccess(FEATURES.SETTINGS) || (isAdmin && !isCorrespondent)
  const showSuperAdminDropdown = isSuperAdmin

  // Top-level links (always visible section)
  const NAV_LINKS = useMemo(() => [
    { label: 'Dashboard', to: '/', visible: true },
    { label: 'Systems', to: '/systems', visible: true },
    { label: 'Map', href: '/map/latest', visible: true },
    { label: 'Create', to: '/create', visible: true },
    { label: 'Discoveries', to: '/discoveries', visible: true },
    { label: 'Community Stats', to: '/community-stats', visible: true },
    { label: 'Events', to: '/events', visible: isAdmin && !isCorrespondent },
    { label: 'War Room', to: '/war-room', visible: canAccess(FEATURES.WAR_ROOM) || isCorrespondent,
      className: 'text-red-400 font-bold', badge: 'conflict' },
  ], [isAdmin, isCorrespondent, canAccess])

  // Dropdown groups
  const NAV_GROUPS = useMemo(() => [
    {
      name: 'analytics', label: 'Analytics', visible: showAnalyticsDropdown,
      items: [
        { label: 'Analytics', to: '/analytics', visible: isSuperAdmin },
        { label: 'Partner Analytics', to: '/partner-analytics', visible: isAdmin && !isCorrespondent },
        { label: 'DB Stats', to: '/db_stats', visible: true },
      ]
    },
    {
      name: 'admin', label: 'Admin', visible: showAdminDropdown, showBadge: true,
      items: [
        { label: 'Approvals', to: '/pending-approvals', visible: canAccess(FEATURES.APPROVALS), badge: 'pending' },
        { label: 'Settings', to: '/settings', visible: canAccess(FEATURES.SETTINGS) },
        { label: 'Extractors', to: '/admin/extractors', visible: isAdmin && !isCorrespondent },
        { label: 'Sub-Admins', to: '/admin/sub-admins', visible: isSuperAdmin || isPartner },
        { label: 'CSV Import', to: '/csv-import', visible: canAccess(FEATURES.CSV_IMPORT) },
        { label: 'Data Restrictions', to: '/data-restrictions', visible: isAdmin && !isCorrespondent },
      ]
    },
    {
      name: 'superadmin', label: 'Super Admin', visible: showSuperAdminDropdown,
      items: [
        { label: 'User Management', to: '/admin/users', visible: true },
        { label: 'API Keys', to: '/api-keys', visible: true },
        { label: 'Partners (Legacy)', to: '/admin/partners', visible: true },
        { label: 'Audit Log', to: '/admin/audit', visible: true },
      ]
    },
  ], [showAnalyticsDropdown, showAdminDropdown, showSuperAdminDropdown,
      isSuperAdmin, isAdmin, isCorrespondent, isPartner, canAccess])

  // DB Stats fallback (shown as top-level link when analytics dropdown isn't visible)
  const showDbStatsTopLevel = !showAnalyticsDropdown

  // Shared styles
  const navLink = 'px-3 py-1 hover:underline whitespace-nowrap'
  const dropdownTrigger = 'px-3 py-1 hover:underline whitespace-nowrap flex items-center gap-1 cursor-pointer select-none'
  const dropdownPanel = 'absolute top-full left-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1 min-w-[180px] z-50'
  const dropdownItem = 'block w-full text-left px-4 py-2 hover:bg-gray-700 whitespace-nowrap'

  // Resolve badge value
  const getBadge = (type) => {
    if (type === 'pending') return pendingCount
    if (type === 'conflict') return activeConflictCount
    return 0
  }

  return (
    <header className="p-4 shadow" style={{ background: 'linear-gradient(90deg, var(--app-card), rgba(255,255,255,0.02))' }}>
      <div className="container mx-auto" role="navigation" aria-label="Main navigation">
        <div className="flex items-center justify-between">
          {/* Logo + user info */}
          <div className="flex items-center space-x-4">
            <div style={{ background: 'linear-gradient(135deg, var(--app-primary), var(--app-accent-2))' }} className="p-2 rounded-lg">
              <SparklesIcon className="w-7 h-7 text-white" />
            </div>
            <div>
              <div className="text-xl font-semibold" style={{ color: 'var(--app-text)' }}>Haven Control Room</div>
              <div className="text-sm muted" style={{ color: 'var(--app-accent-3)' }}>
                {user ? (
                  <span>
                    {user?.displayName || user?.username}
                    {isPartner && user?.discordTag && <span className="ml-1 text-cyan-400">({user.discordTag})</span>}
                    {isSuperAdmin && <span className="ml-1 text-yellow-400">(Super Admin)</span>}
                    {isSubAdmin && <span className="ml-1 text-amber-400">(Sub-Admin)</span>}
                    {isCorrespondent && <span className="ml-1 text-red-400">(War Correspondent)</span>}
                    {isMember && <span className="ml-1 text-green-400">(Member)</span>}
                  </span>
                ) : 'Web'}
              </div>
            </div>
          </div>

          {/* ================================================================ */}
          {/* Desktop Navigation — rendered from NAV_LINKS + NAV_GROUPS        */}
          {/* ================================================================ */}
          <nav className="hidden lg:flex items-center space-x-1" aria-label="Primary" ref={dropdownRef}>
            {/* Top-level links */}
            {NAV_LINKS.filter(l => l.visible).map(link => (
              link.href ? (
                <a key={link.label} className={`${navLink} ${link.className || ''}`} href={link.href}>
                  {link.label}
                </a>
              ) : (
                <Link key={link.label} className={`${navLink} ${link.className || ''} ${link.badge ? 'relative' : ''}`} to={link.to}>
                  {link.label}
                  {link.badge && <ConflictBadge count={getBadge(link.badge)} className="absolute -top-1 -right-1" />}
                </Link>
              )
            ))}

            {/* DB Stats fallback (public, when analytics dropdown isn't shown) */}
            {showDbStatsTopLevel && <Link className={navLink} to="/db_stats">DB Stats</Link>}

            {/* Dropdown groups */}
            {NAV_GROUPS.filter(g => g.visible).map(group => (
              <div key={group.name} className="relative">
                <button className={`${dropdownTrigger} relative`} onClick={() => toggleDropdown(group.name)}>
                  {group.label}
                  {group.showBadge && pendingCount > 0 && canAccess(FEATURES.APPROVALS) && (
                    <CountBadge count={pendingCount} />
                  )}
                  <ChevronDownIcon className={`w-3 h-3 transition-transform ${openDropdown === group.name ? 'rotate-180' : ''}`} />
                </button>
                {openDropdown === group.name && (
                  <div className={dropdownPanel}>
                    {group.items.filter(i => i.visible).map(item => (
                      <Link key={item.to} className={`${dropdownItem} ${item.badge ? 'flex justify-between items-center' : ''}`} to={item.to} onClick={closeDropdown}>
                        <span>{item.label}</span>
                        {item.badge && <CountBadge count={getBadge(item.badge)} className="ml-2" />}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {/* Profile + Auth */}
            {user && <Link className={`${navLink} text-green-400`} to="/profile">My Profile</Link>}
            {!user ? (
              <button className="px-3 py-1 bg-blue-500 text-white rounded whitespace-nowrap" onClick={() => setShowLogin(true)}>Login</button>
            ) : (
              <button className="px-3 py-1 bg-red-500 text-white rounded whitespace-nowrap" onClick={() => auth.logout()}>Logout</button>
            )}
          </nav>

          {/* Mobile Menu Button */}
          <button className="lg:hidden p-2 text-white" onClick={() => setMobileMenuOpen(!mobileMenuOpen)} aria-label="Toggle menu">
            {mobileMenuOpen ? <XMarkIcon className="w-6 h-6" /> : <Bars3Icon className="w-6 h-6" />}
          </button>
        </div>

        {/* ================================================================ */}
        {/* Mobile Navigation — rendered from same NAV_LINKS + NAV_GROUPS    */}
        {/* ================================================================ */}
        {mobileMenuOpen && (
          <nav className="lg:hidden mt-4 flex flex-col space-y-1 pb-4" aria-label="Mobile">
            {/* Top-level links */}
            {NAV_LINKS.filter(l => l.visible).map(link => (
              link.href ? (
                <a key={link.label} className={`px-3 py-2 hover:bg-gray-700 rounded ${link.className || ''}`} href={link.href} onClick={closeMenu}>
                  {link.label}
                </a>
              ) : (
                <Link key={link.label} className={`px-3 py-2 hover:bg-gray-700 rounded ${link.className || ''} ${link.badge ? 'flex justify-between items-center' : ''}`} to={link.to} onClick={closeMenu}>
                  <span>{link.label}</span>
                  {link.badge && <ConflictBadge count={getBadge(link.badge)} />}
                </Link>
              )
            ))}

            {/* DB Stats fallback */}
            {showDbStatsTopLevel && <Link className="px-3 py-2 hover:bg-gray-700 rounded" to="/db_stats" onClick={closeMenu}>DB Stats</Link>}

            {/* Dropdown groups as mobile sections */}
            {NAV_GROUPS.filter(g => g.visible).map(group => (
              <React.Fragment key={group.name}>
                <div className="pt-2 mt-1 border-t border-gray-700">
                  <div className="px-3 py-1 text-xs text-gray-500 uppercase tracking-wider">{group.label}</div>
                </div>
                {group.items.filter(i => i.visible).map(item => (
                  <Link key={item.to} className={`px-3 py-2 hover:bg-gray-700 rounded pl-5 ${item.badge ? 'flex justify-between items-center' : ''}`} to={item.to} onClick={closeMenu}>
                    <span>{item.label}</span>
                    {item.badge && <CountBadge count={getBadge(item.badge)} />}
                  </Link>
                ))}
              </React.Fragment>
            ))}

            {/* Auth section */}
            <div className="pt-2 border-t border-gray-700">
              {user && (
                <div className="px-3 py-2 text-sm text-gray-400 mb-2">
                  Logged in as: {user?.displayName || user?.username}
                  {isPartner && user?.discordTag && <span className="text-cyan-400"> ({user.discordTag})</span>}
                  {isSubAdmin && <span className="text-amber-400"> (Sub-Admin)</span>}
                  {isCorrespondent && <span className="text-yellow-400"> (War Correspondent)</span>}
                  {isMember && <span className="text-green-400"> (Member)</span>}
                </div>
              )}
              {user && (
                <Link className="px-3 py-2 hover:bg-gray-700 rounded text-green-400 block mb-2" to="/profile" onClick={closeMenu}>My Profile</Link>
              )}
              {!user ? (
                <button className="w-full px-3 py-2 bg-blue-500 text-white rounded" onClick={() => { setShowLogin(true); closeMenu() }}>Login</button>
              ) : (
                <button className="w-full px-3 py-2 bg-red-500 text-white rounded" onClick={() => { auth.logout(); closeMenu() }}>Logout</button>
              )}
            </div>
          </nav>
        )}
      </div>
      <AdminLoginModal open={showLogin} onClose={() => setShowLogin(false)} />
    </header>
  )
}
