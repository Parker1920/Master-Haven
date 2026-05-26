import { useNavigate } from 'react-router-dom'
import useCountdown from '../hooks/useCountdown.js'

const HIGHLIGHTS = [
  ['🎆', 'Opening Ceremony', 'Multi-tool light shows, a parade of starships, and the first volley of fireworks lighting up the festival grounds at dusk.'],
  ['🏛️', 'Festival Grounds', 'Pavilions, gathering halls, and themed builds from every civilization. Wander, gawk, and find your tribe between events.'],
  ['🎲', 'Fortune & Fireworks', 'Gambling halls in the Trade Lord tradition — community-run games of chance, prizes, and skyward sparks at every win.'],
  ['🏁', 'Exocraft Races', 'The classic UD tradition — high-speed runs across grasslands and ridges with prizes for fastest, weirdest, and most photogenic.'],
  ['📸', 'Photo Mode Hunt', 'A scavenger hunt across host worlds with themed prompts. Winners featured on the official UD Summer site.'],
  ['🎤', 'Closing Ceremony', 'Group photo, ambassador speeches, fireworks finale, and the symbolic baton-pass to UD-Winter ’26.'],
]

export default function Main() {
  const navigate = useNavigate()
  const { days, hours, mins, secs } = useCountdown()

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
          <h1 className="hero-title">
            SUMMER<br />
            <span className="accent">GRAND FESTIVAL</span>
          </h1>
          <p className="hero-subtitle">
            Once a year was never enough. The Grand Festival returns — Trade Lords, travelers, and
            every alliance gathering on grass-green plains under summer skies.
          </p>
          <div className="hero-meta">
            <div className="hero-meta-pill"><strong>WHEN</strong> June 19–21, 2026</div>
            <div className="hero-meta-pill"><strong>WHERE</strong> Host system TBD</div>
            <div className="hero-meta-pill"><strong>WHO</strong> All civilizations welcome</div>
          </div>
          <button className="hero-cta" onClick={() => navigate('/signup')}>
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
          <h2 className="section-title">The Grand Festival</h2>
          <p className="section-sub">
            A gathering of Trade Lords, travelers, and every wandering soul — across alliances,
            across galaxies
          </p>

          <div className="hl-grid">
            {HIGHLIGHTS.map(([icon, title, body]) => (
              <div className="hl-card" key={title}>
                <span className="hl-icon">{icon}</span>
                <h3>{title}</h3>
                <p>{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  )
}
