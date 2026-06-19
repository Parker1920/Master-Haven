import React, { useState, useEffect, useContext } from 'react'
import { Link } from 'react-router-dom'
import LeaderboardTable from '../components/LeaderboardTable'
import { AuthContext } from '../utils/AuthContext'
import { formatDate } from '../hooks/useDateFormat'
import { getPublicEvents, getPublicEventLeaderboard } from '../utils/api'

/**
 * Public Community Events showcase — Route: /events (no auth).
 *
 * Read-only view of active competitions and their live, approved-only
 * leaderboards. Admins create + manage events at /events/manage (and via the
 * Analytics Hub → Events tab). A submission joins an event by picking it in the
 * wizard / discovery modal; only APPROVED, event-tagged rows score.
 */

const EVENT_TYPE_LABELS = {
  submissions: { label: 'Systems', icon: '🌌', pill: 'pill-teal' },
  discoveries: { label: 'Discoveries', icon: '🔬', pill: 'pill-purple' },
  both: { label: 'Systems + Discoveries', icon: '🏆', pill: 'pill-emerald' },
}

const STATUS_PILL = {
  active: 'pill-emerald',
  upcoming: 'pill-amber',
  ended: 'pill-muted',
  inactive: 'pill-muted',
}

const STATUS_LABEL = {
  active: 'Active',
  upcoming: 'Upcoming',
  ended: 'Ended',
  inactive: 'Inactive',
}

