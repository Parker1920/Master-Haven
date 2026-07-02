import { useEffect, useState } from 'react'
import {
  adminLogin,
  adminLogout,
  adminMe,
  getAdminInquiries,
  getAdminPayments,
  getAdminSummary,
  setInquiryHandled,
} from '../api'

const money = (cents) => `$${(cents / 100).toFixed(2)}`
const fmt = (s) => (s ? s.replace('T', ' ').slice(0, 16) : '—')

export default function Admin() {
  const [phase, setPhase] = useState('checking') // checking | login | in
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState('inquiries')
  const [summary, setSummary] = useState(null)
  const [inquiries, setInquiries] = useState([])
  const [payments, setPayments] = useState([])

  async function load() {
    const [s, i, p] = await Promise.all([getAdminSummary(), getAdminInquiries(), getAdminPayments()])
    setSummary(s)
    setInquiries(i)
    setPayments(p)
  }

  useEffect(() => {
    adminMe()
      .then(async () => { await load(); setPhase('in') })
      .catch(() => setPhase('login'))
  }, [])

  async function doLogin(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await adminLogin(password)
      await load()
      setPhase('in')
      setPassword('')
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  async function doLogout() {
    try { await adminLogout() } catch { /* ignore */ }
    setPhase('login')
    setSummary(null)
    setInquiries([])
    setPayments([])
  }

  async function toggleHandled(q) {
    const next = q.handled ? 0 : 1
    try {
      await setInquiryHandled(q.id, !!next)
      setInquiries((list) => list.map((x) => (x.id === q.id ? { ...x, handled: next } : x)))
      setSummary((s) => (s ? { ...s, new_inquiries: s.new_inquiries + (next ? -1 : 1) } : s))
    } catch (err) {
      setError(err.message)
    }
  }

  if (phase === 'checking') {
    return <div className="page"><p style={{ color: 'var(--dim)' }}>Checking session…</p></div>
  }

  if (phase === 'login') {
    return (
      <div className="admin-login">
        <form className="form-card" onSubmit={doLogin} style={{ maxWidth: 380, width: '100%' }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>Admin</div>
          <h2 style={{ fontSize: 22, marginBottom: 18 }}>Voyager's Haven console</h2>
          <div className="field">
            <label>Password</label>
            <input type="password" value={password} autoFocus onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
          {error && <p style={{ color: 'var(--amber)', fontSize: 13, margin: '-4px 0 14px' }}>{error}</p>}
          <button className="pay-primary" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        </form>
      </div>
    )
  }

  return (
    <div className="admin wrap">
      <div className="admin-head">
        <div>
          <span className="eyebrow">Admin console</span>
          <h1>Submissions</h1>
        </div>
        <button className="pay-secondary" style={{ width: 'auto', marginTop: 0, padding: '10px 18px' }} onClick={doLogout}>Log out</button>
      </div>

      {summary && (
        <div className="admin-stats">
          <div className="astat"><div className="n">{summary.new_inquiries}</div><div className="l">New inquiries</div></div>
          <div className="astat"><div className="n">{summary.inquiries}</div><div className="l">Total inquiries</div></div>
          <div className="astat"><div className="n">{summary.payments_paid}</div><div className="l">Payments (paid)</div></div>
        </div>
      )}

      <div className="mode-switch" style={{ margin: '4px 0 24px' }}>
        <button className={tab === 'inquiries' ? 'on' : ''} onClick={() => setTab('inquiries')}>Inquiries ({inquiries.length})</button>
        <button className={tab === 'payments' ? 'on' : ''} onClick={() => setTab('payments')}>Payments ({payments.length})</button>
      </div>

      {tab === 'inquiries' && (
        <div className="admin-inquiries">
          {inquiries.length === 0 && <p style={{ color: 'var(--dim)' }}>No inquiries yet.</p>}
          {inquiries.map((q) => (
            <div className={`inq-card${q.handled ? ' done' : ''}`} key={q.id}>
              <div className="inq-top">
                <div>
                  <span className={`pill ${q.handled ? 'p-live' : 'p-client'}`}>{q.handled ? 'Handled' : 'New'}</span>
                  <span className="inq-name" style={{ marginLeft: 10 }}>{q.name}</span>
                  <a className="inq-email" href={`mailto:${q.email}`}>{q.email}</a>
                </div>
                <span className="inq-date">{fmt(q.created_at)}</span>
              </div>
              <div className="inq-meta">
                {q.project_type && <span className="tag">{q.project_type}</span>}
                {q.budget && <span className="tag">{q.budget}</span>}
              </div>
              <p className="inq-msg">{q.message}</p>
              <div className="inq-actions">
                <a className="head-link" href={`mailto:${q.email}?subject=Re: your project inquiry`}>Reply →</a>
                <button className="inq-toggle" onClick={() => toggleHandled(q)}>
                  {q.handled ? 'Mark as new' : 'Mark handled'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'payments' && (
        <div className="fleet">
          {payments.length === 0 && <p style={{ color: 'var(--dim)', padding: 14 }}>No payments yet.</p>}
          {payments.map((p) => (
            <div className="fleet-row pay-row" key={p.id}>
              <div className="fleet-name">
                {money(p.amount_cents)}
                <span className="fleet-maker"> · {p.kind}{p.invoice_number ? ` · ${p.invoice_number}` : ''}</span>
              </div>
              <div className="fleet-domain">{p.reference} · {fmt(p.created_at)}{p.email ? ` · ${p.email}` : ''}</div>
              <span className={`pill ${p.status === 'paid' ? 'p-live' : 'p-internal'}`}>{p.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
