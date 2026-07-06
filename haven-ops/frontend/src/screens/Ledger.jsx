import { useState } from 'react'
import { api, money } from '../api'
import AttachButton from '../components/AttachButton.jsx'
import FormModal from '../components/FormModal.jsx'
import { useFetch } from '../hooks'
import { useToast } from '../toast.jsx'
import { Badge, Card, DocActions, EditBtn, Gauge, Row } from '../ui.jsx'

// Display-only until live money ingestion (Phase 2 Stripe/bank feeds).
const COST_CENTERS = [
  ['gold', 'Finance & Treasury'], ['purple', 'R&D / AI'], ['teal', 'Engineering'],
  ['#6ea8fe', 'Community & Products'], ['#f78da3', 'Ops & Infrastructure'],
]

const KIND_OPTIONS = [['bank', 'Bank'], ['processor', 'Processor'],
  ['exchange-paper', 'Exchange (paper)'], ['other', 'Other']]
const TX_KINDS = [['payment', 'Payment (in)'], ['expense', 'Expense (out)'],
  ['transfer', 'Transfer'], ['adjustment', 'Adjustment']]

export default function Ledger() {
  const accounts = useFetch('/accounts')
  const engagements = useFetch('/engagements')
  const transactions = useFetch('/transactions')
  const assets = useFetch('/assets')
  const company = useFetch('/company')
  const documents = useFetch('/documents')
  const toast = useToast()
  const [sheet, setSheet] = useState(null) // {kind, item}

  const bank = (accounts.data || []).find((a) => a.kind === 'bank')
  const inflow = (transactions.data || []).filter((t) => t.amount_cents > 0)
    .reduce((s, t) => s + t.amount_cents, 0)
  const taxDue = Math.floor(inflow / 4)
  const engById = Object.fromEntries((engagements.data || []).map((e) => [e.id, e]))
  const docById = Object.fromEntries((documents.data || []).map((d) => [d.id, d]))

  const paidCents = (engagementId) =>
    (transactions.data || [])
      .filter((t) => t.engagement_id === engagementId && t.kind === 'payment')
      .reduce((s, t) => s + t.amount_cents, 0)

  const accountAmt = (a) => {
    if (a.kind === 'exchange-paper') return <span className="amt dim">paper</span>
    if (a.balance_cents_manual == null) return <span className="amt dim">—</span>
    return <span className="amt">{money(a.balance_cents_manual)}</span>
  }
  const accountIcon = { bank: '🏦', processor: '💳', 'exchange-paper': '📈' }
  const undocumented = (assets.data || []).find((a) => !a.documented)

  const crudSheet = (kind, path, reload, fields, item, defaults = {}) => (
    <FormModal title={`${item ? 'Edit' : 'Add'} ${kind}`} fields={fields}
      initial={item || defaults}
      onSubmit={async (vals) => {
        if (item) await api.put(`${path}/${item.id}`, vals)
        else await api.post(path, vals)
        reload()
        toast(`${kind} saved`)
      }}
      onDelete={item ? async () => { await api.del(`${path}/${item.id}`); reload(); toast(`${kind} deleted`) } : undefined}
      onClose={() => setSheet(null)} />
  )

  const sheets = {
    account: (item) => crudSheet('account', '/accounts', accounts.reload, [
      { name: 'name', label: 'Name', required: true },
      { name: 'kind', label: 'Kind', type: 'select', options: KIND_OPTIONS, required: true },
      { name: 'balance_cents_manual', label: 'Balance ($)', type: 'money',
        hint: 'leave empty = unknown/not opened yet — manual until Phase 2 feeds' },
      { name: 'status', label: 'Status note' },
    ], item, { kind: 'bank' }),
    transaction: (item) => crudSheet('transaction', '/transactions', transactions.reload, [
      { name: 'amount_cents', label: 'Amount ($)', type: 'money', required: true,
        hint: 'negative = outflow (e.g. -12.50)' },
      { name: 'kind', label: 'Kind', type: 'select', options: TX_KINDS, required: true },
      { name: 'account_id', label: 'Account', type: 'select', numeric: true,
        options: (accounts.data || []).map((a) => [a.id, a.name]),
        hint: 'leave — if the rail is unconfirmed' },
      { name: 'engagement_id', label: 'Engagement', type: 'select', numeric: true,
        options: (engagements.data || []).map((e) => [e.id, e.code]) },
      { name: 'ts', label: 'Date', type: 'date' },
      { name: 'rail', label: 'Rail', placeholder: 'e.g. Stripe, check, cash' },
      { name: 'note', label: 'Note', type: 'textarea' },
    ], item, { kind: 'payment', ts: new Date().toISOString().slice(0, 10) }),
    asset: (item) => crudSheet('asset', '/assets', assets.reload, [
      { name: 'label', label: 'Label', required: true },
      { name: 'category', label: 'Category', placeholder: 'capital' },
      { name: 'value_cents', label: 'Value ($)', type: 'money', required: true },
      { name: 'documented', label: 'Documented (receipt/record on file)', type: 'checkbox' },
      { name: 'note', label: 'Note', type: 'textarea' },
    ], item, { category: 'capital' }),
  }

  return (
    <>
      <h1 className="screen-title">Ledger</h1>
      <p className="screen-sub">Accounts, invoices, and where every dollar sits</p>

      <div className="gauges">
        <Gauge accent="teal" label="Cash on hand"
          val={bank && bank.balance_cents_manual != null ? money(bank.balance_cents_manual) : 'Opens Mon'}
          pending={!bank || bank.balance_cents_manual == null}
          foot={bank && bank.balance_cents_manual != null ? 'Business checking' : 'Deposit TBD'} />
        <Gauge accent="gold" label="Reserved for tax" val={money(0)}
          foot={`${money(taxDue)} due · 25% of ${money(inflow)}`} />
      </div>

      <Card title="Accounts"
        action={<button className="link" type="button" onClick={() => setSheet({ kind: 'account', item: null })}>Add</button>}>
        {(accounts.data || []).map((a) => (
          <Row key={a.id} icon={accountIcon[a.kind] || '💰'}
            name={a.name.split('·')[0].trim()}
            meta={a.name.includes('·') ? a.name.split('·').slice(1).join('·').trim() : (a.status || '').split(';')[0]}
            right={<span className="acts">{accountAmt(a)}<EditBtn onClick={() => setSheet({ kind: 'account', item: a })} /></span>} />
        ))}
      </Card>

      <Card title="Invoices">
        {(engagements.data || []).map((e) => (
          <Row key={e.id} icon="📄" name={e.code} meta={`${e.client?.contact} (${e.client?.name}) · ${e.title}`}
            right={
              <span style={{ textAlign: 'right' }}>
                <span className="amt">{money(e.value_cents)}</span><br />
                <span style={{ marginTop: 4, display: 'inline-block' }}>
                  {paidCents(e.id) >= e.value_cents ? <Badge tone="ok">Paid</Badge> : <Badge tone="warn">Open</Badge>}
                </span>
              </span>
            } />
        ))}
        <p className="note">Derived from engagements + payment transactions. Generate the invoice PDF from the engagement's Documents card.</p>
      </Card>

      <Card title="Transactions"
        action={<button className="link" type="button" onClick={() => setSheet({ kind: 'transaction', item: null })}>Add</button>}>
        {(transactions.data || []).map((t) => (
          <Row key={t.id} icon={t.amount_cents >= 0 ? '✔️' : '↘️'}
            name={`${t.kind === 'payment' ? 'Payment received' : (t.kind || 'entry')} — ${engById[t.engagement_id]?.client?.contact || (t.rail || '')}`}
            meta={`${engById[t.engagement_id]?.code || ''} · rail ${t.rail || 'unknown'} · ${t.ts ? t.ts.slice(0, 10) : 'on file'}`}
            right={
              <span className="acts">
                <span className="amt">{t.amount_cents > 0 ? '+' : ''}{money(t.amount_cents)}</span>
                <EditBtn onClick={() => setSheet({ kind: 'transaction', item: t })} />
              </span>
            } />
        ))}
        {(transactions.data || []).some((t) => t.account_id == null) && (
          <p className="note">⚠ At least one inflow predates the business account — confirm which rail it landed in, for the veil record.</p>
        )}
      </Card>

      <Card title="Cost centers · 5 departments">
        {COST_CENTERS.map(([color, name]) => (
          <div className="cc" key={name}>
            <span className="dotc" style={{ background: color.startsWith('#') ? color : `var(--${color})` }} />
            <span className="cn">{name}</span>
            <span className="cv">{money(0)}</span>
          </div>
        ))}
      </Card>

      <Card title="Capital assets · Schedule A"
        action={
          <span className="acts">
            {company.data && <span className="amt-tot">{money(company.data.capital_total_cents)}</span>}
            <button className="link" type="button" onClick={() => setSheet({ kind: 'asset', item: null })}>Add</button>
          </span>
        }>
        {(assets.data || []).map((a) => (
          <Row key={a.id} icon={a.label.includes('IP') ? '📜' : a.label === 'Cash' ? '💵' : '📦'}
            name={a.label} meta={(a.note || '').split('—')[0].trim()}
            right={
              <span className="acts">
                <span style={{ textAlign: 'right' }}>
                  <span className={`amt${a.documented ? '' : ' dim'}`}>{money(a.value_cents)}</span><br />
                  <span style={{ marginTop: 4, display: 'inline-block' }}>
                    {a.documented ? <Badge tone="ok">Documented</Badge> : <Badge tone="bad">Itemize</Badge>}
                  </span>
                </span>
                {a.document_id && docById[a.document_id]
                  ? <DocActions doc={docById[a.document_id]} />
                  : <AttachButton path={`/assets/${a.id}/receipt`} label="Receipt"
                      onDone={() => { assets.reload(); documents.reload() }} />}
                <EditBtn onClick={() => setSheet({ kind: 'asset', item: a })} />
              </span>
            } />
        ))}
        {undocumented && <p className="note">⚠ {undocumented.note}. This is the app flagging an undocumented number, not a rounding gap.</p>}
      </Card>

      {sheet && sheets[sheet.kind](sheet.item)}
    </>
  )
}