export default function EventsPublic() {
  const { isAdmin } = useContext(AuthContext)

  const [loading, setLoading] = useState(true)
  const [events, setEvents] = useState([])
  const [error, setError] = useState('')

  // Leaderboard modal
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [tab, setTab] = useState('submissions')
  const [board, setBoard] = useState({ leaderboard: [], totals: {} })
  const [boardLoading, setBoardLoading] = useState(false)

  useEffect(() => {
    let mounted = true
    getPublicEvents()
      .then((d) => { if (mounted) setEvents(d.events || []) })
      .catch(() => mounted && setError('Could not load events right now.'))
      .finally(() => mounted && setLoading(false))
    return () => { mounted = false }
  }, [])

  const availableTabs = (event) => {
    const t = event?.event_type || 'submissions'
    if (t === 'submissions') return ['submissions']
    if (t === 'discoveries') return ['discoveries']
    return ['combined', 'submissions', 'discoveries']
  }

  const openLeaderboard = async (event, nextTab = null) => {
    const t = event.event_type || 'submissions'
    const defaultTab = t === 'discoveries' ? 'discoveries' : t === 'both' ? 'combined' : 'submissions'
    const useTab = nextTab || defaultTab
    setSelectedEvent(event)
    setTab(useTab)
    setBoardLoading(true)
    try {
      const d = await getPublicEventLeaderboard(event.id, useTab)
      setBoard({ leaderboard: d.leaderboard || [], totals: d.totals || {} })
    } catch {
      setBoard({ leaderboard: [], totals: {} })
    } finally {
      setBoardLoading(false)
    }
  }

  // Group by lifecycle for sectioned display.
  const groups = { active: [], upcoming: [], ended: [] }
  for (const e of events) {
    const s = e.status || 'active'
    ;(groups[s] || groups.active).push(e)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--app-bg)' }}>
        <div className="animate-spin rounded-full h-12 w-12 border-b-2" style={{ borderColor: 'var(--app-primary)' }}></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-6" style={{ background: 'var(--app-bg)' }}>
      <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--app-text)' }}>
            <span>🏆</span> Community Events
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--app-text)', opacity: 0.65 }}>
            Live competitions across the Haven communities. Enter one by picking it when you
            submit a system or discovery — only approved entries score.
          </p>
        </div>
        {isAdmin && (
          <Link to="/events/manage" className="haven-btn-ghost px-4 py-2 rounded-lg text-sm">
            Manage events →
          </Link>
        )}
      </div>

      {error && (
        <div className="haven-card p-4 mb-4 text-sm" style={{ color: 'var(--app-accent-amber)' }}>
          {error}
        </div>
      )}

      {events.length === 0 ? (
        <div className="haven-card p-12 text-center">
          <div className="text-4xl mb-4">📅</div>
          <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--app-text)' }}>No Active Events</h3>
          <p className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
            There are no community competitions running right now. Check back soon!
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          <EventSection title="Active Now" events={groups.active} onView={openLeaderboard} highlight />
          <EventSection title="Upcoming" events={groups.upcoming} onView={openLeaderboard} />
          <EventSection title="Past Events" events={groups.ended} onView={openLeaderboard} />
        </div>
      )}

      {/* Leaderboard Modal */}
      {selectedEvent && (
        <div className="haven-modal" onClick={() => setSelectedEvent(null)}>
          <div className="haven-modal-panel haven-modal-panel-wide" onClick={(e) => e.stopPropagation()}>
            <div className="haven-modal-header">
              <div>
                <div style={{ color: 'var(--app-text)' }}>
                  {(EVENT_TYPE_LABELS[selectedEvent.event_type] || EVENT_TYPE_LABELS.submissions).icon}{' '}
                  {selectedEvent.name}
                </div>
                <p className="text-sm mt-1 font-normal" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
                  {formatDate(selectedEvent.start_date)} – {formatDate(selectedEvent.end_date)} · {selectedEvent.discord_tag}
                </p>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="p-2 rounded-lg transition-colors hover:bg-white/10"
                style={{ color: 'var(--app-text)' }}
                aria-label="Close"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="haven-modal-body">
              {availableTabs(selectedEvent).length > 1 && (
                <div className="haven-card flex items-center rounded-lg overflow-hidden mb-4">
                  {availableTabs(selectedEvent).map((t) => (
                    <button
                      key={t}
                      onClick={() => openLeaderboard(selectedEvent, t)}
                      className="px-4 py-2 text-sm font-medium transition-colors flex-1"
                      style={{
                        background: tab === t ? 'var(--app-primary)' : 'transparent',
                        color: tab === t ? '#000' : 'var(--app-text)',
                      }}
                    >
                      {t === 'submissions' ? 'Systems' : t === 'discoveries' ? 'Discoveries' : 'Combined'}
                    </button>
                  ))}
                </div>
              )}

              <BoardTotals tab={tab} totals={board.totals} />

              {tab === 'discoveries' ? (
                <DiscoveryLeaderboard data={board.leaderboard} loading={boardLoading} />
              ) : tab === 'combined' ? (
                <CombinedLeaderboard data={board.leaderboard} loading={boardLoading} />
              ) : (
                <LeaderboardTable data={board.leaderboard} showCommunity={false} loading={boardLoading} />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function EventSection({ title, events, onView, highlight }) {
  if (!events || events.length === 0) return null
  return (
    <div>
      <h2 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--app-accent-3)' }}>
        {title}
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {events.map((event) => (
          <EventCard key={event.id} event={event} onView={onView} highlight={highlight} />
        ))}
      </div>
    </div>
  )
}

function EventCard({ event, onView, highlight }) {
  const typeInfo = EVENT_TYPE_LABELS[event.event_type] || EVENT_TYPE_LABELS.submissions
  const status = event.status || 'active'
  const eventType = event.event_type || 'submissions'
  const participants = Math.max(event.participant_count || 0, event.discovery_participant_count || 0)
  return (
    <div
      className="haven-card haven-card-hover p-4"
      style={highlight ? { borderColor: 'rgba(52, 211, 153, 0.4)' } : undefined}
    >
      <div className="flex items-start justify-between mb-3 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-2xl">{typeInfo.icon}</span>
          <div className="min-w-0">
            <h3 className="font-semibold truncate" style={{ color: 'var(--app-text)' }}>{event.name}</h3>
            <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
              <span className={`pill ${STATUS_PILL[status]}`}>{STATUS_LABEL[status]}</span>
              <span className={`pill ${typeInfo.pill}`}>{typeInfo.label}</span>
            </div>
          </div>
        </div>
        <span className="pill pill-teal shrink-0">{event.discord_tag}</span>
      </div>

      <div className="text-sm mb-3" style={{ color: 'var(--app-text)', opacity: 0.7 }}>
        {formatDate(event.start_date)} – {formatDate(event.end_date)}
      </div>

      {event.description && (
        <p className="text-sm mb-3" style={{ color: 'var(--app-text)', opacity: 0.6 }}>
          {event.description}
        </p>
      )}

      <div className="flex items-center gap-4 mb-4 text-sm flex-wrap" style={{ color: 'var(--app-text)' }}>
        {(eventType === 'submissions' || eventType === 'both') && (
          <div><span className="font-semibold" style={{ color: 'var(--app-primary)' }}>{event.submission_count || 0}</span> systems</div>
        )}
        {(eventType === 'discoveries' || eventType === 'both') && (
          <div><span className="font-semibold" style={{ color: 'var(--app-accent-2)' }}>{event.discovery_count || 0}</span> discoveries</div>
        )}
        <div><span className="font-semibold" style={{ color: 'var(--app-accent-2)' }}>{participants}</span> participants</div>
      </div>

      <button
        onClick={() => onView(event)}
        className="haven-btn-ghost w-full px-3 py-2 rounded-lg text-sm font-medium"
        style={{ color: 'var(--app-primary)', borderColor: 'rgba(0, 194, 179, 0.3)' }}
      >
        View Leaderboard
      </button>
    </div>
  )
}

function BoardTotals({ tab, totals }) {
  const cards =
    tab === 'discoveries'
      ? [
          ['Discoveries', totals.total_discoveries || 0, 'var(--app-accent-2)'],
          ['Discoverers', totals.participants || 0, 'var(--app-accent-2)'],
        ]
      : tab === 'combined'
      ? [
          ['Systems', totals.total_submissions || 0, 'var(--app-primary)'],
          ['Discoveries', totals.total_discoveries || 0, 'var(--app-accent-2)'],
          ['Combined', totals.combined_total || 0, 'var(--app-accent-amber)'],
          ['Participants', totals.participants || 0, 'var(--app-accent-2)'],
        ]
      : [
          ['Systems', totals.total_submissions || 0, 'var(--app-primary)'],
          ['Participants', totals.participants || 0, 'var(--app-accent-2)'],
        ]
  // Static classes only — Tailwind JIT can't see interpolated class names.
  const colClass = { 2: 'grid-cols-2', 3: 'grid-cols-2 md:grid-cols-3', 4: 'grid-cols-2 md:grid-cols-4' }[cards.length] || 'grid-cols-2'
  return (
    <div className={`grid gap-4 mb-6 ${colClass}`}>
      {cards.map(([label, value, color]) => (
        <div key={label} className="haven-card p-3 text-center">
          <div className="text-2xl font-bold" style={{ color }}>{value}</div>
          <div className="text-sm" style={{ color: 'var(--app-text)', opacity: 0.7 }}>{label}</div>
        </div>
      ))}
    </div>
  )
}

function DiscoveryLeaderboard({ data, loading }) {
  if (loading) return <div className="text-center py-8" style={{ color: 'var(--muted)' }}>Loading leaderboard…</div>
  if (!data || data.length === 0) return <div className="text-center py-8" style={{ color: 'var(--muted)' }}>No discoveries entered in this event yet.</div>
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
              <td className="py-3 px-2"><RankBadge rank={entry.rank} /></td>
              <td className="py-3 px-2 font-medium" style={{ color: 'var(--app-text)' }}>{entry.username}</td>
              <td className="py-3 px-2 text-right font-semibold" style={{ color: 'var(--app-accent-2)' }}>{entry.total_discoveries}</td>
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
  if (loading) return <div className="text-center py-8" style={{ color: 'var(--muted)' }}>Loading leaderboard…</div>
  if (!data || data.length === 0) return <div className="text-center py-8" style={{ color: 'var(--muted)' }}>No activity entered in this event yet.</div>
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
              <td className="py-3 px-2"><RankBadge rank={entry.rank} /></td>
              <td className="py-3 px-2 font-medium" style={{ color: 'var(--app-text)' }}>{entry.username}</td>
              <td className="py-3 px-2 text-right" style={{ color: 'var(--app-primary)' }}>{entry.total_submissions}</td>
              <td className="py-3 px-2 text-right" style={{ color: 'var(--app-accent-2)' }}>{entry.total_discoveries}</td>
              <td className="py-3 px-2 text-right font-semibold" style={{ color: 'var(--app-accent-amber)' }}>{entry.combined_total}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RankBadge({ rank }) {
  const label = rank <= 3 ? ['', '1st', '2nd', '3rd'][rank] : `#${rank}`
  return (
    <span className={`font-bold ${rank <= 3 ? 'text-amber-400' : ''}`} style={{ color: rank > 3 ? 'var(--app-text)' : undefined }}>
      {label}
    </span>
  )
}
