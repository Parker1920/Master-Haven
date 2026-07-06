import { api, money, shortDate } from '../api'
import { useFetch } from '../hooks'
import { useToast } from '../toast.jsx'
import { Badge, Card, Gauge, Row, Todo } from '../ui.jsx'

// Bridge home — the whole company, one glance. All gauges are computed live.
export default function Overview({ nav }) {
  const tasks = useFetch('/tasks')
  const accounts = useFetch('/accounts')
  const company = useFetch('/company')
  const engagements = useFetch('/engagements')
  const compliance = useFetch('/compliance')
  const transactions = useFetch('/transactions')
  const toast = useToast()

  const today = new Date()
  const sub = `The whole company, one glance — ${today.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}`

  // ── Live gauge math (integer cents throughout) ─────────────────────────
  const bank = (accounts.data || []).find((a) => a.kind === 'bank')
  const inflow = (transactions.data || []).filter((t) => t.amount_cents > 0)
    .reduce((s, t) => s + t.amount_cents, 0)
  const taxDue = Math.floor(inflow / 4) // 25% of closed profit
  const openInvoices = (engagements.data || []).filter((e) => e.state !== 'closed')
    .reduce((s, e) => s + e.value_cents, 0)
  const paidCode = (engagements.data || []).find((e) => e.state === 'closed')?.code
  const gaps = (engagements.data || []).filter((e) => e.missing_docs.length > 0)

  const needsYou = (tasks.data || [])
    .filter((t) => !t.done)
    .sort((a, b) => (a.priority || 'P9').localeCompare(b.priority || 'P9'))
    .slice(0, 4)

  const toggleTask = (t) =>
    api.put(`/tasks/${t.id}`, { done: t.done ? 0 : 1 }).then(tasks.reload).catch((e) => toast(e.message))

  const obligations = [...(compliance.data || [])]
    .filter((c) => c.status === 'open')
    .sort((a, b) => {
      const key = (c) => (c.kind === 'flag' ? '0' : c.kind === 'rolling' ? '9' : `1${c.due_date}`)
      return key(a).localeCompare(key(b))
    })
    .slice(0, 3)
  const whenLabel = (c) =>
    c.kind === 'flag' ? 'ASAP' : c.kind === 'rolling' ? 'Rolling' : shortDate(c.due_date)

  const accountBadge = (a) => {
    if (a.kind === 'bank' && a.balance_cents_manual == null) return <Badge tone="warn">Opens Mon</Badge>
    if (a.kind === 'processor') return <Badge tone="mute">Pending</Badge>
    if (a.kind === 'exchange-paper') return <Badge tone="info">Paper</Badge>
    return <Badge tone="ok">{a.status || 'OK'}</Badge>
  }
  const accountIcon = { bank: '🏦', processor: '💳', 'exchange-paper': '📈' }
  const accountMeta = (a) => (a.status || '').split(';')[0]

  return (
    <>
      <h1 className="screen-title">Bridge</h1>
      <p className="screen-sub">{sub}</p>

      <div className="gauges">
        <Gauge accent="teal" label="Treasury"
          val={bank && bank.balance_cents_manual != null ? money(bank.balance_cents_manual) : 'Opens Mon'}
          pending={!bank || bank.balance_cents_manual == null}
          foot="Business checking" />
        <Gauge accent="gold" label="Tax reserve" val={money(0)}
          foot={inflow ? `${money(taxDue)} due · 25% of ${money(inflow)}` : '25% of closed profit'} />
        <Gauge accent="purple" label="Open invoices" val={money(openInvoices)}
          foot={paidCode ? `${paidCode.replace('VHAV-C-2026-', 'VHAV-')} paid` : 'none open'} />
        <Gauge accent={gaps.length ? 'bad' : 'ok'} label="Record gaps" val={String(gaps.length)}
          foot={gaps.length ? 'Missing finish paperwork' : 'All records sealed'} />
      </div>

      <Card title="Needs you"
        action={<button className="link" type="button" onClick={() => nav('compliance')}>All tasks →</button>}>
        {needsYou.map((t) => <Todo key={t.id} task={t} onToggle={toggleTask} />)}
        {needsYou.length === 0 && tasks.data && (
          <div className="empty"><b>Nothing needs you</b>Standing to-do is clear.</div>
        )}
      </Card>

      <Card title="Money"
        action={<button className="link" type="button" onClick={() => nav('ledger')}>Ledger →</button>}>
        {(accounts.data || []).map((a) => (
          <Row key={a.id} icon={accountIcon[a.kind] || '💰'}
            name={a.name.split('·')[0].trim()} meta={accountMeta(a)} right={accountBadge(a)} />
        ))}
        {company.data && (
          <Row icon="🧾" name="Capital contributed" meta="Schedule A"
            right={<span className="amt">{money(company.data.capital_total_cents)}</span>} />
        )}
      </Card>

      <Card title="Next obligations"
        action={<button className="link" type="button" onClick={() => nav('compliance')}>Calendar →</button>}>
        {obligations.map((c) => (
          <div className="cal" key={c.id}>
            <span className="when">{whenLabel(c)}</span>
            <span className="body">
              <span className="h">{c.title} {c.kind === 'flag' && <Badge tone="bad">Flag</Badge>}</span>
              <span className="d">{c.detail}</span>
            </span>
          </div>
        ))}
      </Card>
    </>
  )
}
