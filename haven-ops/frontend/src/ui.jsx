// Shared primitives — markup lifted from mockup v0.7 so screens stay terse.

export function Card({ title, action, children }) {
  return (
    <div className="card">
      {title && (
        <div className="card-head">
          <h3>{title}</h3>
          {action}
        </div>
      )}
      {children}
    </div>
  )
}

export function Badge({ tone = 'mute', children }) {
  return <span className={`badge b-${tone}`}>{children}</span>
}

export function Gauge({ accent, label, val, pending, foot }) {
  return (
    <div className="gauge" style={{ '--accent': `var(--${accent})` }}>
      <div className="label">{label}</div>
      <div className={`val${pending ? ' pending' : ''}`}>{val}</div>
      {foot && <div className="foot">{foot}</div>}
    </div>
  )
}

export function Row({ icon, name, meta, right }) {
  return (
    <div className="row">
      {icon && <span className="ic">{icon}</span>}
      <span className="grow">
        <span className="name">{name}</span>
        {meta && <span className="meta">{meta}</span>}
      </span>
      {right}
    </div>
  )
}

export function KV({ k, v, tone, action }) {
  return (
    <div className="kv">
      <span className="k">{k}</span>
      <span className={`v${tone ? ` ${tone}` : ''}`}>{v ?? '—'}</span>
      {action}
    </div>
  )
}

export const CheckIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#0a0d13" strokeWidth="3.5">
    <path d="M20 6L9 17l-5-5" />
  </svg>
)

// Persisted to-do row: toggling PUTs done and the caller reloads.
export function Todo({ task, onToggle }) {
  const done = Number(task.done) === 1
  return (
    <button
      className={`todo${done ? ' done' : ''}${task.priority === 'P0' ? ' mon' : ''}`}
      type="button"
      onClick={() => onToggle(task)}
    >
      <span className="box"><CheckIcon /></span>
      <span className="t">
        {task.title}
        {task.detail && <small>{task.detail}</small>}
      </span>
    </button>
  )
}

export function Cal({ when, title, detail, badge, action }) {
  return (
    <div className="cal">
      <span className="when">{when}</span>
      <span className="body">
        <span className="h">{title} {badge}</span>
        {detail && <span className="d">{detail}</span>}
      </span>
      {action}
    </div>
  )
}

// Lifecycle: inquiry → proposal → contract → in_progress → delivered → closed
export const STAGES = ['inquiry', 'proposal', 'contract', 'in_progress', 'delivered', 'closed']

export function StageBar({ state }) {
  const idx = Math.max(STAGES.indexOf(state), 0)
  const closed = state === 'closed'
  return (
    <span className="stagebar">
      {STAGES.map((s, i) => (
        <span key={s} className={`seg${closed || i < idx ? ' on' : i === idx ? ' cur' : ''}`} />
      ))}
    </span>
  )
}

export const stateLabel = (state) =>
  state === 'closed' ? 'Closed w/ receipt'
    : (state || '').replace('_', ' ').replace(/^./, (c) => c.toUpperCase())

// View (inline) + download for any document record that has a real file.
export function DocActions({ doc }) {
  if (!doc || !(doc.has_file ?? doc.sha256)) return null
  return (
    <span className="acts">
      <a className="mini teal" href={`/api/documents/${doc.id}/file`} target="_blank" rel="noreferrer">View</a>
      <a className="mini" href={`/api/documents/${doc.id}/file?dl=1`} title="Download">⤓</a>
    </span>
  )
}

export const EditBtn = ({ onClick, label = '✎' }) => (
  <button type="button" className="mini" onClick={onClick} aria-label="Edit">{label}</button>
)
