import { useEffect, useState } from 'react'
import banner from './assets/brand-banner.png'
import DocModal from './components/DocModal.jsx'
import Company from './screens/Company.jsx'
import Compliance from './screens/Compliance.jsx'
import EngagementDetail from './screens/EngagementDetail.jsx'
import Ledger from './screens/Ledger.jsx'
import Overview from './screens/Overview.jsx'
import Registry from './screens/Registry.jsx'
import Work from './screens/Work.jsx'
import { ToastProvider } from './toast.jsx'

// Bottom tabs — icons lifted from mockup v0.7.
const TABS = [
  { key: 'overview', label: 'Overview', icon: <><circle cx="12" cy="12" r="9" /><path d="M15.5 8.5l-2 5.5-5 2 2-5.5z" /></> },
  { key: 'engagements', label: 'Work', icon: <><path d="M7 3h7l4 4v14H7z" /><path d="M13 3v5h5M10 13h5M10 17h5" /></> },
  { key: 'ledger', label: 'Ledger', icon: <><path d="M4 5h16v14H4z" /><path d="M4 9h16M9 9v10" /></> },
  { key: 'registry', label: 'Registry', icon: <><path d="M6 3h9l4 4v14H6z" /><path d="M14 3v5h5M9 13h7M9 17h7" /></> },
  { key: 'compliance', label: 'Compliance', icon: <><path d="M9 11l2 2 4-4" /><path d="M5 4h14v16H5z" /></> },
]

export default function App() {
  const [screen, setScreen] = useState('overview')
  const [engagementId, setEngagementId] = useState(null)
  const [docModalOpen, setDocModalOpen] = useState(false)
  const [apiOk, setApiOk] = useState(null)

  useEffect(() => {
    fetch('/api/health').then((r) => r.json()).then((d) => setApiOk(!!d.ok)).catch(() => setApiOk(false))
  }, [])

  // Mirrors the mockup's showScreen(): pure state, no anchor navigation.
  const nav = (target, id = null) => {
    if (id != null) setEngagementId(id)
    setScreen(target)
    window.scrollTo(0, 0)
  }

  const activeTab = screen === 'engagement' ? 'engagements' : screen
  const screens = {
    overview: <Overview nav={nav} />,
    engagements: <Work nav={nav} />,
    engagement: <EngagementDetail nav={nav} engagementId={engagementId} />,
    ledger: <Ledger nav={nav} />,
    registry: <Registry nav={nav} />,
    compliance: <Compliance nav={nav} />,
    company: <Company nav={nav} openDocModal={() => setDocModalOpen(true)} />,
  }

  return (
    <ToastProvider>
      <div className="bg-layer" />
      <header className="appbar">
        <span className="brandplate"><img className="brand" src={banner} alt="Voyager's Haven LLC" /></span>
        <span className="opstag">OPS</span>
        <button type="button" className="co-btn" aria-label="Company" onClick={() => nav('company')}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M4 20V8l8-4 8 4v12" /><path d="M9 20v-6h6v6" />
          </svg>
        </button>
        <div className={`lock${apiOk == null ? '' : apiOk ? ' ok' : ' bad'}`}>
          <span className="dot" />Tailnet
        </div>
      </header>

      {/* keyed so the rise animation replays per screen, like the mockup */}
      <section className="screen" key={screen === 'engagement' ? `eng-${engagementId}` : screen}>
        {screens[screen]}
      </section>

      <nav className="tabbar">
        {TABS.map((t) => (
          <button key={t.key} type="button" className={`tab${activeTab === t.key ? ' active' : ''}`} onClick={() => nav(t.key)}>
            <svg viewBox="0 0 24 24">{t.icon}</svg>
            <span>{t.label}</span>
          </button>
        ))}
      </nav>

      <DocModal open={docModalOpen} onClose={() => setDocModalOpen(false)} />
    </ToastProvider>
  )
}
