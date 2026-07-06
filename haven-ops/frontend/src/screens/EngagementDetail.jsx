import { useState } from 'react'
import { api, money } from '../api'
import AttachButton from '../components/AttachButton.jsx'
import FormModal from '../components/FormModal.jsx'
import GenerateModal from '../components/GenerateModal.jsx'
import { useFetch } from '../hooks'
import { useToast } from '../toast.jsx'
import { Badge, Card, DocActions, EditBtn, KV, STAGES, StageBar, stateLabel } from '../ui.jsx'

export default function EngagementDetail({ nav, engagementId }) {
  const engagement = useFetch(`/engagements/${engagementId}`)
  const events = useFetch(`/engagements/${engagementId}/events`)
  const docs = useFetch(`/engagements/${engagementId}/documents`)
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [sheet, setSheet] = useState(null) // 'note' | 'generate' | 'upload' | 'edit' | 'client'
  const [genType, setGenType] = useState('') // preselected type for the Generate sheet

  const e = engagement.data
  if (!e) return <p className="screen-sub">{engagement.error ? String(engagement.error.message) : 'Loading…'}</p>

  const missing = docs.data?.missing ?? e.missing_docs
  const requiredLabels = Object.fromEntries((docs.data?.required || []).map((r) => [r.doc_type, r.label]))
  const docById = Object.fromEntries((docs.data?.documents || []).map((d) => [d.id, d]))
  const reloadAll = () => { engagement.reload(); events.reload(); docs.reload() }

  const nextStage = e.state !== 'closed' ? STAGES[STAGES.indexOf(e.state) + 1] : null

  // Open the Generate sheet — per-type fields, optionally preselected.
  const openGenerate = (docType = '') => {
    setGenType(docType)
    setSheet('generate')
  }

  const doGenerate = async (docType, fields) => {
    const body = fields ? { doc_type: docType, fields } : { doc_type: docType }
    const res = await api.post(`/engagements/${engagementId}/documents`, body)
    toast(`${requiredLabels[docType] || docType} v${res.document.version} generated & frozen${res.signature_stamped ? ' · signature stamped' : ''}`)
    reloadAll()
  }

  const advance = () => {
    if (busy || !nextStage) return
    setBusy(true)
    api.post(`/engagements/${engagementId}/advance`, {})
      .then(() => { toast(`Stage advanced — ${stateLabel(nextStage)}`); reloadAll() })
      .catch((err) => toast(err.message))
      .finally(() => setBusy(false))
  }

  const eventClass = (ev) => (ev.kind === 'gap' ? (missing.length ? 'gap' : 'done') : 'done')

  return (
    <>
      <button className="back" type="button" onClick={() => nav('engagements')}>‹ Engagements</button>
      <h1 className="screen-title">{e.code}</h1>
      <p className="screen-sub">{e.client?.contact} ({e.client?.name}) · {e.title} · {money(e.value_cents)}</p>

      <Card title="Stage"
        action={
          <span className="acts">
            {missing.length
              ? <Badge tone="bad">{stateLabel(e.state)} · {missing.length} gap{missing.length > 1 ? 's' : ''}</Badge>
              : <Badge tone="ok">{stateLabel(e.state)} · sealed</Badge>}
            <EditBtn onClick={() => setSheet('edit')} />
          </span>
        }>
        <StageBar state={e.state} />
        <div className="stagelabel"><span>Inquiry</span><span>{stateLabel(e.state)}</span></div>
        {nextStage && (
          <button type="button" className="btn-sm" style={{ marginTop: 12, width: '100%' }}
            disabled={busy} onClick={advance}>
            Advance → {stateLabel(nextStage)}
          </button>
        )}
      </Card>

      {missing.length > 0 && (
        <div className="gapstrip">
          <div className="t"><span>⚠</span><span>Record incomplete — finish paperwork missing</span></div>
          <p className="d">
            Missing: <b>{missing.map((m) => requiredLabels[m] || m).join(', ')}</b>. Generate the
            missing document{missing.length > 1 ? 's' : ''} to seal the record — generation freezes
            a PDF and appends to the papertrail.
          </p>
          {missing.map((m) => (
            <button key={m} type="button" disabled={busy} onClick={() => openGenerate(m)}>
              Generate &amp; send {requiredLabels[m] || m}
            </button>
          ))}
        </div>
      )}

      <Card title="Papertrail"
        action={
          <span className="acts">
            <button className="link" type="button" onClick={() => setSheet('note')}>Add note</button>
            <Badge tone="mute">Immutable log</Badge>
          </span>
        }>
        <div className="timeline">
          {(events.data || []).map((ev) => {
            const cls = eventClass(ev)
            const doc = ev.document_id ? docById[ev.document_id] : null
            return (
              <div className={`tl ${cls}`} key={ev.id}>
                <span className="node">{cls === 'gap' ? '!' : '✓'}</span>
                <div className="when">{ev.ts ? ev.ts.slice(0, 10) : 'on file'}</div>
                <div className="h">{ev.title}{ev.kind === 'gap' && !missing.length ? ' — since resolved ↓' : ''}</div>
                {ev.detail && <div className="m">{ev.detail}</div>}
                {doc && (doc.sha256
                  ? <a className="dl frozen" href={`/api/documents/${doc.id}/file`} target="_blank" rel="noreferrer">⤓ {doc.filename} · frozen</a>
                  : <span className="dl pending">{doc.title || 'document'} · on file (pre-app)</span>)}
              </div>
            )
          })}
        </div>
      </Card>

      <Card title="Documents · this engagement"
        action={
          <span className="acts">
            <button className="link" type="button" onClick={() => setSheet('upload')}>Upload</button>
            <button className="link" type="button" onClick={() => openGenerate()}>Generate</button>
          </span>
        }>
        {(docs.data?.documents || []).map((d) => (
          <div className="row" key={d.id}>
            <span className="ic">{d.origin === 'uploaded' ? '📎' : d.doc_type === 'sow' ? '📄' : '🧾'}</span>
            <span className="grow">
              <span className="name">{d.title || d.doc_type}</span>
              <span className="meta">v{d.version} · {d.generated_at ? String(d.generated_at).slice(0, 10) : 'on file (pre-app)'} · frozen</span>
            </span>
            {d.sha256
              ? <DocActions doc={d} />
              : <span className="acts">
                  <AttachButton path={`/documents/${d.id}/file`} onDone={reloadAll} />
                  <Badge tone="mute">On file</Badge>
                </span>}
          </div>
        ))}
        {missing.map((m) => (
          <div className="row" key={m}>
            <span className="ic">⚠️</span>
            <span className="grow">
              <span className="name">{requiredLabels[m] || m}</span>
              <span className="meta">Never issued</span>
            </span>
            <Badge tone="bad">Missing</Badge>
          </div>
        ))}
      </Card>

      <Card title="Client" action={<EditBtn onClick={() => setSheet('client')} />}>
        <KV k="Contact" v={`${e.client?.name} · "${e.client?.contact}"`} />
        <KV k="Upstream" v={e.client?.entity} />
        <KV k="Bill-to" v={e.client?.bill_to} />
      </Card>

      {sheet === 'note' && (
        <FormModal title="Add papertrail note" submitLabel="Append to trail"
          fields={[
            { name: 'title', label: 'Title', required: true },
            { name: 'detail', label: 'Detail', type: 'textarea' },
            { name: 'kind', label: 'Kind', type: 'select', required: true,
              options: [['note', 'Note'], ['correspondence', 'Correspondence'], ['delivery', 'Delivery'], ['payment', 'Payment'], ['other', 'Other']] },
            { name: 'ts', label: 'Date', type: 'date' },
            { name: 'actor', label: 'Actor' },
          ]}
          initial={{ kind: 'note', ts: new Date().toISOString().slice(0, 10), actor: 'Voyager’s Haven' }}
          onSubmit={async (vals) => {
            await api.post(`/engagements/${engagementId}/events`, vals)
            events.reload()
            toast('Appended — the trail never edits, only grows')
          }}
          onClose={() => setSheet(null)} />
      )}

      {sheet === 'generate' && (
        <GenerateModal
          generatable={docs.data?.generatable || []}
          initialType={genType}
          onGenerate={doGenerate}
          onClose={() => setSheet(null)} />
      )}

      {sheet === 'upload' && (
        <FormModal title="Upload to this engagement" submitLabel="Upload & freeze"
          fields={[
            { name: 'title', label: 'Title', required: true },
            { name: 'doc_type', label: 'Type', placeholder: 'attachment', hint: 'e.g. signed_copy, evidence, correspondence' },
            { name: 'file', label: 'File', type: 'file', required: true },
          ]}
          onSubmit={async ({ file, ...fields }) => {
            await api.upload('/documents/upload', file, {
              ...fields, doc_type: fields.doc_type || 'attachment', engagement_id: engagementId,
            })
            reloadAll()
            toast('Uploaded · frozen with sha256')
          }}
          onClose={() => setSheet(null)} />
      )}

      {sheet === 'edit' && (
        <FormModal title={`Edit ${e.code}`} initial={e}
          fields={[
            { name: 'title', label: 'Work', required: true },
            { name: 'value_cents', label: 'Value ($)', type: 'money' },
            { name: 'opened_at', label: 'Opened', type: 'date' },
            { name: 'note', label: 'Note', type: 'textarea' },
          ]}
          onSubmit={async (vals) => {
            await api.put(`/engagements/${engagementId}`, vals)
            reloadAll()
            toast('Engagement updated')
          }}
          onClose={() => setSheet(null)} />
      )}

      {sheet === 'client' && e.client && (
        <FormModal title={`Edit client — ${e.client.name}`} initial={e.client}
          fields={[
            { name: 'name', label: 'Name', required: true },
            { name: 'contact', label: 'Handle / contact' },
            { name: 'entity', label: 'Entity / upstream' },
            { name: 'bill_to', label: 'Bill-to' },
          ]}
          onSubmit={async (vals) => {
            await api.put(`/clients/${e.client.id}`, vals)
            engagement.reload()
            toast('Client updated')
          }}
          onClose={() => setSheet(null)} />
      )}
    </>
  )
}
