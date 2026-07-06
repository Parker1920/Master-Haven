import { useState } from 'react'
import { api, shortDate } from '../api'
import FormModal from '../components/FormModal.jsx'
import { useFetch } from '../hooks'
import { useToast } from '../toast.jsx'
import { Badge, Cal, Card, EditBtn, Row, Todo } from '../ui.jsx'

const PRIORITIES = [['P0', 'P0'], ['P1', 'P1'], ['P2', 'P2'], ['P3', 'P3'], ['P4', 'P4']]
const CAL_KINDS = [['deadline', 'Deadline'], ['flag', 'Flag (ASAP)'], ['rolling', 'Rolling']]

export default function Compliance({ nav }) {
  const compliance = useFetch('/compliance')
  const engagements = useFetch('/engagements')
  const tasks = useFetch('/tasks')
  const flags = useFetch('/flags')
  const toast = useToast()
  const [sheet, setSheet] = useState(null) // {kind, item}

  const calendar = [...(compliance.data || [])]
    .filter((c) => c.status === 'open')
    .sort((a, b) => {
      const key = (c) => (c.kind === 'flag' ? '0' : c.kind === 'rolling' ? '9' : `1${c.due_date}`)
      return key(a).localeCompare(key(b))
    })
  const whenLabel = (c) =>
    c.kind === 'flag' ? 'ASAP' : c.kind === 'rolling' ? 'Rolling' : shortDate(c.due_date)

  const allTasks = tasks.data || []
  const doneCount = allTasks.filter((t) => t.done).length
  const toggleTask = (t) =>
    api.put(`/tasks/${t.id}`, { done: t.done ? 0 : 1 }).then(tasks.reload).catch((e) => toast(e.message))

  const setFlagStatus = (f, status) =>
    api.put(`/flags/${f.id}`, { status }).then(flags.reload).catch((e) => toast(e.message))

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
    calendar: (item) => crudSheet('calendar item', '/compliance', compliance.reload, [
      { name: 'title', label: 'Title', required: true },
      { name: 'detail', label: 'Detail' },
      { name: 'kind', label: 'Kind', type: 'select', options: CAL_KINDS, required: true },
      { name: 'due_date', label: 'Due date', type: 'date', hint: 'ignored for flag/rolling' },
      { name: 'status', label: 'Status', type: 'select', options: [['open', 'Open'], ['done', 'Done']], required: true },
    ], item, { kind: 'deadline', status: 'open' }),
    task: (item) => crudSheet('task', '/tasks', tasks.reload, [
      { name: 'title', label: 'Title', required: true },
      { name: 'detail', label: 'Detail', type: 'textarea' },
      { name: 'priority', label: 'Priority', type: 'select', options: PRIORITIES },
      { name: 'due', label: 'Due', placeholder: "'ASAP', '2026-07-06', 'Monday'…" },
      { name: 'owner', label: 'Owner', placeholder: 'Parker' },
      { name: 'blocked_by', label: 'Blocked by' },
      { name: 'category', label: 'Category', placeholder: 'banking / compliance / records / …' },
    ], item, { owner: 'Parker' }),
    flag: (item) => crudSheet('flag', '/flags', flags.reload, [
      { name: 'title', label: 'Title', required: true },
      { name: 'category', label: 'Category', placeholder: 'compliance / security / legal / infra / finance / records' },
      { name: 'status', label: 'Status', type: 'select', options: [['open', 'Open'], ['resolved', 'Resolved']], required: true },
    ], item, { status: 'open' }),
  }

  return (
    <>
      <h1 className="screen-title">Compliance</h1>
      <p className="screen-sub">Deadlines, contracts, and the standing to-do</p>

      <Card title="Calendar"
        action={<button className="link" type="button" onClick={() => setSheet({ kind: 'calendar', item: null })}>Add</button>}>
        {calendar.map((c) => (
          <Cal key={c.id} when={whenLabel(c)} title={c.title} detail={c.detail}
            badge={c.kind === 'flag' ? <Badge tone="bad">Flag</Badge> : null}
            action={<EditBtn onClick={() => setSheet({ kind: 'calendar', item: c })} />} />
        ))}
      </Card>

      <Card title="Contracts">
        {(engagements.data || []).map((e) => (
          <Row key={e.id} icon="📄" name={e.code}
            meta={`${e.client?.contact} · ${e.state}${e.missing_docs.length ? ' · finish paperwork missing' : ' · record sealed'}`}
            right={e.missing_docs.length
              ? <Badge tone="bad">{e.missing_docs.length} gap{e.missing_docs.length > 1 ? 's' : ''}</Badge>
              : <Badge tone="ok">Sealed</Badge>} />
        ))}
      </Card>

      <Card title="Flags"
        action={<button className="link" type="button" onClick={() => setSheet({ kind: 'flag', item: null })}>Add</button>}>
        {(flags.data || []).map((f) => (
          <Row key={f.id} icon={f.status === 'open' ? '🚩' : '✅'} name={f.title} meta={f.category}
            right={
              <span className="acts">
                {f.status === 'open'
                  ? <button type="button" className="mini teal" onClick={() => setFlagStatus(f, 'resolved')}>Resolve</button>
                  : <button type="button" className="mini" onClick={() => setFlagStatus(f, 'open')}>Reopen</button>}
                <EditBtn onClick={() => setSheet({ kind: 'flag', item: f })} />
              </span>
            } />
        ))}
      </Card>

      <Card title="Standing to-do"
        action={
          <span className="acts">
            <Badge tone="mute">{doneCount} / {allTasks.length}</Badge>
            <button className="link" type="button" onClick={() => setSheet({ kind: 'task', item: null })}>Add</button>
          </span>
        }>
        {allTasks.map((t) => (
          <div key={t.id} className="todo-row">
            <Todo task={t} onToggle={toggleTask} />
            <EditBtn onClick={() => setSheet({ kind: 'task', item: t })} />
          </div>
        ))}
      </Card>

      {sheet && sheets[sheet.kind](sheet.item)}
    </>
  )
}
