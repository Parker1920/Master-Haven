import { useNavigate } from 'react-router-dom'
import { DISCORD_INVITE_URL } from '../config.js'

const ROLES = [
  ['🎟️', 'Attend', 'Show up, explore the grounds, take photos, race your friends. No commitment.'],
  ['🏗️', 'Build', 'Contribute a base on the host planet — pavilion, gathering hall, themed venue.'],
  ['🎤', 'Host an Event', "Run a contest, race, tour, or clinic. We'll add it to the schedule."],
]

const FAQ = [
  ['Do I need to be in a civilization?', 'No. Solo travelers are welcome — many UD attendees over the years have come unaffiliated. Bring yourself, that\'s enough.'],
  ['Which platform / save mode?', 'Cross-platform play means PC, PlayStation, Xbox, and Switch can all meet up. Normal save recommended; multiplayer features are limited on permadeath.'],
  ['Will there be a winter UD too?', 'Yes. The end-of-year UD remains the main annual event — December 2026 will be the 10th. Summer UD is the new mid-year addition, not a replacement.'],
  ['Can my civilization host a build?', 'Yes. Reach out in Discord — host system coordinates and a build slot will be assigned once the host planet is finalized.'],
  ["What's the dress code?", 'Loud. Bring your brightest exosuit, your weirdest ship, and your most photogenic exocraft. Festival rules apply.'],
]

export default function SignUp() {
  const navigate = useNavigate()

  const onDiscord = () => {
    if (DISCORD_INVITE_URL) window.open(DISCORD_INVITE_URL, '_blank', 'noopener')
    else
      alert(
        'The Discord invite link will be added here once it’s finalized. In the meantime, reach the organizers through the Voyager’s Haven community.'
      )
  }

  return (
    <main className="page active">
      <section className="signup-hero">
        <h1>Join the Festival</h1>
        <p>
          Whether you want to attend, build, host, or just wander the festival grounds in good
          company — there's a place for you at the gathering.
        </p>
      </section>

      <section className="signup-body">
        <div className="signup-inner">
          <div className="signup-card">
            <h2>Three Ways to Take Part</h2>
            <p>
              Pick what fits your time and energy. All paths lead to the same Discord — RSVPs and
              coordination happen there.
            </p>

            <div className="signup-roles">
              {ROLES.map(([ico, title, body]) => (
                <div className="signup-role" key={title}>
                  <div className="ico">{ico}</div>
                  <div>
                    <h4>{title}</h4>
                    <p>{body}</p>
                  </div>
                </div>
              ))}
            </div>

            <button className="signup-discord" onClick={onDiscord}>
              ▸ Open the Discord
            </button>
            <p style={{ fontSize: '0.78rem', opacity: 0.6, marginTop: '1rem', marginBottom: 0 }}>
              Already in the server? Head to <code>#summer-ud-signup</code>.
            </p>

            <div className="signup-civ-cta">
              <span>Representing a civilization?</span>
              <button className="link-btn" onClick={() => navigate('/whos-going/submit')}>
                Add your civ to the roster →
              </button>
            </div>
          </div>

          <div>
            <h2 className="faq-heading">FAQ</h2>
            <div className="signup-faq">
              {FAQ.map(([q, a]) => (
                <details className="faq-item" key={q}>
                  <summary>{q}</summary>
                  <p>{a}</p>
                </details>
              ))}
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
