import { useState } from 'react'
import { api } from '../api'
import FormModal from '../components/FormModal.jsx'
import { useFetch } from '../hooks'
import { useToast } from '../toast.jsx'
import { Badge, Card, EditBtn, KV, Row } from '../ui.jsx'

// Initiative status/priority → badge, mirroring the mockup's chips.
function initiativeBadge(i) {
  const map = {
    live: ['ok', 'Live'],
    delivered: ['ok', 'Delivered'],
    build: ['info', i.priority ? `${i.priority} · build` : 'Build'],
    conflict: ['bad', 'Conflict'],
    paper: ['info', 'Paper'],
    draft: ['warn', 'Draft'],
    'launch-prep': ['warn', i.priority || 'Launch'],
    mockup: ['mute', i.priority || 'Mockup'],
  }
  const [tone, label] = map[i.status] || ['mute', i.priority || i.status || '—']
  return <Badge tone={tone}>{label}</Badge>
}

const personBadge = (tags) => {
  if (!tags) return null
  if (tags.includes('co-owner')) return <Badge tone="info">Co-owner (pending)</Badge>
  if (tags === 'external') return <Badge tone="mute">External</Badge>
  if (tags === 'partner') return <Badge tone="mute">Partner</Badge>
  return null
}

const STATUS_OPTIONS = [['live', 'Live'], ['build', 'Build'], ['launch-prep', 'Launch prep'],
  ['delivered', 'Delivered'], ['paper', 'Paper'], ['draft', 'Draft'],
  ['mockup', 'Mockup'], ['conflict', 'Conflict']]

