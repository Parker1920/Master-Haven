import { useLayoutEffect, useRef, useState } from 'react'
import DiscordLink from './DiscordLink.jsx'

export default function CivCard({ civ, discordUrl }) {
  // Every participating civilization is a host in its own way — the public
  // roster shows them all as Host. (Admin still shows the real status for management.)
  const [expanded, setExpanded] = useState(false)
  const [overflowing, setOverflowing] = useState(false)
  const pRef = useRef(null)

  // Detect whether the (collapsed) description actually overflows its clamp, so
  // the "Read more" button only appears when there's more to read. Re-measure
  // on resize since the clamp height depends on column width.
  useLayoutEffect(() => {
    const el = pRef.current
    if (!el) return
    const measure = () => {
      // Only meaningful while collapsed; when expanded there's no clamp to overflow.
      if (expanded) return
      setOverflowing(el.scrollHeight > el.clientHeight + 1)
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [civ.description, expanded])

  return (
    <div className="civ-card">
      {civ.logo_url && (
        <img className="civ-logo" src={civ.logo_url} alt={`${civ.name} emblem`} loading="lazy" />
      )}
      <div className="badge host">★ Host</div>
      <h3>{civ.name}</h3>
      <div className="role">{civ.role}</div>
      <p ref={pRef} className={expanded ? '' : 'clamped'}>{civ.description}</p>
      {(overflowing || expanded) && (
        <button
          type="button"
          className="civ-readmore"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          {expanded ? 'Show less ▲' : 'Read more …'}
        </button>
      )}
      {discordUrl && (
        <div className="civ-discord">
          <DiscordLink url={discordUrl} label="Join this Discord" />
        </div>
      )}
    </div>
  )
}
