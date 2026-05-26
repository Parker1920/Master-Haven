import { useNavigate, useLocation } from 'react-router-dom'
import { DISCORD_INVITE_URL } from '../config.js'

const LINKS = [
  { label: 'Main', path: '/' },
  { label: 'About', path: '/about' },
  { label: 'Lore', path: '/lore' },
  { label: "Who's Going", path: '/whos-going' },
  { label: 'Sign Up', path: '/signup' },
]

// Rendered as <button>s (not <a>) to honor the mockup's `.nav-links button` CSS
// contract exactly.
export default function Nav() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const isActive = (path) => (path === '/' ? pathname === '/' : pathname.startsWith(path))

  const onDiscord = () => {
    if (DISCORD_INVITE_URL) window.open(DISCORD_INVITE_URL, '_blank', 'noopener')
    else navigate('/signup')
  }

  return (
    <nav className="top-nav">
      <div className="nav-inner">
        <div className="nav-logo" onClick={() => navigate('/')}>
          <img className="nav-logo-mark" src="/festival-mark.svg" alt="" aria-hidden="true" />
          GRAND FESTIVAL <span className="summer-tag">SUMMER '26</span>
        </div>
        <ul className="nav-links">
          {LINKS.map((l) => (
            <li key={l.path}>
              <button className={isActive(l.path) ? 'active' : ''} onClick={() => navigate(l.path)}>
                {l.label}
              </button>
            </li>
          ))}
        </ul>
        <button className="nav-discord" onClick={onDiscord}>
          Join Discord →
        </button>
      </div>
    </nav>
  )
}