export default function Company({ openDocModal }) {
  const company = useFetch('/company')
  const initiatives = useFetch('/initiatives')
  const people = useFetch('/people')
  const environment = useFetch('/environment')
  const toast = useToast()
  const [sigMissing, setSigMissing] = useState(false)
  const [sheet, setSheet] = useState(null) // {kind, item}

  const c = company.data

  const copy = (value, label) => {
    const write = navigator.clipboard?.writeText
      ? navigator.clipboard.writeText(value)
      : Promise.reject()
    write.then(() => toast(`Copied ${label}`)).catch(() => window.prompt('Copy:', value))
  }

  const quickRef = c ? [
    ['Legal name', c.legal_name], ['Entity #', c.entity_no], ['EIN', c.ein],
    ['Type', c.entity_type], ['Formed', c.formed], ['Office', c.office],
    ['NAICS', c.naics], ['Bank', c.bank],
  ] : []

  const envTone = (status) =>
    /broken/i.test(status || '') ? 'bad' : (status || '').includes('⚠') ? 'warn' : undefined

  // ── One CRUD sheet per register (create when item is null, else edit) ──
  const crudSheet = (kind, path, reload, fields, item, extra = {}) => (
    <FormModal
      title={`${item ? 'Edit' : 'Add'} ${kind}`}
      fields={fields}
      initial={item || extra.defaults || {}}
      onSubmit={async (vals) => {
        if (item) await api.put(`${path}/${item.id}`, vals)
        else await api.post(path, vals)
        reload()
        toast(`${kind} saved`)
      }}
      onDelete={item ? async () => { await api.del(`${path}/${item.id}`); reload(); toast(`${kind} deleted`) } : undefined}
      onClose={() => setSheet(null)}
    />
  )

  const sheets = {
    company: () => (
      <FormModal title="Edit company" initial={c}
        fields={[
          { name: 'legal_name', label: 'Legal name', required: true },
          { name: 'entity_type', label: 'Type' },
          { name: 'entity_no', label: 'Entity #' },
          { name: 'ein', label: 'EIN' },
          { name: 'formed', label: 'Formed' },
          { name: 'office', label: 'Office' },
          { name: 'naics', label: 'NAICS' },
          { name: 'oa_status', label: 'Operating Agreement' },
          { name: 'bank', label: 'Bank' },
          { name: 'capital_total_cents', label: 'Schedule A capital ($)', type: 'money' },
          { name: 'capital_note', label: 'Capital note', type: 'textarea' },
        ]}
        onSubmit={async (vals) => { await api.put('/company', vals); company.reload(); toast('Company updated') }}
        onClose={() => setSheet(null)} />
    ),
    person: (item) => crudSheet('person', '/people', people.reload, [
      { name: 'name', label: 'Name', required: true },
      { name: 'role', label: 'Role' },
      { name: 'domain', label: 'Domain' },
      { name: 'tags', label: 'Tags', hint: "'partner', 'external', 'co-owner (pending)' drive the badges + the emit" },
      { name: 'sort', label: 'Sort', type: 'number' },
    ], item),
    initiative: (item) => crudSheet('initiative', '/initiatives', initiatives.reload, [
      { name: 'name', label: 'Name', required: true },
      { name: 'status', label: 'Status', type: 'select', options: STATUS_OPTIONS },
      { name: 'domain', label: 'Domain / host' },
      { name: 'port', label: 'Port' },
      { name: 'priority', label: 'Priority', hint: 'P0–P4 — feeds the emitted Priority Stack' },
      { name: 'note', label: 'Note', type: 'textarea' },
      { name: 'sort', label: 'Sort', type: 'number' },
    ], item),
    environment: (item) => crudSheet('environment item', '/environment', environment.reload, [
      { name: 'item', label: 'Item', required: true },
      { name: 'status', label: 'Status', hint: 'include ⚠ to tint it amber here and in the emit' },
      { name: 'sort', label: 'Sort', type: 'number' },
    ], item),
  }

  return (
    <>
      <h1 className="screen-title">Company</h1>
      <p className="screen-sub">The reference layer Haven Ops emits your doc from</p>

      <Card title="Project Instructions">
        <div className="split">
          <div className="half">
            <div className="h">Durable half</div>
            <div className="p">Rules, dynamic, response patterns — hand-kept, rarely changes</div>
          </div>
          <div className="half">
            <div className="h">Live half</div>
            <div className="p">Rendered from the registers below — never goes stale</div>
          </div>
        </div>
        <button className="gen-btn" type="button" onClick={openDocModal}>Generate current doc</button>
        <p className="note">
          This is the fix for the June-1 drift: the live sections stop being typed by hand.
          You edit the data here; the doc is emitted.
        </p>
      </Card>

      <Card title="Quick reference"
        action={c && (
          <span className="acts">
            <button className="link" type="button"
              onClick={() => copy(quickRef.map(([k, v]) => `${k}: ${v}`).join('\n'), 'all')}>Copy all</button>
            <EditBtn onClick={() => setSheet({ kind: 'company' })} />
          </span>
        )}>
        {quickRef.map(([k, v]) => (
          <KV key={k} k={k} v={v}
            action={<button className="cp" type="button" onClick={() => copy(v || '', k)}>Copy</button>} />
        ))}
      </Card>

      <Card title="E-signature on file">
        {!sigMissing ? (
          <span className="sigcard-lg">
            {/* streamed from the data dir via the API — never bundled */}
            <img src="/api/company/signature" alt="signature on file" onError={() => setSigMissing(true)} />
          </span>
        ) : (
          <Badge tone="bad">signature.png not in the data dir</Badge>
        )}
        <p className="note">
          Stamped as {c?.legal_name || 'the company'}'s signature on generated documents —
          SOW, completion certificates, receipts — the moment you sign.
        </p>
      </Card>

      <Card title="Initiatives · emits &quot;Active Initiatives&quot;"
        action={<button className="link" type="button" onClick={() => setSheet({ kind: 'initiative', item: null })}>Add</button>}>
        {(initiatives.data || []).map((i) => (
          <Row key={i.id} name={i.name}
            meta={[i.domain, i.port && `:${i.port}`, i.note].filter(Boolean).join(' · ')}
            right={<span className="acts">{initiativeBadge(i)}<EditBtn onClick={() => setSheet({ kind: 'initiative', item: i })} /></span>} />
        ))}
      </Card>

      <Card title="People · emits &quot;Key People&quot;"
        action={<button className="link" type="button" onClick={() => setSheet({ kind: 'person', item: null })}>Add</button>}>
        {(people.data || []).map((p) => (
          <Row key={p.id} name={p.name} meta={p.role}
            right={<span className="acts">{personBadge(p.tags)}<EditBtn onClick={() => setSheet({ kind: 'person', item: p })} /></span>} />
        ))}
      </Card>

      <Card title="Environment · emits &quot;Current State&quot;"
        action={<button className="link" type="button" onClick={() => setSheet({ kind: 'environment', item: null })}>Add</button>}>
        {(environment.data || []).map((env) => (
          <KV key={env.id} k={env.item} v={env.status} tone={envTone(env.status)}
            action={<EditBtn onClick={() => setSheet({ kind: 'environment', item: env })} />} />
        ))}
      </Card>

      {sheet && sheets[sheet.kind](sheet.item)}
    </>
  )
}
