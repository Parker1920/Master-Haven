// Festival team / credits. Hardcoded per the site's "details live in code"
// convention (only the civ list is dynamic). [name, org|null, role].
const TEAM = [
  ['Jenness & Agent Spike', null, 'Festival MCs'],
  ['Art3mis', null, 'Lead moderation · created Viobot'],
  ['Santa & Bread Pirate', null, 'Moderation'],
  ['Mjstral', null, 'Sponsor · Service bot — free Corvette delivery during Happy Hour'],
  ['Ekimo', null, 'Website'],
]

export default function Footer() {
  return (
    <footer>
      <section className="footer-credits" aria-label="Festival team">
        <h2 className="footer-credits-title">
          <span aria-hidden="true">☀</span> Made possible by <span aria-hidden="true">☀</span>
        </h2>
        <ul className="footer-credits-list">
          {TEAM.map(([name, org, role]) => (
            <li className="footer-credit" key={name}>
              <span className="footer-credit-name">
                {name}
                {org && <span className="footer-credit-org"> · {org}</span>}
              </span>
              <span className="footer-credit-role">{role}</span>
            </li>
          ))}
        </ul>
      </section>

      <p className="credit">Summer Grand Festival · 2026</p>
      <p style={{ marginTop: '0.8rem', fontSize: '0.75rem' }}>
        In the spirit of the original beacon — groups of similar minds, finding one another.
      </p>
    </footer>
  )
}
