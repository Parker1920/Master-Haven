import React, { useState, useEffect, useContext } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import LeaderboardTable from '../components/LeaderboardTable'
import { format, parseISO } from 'date-fns'
import { AuthContext } from '../utils/AuthContext'

const EVENT_TYPE_LABELS = {
  submissions: { label: 'System Submissions', icon: '🌌', color: 'bg-cyan-500' },
  discoveries: { label: 'Discoveries', icon: '🔬', color: 'bg-purple-500' },
  both: { label: 'Systems + Discoveries', icon: '🏆', color: 'bg-amber-500' }
}

export default function Events() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const { isSuperAdmin, isAdmin, isPartner, user } = auth

  const [loading, setLoading] = useState(true)
  const [events, setEvents] = useState([])
  const [discordTags, setDiscordTags] = useState([])

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showLeaderboardModal, setShowLeaderboardModal] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [eventLeaderboard, setEventLeaderboard] = useState({ leaderboard: [], totals: {} })
  const [leaderboardLoading, setLeaderboardLoading] = useState(false)
  const [leaderboardTab, setLeaderboardTab] = useState('submissions')

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    discord_tag: '',
    start_date: '',
    end_date: '',
    description: '',
    event_type: 'submissions'
  })

  // Redirect if not admin or partner
  useEffect(() => {
    if (!auth.loading && !isAdmin && !isPartner) {
      navigate('/')
    }
  }, [auth.loading, isAdmin, isPartner, navigate])

  // Fetch discord tags (for super admin dropdown)
  useEffect(() => {
    const fetchTags = async () => {
      try {
        const res = await axios.get('/api/discord_tags')
        setDiscordTags(res.data.tags || [])
      } catch (err) {
        console.error('Failed to fetch discord tags:', err)
      }
    }
    if (isSuperAdmin) {
      fetchTags()
    }
  }, [isSuperAdmin])

  // Fetch events
  useEffect(() => {
    if (!isAdmin && !isPartner) return

    const fetchEvents = async () => {
      try {
        const res = await axios.get('/api/events', {
          params: { include_inactive: true },
          withCredentials: true
        })
        setEvents(res.data.events || [])
      } catch (err) {
        console.error('Failed to fetch events:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchEvents()
  }, [isAdmin, isPartner])

  const handleCreateEvent = async (e) => {
    e.preventDefault()
    try {
      const res = await axios.post(`/api/events`, formData, { withCredentials: true })
      if (res.data.success) {
        // Refresh events list
        const eventsRes = await axios.get(`/api/events`, {
          params: { include_inactive: true },
          withCredentials: true
        })
        setEvents(eventsRes.data.events || [])
        setShowCreateModal(false)
        setFormData({ name: '', discord_tag: '', start_date: '', end_date: '', description: '', event_type: 'submissions' })
      }
    } catch (err) {
      console.error('Failed to create event:', err)
      alert(err.response?.data?.detail || 'Failed to create event')
    }
  }

  const handleViewLeaderboard = async (event, tab = null) => {
    const eventType = event.event_type || 'submissions'
    // Determine the default tab based on event type
    const defaultTab = eventType === 'discoveries' ? 'discoveries'
      : eventType === 'both' ? 'combined'
      : 'submissions'
    const selectedTab = tab || defaultTab

    setSelectedEvent(event)
    setLeaderboardTab(selectedTab)
    setShowLeaderboardModal(true)
    setLeaderboardLoading(true)
    try {
      const res = await axios.get(`/api/events/${event.id}/leaderboard`, {
        params: { tab: selectedTab },
        withCredentials: true
      })
      setEventLeaderboard({
        leaderboard: res.data.leaderboard || [],
        totals: res.data.totals || {}
      })
    } catch (err) {
      console.error('Failed to fetch event leaderboard:', err)
    } finally {
      setLeaderboardLoading(false)
    }
  }

  const handleTabChange = (tab) => {
    if (selectedEvent) {
      handleViewLeaderboard(selectedEvent, tab)
    }
  }

  const handleToggleActive = async (event) => {
    try {
      await axios.put(`/api/events/${event.id}`, {
        is_active: event.is_active ? 0 : 1
      }, { withCredentials: true })

      // Refresh events list
      const res = await axios.get(`/api/events`, {
        params: { include_inactive: true },
        withCredentials: true
      })
      setEvents(res.data.events || [])
    } catch (err) {
      console.error('Failed to toggle event:', err)
    }
  }

  const handleDeleteEvent = async (event) => {
    if (!window.confirm(`Are you sure you want to delete "${event.name}"?`)) return

    try {
      await axios.delete(`/api/events/${event.id}`, { withCredentials: true })

      // Refresh events list
      const res = await axios.get(`/api/events`, {
        params: { include_inactive: true },
        withCredentials: true
      })
      setEvents(res.data.events || [])
    } catch (err) {
      console.error('Failed to delete event:', err)
    }
  }

  const formatDate = (dateStr) => {
    try {
      return format(parseISO(dateStr), 'MMM d, yyyy')
    } catch {
      return dateStr
    }
  }

  const getEventStatus = (event) => {
    const now = new Date().toISOString()
    if (!event.is_active) return { label: 'Inactive', color: 'bg-gray-500' }
    if (event.start_date > now) return { label: 'Upcoming', color: 'bg-blue-500' }
    if (event.end_date + 'T23:59:59' < now) return { label: 'Ended', color: 'bg-gray-500' }
    return { label: 'Active', color: 'bg-green-500' }
  }

  // Get available tabs for event's leaderboard modal
  const getAvailableTabs = (event) => {
    const eventType = event?.event_type || 'submissions'
    if (eventType === 'submissions') return ['submissions']
    if (eventType === 'discoveries') return ['discoveries']
    return ['combined', 'submissions', 'discoveries']
  }

  // Show loading while auth is loading
  if (auth.loading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--app-bg)' }}>
        <div className="animate-spin rounded-full h-12 w-12 border-b-2" style={{ borderColor: 'var(--app-primary)' }}></div>
      </div>
    )
  }

  // Don't render if not authorized
  if (!isAdmin && !isPartner) {
    return null
  }

  return (
    <div className="min-h-screen p-6" style={{ background: 'var(--app-bg)' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>Community Events</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
            Track submissions and discoveries during event periods
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors"
          style={{ background: 'var(--app-primary)', color: '#000' }}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Event
        </button>
      </div>

      {/* Events List */}
      {events.length === 0 ? (
        <div
          className="rounded-xl p-12 text-center"
          style={{
            background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
            border: '1px solid rgba(255,255,255,0.04)'
          }}
        >
          <div className="text-4xl mb-4">📅</div>
          <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--app-text)' }}>No Events Yet</h3>
          <p className="text-sm mb-4" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
            Create your first event to start tracking
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 rounded-lg font-medium"
            style={{ background: 'var(--app-primary)', color: '#000' }}
          >
            Create Event
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {events.map((event) => {
            const status = getEventStatus(event)
            const eventType = event.event_type || 'submissions'
            const typeInfo = EVENT_TYPE_LABELS[eventType] || EVENT_TYPE_LABELS.submissions
            return (
              <div
                key={event.id}
                className="rounded-xl p-4"
                style={{
                  background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
                  border: '1px solid rgba(255,255,255,0.04)'
                }}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">{typeInfo.icon}</span>
                    <div>
                      <h3 className="font-semibold" style={{ color: 'var(--app-text)' }}>{event.name}</h3>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${status.color}`}>
                          {status.label}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${typeInfo.color}`}>
                          {typeInfo.label}
                        </span>
                      </div>
                    </div>
                  </div>
                  <span
                    className="px-2 py-1 rounded text-xs font-medium"
                    style={{ background: 'rgba(0, 194, 179, 0.1)', color: 'var(--app-primary)' }}
                  >
                    {event.discord_tag}
                  </span>
                </div>

                <div className="text-sm mb-3" style={{ color: 'var(--app-text)', opacity: 0.7 }}>
                  {formatDate(event.start_date)} - {formatDate(event.end_date)}
                </div>

                {event.description && (
                  <p className="text-sm mb-3" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
                    {event.description}
                  </p>
                )}

                <div className="flex items-center gap-4 mb-4 text-sm flex-wrap" style={{ color: 'var(--app-text)' }}>
                  {(eventType === 'submissions' || eventType === 'both') && (
                    <div>
                      <span className="font-semibold" style={{ color: 'var(--app-primary)' }}>
                        {event.submission_count}
                      </span> submissions
                    </div>
                  )}
                  {(eventType === 'discoveries' || eventType === 'both') && (
                    <div>
                      <span className="font-semibold" style={{ color: '#a855f7' }}>
                        {event.discovery_count}
                      </span> discoveries
                    </div>
                  )}
                  <div>
                    <span className="font-semibold" style={{ color: 'var(--app-accent-2)' }}>
                      {Math.max(event.participant_count || 0, event.discovery_participant_count || 0)}
                    </span> participants
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-3" style={{ borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                  <button
                    onClick={() => handleViewLeaderboard(event)}
                    className="flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                    style={{
                      background: 'rgba(0, 194, 179, 0.1)',
                      color: 'var(--app-primary)',
                      border: '1px solid rgba(0, 194, 179, 0.2)'
                    }}
                  >
                    View Leaderboard
                  </button>
                  <button
                    onClick={() => handleToggleActive(event)}
                    className="px-3 py-2 rounded-lg text-sm transition-colors"
                    style={{
                      background: 'rgba(255,255,255,0.05)',
                      color: 'var(--app-text)',
                      border: '1px solid rgba(255,255,255,0.1)'
                    }}
                  >
                    {event.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                  <button
                    onClick={() => handleDeleteEvent(event)}
                    className="px-3 py-2 rounded-lg text-sm transition-colors"
                    style={{
                      background: 'rgba(239, 68, 68, 0.1)',
                      color: '#ef4444',
                      border: '1px solid rgba(239, 68, 68, 0.2)'
                    }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Create Event Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60" onClick={() => setShowCreateModal(false)} />
          <div
            className="relative rounded-xl p-6 w-full max-w-md"
            style={{
              background: 'var(--app-card)',
              border: '1px solid rgba(255,255,255,0.1)'
            }}
          >
            <h2 className="text-xl font-semibold mb-4" style={{ color: 'var(--app-text)' }}>Create New Event</h2>
            <form onSubmit={handleCreateEvent}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
                    Event Name
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                    className="w-full px-3 py-2 rounded-lg"
                    placeholder="Winter Exploration Event"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
                    Event Type
                  </label>
                  <select
                    value={formData.event_type}
                    onChange={(e) => setFormData({ ...formData, event_type: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg"
                  >
                    <option value="submissions">System Submissions</option>
                    <option value="discoveries">Discoveries</option>
                    <option value="both">Both (Systems + Discoveries)</option>
                  </select>
                </div>

                {isSuperAdmin && (
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
                      Community
                    </label>
                    <select
                      value={formData.discord_tag}
                      onChange={(e) => setFormData({ ...formData, discord_tag: e.target.value })}
                      required
                      className="w-full px-3 py-2 rounded-lg"
                    >
                      <option value="">Select community...</option>
                      {discordTags.map((tag) => (
                        <option key={tag.tag} value={tag.tag}>{tag.name}</option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
                      Start Date
                    </label>
                    <input
                      type="date"
                      value={formData.start_date}
                      onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                      required
                      className="w-full px-3 py-2 rounded-lg"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
                      End Date
                    </label>
                    <input
                      type="date"
                      value={formData.end_date}
                      onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                      required
                      className="w-full px-3 py-2 rounded-lg"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
                    Description (optional)
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 rounded-lg"
                    placeholder="Describe the event..."
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-lg text-sm"
                  style={{ color: 'var(--app-text)', border: '1px solid rgba(255,255,255,0.1)' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg text-sm font-medium"
                  style={{ background: 'var(--app-primary)', color: '#000' }}
                >
                  Create Event
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Leaderboard Modal */}
      {showLeaderboardModal && selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60" onClick={() => setShowLeaderboardModal(false)} />
          <div
            className="relative rounded-xl p-6 w-full max-w-4xl max-h-[90vh] overflow-y-auto"
            style={{
              background: 'var(--app-card)',
              border: '1px solid rgba(255,255,255,0.1)'
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold" style={{ color: 'var(--app-text)' }}>
                  {(EVENT_TYPE_LABELS[selectedEvent.event_type] || EVENT_TYPE_LABELS.submissions).icon}{' '}
                  {selectedEvent.name}
                </h2>
                <p className="text-sm mt-1" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
                  {formatDate(selectedEvent.start_date)} - {formatDate(selectedEvent.end_date)}
                </p>
              </div>
              <button
                onClick={() => setShowLeaderboardModal(false)}
                className="p-2 rounded-lg transition-colors hover:bg-white/10"
                style={{ color: 'var(--app-text)' }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Tab Switcher */}
            {getAvailableTabs(selectedEvent).length > 1 && (
              <div className="flex items-center rounded-lg overflow-hidden mb-4" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' }}>
                {getAvailableTabs(selectedEvent).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => handleTabChange(tab)}
                    className="px-4 py-2 text-sm font-medium transition-colors flex-1"
                    style={{
                      background: leaderboardTab === tab ? 'var(--app-primary)' : 'transparent',
                      color: leaderboardTab === tab ? '#000' : 'var(--app-text)'
                    }}
                  >
                    {tab === 'submissions' ? 'Systems' : tab === 'discoveries' ? 'Discoveries' : 'Combined'}
                  </button>
                ))}
              </div>
            )}

            {/* Event Stats */}
            <div className={`grid gap-4 mb-6 ${
              leaderboardTab === 'combined' ? 'grid-cols-4' :
              leaderboardTab === 'submissions' ? 'grid-cols-3' : 'grid-cols-2'
            }`}>
              {leaderboardTab === 'submissions' && (
                <>
                  <div className="p-4 rounded-lg text-center" style={{ background: 'rgba(0, 194, 179, 0.1)' }}>
                    <div className="text-2xl font-bold" style={{ color: 'var(--app-primary)' }}>
                      {eventLeaderboard.totals.total_submissions || 0}
                    </div>
                    <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>Submissions</div>
                  </div>
                  <div className="p-4 rounded-lg text-center" style={{ background: 'rgba(34, 197, 94, 0.1)' }}>
                    <div className="text-2xl font-bold" style={{ color: '#22c55e' }}>
                      {eventLeaderboard.totals.total_approved || 0}
                    </div>
                    <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>Approved</div>
                  </div>
                  <div className="p-4 rounded-lg text-center" style={{ background: 'rgba(157, 78, 221, 0.1)' }}>
                    <div className="text-2xl font-bold" style={{ color: 'var(--app-accent-2)' }}>
                      {eventLeaderboard.totals.participants || 0}
                    </div>
                    <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>Participants</div>
                  </div>
                </>
              )}
              {leaderboardTab === 'discoveries' && (
                <>
                  <div className="p-4 rounded-lg text-center" style={{ background: 'rgba(168, 85, 247, 0.1)' }}>
                    <div className="text-2xl font-bold" style={{ color: '#a855f7' }}>
                      {eventLeaderboard.totals.total_discoveries || 0}
                    </div>
                    <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>Discoveries</div>
                  </div>
                  <div className="p-4 rounded-lg text-center" style={{ background: 'rgba(157, 78, 221, 0.1)' }}>
                    <div className="text-2xl font-bold" style={{ color: 'var(--app-accent-2)' }}>
                      {eventLeaderboard.totals.participants || 0}
                    </div>
                    <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>Discoverers</div>
                  </div>
                </>
              )}
              {leaderboardTab === 'combined' && (
                <>
                  <div className="p-4 rounded-lg text-center" style={{ background: 'rgba(0, 194, 179, 0.1)' }}>
                    <div className="text-2xl font-bold" style={{ color: 'var(--app-primary)' }}>
                      {eventLeaderboard.totals.total_submissions || 0}
                    </div>
                    <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>Submissions</div>
                  </div>
                  <div className="p-4 rounded-lg text-center" style={{ background: 'rgba(168, 85, 247, 0.1)' }}>
                    <div className="text-2xl font-bold" style={{ color: '#a855f7' }}>
                      {eventLeaderboard.totals.total_discoveries || 0}
                    </div>
                    <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>Discoveries</div>
                  </div>
                  <div className="p-4 rounded-lg text-center" style={{ background: 'rgba(245, 158, 11, 0.1)' }}>
                    <div className="text-2xl font-bold" style={{ color: '#f59e0b' }}>
                      {eventLeaderboard.totals.combined_total || 0}
                    </div>
                    <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>Combined</div>
                  </div>
                  <div className="p-4 rounded-lg text-center" style={{ background: 'rgba(157, 78, 221, 0.1)' }}>
                    <div className="text-2xl font-bold" style={{ color: 'var(--app-accent-2)' }}>
                      {eventLeaderboard.totals.participants || 0}
                    </div>
                    <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>Participants</div>
                  </div>
                </>
              )}
            </div>

            {/* Leaderboard Table */}
            {leaderboardTab === 'discoveries' ? (
              <DiscoveryLeaderboard data={eventLeaderboard.leaderboard} loading={leaderboardLoading} />
            ) : leaderboardTab === 'combined' ? (
              <CombinedLeaderboard data={eventLeaderboard.leaderboard} loading={leaderboardLoading} />
            ) : (
              <LeaderboardTable
                data={eventLeaderboard.leaderboard}
                showCommunity={false}
                loading={leaderboardLoading}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}


function DiscoveryLeaderboard({ data, loading }) {
  if (loading) {
    return <div className="text-center py-8 text-gray-400">Loading leaderboard...</div>
  }

  if (!data || data.length === 0) {
    return <div className="text-center py-8 text-gray-400">No discoveries during this event period.</div>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
            <th className="text-left py-3 px-2" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Rank</th>
            <th className="text-left py-3 px-2" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Discoverer</th>
            <th className="text-right py-3 px-2" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Discoveries</th>
            <th className="text-right py-3 px-2" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Types</th>
          </tr>
        </thead>
        <tbody>
          {data.map((entry) => (
            <tr key={entry.rank} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <td className="py-3 px-2">
                <span className={`font-bold ${entry.rank <= 3 ? 'text-amber-400' : ''}`} style={{ color: entry.rank > 3 ? 'var(--app-text)' : undefined }}>
                  {entry.rank <= 3 ? ['', '1st', '2nd', '3rd'][entry.rank] : `#${entry.rank}`}
                </span>
              </td>
              <td className="py-3 px-2 font-medium" style={{ color: 'var(--app-text)' }}>
                {entry.username}
              </td>
              <td className="py-3 px-2 text-right font-semibold" style={{ color: '#a855f7' }}>
                {entry.total_discoveries}
              </td>
              <td className="py-3 px-2 text-right" style={{ color: 'var(--app-text)', opacity: 0.7 }}>
                {entry.types_count} {entry.types_count === 1 ? 'type' : 'types'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


function CombinedLeaderboard({ data, loading }) {
  if (loading) {
    return <div className="text-center py-8 text-gray-400">Loading leaderboard...</div>
  }

  if (!data || data.length === 0) {
    return <div className="text-center py-8 text-gray-400">No activity during this event period.</div>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
            <th className="text-left py-3 px-2" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Rank</th>
            <th className="text-left py-3 px-2" style={{ color: 'var(--app-text)', opacity: 0.6 }}>User</th>
            <th className="text-right py-3 px-2" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Systems</th>
            <th className="text-right py-3 px-2" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Discoveries</th>
            <th className="text-right py-3 px-2" style={{ color: 'var(--app-text)', opacity: 0.6 }}>Total</th>
          </tr>
        </thead>
        <tbody>
          {data.map((entry) => (
            <tr key={entry.rank} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <td className="py-3 px-2">
                <span className={`font-bold ${entry.rank <= 3 ? 'text-amber-400' : ''}`} style={{ color: entry.rank > 3 ? 'var(--app-text)' : undefined }}>
                  {entry.rank <= 3 ? ['', '1st', '2nd', '3rd'][entry.rank] : `#${entry.rank}`}
                </span>
              </td>
              <td className="py-3 px-2 font-medium" style={{ color: 'var(--app-text)' }}>
                {entry.username}
              </td>
              <td className="py-3 px-2 text-right" style={{ color: 'var(--app-primary)' }}>
                {entry.total_submissions}
              </td>
              <td className="py-3 px-2 text-right" style={{ color: '#a855f7' }}>
                {entry.total_discoveries}
              </td>
              <td className="py-3 px-2 text-right font-semibold" style={{ color: '#f59e0b' }}>
                {entry.combined_total}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
