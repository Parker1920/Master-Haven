import { useState } from 'react'
import { lookupInvoice, payInvoiceSimulated } from '../api'
import { LockIcon } from './icons'
import { useToast } from './Toast'

const money = (cents) => `$${(cents / 100).toFixed(2)}`

// Enter an invoice number → it auto-populates the invoice we already have on
// record (amount/description are read-only, so nobody can change the amount) →
// pay. Live invoices redirect to Stripe's hosted invoice; simulated (local dev)
// runs the mock card modal and marks our record paid.
export default function InvoicePay() {
  const toast = useToast()
  const [number, setNumber] = useState('')
  const [inv, setInv] = useState(null)
  const [busy, setBusy] = useState(false)
  const [modal, setModal] = useState(null)

  async function look() {
    if (!number.trim()) { toast('Enter your invoice number', 'err'); return }
    setBusy(true); setInv(null)
    try {
      const r = await lookupInvoice(number.trim())
      setInv(r)
      if (!r.found) toast('No invoice found with that number', 'err')
    } catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }

  function pay() {
    if (inv.hosted_invoice_url) { window.location.href = inv.hosted_invoice_url; return } // live → Stripe hosted invoice
    setModal({ stage: 'pay' }) // simulated
  }
  async function paySimulated() {
    try { const r = await payInvoiceSimulated(inv.number); setModal({ stage: 'receipt', ...r }) }
    catch (e) { toast(e.message, 'err'); setModal(null) }
  }
  function done() { setModal(null); setInv({ ...inv, status: 'paid' }); toast('Invoice paid — thank you!') }

  const statusPill = (s) => (s === 'paid' ? 'p-live' : s === 'void' ? 'p-internal' : 'p-client')

  return (
    <div className="support">
      <div className="field">
        <label>Invoice number</label>
        <div className="inv-lookup-row">
          <input value={number} onChange={(e) => setNumber(e.target.value)} placeholder="e.g. VH-2026-001"
                 onKeyDown={(e) => e.key === 'Enter' && look()} />
          <button className="btn btn-ghost" onClick={look} disabled={busy}>{busy ? '…' : 'Look up'}</button>
        </div>
      </div>

      {inv && inv.found && (
        <div className="inv-detail">
          <div className="inv-detail-head">
            <span className="inv-detail-num">{inv.number}</span>
            <span className={`pill ${statusPill(inv.status)}`}>{inv.status}</span>
          </div>
          {inv.customer_name && <div className="inv-detail-row"><span>Billed to</span><b>{inv.customer_name}</b></div>}
          {inv.description && <div className="inv-detail-row"><span>For</span><b>{inv.description}</b></div>}
          <div className="inv-detail-row"><span>Amount due</span><b className="inv-amt">{money(inv.amount_cents)}</b></div>

          {inv.status === 'open' && <button className="pay-primary" style={{ marginTop: 16 }} onClick={pay}>Pay {money(inv.amount_cents)}</button>}
          {inv.status === 'paid' && <p className="inv-paid-note">✓ This invoice is already paid. Thank you!</p>}
          {inv.status === 'void' && <p className="inv-void-note">This invoice has been voided — reach out if you have questions.</p>}
        </div>
      )}

      {inv && inv.found === false && (
        <p style={{ color: 'var(--dim)', marginTop: 12, fontSize: 14 }}>
          No invoice found with that number. Double-check it against the invoice we sent you.
        </p>
      )}

      <div className="trust-line" style={{ marginTop: 22 }}>
        <LockIcon /> Payments handled by Stripe — card details never touch our servers.
      </div>

      {modal && modal.stage === 'pay' && (
        <div className="modal-veil" onClick={(e) => e.target === e.currentTarget && setModal(null)}>
          <div className="modal">
            <button className="modal-x" onClick={() => setModal(null)}>×</button>
            <div className="modal-bar">🔒 checkout.stripe.com · secure</div>
            <div className="modal-body">
              <div className="m-to">Paying invoice</div>
              <div className="m-biz">{inv.number}</div>
              <div className="m-amt">{money(inv.amount_cents)}</div>
              <div className="fake-field"><span>Card number</span><span>•••• •••• •••• 4242</span></div>
              <div className="fake-field"><span>Expiry</span><span>04 / 28</span></div>
              <div className="fake-field"><span>CVC</span><span>•••</span></div>
              <button className="modal-pay" onClick={paySimulated}>Pay {money(inv.amount_cents)}</button>
              <div className="modal-note">Simulated checkout (local dev) — no real charge. Live invoices open Stripe's hosted invoice page.</div>
            </div>
          </div>
        </div>
      )}

      {modal && modal.stage === 'receipt' && (
        <div className="modal-veil" onClick={(e) => e.target === e.currentTarget && done()}>
          <div className="modal receipt">
            <div className="modal-bar">✓ Invoice paid</div>
            <div className="modal-body">
              <div className="r-check">✓</div>
              <div className="r-row"><span>Invoice</span><b>{modal.number}</b></div>
              <div className="r-row"><span>Amount</span><b>{money(modal.amount_cents)}</b></div>
              <div className="r-row" style={{ border: 'none' }}><span>Status</span><b>{modal.status}</b></div>
              <div className="r-thanks">Thank you! A receipt has been recorded for you and Voyager's Haven.</div>
              <button className="modal-pay" style={{ background: 'var(--ok)', marginTop: 16 }} onClick={done}>Done</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
