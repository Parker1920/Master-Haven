import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import { getShopProducts, shopCheckout, shopComplete } from '../api'
import { useToast } from '../components/Toast'

const money = (cents) => `$${(cents / 100).toFixed(2)}`

const TINTS = [
  'linear-gradient(135deg, rgba(0,194,179,.22), rgba(94,231,223,.06))',
  'linear-gradient(135deg, rgba(167,139,250,.22), rgba(167,139,250,.05))',
  'linear-gradient(135deg, rgba(255,181,71,.20), rgba(255,181,71,.05))',
  'linear-gradient(135deg, rgba(96,165,250,.20), rgba(96,165,250,.05))',
]

const EMPTY_FORM = { name: '', email: '', phone: '', line1: '', line2: '', city: '', state: '', postal: '' }

export default function Shop() {
  const toast = useToast()
  const [products, setProducts] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [modal, setModal] = useState(null) // {stage:'pay'|'receipt', reference, amount_cents, label, product}
  const [form, setForm] = useState(EMPTY_FORM)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  useEffect(() => {
    getShopProducts().then(setProducts).catch((e) => { toast(e.message, 'err'); setProducts([]) })
  }, [toast])

  async function buy(p) {
    setBusyId(p.id)
    try {
      const res = await shopCheckout({ product_id: p.id, quantity: 1 })
      if (res.provider === 'stripe' && res.checkout_url) {
        window.location.href = res.checkout_url // live: Stripe collects contact + shipping
        return
      }
      setForm(EMPTY_FORM)
      setModal({ stage: 'pay', reference: res.reference, amount_cents: res.amount_cents, label: res.label, product: p })
    } catch (e) {
      toast(e.message, 'err')
    } finally {
      setBusyId(null)
    }
  }

  async function placeOrder() {
    const needsShip = modal.product.requires_shipping
    if (!form.email.trim()) { toast('Email is required', 'err'); return }
    if (needsShip && (!form.name.trim() || !form.line1.trim() || !form.city.trim() || !form.state.trim() || !form.postal.trim())) {
      toast('Name and full shipping address are required', 'err'); return
    }
    try {
      const done = await shopComplete({ reference: modal.reference, ...form })
      setModal({ stage: 'receipt', reference: done.reference, amount_cents: done.amount_cents, label: done.item_label })
    } catch (e) {
      toast(e.message, 'err')
    }
  }

  function closeReceipt() { setModal(null); toast('Thanks for the order!') }

  return (
    <>
      <PageHeader
        eyebrow="Shop"
        title="Voyager's Haven merch"
        lede="A small line of gear for the travelers who chart the galaxy with us. Everything ships from Pennsylvania; supporting the shop helps keep the community tools free."
      />

      <section className="section wrap">
        {products === null && <p style={{ color: 'var(--dim)' }}>Loading…</p>}
        {products && products.length === 0 && <p style={{ color: 'var(--dim)' }}>The shop is being stocked — check back soon.</p>}
        <div className="shop-grid">
          {products && products.map((p, i) => (
            <div className="product" key={p.id}>
              <div className="product-media" style={{ background: p.image_url ? undefined : TINTS[i % TINTS.length] }}>
                {p.image_url ? <img src={p.image_url} alt={p.name} /> : <span className="product-media-mark" aria-hidden="true">✦</span>}
                {!p.requires_shipping && <span className="product-badge">Digital</span>}
              </div>
              <div className="product-body">
                <div className="product-top">
                  <h3>{p.name}</h3>
                  <span className="product-price">{money(p.price_cents)}</span>
                </div>
                {p.description && <p className="product-desc">{p.description}</p>}
                <button className="btn btn-primary product-buy" disabled={busyId === p.id} onClick={() => buy(p)}>
                  {busyId === p.id ? 'Starting…' : 'Buy'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {modal && modal.stage === 'pay' && (
        <div className="modal-veil" onClick={(e) => e.target === e.currentTarget && setModal(null)}>
          <div className="modal" style={{ maxWidth: 440, maxHeight: '92vh', overflowY: 'auto' }}>
            <button className="modal-x" onClick={() => setModal(null)}>×</button>
            <div className="modal-bar">🔒 checkout.stripe.com · secure</div>
            <div className="modal-body">
              <div className="m-to">Order</div>
              <div className="m-biz">{modal.label}</div>
              <div className="m-amt">{money(modal.amount_cents)}</div>

              <div className="co-section">Contact</div>
              <input className="co-input" placeholder="Full name" value={form.name} onChange={set('name')} />
              <input className="co-input" placeholder="Email" value={form.email} onChange={set('email')} />
              <input className="co-input" placeholder="Phone (optional)" value={form.phone} onChange={set('phone')} />

              {modal.product.requires_shipping && (
                <>
                  <div className="co-section">Shipping address</div>
                  <input className="co-input" placeholder="Address line 1" value={form.line1} onChange={set('line1')} />
                  <input className="co-input" placeholder="Apt, suite (optional)" value={form.line2} onChange={set('line2')} />
                  <div className="co-row">
                    <input className="co-input" placeholder="City" value={form.city} onChange={set('city')} />
                    <input className="co-input" placeholder="State" value={form.state} onChange={set('state')} style={{ maxWidth: 90 }} />
                    <input className="co-input" placeholder="ZIP" value={form.postal} onChange={set('postal')} style={{ maxWidth: 110 }} />
                  </div>
                </>
              )}

              <div className="co-section">Payment</div>
              <div className="fake-field"><span>Card number</span><span>•••• •••• •••• 4242</span></div>
              <div className="fake-field"><span>Expiry / CVC</span><span>04 / 28 · •••</span></div>

              <button className="modal-pay" onClick={placeOrder}>Place order · {money(modal.amount_cents)}</button>
              <div className="modal-note">Simulated checkout (local dev) — no real charge. Live mode redirects to Stripe, which collects this same info.</div>
            </div>
          </div>
        </div>
      )}

      {modal && modal.stage === 'receipt' && (
        <div className="modal-veil" onClick={(e) => e.target === e.currentTarget && closeReceipt()}>
          <div className="modal receipt">
            <div className="modal-bar">✓ Order placed</div>
            <div className="modal-body">
              <div className="r-check">✓</div>
              <div className="r-row"><span>Item</span><b>{modal.label}</b></div>
              <div className="r-row"><span>Amount</span><b>{money(modal.amount_cents)}</b></div>
              <div className="r-row" style={{ border: 'none' }}><span>Reference</span><b>{modal.reference}</b></div>
              <div className="r-thanks">Thanks! Your order is in the admin queue with your ship-to details.</div>
              <button className="modal-pay" style={{ background: 'var(--ok)', marginTop: 16 }} onClick={closeReceipt}>Done</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
