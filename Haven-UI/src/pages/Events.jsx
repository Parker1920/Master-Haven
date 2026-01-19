import React, { useState, useEffect, useContext } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import LeaderboardTable from '../components/LeaderboardTable'
import { format, parseISO } from 'date-fns'
import { AuthContext } from '../utils/AuthContext'

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

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    discord_tag: '',
    start_date: '',
    end_date: '',
    description: ''
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
        setFormData({ name: '', discord_tag: '', start_date: '', end_date: '', description: '' })
      }
    } catch (err) {
      console.error('Failed to create event:', err)
      alert(err.response?.data?.detail || 'Failed to create event')
    }
  }

  const handleViewLeaderboard = async (event) => {
    setSelectedEvent(event)
    setShowLeaderboardModal(true)
    setLeaderboardLoading(true)
    try {
      const res = await axios.get(`/api/events/${event.id}/leaderboard`, {
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
          <h1 className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>Submission Events</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
            Track submissions during event periods
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
            Create your first submission event to start tracking
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
                    <span className="text-2xl">🏆</span>
                    <div>
                      <h3 className="font-semibold" style={{ color: 'var(--app-text)' }}>{event.name}</h3>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${status.color}`}>
                        {status.label}
                      </span>
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

                <div className="flex items-center gap-4 mb-4 text-sm" style={{ color: 'var(--app-text)' }}>
                  <div>
                    <span className="font-semibold" style={{ color: 'var(--app-primary)' }}>
                      {event.submission_count}
                    </span> submissions
                  </div>
                  <div>
                    <span className="font-semibold" style={{ color: 'var(--app-accent-2)' }}>
                      {event.participant_count}
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
                  🏆 {selectedEvent.name}
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

            {/* Event Stats */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div
                className="p-4 rounded-lg text-center"
                style={{ background: 'rgba(0, 194, 179, 0.1)' }}
              >
                <div className="text-2xl font-bold" style={{ color: 'var(--app-primary)' }}>
                  {eventLeaderboard.totals.total_submissions || 0}
                </div>
                <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>
                  Total Submissions
                </div>
              </div>
              <div
                className="p-4 rounded-lg text-center"
                style={{ background: 'rgba(34, 197, 94, 0.1)' }}
              >
                <div className="text-2xl font-bold" style={{ color: '#22c55e' }}>
                  {eventLeaderboard.totals.total_approved || 0}
                </div>
                <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>
                  Approved
                </div>
              </div>
              <div
                className="p-4 rounded-lg text-center"
                style={{ background: 'rgba(157, 78, 221, 0.1)' }}
              >
                <div className="text-2xl font-bold" style={{ color: 'var(--app-accent-2)' }}>
                  {eventLeaderboard.totals.participants || 0}
                </div>
                <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>
                  Participants
                </div>
              </div>
            </div>

            {/* Leaderboard */}
            <LeaderboardTable
              data={eventLeaderboard.leaderboard}
              showCommunity={false}
              loading={leaderboardLoading}
            />
          </div>
        </div>
      )}
    </div>
  )
}
