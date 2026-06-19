import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useCountdown from '../hooks/useCountdown.js'
import { getSchedule } from '../api.js'
import { DISCORD_INVITE_URL } from '../config.js'
import { activityIcon, activityNote, deriveActivities } from '../scheduleUtils.js'
import GlyphStrip from '../components/GlyphStrip.jsx'

const HOME_TEASER_COUNT = 6

export default function Main() {
  const navigate = useNavigate()
  const { days, hours, mins, secs } = useCountdown()
  const [schedule, setSchedule] = useState(null) // null = loading
  const [schedErr, setSchedErr] = useState(null)

  useEffect(() => {
    let alive = true
    getSchedule()
      .then((d) => alive && setSchedule(d))
      .catch((e) => alive && setSchedErr(e.message))
    return () => {
      alive = false
    }
  }, [])

  const activities = deriveActivities(schedule?.days)
  const teaser = activities.slice(0, HOME_TEASER_COUNT)

  // Hero CTA jumps straight into the festival Discord; if no invite is set yet,
  // fall back to the Sign Up page (same pattern as the nav Discord button).
  const onJoin = () => {
    if (DISCORD_INVITE_URL) window.open(DISCORD_INVITE_URL, '_blank', 'noopener')
    else navigate('/signup')
  }

  return (
    <main className="page active">
      <section className="hero">
        <div className="stars" />

        <div className="firework fw1" />
        <div className="firework fw2" />
        <div className="firework fw3" />
        <div className="firework fw4" />

        <div className="bulb-string">
          {Array.from({ length: 30 }).map((_, i) => (
            <span className="bulb" key={i} />
          ))}
        </div>
        <div className="skyline" />

        <div className="hero-content">
          <div className="hero-eyebrow">★ A NEW MID-YEAR TRADITION ★</div>
          {/* NMS wordmark "1st Annual GRAND FESTIVAL 2026 — NO MAN'S SKY".
              Keeps an <h1> for SEO/screen-readers via aria-label on the picture
              and an offscreen <span>. */}
          <picture className="hero-wordmark-wrap">
            <source srcSet="/branding/wordmark.webp" type="image/webp" />
            <img
              className="hero-wordmark"
              src="/branding/wordmark.png"
              alt="1st Annual Grand Festival 2026 — No Man's Sky"
              fetchpriority="high"
            />
          </picture>
          <h1 className="visually-hidden">1st Annual Grand Festival 2026 — No Man's Sky</h1>
          <p className="hero-subtitle">
            Once a year was never enough. The Grand Festival returns — Trade Lords, travelers, and
            every alliance gathering on grass-green plains under summer skies.
          </p>
          <div className="hero-meta">
            <div className="hero-meta-pill"><strong>WHEN</strong> June 19–21, 2026</div>
            <div className="hero-meta-pill"><strong>WHERE</strong>{schedule?.main_system ? <GlyphStrip code={schedule.main_system} size="sm" /> : ' Host system TBD'}</div>
            <div className="hero-meta-pill"><strong>WHO</strong> All civilizations welcome</div>
          </div>
          <button className="hero-cta" onClick={onJoin}>
            Join the Festival ▸
          </button>
        </div>
      </section>

      <section className="countdown-section">
        <div className="countdown-label">★ Festival Begins In ★</div>
        <div className="countdown">
          <div className="countdown-unit"><div className="countdown-num">{days}</div><div className="countdown-unit-label">Days</div></div>
          <div className="countdown-unit"><div className="countdown-num">{hours}</div><div className="countdown-unit-label">Hours</div></div>
          <div className="countdown-unit"><div className="countdown-num">{mins}</div><div className="countdown-unit-label">Minutes</div></div>
          <div className="countdown-unit"><div className="countdown-num">{secs}</div><div className="countdown-unit-label">Seconds</div></div>
        </div>
      </section>

      <section className="highlights">
        <div className="highlights-inner">
          <h2 className="section-title">
            What's Happening<span className="kzzt-cursor" aria-hidden="true">_</span>
          </h2>
          <p className="section-sub">
            The real lineup — pulled live from the festival schedule. Four days, Friday 19 to
            Sunday 21 June 2026, peaking on the Summer Solstice.
          </p>

          {schedErr && <div className="state-msg error">Couldn't load the lineup ({schedErr}).</div>}
          {schedule === null && !schedErr && <div className="state-msg">Loading the lineup…</div>}
          {schedule !== null && !schedErr && activities.length === 0 && (
            <div className="state-msg muted">Activities will appear here as hosts confirm them.</div>
          )}

          {teaser.length > 0 && (
            <>
              <div className="hl-grid">
                {teaser.map((a, i) => (
                  <div className="hl-card" key={i}>
                    <span className="hl-icon">{activityIcon(a)}</span>
                    <h3>{a.event || a.host}</h3>
                    <p>{activityNote(a)}</p>
                  </div>
                ))}
              </div>
              <div style={{ textAlign: 'center', marginTop: '2.5rem' }}>
                <button className="hero-cta" onClick={() => navigate('/whos-going')}>
                  See all {activities.length} activities &amp; the schedule ▸
                </button>
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  )
}
