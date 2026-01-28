import React, { useState, useEffect, useContext } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { AuthContext } from '../utils/AuthContext'

export default function WarRoomAdmin() {
  const auth = useContext(AuthContext)
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [enrolledCivs, setEnrolledCivs] = useState([])
  const [allPartners, setAllPartners] = useState([])
  const [correspondents, setCorrespondents] = useState([])
  const [selectedPartner, setSelectedPartner] = useState('')
  const [newCorrespondent, setNewCorrespondent] = useState({ username: '', password: '', display_name: '' })
  const [message, setMessage] = useState(null)
  const [editingHomeRegion, setEditingHomeRegion] = useState(null)
  const [homeRegionForm, setHomeRegionForm] = useState({ region_x: '', region_y: '', region_z: '', region_name: '', galaxy: 'Euclid' })
  const [regionSearchQuery, setRegionSearchQuery] = useState('')
  const [regionSearchResults, setRegionSearchResults] = useState([])
  const [searchingRegions, setSearchingRegions] = useState(false)

  // Redirect if not super admin
  useEffect(() => {
    if (!auth.loading && !auth.isSuperAdmin) {
      navigate('/war-room')
    }
  }, [auth.loading, auth.isSuperAdmin, navigate])

  const fetchData = async () => {
    try {
      const [enrollmentRes, partnersRes, correspondentsRes] = await Promise.all([
        axios.get('/api/warroom/enrollment'),
        axios.get('/api/partners'),
        axios.get('/api/warroom/correspondents')
      ])

      setEnrolledCivs(enrollmentRes.data)
      setAllPartners(partnersRes.data.partners || [])
      setCorrespondents(correspondentsRes.data)
    } catch (err) {
      console.error('Failed to fetch admin data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const enrollPartner = async () => {
    if (!selectedPartner) return

    try {
      await axios.post('/api/warroom/enrollment', { partner_id: parseInt(selectedPartner) })
      setMessage({ type: 'success', text: 'Partner enrolled successfully!' })
      setSelectedPartner('')
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to enroll partner' })
    }
  }

  const unenrollPartner = async (partnerId) => {
    if (!confirm('Are you sure you want to unenroll this civilization from the War Room?')) return

    try {
      await axios.delete(`/api/warroom/enrollment/${partnerId}`)
      setMessage({ type: 'success', text: 'Partner unenrolled successfully' })
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to unenroll partner' })
    }
  }

  const createCorrespondent = async () => {
    if (!newCorrespondent.username || !newCorrespondent.password) {
      setMessage({ type: 'error', text: 'Username and password required' })
      return
    }

    try {
      await axios.post('/api/warroom/correspondents', newCorrespondent)
      setMessage({ type: 'success', text: 'Correspondent created successfully!' })
      setNewCorrespondent({ username: '', password: '', display_name: '' })
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to create correspondent' })
    }
  }

  const recalculateStats = async () => {
    try {
      await axios.post('/api/warroom/statistics/recalculate')
      setMessage({ type: 'success', text: 'Statistics recalculated!' })
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to recalculate statistics' })
    }
  }

  const openHomeRegionEditor = (civ) => {
    setEditingHomeRegion(civ)
    setHomeRegionForm({
      region_x: civ.home_region_x ?? '',
      region_y: civ.home_region_y ?? '',
      region_z: civ.home_region_z ?? '',
      region_name: civ.home_region_name ?? '',
      galaxy: civ.home_galaxy ?? 'Euclid'
    })
    setRegionSearchQuery('')
    setRegionSearchResults([])
  }

  // Search for regions when editing home region
  useEffect(() => {
    if (!editingHomeRegion || regionSearchQuery.length < 2) {
      setRegionSearchResults([])
      return
    }

    const timer = setTimeout(async () => {
      setSearchingRegions(true)
      try {
        // Search for systems by the partner's discord_tag
        const res = await axios.get(`/api/warroom/territory/search?q=${encodeURIComponent(regionSearchQuery)}&discord_tag=${encodeURIComponent(editingHomeRegion.discord_tag)}&limit=20`)
        setRegionSearchResults(res.data)
      } catch (err) {
        console.error('Region search failed:', err)
      } finally {
        setSearchingRegions(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [regionSearchQuery, editingHomeRegion])

  const selectRegionFromSearch = (system) => {
    setHomeRegionForm({
      region_x: system.region_x ?? '',
      region_y: system.region_y ?? '',
      region_z: system.region_z ?? '',
      region_name: system.region_name || '',
      galaxy: system.galaxy || 'Euclid'
    })
    setRegionSearchQuery('')
    setRegionSearchResults([])
  }

  const saveHomeRegion = async () => {
    if (!editingHomeRegion) return

    try {
      await axios.put(`/api/warroom/enrollment/${editingHomeRegion.partner_id}/home-region`, {
        region_x: homeRegionForm.region_x ? parseInt(homeRegionForm.region_x) : null,
        region_y: homeRegionForm.region_y ? parseInt(homeRegionForm.region_y) : null,
        region_z: homeRegionForm.region_z ? parseInt(homeRegionForm.region_z) : null,
        region_name: homeRegionForm.region_name || null,
        galaxy: homeRegionForm.galaxy
      })
      setMessage({ type: 'success', text: 'Home region updated!' })
      setEditingHomeRegion(null)
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to update home region' })
    }
  }

  // Get partners not yet enrolled
  const enrolledIds = enrolledCivs.map(c => c.partner_id)
  const availablePartners = allPartners.filter(p => !enrolledIds.includes(p.id))

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#0a0c10' }}>
        <div className="text-red-400 text-xl animate-pulse">Loading...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen -m-6" style={{ backgroundColor: '#0a0c10', color: '#e5e7eb' }}>
      {/* Header */}
      <div className="border-b border-red-500/30 bg-gray-900/90 px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-red-500 tracking-wider">WAR ROOM ADMIN</h1>
          <button
            onClick={() => navigate('/war-room')}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm"
          >
            Back to War Room
          </button>
        </div>
      </div>

      {/* Message */}
      {message && (
        <div className={`mx-6 mt-4 p-3 rounded ${message.type === 'success' ? 'bg-green-500/20 border border-green-500/30 text-green-400' : 'bg-red-500/20 border border-red-500/30 text-red-400'}`}>
          {message.text}
          <button onClick={() => setMessage(null)} className="ml-4 text-xs opacity-60 hover:opacity-100">Dismiss</button>
        </div>
      )}

      <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Enrolled Civilizations */}
        <div className="bg-gray-900/80 border border-red-500/20 rounded-lg">
          <div className="px-4 py-3 border-b border-red-500/20">
            <h2 className="text-lg font-bold text-red-400">Enrolled Civilizations ({enrolledCivs.length})</h2>
          </div>
          <div className="p-4">
            {enrolledCivs.length === 0 ? (
              <p className="text-gray-500 text-sm">No civilizations enrolled yet.</p>
            ) : (
              <div className="space-y-2">
                {enrolledCivs.map(civ => (
                  <div key={civ.partner_id} className="bg-gray-800/50 rounded p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-4 h-4 rounded-full"
                          style={{ backgroundColor: civ.region_color }}
                        />
                        <div>
                          <div className="font-medium">{civ.display_name}</div>
                          <div className="text-xs text-gray-500">{civ.discord_tag}</div>
                        </div>
                      </div>
                      <button
                        onClick={() => unenrollPartner(civ.partner_id)}
                        className="px-2 py-1 bg-red-600 hover:bg-red-500 rounded text-xs"
                      >
                        Unenroll
                      </button>
                    </div>
                    {/* Home Region */}
                    <div className="mt-2 pt-2 border-t border-gray-700">
                      {civ.home_region_x !== null ? (
                        <div className="flex items-center justify-between">
                          <div className="text-xs text-gray-400">
                            Home: <span className="text-white">{civ.home_region_name || `(${civ.home_region_x}, ${civ.home_region_y}, ${civ.home_region_z})`}</span>
                            <span className="ml-1 text-gray-500">- {civ.home_galaxy}</span>
                          </div>
                          <button
                            onClick={() => openHomeRegionEditor(civ)}
                            className="text-xs text-cyan-400 hover:text-cyan-300"
                          >
                            Edit
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => openHomeRegionEditor(civ)}
                          className="text-xs text-cyan-400 hover:text-cyan-300"
                        >
                          + Set Home Region
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Enroll new partner */}
            <div className="mt-4 pt-4 border-t border-gray-700">
              <label className="block text-sm text-gray-400 mb-2">Enroll New Civilization</label>
              <div className="flex gap-2">
                <select
                  value={selectedPartner}
                  onChange={(e) => setSelectedPartner(e.target.value)}
                  className="flex-1 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
                >
                  <option value="">Select a partner...</option>
                  {availablePartners.map(p => (
                    <option key={p.id} value={p.id}>{p.display_name} ({p.discord_tag})</option>
                  ))}
                </select>
                <button
                  onClick={enrollPartner}
                  disabled={!selectedPartner}
                  className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded text-sm font-bold"
                >
                  Enroll
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* War Correspondents */}
        <div className="bg-gray-900/80 border border-red-500/20 rounded-lg">
          <div className="px-4 py-3 border-b border-red-500/20">
            <h2 className="text-lg font-bold text-red-400">War Correspondents ({correspondents.length})</h2>
          </div>
          <div className="p-4">
            {correspondents.length > 0 && (
              <div className="space-y-2 mb-4">
                {correspondents.map(c => (
                  <div key={c.id} className="flex items-center justify-between bg-gray-800/50 rounded p-3">
                    <div>
                      <div className="font-medium">{c.display_name || c.username}</div>
                      <div className="text-xs text-gray-500">@{c.username}</div>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs ${c.is_active ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>
                      {c.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Create new correspondent */}
            <div className="space-y-3 pt-4 border-t border-gray-700">
              <label className="block text-sm text-gray-400">Create New Correspondent</label>
              <input
                type="text"
                placeholder="Username"
                value={newCorrespondent.username}
                onChange={(e) => setNewCorrespondent(prev => ({ ...prev, username: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
              />
              <input
                type="password"
                placeholder="Password"
                value={newCorrespondent.password}
                onChange={(e) => setNewCorrespondent(prev => ({ ...prev, password: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
              />
              <input
                type="text"
                placeholder="Display Name (optional)"
                value={newCorrespondent.display_name}
                onChange={(e) => setNewCorrespondent(prev => ({ ...prev, display_name: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
              />
              <button
                onClick={createCorrespondent}
                className="w-full py-2 bg-red-600 hover:bg-red-500 rounded text-sm font-bold"
              >
                Create Correspondent
              </button>
            </div>
          </div>
        </div>

        {/* Admin Actions */}
        <div className="bg-gray-900/80 border border-red-500/20 rounded-lg lg:col-span-2">
          <div className="px-4 py-3 border-b border-red-500/20">
            <h2 className="text-lg font-bold text-red-400">Admin Actions</h2>
          </div>
          <div className="p-4 flex flex-wrap gap-4">
            <button
              onClick={recalculateStats}
              className="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 rounded text-sm font-bold"
            >
              Recalculate Statistics
            </button>
            <button
              onClick={() => navigate('/war-room')}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm"
            >
              View War Room
            </button>
          </div>
        </div>
      </div>

      {/* Home Region Modal */}
      {editingHomeRegion && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-cyan-500/30 rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold text-cyan-400 mb-4">
              Set Home Region: {editingHomeRegion.display_name}
            </h2>
            <div className="space-y-4">
              {/* Searchable Region Selector */}
              <div>
                <label className="block text-sm text-gray-400 mb-2">Search Your Systems</label>
                <div className="relative">
                  <input
                    type="text"
                    value={regionSearchQuery}
                    onChange={(e) => setRegionSearchQuery(e.target.value)}
                    placeholder={`Search systems with ${editingHomeRegion.discord_tag} tag...`}
                    className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
                  />
                  {searchingRegions && (
                    <span className="absolute right-3 top-2 text-gray-400 text-sm">...</span>
                  )}
                  {regionSearchResults.length > 0 && (
                    <div className="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-600 rounded shadow-lg max-h-48 overflow-y-auto">
                      {regionSearchResults.map(s => (
                        <button
                          key={s.id}
                          onClick={() => selectRegionFromSearch(s)}
                          className="w-full text-left px-3 py-2 hover:bg-gray-700 text-sm border-b border-gray-700 last:border-b-0"
                        >
                          <div className="font-medium text-white">{s.name}</div>
                          <div className="text-xs text-gray-400">
                            {s.region_name || `(${s.region_x}, ${s.region_y}, ${s.region_z})`} - {s.galaxy}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-1">Search for a system in {editingHomeRegion.discord_tag}'s territory</p>
              </div>

              {/* Selected Region Display */}
              {homeRegionForm.region_x !== '' && (
                <div className="bg-gray-800/50 border border-cyan-500/30 rounded p-3">
                  <div className="text-sm text-gray-400 mb-1">Selected Region:</div>
                  <div className="text-white font-medium">
                    {homeRegionForm.region_name || 'Unnamed Region'}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    Coordinates: ({homeRegionForm.region_x}, {homeRegionForm.region_y}, {homeRegionForm.region_z}) • {homeRegionForm.galaxy}
                  </div>
                </div>
              )}

              {!homeRegionForm.region_x && homeRegionForm.region_x !== 0 && (
                <div className="text-sm text-yellow-400 text-center py-2">
                  Search and select a system to set as home region
                </div>
              )}

              <p className="text-xs text-gray-500">
                The home region (HQ) will be displayed on the war map and is protected from peace treaty demands.
              </p>
              <div className="flex gap-3 pt-2">
                <button
                  onClick={saveHomeRegion}
                  disabled={homeRegionForm.region_x === '' && homeRegionForm.region_x !== 0}
                  className="flex-1 py-2 bg-cyan-600 hover:bg-cyan-500 rounded font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Save Home Region
                </button>
                <button
                  onClick={() => setEditingHomeRegion(null)}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
