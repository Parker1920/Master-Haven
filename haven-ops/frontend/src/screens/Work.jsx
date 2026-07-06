import { useState } from 'react'
import { api, money } from '../api'
import FormModal from '../components/FormModal.jsx'
import { useFetch } from '../hooks'
import { useToast } from '../toast.jsx'
import { Card, StageBar, stateLabel } from '../ui.jsx'

const STATE_OPTIONS = [['inquiry', 'Inquiry'], ['proposal', 'Proposal'], ['contract', 'Contract'],
  ['in_progress', 'In progress'], ['delivered', 'Delivered'], ['closed', 'Closed']]

export default function Work({ nav }) {
  const engagements = useFetch('/engagements')
  const clients = useFetch('/clients')
  const toast = useToast()
  const [sheet, setSheet] = useState(null) // 'engagement' | 'client'

  const list = engagements.data || []
  const active = list.filter((e) => e.state !== 'closed')
  const closed = list.filter((e) => e.state === 'closed')

  // Next free code for the current year: VHAV-C-YYYY-NNN
  const nextCode = () => {
    const year = new Date().getFullYear()
    const re = new RegExp(`^VHAV-C-${year}-(\\d+)$`)
    const n = Math.max(0, ...list.map((e) => Number(re.exec(e.code)?.[1] || 0))) + 1
    return `VHAV-C-${year}-${String(n).padStart(3, '0')}`
  }

  const EngRow = ({ e }) => (
    <button className="eng-row" type="button" onClick={() => nav('engagement', e.id)}>
      <span className="ic">🧾</span>
      <span className="grow" style={{ flex: 1 }}>
        <span className="name">{e.code}</span>
        <span className="meta">
          {e.client?.contact} · {e.title} · {money(e.value_cents)}{e.state === 'closed' ? ' · paid' : ''}
        </span>
        <StageBar state={e.state} />
        <span className="stagelabel">
          <span>{stateLabel(e.state)}</span>
          {e.missing_docs.length > 0
            ? <span style={{ color: 'var(--bad)' }}>⚠ {e.missing_docs.length} gap{e.missing_docs.length > 1 ? 's' : ''} ▸</span>
            : <span>sealed ▸</span>}
        </span>
      </span>
    </button>
  )

  return (
    <>
      <h1 className="screen-title">Engagements</h1>
      <p className="screen-sub">Every client request — inquiry to receipt</p>

      <Card title="The lifecycle">
        <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0, lineHeight: 1.65 }}>
          Inquiry → Proposal → Contract → In&nbsp;progress → Delivered → Closed.
          A document is generated and <b style={{ color: 'var(--purple)' }}>frozen</b> at each gate;
          the close issues a <b style={{ color: 'var(--gold)' }}>receipt</b>. Nothing is ever overwritten.
        </p>
      </Card>

      <Card title={`Active · ${active.length}`}
        action={
          <span className="acts">
            <button className="link" type="button" onClick={() => setSheet('client')}>+ Client</button>
            <button className="link" type="button" onClick={() => setSheet('engagement')}>New</button>
          </span>
        }>
        {active.map((e) => <EngRow key={e.id} e={e} />)}
        {active.length === 0 && engagements.data && (
          <div className="empty"><b>No active engagements</b>Start one when the next inquiry lands.</div>
        )}
      </Card>

      <Card title={`Closed · ${closed.length}`}>
        {closed.map((e) => <EngRow key={e.id} e={e} />)}
      </Card>

      {sheet === 'engagement' && (
        <FormModal title="New engagement" submitLabel="Open engagement"
          fields={[
            { name: 'code', label: 'Code', required: true },
            { name: 'client_id', label: 'Client', type: 'select', numeric: true, required: true,
              options: (clients.data || []).map((cl) => [cl.id, `${cl.contact ? cl.contact + ' — ' : ''}${cl.name}`]),
              hint: 'someone new? close this and use + Client first' },
            { name: 'title', label: 'Work', required: true },
            { name: 'value_cents', label: 'Value ($)', type: 'money' },
            { name: 'state', label: 'Stage', type: 'select', options: STATE_OPTIONS, required: true },
            { name: 'opened_at', label: 'Opened', type: 'date' },
            { name: 'note', label: 'Note', type: 'textarea' },
          ]}
          initial={{ code: nextCode(), state: 'inquiry', opened_at: new Date().toISOString().slice(0, 10) }}
          onSubmit={async (vals) => {
            await api.post('/engagements', { ...vals, value_cents: vals.value_cents ?? 0 })
            engagements.reload()
            toast(`${vals.code} opened`)
          }}
          onClose={() => setSheet(null)} />
      )}

      {sheet === 'client' && (
        <FormModal title="New client" submitLabel="Add client"
          fields={[
            { name: 'name', label: 'Name', required: true },
            { name: 'contact', label: 'Handle / contact' },
            { name: 'entity', label: 'Entity / upstream' },
            { name: 'bill_to', label: 'Bill-to' },
          ]}
          onSubmit={async (vals) => {
            await api.post('/clients', vals)
            clients.reload()
            toast(`Client ${vals.name} added — now open the engagement`)
          }}
          onClose={() => setSheet(null)} />
      )}
    </>
  )
}
