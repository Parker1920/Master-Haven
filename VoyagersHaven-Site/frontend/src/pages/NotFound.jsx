import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="page" style={{ textAlign: 'center' }}>
      <div className="eyebrow" style={{ display: 'block', marginBottom: 14 }}>404</div>
      <h1>Off the charted map</h1>
      <p style={{ maxWidth: '46ch', margin: '0 auto 8px' }}>
        This page doesn't exist — it may have moved, or the link was mistyped.
      </p>
      <Link className="back" to="/">← Back to Voyager's Haven</Link>
    </div>
  )
}
