import { useState } from 'react'
import { completeCheckout, createCheckout } from '../api'
import { TIERS } from '../data/site'
import { LockIcon } from './icons'
import { useToast } from './Toast'

const money = (cents) => (cents / 100).toFixed(2)

// Voluntary support contributions. (Client invoices are now sent from the admin
// console via Stripe Invoicing — the public invoice tab was retired.)
export default function SupportPanel() {
  const toast = useToast()
  const [tier, setTier] = useState(1)
  const [custom, setCustom] = useState('')
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [modal, setModal] = useState(null)

  const usingCustom = custom !== ''
  const amount = usingCustom ? parseFloat(custom) || 0 : TIERS[tier].amount

  function pickTier(i) { setTier(i); setCustom('') }

  async function startCheckout() {
    if (!amount || amount <= 0) { toast('Enter an amount first', 'err'); return }
    setBusy(true)
    try {
      const res = await createCheckout({ kind: 'support', amount, email: email || null })
      if (res.provider === 'stripe' && res.checkout_url) { window.location.href = res.checkout_url; return }
      setModal({ stage: 'pay', reference: res.reference, amount_cents: res.amount_cents, email })
    } catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }

  async function paySimulated() {
    try { const r = await completeCheckout(modal.reference); setModal({ stage: 'receipt', ...r, email: modal.email }) }
    catch (e) { toast(e.message, 'err'); setModal(null) }
  }
  function closeReceipt() { setModal(null); toast('Thank you for the support') }

  return (
    <div className="support">
      <div className="tiers">
        {TIERS.map((t, i) => (
          <div key={t.name} className={`tier${!usingCustom && tier === i ? ' sel' : ''}`} role="button" tabIndex={0}
               onClick={() => pickTier(i)} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && pickTier(i)}>
            <div className="amt">${t.amount}</div>
            <div className="nm">{t.name}</div>
          </div>
        ))}
      </div>
      <div className={`custom-row${usingCustom ? ' sel' : ''}`}>
        <label>Custom</label><span className="cur">$</span>
        <input type="number" min="1" placeholder="Other amount" value={custom} onChange={(e) => setCustom(e.target.value)} />
      </div>

      <div className="field" style={{ marginTop: 4 }}>
        <label>Email for receipt (optional)</label>
        <input type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>

      <button className="pay-primary" onClick={startCheckout} disabled={busy}>
        {`Support with $${amount > 0 ? amount : 0}`}
      </button>

      <div className="trust-line">
        <LockIcon />
        Payments handled by Stripe — card details never touch our servers.
      </div>

      {modal && modal.stage === 'pay' && (
        <div className="modal-veil" onClick={(e) => e.target === e.currentTarget && setModal(null)}>
          <div className="modal">
            <button className="modal-x" onClick={() => setModal(null)}>×</button>
            <div className="modal-bar">🔒 checkout.stripe.com · secure</div>
            <div className="modal-body">
              <div className="m-to">Paying</div>
              <div className="m-biz">Voyager's Haven LLC</div>
              <div className="m-amt">${money(modal.amount_cents)}</div>
              <div className="fake-field"><span>Card number</span><span>•••• •••• •••• 4242</span></div>
              <div className="fake-field"><span>Expiry</span><span>04 / 28</span></div>
              <div className="fake-field"><span>CVC</span><span>•••</span></div>
              <button className="modal-pay" onClick={paySimulated}>Pay ${money(modal.amount_cents)}</button>
              <div className="modal-note">Simulated Stripe Checkout — no real charge. Set STRIPE_MODE=live to enable real payments.</div>
            </div>
          </div>
        </div>
      )}

      {modal && modal.stage === 'receipt' && (
        <div className="modal-veil" onClick={(e) => e.target === e.currentTarget && closeReceipt()}>
          <div className="modal receipt">
            <div className="modal-bar">✓ Payment complete</div>
            <div className="modal-body">
              <div className="r-check">✓</div>
              <div className="r-row"><span>Paid to</span><b>Voyager's Haven LLC</b></div>
              <div className="r-row"><span>Amount</span><b>${money(modal.amount_cents)}</b></div>
              <div className="r-row" style={{ border: 'none' }}><span>Reference</span><b>{modal.reference}</b></div>
              <div className="r-thanks">Thank you for keeping the work online.</div>
              <button className="modal-pay" style={{ background: 'var(--ok)', marginTop: 16 }} onClick={closeReceipt}>Done</button>
              <div className="modal-note">Recorded on our server{modal.email ? ' · receipt emailed' : ''}.</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
