import { useEffect, useState } from 'react'
import {
  adminLogin, adminLogout, adminMe, getAdminSummary,
  getAdminInquiries, setInquiryHandled,
  getAdminPayments,
  getAdminProducts, createProduct, updateProduct, deleteProduct,
  getAdminOrders, setOrderFulfilled,
  getAdminInvoices, createInvoice, recordPaidInvoice, markInvoicePaid, voidInvoice,
} from '../api'

const money = (cents) => `$${(cents / 100).toFixed(2)}`
const fmt = (s) => (s ? s.replace('T', ' ').slice(0, 16) : '—')
const BLANK_PRODUCT = { name: '', description: '', price: '', image_url: '', active: true, requires_shipping: true, sort_order: 0 }
const BLANK_INVOICE = { customer_name: '', customer_email: '', description: '', amount: '', recordPaid: false }
const stageLabel = (s) => (s === 'paid' ? 'Paid' : s === 'invoiced' ? 'Invoiced' : 'New')
const stagePill = (s) => (s === 'paid' ? 'p-live' : s === 'invoiced' ? 'p-hosted' : 'p-client')

export default function Admin() {
  const [phase, setPhase] = useState('checking')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState('inquiries')
  const [summary, setSummary] = useState(null)
  const [inquiries, setInquiries] = useState([])
  const [payments, setPayments] = useState([])
  const [products, setProducts] = useState([])
  const [orders, setOrders] = useState([])
  const [invoices, setInvoices] = useState([])
  const [editing, setEditing] = useState(null)
  const [invForm, setInvForm] = useState(BLANK_INVOICE)
  const [invBusy, setInvBusy] = useState(false)
  const [inqInvoice, setInqInvoice] = useState(null) // create an invoice from a specific inquiry

  async function load() {
    const [s, i, p, pr, o, inv] = await Promise.all([
      getAdminSummary(), getAdminInquiries(), getAdminPayments(),
      getAdminProducts(), getAdminOrders(), getAdminInvoices(),
    ])
    setSummary(s); setInquiries(i); setPayments(p); setProducts(pr); setOrders(o); setInvoices(inv)
  }

  useEffect(() => {
    adminMe().then(async () => { await load(); setPhase('in') }).catch(() => setPhase('login'))
  }, [])

  async function doLogin(e) {
    e.preventDefault(); setBusy(true); setError('')
    try { await adminLogin(password); await load(); setPhase('in'); setPassword('') }
    catch (err) { setError(err.message || 'Login failed') } finally { setBusy(false) }
  }
  async function doLogout() {
    try { await adminLogout() } catch { /* ignore */ }
    setPhase('login'); setSummary(null); setInquiries([]); setPayments([]); setProducts([]); setOrders([]); setInvoices([])
  }

  async function toggleHandled(q) {
    const next = q.handled ? 0 : 1
    try {
      await setInquiryHandled(q.id, !!next)
      setInquiries((l) => l.map((x) => (x.id === q.id ? { ...x, handled: next } : x)))
      setSummary((s) => (s ? { ...s, new_inquiries: s.new_inquiries + (next ? -1 : 1) } : s))
    } catch (err) { setError(err.message) }
  }

  // products
  function newProduct() { setError(''); setEditing({ ...BLANK_PRODUCT }) }
  function editProduct(p) {
    setError('')
    setEditing({ id: p.id, name: p.name, description: p.description || '', price: (p.price_cents / 100).toString(),
      image_url: p.image_url || '', active: !!p.active, requires_shipping: !!p.requires_shipping, sort_order: p.sort_order || 0 })
  }
  async function saveProduct() {
    const e = editing
    if (!e.name.trim() || e.price === '') { setError('Name and price are required'); return }
    const payload = { name: e.name.trim(), description: e.description || null, price: parseFloat(e.price) || 0,
      image_url: e.image_url || null, active: !!e.active, requires_shipping: !!e.requires_shipping, sort_order: Number(e.sort_order) || 0 }
    try { if (e.id) await updateProduct(e.id, payload); else await createProduct(payload); setEditing(null); await load() }
    catch (err) { setError(err.message) }
  }
  async function removeProduct(p) {
    if (!window.confirm(`Delete "${p.name}"?`)) return
    try { await deleteProduct(p.id); await load() } catch (err) { setError(err.message) }
  }

  // orders
  async function toggleFulfilled(o) {
    try { await setOrderFulfilled(o.id, !o.fulfilled); setOrders((l) => l.map((x) => (x.id === o.id ? { ...x, fulfilled: o.fulfilled ? 0 : 1 } : x))) }
    catch (err) { setError(err.message) }
  }

  // invoices
  const setInv = (k) => (e) => setInvForm((f) => ({ ...f, [k]: e.target.value }))
  async function submitInvoice() {
    if (!invForm.customer_email.trim() || !invForm.amount) { setError('Client email and amount are required'); return }
    setInvBusy(true); setError('')
    const payload = { customer_name: invForm.customer_name || null, customer_email: invForm.customer_email.trim(),
      description: invForm.description || null, amount: parseFloat(invForm.amount) || 0 }
    try {
      if (invForm.recordPaid) await recordPaidInvoice(payload)
      else await createInvoice(payload)
      setInvForm(BLANK_INVOICE); await load()
    } catch (err) { setError(err.message) } finally { setInvBusy(false) }
  }

  // create an invoice pre-filled from an inquiry, linked back to that lead
  function startInvoiceFromInquiry(q) {
    setError('')
    setInqInvoice({ inquiry_id: q.id, inquiry_name: q.name, customer_name: q.name || '',
      customer_email: q.email || '', description: '', amount: '', recordPaid: false })
  }
  async function submitInqInvoice() {
    const f = inqInvoice
    if (!f.customer_email.trim() || !f.amount) { setError('Client email and amount are required'); return }
    setInvBusy(true); setError('')
    const payload = { customer_name: f.customer_name || null, customer_email: f.customer_email.trim(),
      description: f.description || null, amount: parseFloat(f.amount) || 0, inquiry_id: f.inquiry_id }
    try {
      if (f.recordPaid) await recordPaidInvoice(payload)
      else await createInvoice(payload)
      setInqInvoice(null); await load()
    } catch (err) { setError(err.message) } finally { setInvBusy(false) }
  }
  async function doMarkPaid(inv) { try { await markInvoicePaid(inv.id); await load() } catch (err) { setError(err.message) } }
  async function doVoid(inv) { if (!window.confirm(`Void invoice ${inv.number}?`)) return; try { await voidInvoice(inv.id); await load() } catch (err) { setError(err.message) } }

  if (phase === 'checking') return <div className="page"><p style={{ color: 'var(--dim)' }}>Checking session…</p></div>

  if (phase === 'login') {
    return (
      <div className="admin-login">
        <form className="form-card" onSubmit={doLogin} style={{ maxWidth: 380, width: '100%' }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>Admin</div>
          <h2 style={{ fontSize: 22, marginBottom: 18 }}>Voyager's Haven console</h2>
          <div className="field"><label>Password</label>
            <input type="password" value={password} autoFocus onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" /></div>
          {error && <p style={{ color: 'var(--amber)', fontSize: 13, margin: '-4px 0 14px' }}>{error}</p>}
          <button className="pay-primary" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        </form>
      </div>
    )
  }

  const invStatusClass = (s) => (s === 'paid' ? 'p-live' : s === 'void' ? 'p-internal' : 'p-client')

  return (
    <div className="admin wrap">
      <div className="admin-head">
        <div><span className="eyebrow">Admin console</span><h1>Console</h1></div>
        <button className="pay-secondary" style={{ width: 'auto', marginTop: 0, padding: '10px 18px' }} onClick={doLogout}>Log out</button>
      </div>

      {summary && (
        <div className="admin-stats">
          <div className="astat"><div className="n">{summary.new_inquiries}</div><div className="l">New inquiries</div></div>
          <div className="astat"><div className="n">{summary.unfulfilled_orders ?? 0}</div><div className="l">Orders to ship</div></div>
          <div className="astat"><div className="n">{summary.open_invoices ?? 0}</div><div className="l">Open invoices</div></div>
        </div>
      )}

      {error && <p style={{ color: 'var(--amber)', fontSize: 13, marginBottom: 12 }}>{error}</p>}

      <div className="mode-switch" style={{ margin: '4px 0 24px', flexWrap: 'wrap' }}>
        <button className={tab === 'inquiries' ? 'on' : ''} onClick={() => setTab('inquiries')}>Inquiries ({inquiries.length})</button>
        <button className={tab === 'orders' ? 'on' : ''} onClick={() => setTab('orders')}>Orders ({orders.length})</button>
        <button className={tab === 'invoices' ? 'on' : ''} onClick={() => setTab('invoices')}>Invoices ({invoices.length})</button>
        <button className={tab === 'merch' ? 'on' : ''} onClick={() => setTab('merch')}>Merch ({products.length})</button>
        <button className={tab === 'payments' ? 'on' : ''} onClick={() => setTab('payments')}>Payments ({payments.length})</button>
      </div>

      {tab === 'inquiries' && (
        <div className="admin-inquiries">
          {inquiries.length === 0 && <p style={{ color: 'var(--dim)' }}>No inquiries yet.</p>}
          {inquiries.map((q) => (
            <div className={`inq-card${q.handled ? ' done' : ''}`} key={q.id}>
              <div className="inq-top">
                <div>
                  <span className={`pill ${stagePill(q.stage)}`}>{stageLabel(q.stage)}</span>
                  {q.handled ? <span className="pill p-internal" style={{ marginLeft: 6 }}>handled</span> : null}
                  <span className="inq-name" style={{ marginLeft: 10 }}>{q.name}</span>
                  <a className="inq-email" href={`mailto:${q.email}`}>{q.email}</a>
                </div>
                <span className="inq-date">{fmt(q.created_at)}</span>
              </div>
              <div className="inq-meta">{q.project_type && <span className="tag">{q.project_type}</span>}{q.budget && <span className="tag">{q.budget}</span>}</div>
              <p className="inq-msg">{q.message}</p>
              {q.invoices && q.invoices.length > 0 && (
                <div className="inq-invoices">
                  {q.invoices.map((iv) => (
                    <div className="inq-inv-row" key={iv.id}>
                      <span className="inq-inv-num">{iv.number || '—'}</span>
                      <span className="inq-inv-amt">{money(iv.amount_cents)}</span>
                      <span className={`pill ${invStatusClass(iv.status)}`}>{iv.status}</span>
                      {iv.status === 'paid' ? <a className="head-link" href={`/receipt/${encodeURIComponent(iv.number)}`} target="_blank" rel="noreferrer">Receipt ↗</a>
                        : iv.hosted_invoice_url ? <a className="head-link" href={iv.hosted_invoice_url} target="_blank" rel="noreferrer">View ↗</a> : null}
                    </div>
                  ))}
                </div>
              )}
              <div className="inq-actions">
                <a className="head-link" href={`mailto:${q.email}?subject=Re: your project inquiry`}>Reply →</a>
                <button className="inq-toggle" onClick={() => startInvoiceFromInquiry(q)}>+ Create invoice</button>
                <button className="inq-toggle" onClick={() => toggleHandled(q)}>{q.handled ? 'Mark as new' : 'Mark handled'}</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'orders' && (
        <div className="orders-list">
          {orders.length === 0 && <p style={{ color: 'var(--dim)' }}>No orders yet.</p>}
          {orders.map((o) => (
            <div className={`order-card${o.fulfilled ? ' done' : ''}`} key={o.id}>
              <div className="order-top">
                <div>
                  <span className={`pill ${o.fulfilled ? 'p-live' : 'p-client'}`}>{o.fulfilled ? 'Fulfilled' : 'New'}</span>
                  <span className="order-item" style={{ marginLeft: 10 }}>{o.item_label}</span>
                  <span className="order-amt">{money(o.amount_cents)}</span>
                </div>
                <span className="inq-date">{fmt(o.created_at)}</span>
              </div>
              <div className="order-body">
                <div><b>{o.customer_name || '—'}</b> · <a className="inq-email" href={`mailto:${o.customer_email}`}>{o.customer_email || '—'}</a>{o.customer_phone ? ` · ${o.customer_phone}` : ''}</div>
                {o.ship_line1 && <div className="order-ship">📦 {[o.ship_line1, o.ship_line2, o.ship_city, o.ship_state, o.ship_postal].filter(Boolean).join(', ')}</div>}
              </div>
              <button className="inq-toggle" onClick={() => toggleFulfilled(o)}>{o.fulfilled ? 'Mark unfulfilled' : 'Mark fulfilled'}</button>
            </div>
          ))}
        </div>
      )}

      {tab === 'invoices' && (
        <div className="admin-invoices">
          <div className="inv-form-card">
            <h3 style={{ fontSize: 16, marginBottom: 14 }}>New invoice</h3>
            <div className="form-row">
              <div className="field"><label>Client name</label><input value={invForm.customer_name} onChange={setInv('customer_name')} placeholder="Acme Co." /></div>
              <div className="field"><label>Client email</label><input value={invForm.customer_email} onChange={setInv('customer_email')} placeholder="client@example.com" /></div>
            </div>
            <div className="form-row">
              <div className="field"><label>Amount (USD)</label><input type="number" step="0.01" value={invForm.amount} onChange={setInv('amount')} placeholder="1500.00" /></div>
              <div className="field"><label>Description</label><input value={invForm.description} onChange={setInv('description')} placeholder="Dashboard build — milestone 1" /></div>
            </div>
            <label className="chk" style={{ margin: '2px 0 12px' }}>
              <input type="checkbox" checked={invForm.recordPaid} onChange={(e) => setInvForm((f) => ({ ...f, recordPaid: e.target.checked }))} />
              Already paid — just record it (no Stripe email/charge)
            </label>
            <button className="pay-primary" onClick={submitInvoice} disabled={invBusy}>{invBusy ? 'Saving…' : (invForm.recordPaid ? 'Record paid sale' : 'Create & send invoice')}</button>
            <p style={{ fontSize: 12.5, color: 'var(--faint)', marginTop: 10 }}>
              Live: Stripe auto-numbers it, emails the client a hosted invoice with a Pay button, and generates the PDF. Local dev: creates a VH-YYYY-NNN record you can mark paid. Tick "already paid" to log a past/external sale with no email.
            </p>
          </div>

          <div className="fleet" style={{ marginTop: 18 }}>
            {invoices.length === 0 && <p style={{ color: 'var(--dim)', padding: 14 }}>No invoices yet.</p>}
            {invoices.map((inv) => (
              <div className="fleet-row inv-row" key={inv.id}>
                <div className="fleet-name">{inv.number || '—'}<span className="fleet-maker"> · {inv.customer_name || inv.customer_email}</span></div>
                <div className="fleet-domain">{money(inv.amount_cents)}{inv.description ? ` · ${inv.description}` : ''}{inv.inquiry_name ? ` · from ${inv.inquiry_name}` : ''} · {fmt(inv.created_at)}</div>
                <div className="inv-actions">
                  {inv.status === 'paid' ? <a className="head-link" href={`/receipt/${encodeURIComponent(inv.number)}`} target="_blank" rel="noreferrer">Receipt</a>
                    : inv.hosted_invoice_url ? <a className="head-link" href={inv.hosted_invoice_url} target="_blank" rel="noreferrer">View</a> : null}
                  {inv.pdf_url && <a className="head-link" href={inv.pdf_url} target="_blank" rel="noreferrer">PDF</a>}
                  {inv.status === 'open' && <button className="inq-toggle" onClick={() => doMarkPaid(inv)}>Mark paid</button>}
                  {inv.status !== 'paid' && inv.status !== 'void' && <button className="inq-toggle" onClick={() => doVoid(inv)}>Void</button>}
                  <span className={`pill ${invStatusClass(inv.status)}`}>{inv.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'merch' && (
        <div className="admin-merch">
          <div className="merch-toolbar">
            <p style={{ color: 'var(--dim)', fontSize: 14, margin: 0 }}>Products shown in the public <b>Shop</b> tab. The price you set here is what customers pay.</p>
            <button className="btn btn-primary" style={{ padding: '10px 18px' }} onClick={newProduct}>+ Add product</button>
          </div>
          {products.length === 0 && <p style={{ color: 'var(--dim)' }}>No products yet.</p>}
          <div className="merch-list">
            {products.map((p) => (
              <div className={`merch-row${p.active ? '' : ' off'}`} key={p.id}>
                <div className="merch-thumb" style={{ background: p.image_url ? undefined : 'linear-gradient(135deg,rgba(0,194,179,.22),rgba(167,139,250,.12))' }}>
                  {p.image_url ? <img src={p.image_url} alt="" /> : <span>✦</span>}
                </div>
                <div className="merch-info">
                  <div className="merch-name">{p.name}
                    {!p.active && <span className="pill p-internal" style={{ marginLeft: 8 }}>hidden</span>}
                    {!p.requires_shipping && <span className="pill p-hosted" style={{ marginLeft: 8 }}>digital</span>}
                  </div>
                  {p.description && <div className="merch-sub">{p.description}</div>}
                </div>
                <div className="merch-price">{money(p.price_cents)}</div>
                <div className="merch-actions">
                  <button className="inq-toggle" onClick={() => editProduct(p)}>Edit</button>
                  <button className="inq-toggle" onClick={() => removeProduct(p)}>Delete</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'payments' && (
        <div className="fleet">
          {payments.length === 0 && <p style={{ color: 'var(--dim)', padding: 14 }}>No payments yet.</p>}
          {payments.map((p) => (
            <div className="fleet-row pay-row" key={p.id}>
              <div className="fleet-name">{money(p.amount_cents)}<span className="fleet-maker"> · {p.kind}{p.item_label ? ` · ${p.item_label}` : ''}{p.invoice_number ? ` · ${p.invoice_number}` : ''}</span></div>
              <div className="fleet-domain">{p.reference} · {fmt(p.created_at)}{p.email ? ` · ${p.email}` : ''}</div>
              <span className={`pill ${p.status === 'paid' ? 'p-live' : 'p-internal'}`}>{p.status}</span>
            </div>
          ))}
        </div>
      )}

      {inqInvoice && (
        <div className="modal-veil" onClick={(e) => e.target === e.currentTarget && setInqInvoice(null)}>
          <div className="modal" style={{ background: 'var(--bg-2)', color: 'var(--text)', maxWidth: 460 }}>
            <div className="modal-body" style={{ padding: 26 }}>
              <h3 style={{ fontSize: 18, marginBottom: 4 }}>Invoice for this lead</h3>
              <p style={{ fontSize: 12.5, color: 'var(--faint)', marginBottom: 16 }}>Linked to {inqInvoice.inquiry_name || 'the inquiry'} — you'll be able to trace it inquiry → invoice → receipt.</p>
              <div className="form-row">
                <div className="field"><label>Client name</label><input value={inqInvoice.customer_name} onChange={(e) => setInqInvoice({ ...inqInvoice, customer_name: e.target.value })} /></div>
                <div className="field"><label>Client email</label><input value={inqInvoice.customer_email} onChange={(e) => setInqInvoice({ ...inqInvoice, customer_email: e.target.value })} /></div>
              </div>
              <div className="form-row">
                <div className="field"><label>Amount (USD)</label><input type="number" step="0.01" value={inqInvoice.amount} onChange={(e) => setInqInvoice({ ...inqInvoice, amount: e.target.value })} placeholder="1500.00" /></div>
                <div className="field"><label>Description</label><input value={inqInvoice.description} onChange={(e) => setInqInvoice({ ...inqInvoice, description: e.target.value })} placeholder="Project — milestone 1" /></div>
              </div>
              <label className="chk" style={{ margin: '2px 0 14px' }}>
                <input type="checkbox" checked={inqInvoice.recordPaid} onChange={(e) => setInqInvoice({ ...inqInvoice, recordPaid: e.target.checked })} />
                Already paid — just record it (no Stripe email/charge)
              </label>
              <button className="pay-primary" onClick={submitInqInvoice} disabled={invBusy}>{invBusy ? 'Saving…' : (inqInvoice.recordPaid ? 'Record paid sale' : 'Create & send invoice')}</button>
              <button className="pay-secondary" onClick={() => setInqInvoice(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {editing && (
        <div className="modal-veil" onClick={(e) => e.target === e.currentTarget && setEditing(null)}>
          <div className="modal" style={{ background: 'var(--bg-2)', color: 'var(--text)', maxWidth: 470 }}>
            <div className="modal-body" style={{ padding: 26 }}>
              <h3 style={{ fontSize: 18, marginBottom: 16 }}>{editing.id ? 'Edit product' : 'New product'}</h3>
              <div className="field"><label>Name</label><input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} placeholder="Cartographer Tee" /></div>
              <div className="field"><label>Description</label><textarea value={editing.description} onChange={(e) => setEditing({ ...editing, description: e.target.value })} placeholder="Short description shown on the card" /></div>
              <div className="form-row">
                <div className="field"><label>Price (USD)</label><input type="number" step="0.01" value={editing.price} onChange={(e) => setEditing({ ...editing, price: e.target.value })} placeholder="28.00" /></div>
                <div className="field"><label>Sort order</label><input type="number" value={editing.sort_order} onChange={(e) => setEditing({ ...editing, sort_order: e.target.value })} /></div>
              </div>
              <div className="field"><label>Image URL (optional)</label><input value={editing.image_url} onChange={(e) => setEditing({ ...editing, image_url: e.target.value })} placeholder="https://…" /></div>
              <div className="merch-toggles">
                <label className="chk"><input type="checkbox" checked={editing.active} onChange={(e) => setEditing({ ...editing, active: e.target.checked })} /> Active (show in shop)</label>
                <label className="chk"><input type="checkbox" checked={editing.requires_shipping} onChange={(e) => setEditing({ ...editing, requires_shipping: e.target.checked })} /> Physical (collect shipping address)</label>
              </div>
              <button className="pay-primary" onClick={saveProduct}>{editing.id ? 'Save changes' : 'Create product'}</button>
              <button className="pay-secondary" onClick={() => setEditing(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
