import React, { useEffect, useState } from 'react'
import { getActiveEvents } from '../../utils/api'

// Event participation picker — opt a system/discovery submission into an active
// community competition. Mirrors ExpeditionPicker, but read-only selection:
// events are created by admins on the Events page, not inline here.
//
// Only shows events that are active AND currently in their date window for the
// chosen community (`discordTag`) and submission `kind`. When there are none,
// the picker hides itself entirely so it never adds noise to the form.
//
// Props:
//   value: number | null              currently-selected event_id
//   onChange(id|null, eventObj?)
//   discordTag: string | null         the community the submission targets
//   kind: 'submission' | 'discovery'  which event types are eligible
const TYPE_LABEL = {
  submissions: 'Systems',
  discoveries: 'Discoveries',
  both: 'Systems + Discoveries',
}

export default function EventPicker({ value, onChange, discordTag, kind = 'submission' }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!discordTag || discordTag === 'personal') {
      setEvents([])
      // Clear a stale selection if the community changed to one with no events.
      if (value) onChange(null, null)
      return
    }
    let mounted = true
    setLoading(true)
    getActiveEvents({ discordTag, kind })
      .then((d) => {
        if (!mounted) return
        const list = d.events || []
        setEvents(list)
        // Drop a selection that's no longer eligible (e.g. community changed).
        if (value && !list.some((e) => e.id === value)) onChange(null, null)
      })
      .catch(() => mounted && setEvents([]))
      .finally(() => mounted && setLoading(false))
    return () => { mounted = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [discordTag, kind])

  // Nothing to enter — keep the form clean.
  if (!loading && events.length === 0) return null

  const selected = events.find((e) => e.id === value)

  return (
    <div className="mb-3">
      <label className="block text-sm font-medium mb-1">
        🏆 Event <span className="opacity-60 font-normal">(optional)</span>
      </label>
      {selected ? (
        <div
          className="flex items-center justify-between gap-3 p-3 rounded"
          style={{ backgroundColor: 'rgba(52, 211, 153, 0.12)', border: '1px solid #34d399' }}
        >
          <div className="min-w-0">
            <span className="inline-block text-xs font-semibold mr-2" style={{ color: '#34d399' }}>
              🏆 Entered in event
            </span>
            <span className="font-semibold">{selected.name}</span>
            <span className="text-xs opacity-60 ml-2">
              {TYPE_LABEL[selected.event_type] || 'Systems'} · ends {String(selected.end_date).slice(0, 10)}
            </span>
          </div>
          <button
            type="button"
            onClick={() => onChange(null, null)}
            className="text-xs opacity-70 hover:opacity-100 underline"
          >
            Clear
          </button>
        </div>
      ) : (
        <select
          className="w-full p-2 rounded"
          style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
          value={value || ''}
          onChange={(e) => {
            const id = e.target.value ? Number(e.target.value) : null
            onChange(id, events.find((x) => x.id === id) || null)
          }}
          disabled={loading}
        >
          <option value="">{loading ? 'Loading…' : '— Not entering an event —'}</option>
          {events.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name} ({TYPE_LABEL[e.event_type] || 'Systems'})
            </option>
          ))}
        </select>
      )}
      <p className="text-xs opacity-60 mt-1">
        Counts toward the event leaderboard once your submission is approved.
      </p>
    </div>
  )
}
