import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="footer wrap">
      <div className="foot-inner">
        <div className="foot-legal">
          <b>Voyager's Haven LLC</b>
          Pennsylvania single-member LLC · Mechanicsburg, PA<br />
          Payments secured by Stripe · self-hosted infrastructure<br />
          © 2026 Voyager's Haven LLC
        </div>
        <div className="foot-links">
          <Link to="/work">Work</Link>
          <Link to="/hosting">Hosting</Link>
          <Link to="/about">About</Link>
          <Link to="/support">Support</Link>
          <Link to="/contact">Contact</Link>
          <Link to="/privacy">Privacy</Link>
          <Link to="/terms">Terms</Link>
        </div>
      </div>
    </footer>
  )
}
