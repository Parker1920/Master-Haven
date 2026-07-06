import { useState } from 'react'
import { api } from '../api'
import AttachButton from '../components/AttachButton.jsx'
import FormModal from '../components/FormModal.jsx'
import { useFetch } from '../hooks'
import { useToast } from '../toast.jsx'
import { Badge, Card, DocActions, Row } from '../ui.jsx'

// Governance doc types (migration 003) → registry badge + icon.
const GOV_META = {
  certificate_of_organization: { icon: '📋', badge: 'Filed', kind: 'Formation' },
  operating_agreement: { icon: '📜', badge: 'Signed', kind: 'Governance' },
  schedule_a: { icon: '🧾', badge: 'Executed', kind: 'Governance' },
  cp575: { icon: '🏛️', badge: 'On file', kind: 'Tax' },
  ops_reference: { icon: '📖', badge: 'Current', kind: 'Reference' },
}

export default function Registry() {
  const documents = useFetch('/documents')
  const flags = useFetch('/flags')
  const templates = useFetch('/templates')
  const engagements = useFetch('/engagements')
  const toast = useToast()
  const [filter, setFilter] = useState('all')
  const [uploadOpen, setUploadOpen] = useState(false)

  const docCat = (d) => (d.engagement_id ? 'contract' : 'gov')
  const visible = (cat) => filter === 'all' || filter === cat

  // Receipt scans live on their assets (Ledger) — keep the registry index clean.
  const docs = (documents.data || []).filter((d) => d.doc_type !== 'receipt_scan')
  const actionFlags = (flags.data || []).filter((f) => f.status === 'open' && f.category === 'compliance')

  const removeUploaded = async (d) => {
    if (!window.confirm(`Delete uploaded document "${d.title}"?`)) return
    try {
      await api.del(`/documents/${d.id}`)
      documents.reload()
      toast('Uploaded document deleted')
    } catch (e) { toast(e.message) }
  }

  return (
    <>
      <h1 className="screen-title">Registry</h1>
      <p className="screen-sub">Every LLC document, indexed — plus the templates that spawn them</p>

      <div className="chips">
        {[['all', 'All'], ['gov', 'Governance'], ['contract', 'Contracts'], ['flag', 'Needs action']].map(([key, label]) => (
          <button key={key} type="button" className={`chip${filter === key ? ' on' : ''}`} onClick={() => setFilter(key)}>
            {label}
          </button>
        ))}
      </div>

      <Card title="Documents"
        action={<button className="link" type="button" onClick={() => setUploadOpen(true)}>Upload</button>}>
        {docs.map((d) => {
          const cat = docCat(d)
          if (!visible(cat)) return null
          const gov = GOV_META[d.doc_type]
          return (
            <Row key={d.id} icon={gov?.icon || (d.origin === 'uploaded' ? '📎' : '📄')}
              name={d.title || d.doc_type}
              meta={gov
                ? `${gov.kind} · ${d.generated_at ? String(d.generated_at).slice(0, 10) : 'on file'}${d.has_file ? '' : ' · no file yet'}`
                : `${d.origin === 'uploaded' ? 'Uploaded' : 'Contract'} · ${d.engagement_code || '—'} · v${d.version}${d.generated_at ? ' · ' + String(d.generated_at).slice(0, 10) : ''}`}
              right={
                <span className="acts">
                  {d.has_file
                    ? <DocActions doc={d} />
                    : <AttachButton path={`/documents/${d.id}/file`} onDone={documents.reload} />}
                  {!d.has_file && gov && <Badge tone="ok">{gov.badge}</Badge>}
                  {!d.has_file && !gov && <Badge tone="mute">{d.engagement_state === 'closed' ? 'Closed' : 'On file'}</Badge>}
                  {d.origin === 'uploaded' && (
                    <button type="button" className="mini" aria-label="Delete" onClick={() => removeUploaded(d)}>✕</button>
                  )}
                </span>
              } />
          )
        })}
        {visible('flag') && actionFlags.map((f) => (
          <Row key={`flag-${f.id}`} icon="⚠️" name={f.title.split('—')[0].trim()}
            meta={`Compliance · ${f.title.includes('—') ? f.title.split('—')[1].trim() : 'unresolved'}`}
            right={<Badge tone="bad">Verify</Badge>} />
        ))}
      </Card>

      <Card title="Template library">
        {(templates.data || []).map((t) => (
          <div className="tpl" key={t.id}>
            <span className="grow">
              <span className="tn">{t.name}</span>
              <span className="td">{t.status === 'ready' ? 'Ready · generates from an engagement' : 'Not built yet'}</span>
            </span>
            <button type="button" className={`btn-sm${t.status === 'ready' ? '' : ' ghost'}`}
              onClick={() => toast(t.status === 'ready'
                ? 'Generate from an engagement — Work → engagement → Documents'
                : `${t.name} template lands in a later dispatch`)}>
              {t.status === 'ready' ? 'New' : 'Build'}
            </button>
          </div>
        ))}
      </Card>

      {uploadOpen && (
        <FormModal title="Upload document" submitLabel="Upload & freeze"
          fields={[
            { name: 'title', label: 'Title', required: true },
            { name: 'doc_type', label: 'Type', placeholder: 'governance', hint: 'free text — e.g. governance, correspondence, signed_copy' },
            { name: 'engagement_id', label: 'Engagement (optional)', type: 'select', numeric: true,
              options: (engagements.data || []).map((e) => [e.id, e.code]) },
            { name: 'file', label: 'File', type: 'file', required: true },
          ]}
          onSubmit={async ({ file, ...fields }) => {
            await api.upload('/documents/upload', file, { ...fields, doc_type: fields.doc_type || 'governance' })
            documents.reload()
            toast('Uploaded · frozen with sha256')
          }}
          onClose={() => setUploadOpen(false)} />
      )}
    </>
  )
}
