import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getReceipt } from '../api'
import { CONTACT_EMAIL } from '../data/site'

const money = (c) => `$${(c / 100).toFixed(2)}`
const fmtDate = (s) => {
  if (!s) return '—'
  const d = new Date(s.includes('T') ? s : s.replace(' ', 'T') + 'Z')
  return isNaN(d) ? s : d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
}

// Public, printable receipt for any PAID invoice — the "with this receipt" end of
// the inquiry -> invoice -> receipt trail. Works for simulated, manual, and Stripe.
export default function Receipt() {
  const { number } = useParams()
  const [rc, setRc] = useState(undefined) // undefined = loading, null = not found
  const [err, setErr] = useState('')

  useEffect(() => {
    let live = true
    getReceipt(number).then((r) => live && setRc(r)).catch((e) => { if (live) { setErr(e.message); setRc(null) } })
    return () => { live = false }
  }, [number])

  if (rc === undefined) return <div className="section wrap"><p style={{ color: 'var(--dim)' }}>Loading receipt…</p></div>
  if (!rc) return (
    <div className="section wrap">
      <h1 style={{ fontSize: 26, marginBottom: 8 }}>Receipt unavailable</h1>
      <p style={{ color: 'var(--dim)' }}>{err || 'We couldn’t find a paid invoice with that number.'}</p>
    </div>
  )

  return (
    <div className="section wrap receipt-page">
      <div className="receipt-doc">
        <div className="receipt-head">
          <div>
            <div className="receipt-brand">Voyager's Haven <span>LLC</span></div>
            <div className="receipt-sub">Software studio · {CONTACT_EMAIL}</div>
          </div>
          <div className="receipt-stamp">PAID</div>
        </div>

        <div className="receipt-title">Receipt</div>

        <div className="receipt-grid">
          <div><span>Receipt no.</span><b>{rc.number}</b></div>
          <div><span>Date paid</span><b>{fmtDate(rc.paid_at)}</b></div>
          <div><span>Billed to</span><b>{rc.customer_name || rc.customer_email}</b></div>
          <div><span>Email</span><b>{rc.customer_email}</b></div>
        </div>

        <div className="receipt-line">
          <div className="receipt-desc">{rc.description || 'Services'}</div>
          <div className="receipt-amt">{money(rc.amount_cents)}</div>
        </div>

        <div className="receipt-total"><span>Total paid</span><b>{money(rc.amount_cents)}</b></div>

        {(rc.invoice_pdf || rc.stripe_receipt_url) && (
          <div className="receipt-links">
            {rc.invoice_pdf && <a className="head-link" href={rc.invoice_pdf} target="_blank" rel="noreferrer">Stripe invoice (PDF) ↗</a>}
            {rc.stripe_receipt_url && <a className="head-link" href={rc.stripe_receipt_url} target="_blank" rel="noreferrer">Stripe payment receipt ↗</a>}
          </div>
        )}

        <div className="receipt-foot">Thank you for supporting Voyager's Haven.</div>
      </div>

      <button className="btn btn-primary receipt-print" onClick={() => window.print()}>Print / Save as PDF</button>
    </div>
  )
}
