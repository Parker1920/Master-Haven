import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCivs, getSchedule } from '../api.js'
import CivCard from '../components/CivCard.jsx'

// A location counts as "real" only if it's an actual portal address — not blank,
// not a TBA/TBD placeholder.
const realLoc = (l) => {
  const v = (l || '').trim()
  return v && !/^(tba|tbd|tbc)$/i.test(v) ? v : null
}
const realText = (t) => {
  const v = (t || '').trim()
  return v && !/^(tba|tbd|tbc)$/i.test(v) ? v : null
}

function ScheduleItem({ item }) {
  const zones = [
    item.est && `${item.est} EST`,
    item.pst && `${item.pst} PST`,
    item.aest && `${item.aest} AEST`,
  ]
    .filter(Boolean)
    .join('  ·  ')
  const title = item.host || item.event || 'TBA'
  const sub = item.host && item.event ? item.event : ''
  return (
    <div className="sched-item">
      <div className="sched-time">
        <div className="sched-gmt">{item.gmt || 'TBA'}</div>
        <div className="sched-gmt-label">GMT</div>
      </div>
      <div className="sched-body">
        <div className="sched-title">{title}</div>
        {sub && <div className="sched-sub">{sub}</div>}
        <div className="sched-meta">
          {zones && <span className="sched-zones">{zones}</span>}
          {realLoc(item.location) && <span className="sched-loc">📍 {item.location.trim()}</span>}
        </div>
      </div>
    </div>
  )
}

export default function WhosGoing() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('civs')
  const [civs, setCivs] = useState(null) // null = loading
  const [error, setError] = useState(null)
  const [schedule, setSchedule] = useState(null) // null = loading
  const [schedErr, setSchedErr] = useState(null)

  useEffect(() => {
    let alive = true
    getCivs()
      .then((data) => alive && setCivs(data))
      .catch((e) => alive && setError(e.message))
    getSchedule()
      .then((data) => alive && setSchedule(data))
      .catch((e) => alive && setSchedErr(e.message))
    return () => {
      alive = false
    }
  }, [])

  const liveDays = schedule?.days || []

  // Attractions = what communities committed to in the schedule sheet, deduped.
  // Included: any row with a stated activity, the festival opening, and reserved
  // slots whose activity is still "TBA" (e.g. NMSCord Hub). Skipped: hosts with a
  // completely blank Event cell who haven't reserved anything (Voyagers Haven,
  // PodManSky) — nothing to show for them yet.
  const attractions = []
  const seen = new Set()
  for (const day of liveDays) {
    for (const item of day.items) {
      const host = (item.host || '').trim()
      const event = realText(item.event) // null for blank / "TBA" / "TBD"
      const reserved = (item.event || '').trim() !== '' || /open/i.test(host)
      if (!host || !reserved) continue
      const key = `${host}||${event || ''}`.toLowerCase()
      if (seen.has(key)) continue
      seen.add(key)
      attractions.push({ host, event, location: item.location })
    }
  }

  return (
    <main className="page active">
      <section className="wg-hero">
        <h1>Who's Going</h1>
        <div className="wg-tabs">
          <button className={`wg-tab ${tab === 'civs' ? 'active' : ''}`} onClick={() => setTab('civs')}>Civilizations</button>
          <button className={`wg-tab ${tab === 'attractions' ? 'active' : ''}`} onClick={() => setTab('attractions')}>Attractions</button>
          <button className={`wg-tab ${tab === 'schedule' ? 'active' : ''}`} onClick={() => setTab('schedule')}>Schedule</button>
        </div>
      </section>

      <section className="wg-body">
        <div className="wg-inner">
          {tab === 'civs' && (
            <div className="wg-pane active">
              <p className="section-sub" style={{ marginBottom: '2rem' }}>
                Updated as RSVPs come in.{' '}
                <button className="link-btn" onClick={() => navigate('/whos-going/submit')}>
                  Add your civilization →
                </button>
              </p>

              {error && <div className="state-msg error">Couldn't load the roster: {error}</div>}
              {!error && civs === null && <div className="state-msg">Loading the roster…</div>}

              {!error && civs !== null && (
                <div className="civ-grid">
                  {civs.map((c) => (
                    <CivCard civ={c} key={c.id} />
                  ))}
                  <div
                    className="civ-card civ-card-cta"
                    onClick={() => navigate('/whos-going/submit')}
                  >
                    <div className="badge tentative">Open Slot</div>
                    <h3>Your Civilization</h3>
                    <div className="role">— add yours —</div>
                    <p>Want your community on this list? Submit it here and an organizer will review it.</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === 'attractions' && (
            <div className="wg-pane active">
              <p className="section-sub" style={{ marginBottom: '2rem' }}>
                What each community is bringing — pulled live from the festival schedule. Hosts who
                haven't confirmed an activity yet aren't listed.
              </p>

              {schedErr && <div className="state-msg error">Couldn't load activities ({schedErr}).</div>}
              {schedule === null && !schedErr && <div className="state-msg">Loading activities…</div>}
              {schedule !== null && !schedErr && attractions.length === 0 && (
                <div className="state-msg muted">No activities confirmed yet — check back soon.</div>
              )}

              {attractions.length > 0 && (
                <div className="attr-list attractions">
                  {attractions.map((a, i) => {
                    const title = a.event || a.host
                    const note = a.event
                      ? `Hosted by ${a.host}`
                      : /open/i.test(a.host)
                        ? 'Festival opening'
                        : 'Details to be announced'
                    return (
                      <div className="attr-item" key={i}>
                        <div className="attr-content">
                          <h4>{title}</h4>
                          <p>{note}</p>
                        </div>
                        {realLoc(a.location) && <div className="attr-host">📍 {a.location.trim()}</div>}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {tab === 'schedule' && (
            <div className="wg-pane active">
              <p className="section-sub" style={{ marginBottom: '1.6rem' }}>
                Four days under summer skies — Friday 19 to Monday 22 June 2026, peaking on the
                Solstice. Times shown in GMT · EST · PST · AEST.
                {schedule?.main_system && (
                  <>
                    {' '}Main system <code>{schedule.main_system}</code>.
                  </>
                )}
              </p>

              {schedErr && <div className="state-msg error">Couldn't load the schedule ({schedErr}).</div>}
              {schedule === null && !schedErr && <div className="state-msg">Loading the live schedule…</div>}
              {schedule !== null && !schedErr && liveDays.length === 0 && (
                <div className="state-msg muted">No sessions scheduled yet — check back soon.</div>
              )}

              {liveDays.map((day) => (
                <div className="sched-day" key={day.label}>
                  <h3 className="sched-day-label">{day.label}</h3>
                  <div className="sched-items">
                    {day.items.map((item, i) => (
                      <ScheduleItem item={item} key={i} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </main>
  )
}
