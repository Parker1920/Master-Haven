import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'

const LINKS = [
  { to: '/work', label: 'Work' },
  { to: '/hosting', label: 'Hosting' },
  { to: '/about', label: 'About' },
  { to: '/shop', label: 'Shop' },
  { to: '/support', label: 'Support' },
]

export default function Nav() {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)

  return (
    <nav className="nav">
      <div className="nav-inner">
        <Link to="/" className="brand" onClick={close}>
          <div className="mark" />
          <div>
            <b>Voyager's Haven</b>
            <span>SOFTWARE STUDIO</span>
          </div>
        </Link>

        <div className={`nav-links${open ? ' open' : ''}`}>
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              onClick={close}
              className={({ isActive }) => (isActive ? 'active' : undefined)}
            >
              {l.label}
            </NavLink>
          ))}
          <Link className="nav-cta" to="/contact" onClick={close}>Start a project</Link>
        </div>

        <button className="nav-toggle" aria-label="Menu" onClick={() => setOpen((o) => !o)}>☰</button>
      </div>
    </nav>
  )
}
