import { useMemo, useState } from 'react'
import { api } from '../api'
import AttachButton from '../components/AttachButton.jsx'
import FormModal from '../components/FormModal.jsx'
import { useFetch } from '../hooks'
import { useToast } from '../toast.jsx'
import { Badge, Card, DocActions, Row, stateLabel } from '../ui.jsx'

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
  const library = useFetch('/template-library')
  const engagements = useFetch('/engagements')
  const toast = useToast()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(() => new Set())
  const [tplOpen, setTplOpen] = useState(null)
  const [uploadOpen, setUploadOpen] = useState(false)

  // Receipt scans live on their assets (Ledger) — keep the registry index clean.
  const docs = (documents.data || []).filter((d) => d.doc_type !== 'receipt_scan')
  const actionFlags = (flags.data || []).filter((f) => f.status === 'open' && f.category === 'compliance')
  const engMap = Object.fromEntries((engagements.data || []).map((e) => [e.id, e]))

  // ── Folders: Governance & Company + one per engagement ────────────────────
  const folders = useMemo(() => {
    const gov = docs.filter((d) => d.engagement_id == null)
    const byEng = new Map()
    for (const d of docs) {
      if (d.engagement_id == null) continue
      if (!byEng.has(d.engagement_id)) byEng.set(d.engagement_id, [])
      byEng.get(d.engagement_id).push(d)
    }
    const engFolders = [...byEng.entries()].map(([id, list]) => {
      const e = engMap[id]
      return {
        key: `eng-${id}`,
        icon: '📁',
        name: e?.code || list[0].engagement_code || `Engagement ${id}`,
        meta: e
          ? [e.client?.name, e.title, stateLabel(e.state)].filter(Boolean).join(' · ')
          : 'engagement',
        docs: list,
      }
    }).sort((a, b) => b.name.localeCompare(a.name)) // newest code first
    return [
      { key: 'gov', icon: '🏛️', name: 'Governance & Company',
        meta: 'formation · agreements · tax · reference', docs: gov },
      ...engFolders,
    ]
  }, [documents.data, engagements.data]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (key) => setOpen((s) => {
    const next = new Set(s)
    next.has(key) ? next.delete(key) : next.add(key)
    return next
  })

  // ── Search: flat matches across every folder ──────────────────────────────
  const ql = q.trim().toLowerCase()
  const hits = ql
    ? docs.filter((d) => [d.title, d.doc_type, d.engagement_code, d.filename]
        .some((s) => s && s.toLowerCase().includes(ql)))
    : []

  const removeUploaded = async (d) => {
    if (!window.confirm(`Delete uploaded document "${d.title}"?`)) return
    try {
      await api.del(`/documents/${d.id}`)
      documents.reload()
      toast('Uploaded document deleted')
    } catch (e) { toast(e.message) }
  }

  const DocRow = ({ d }) => {
    const gov = GOV_META[d.doc_type]
    return (
      <Row icon={gov?.icon || (d.origin === 'uploaded' ? '📎' : '📄')}
        name={d.title || d.doc_type}
        meta={gov
          ? `${gov.kind} · ${d.generated_at ? String(d.generated_at).slice(0, 10) : 'on file'}${d.has_file ? '' : ' · no file yet'}`
          : `${d.origin === 'uploaded' ? 'Uploaded' : 'Generated'} · ${d.engagement_code || '—'} · v${d.version}${d.generated_at ? ' · ' + String(d.generated_at).slice(0, 10) : ''}`}
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
  }

  return (
    <>
      <h1 className="screen-title">Registry</h1>
      <p className="screen-sub">Every LLC document, foldered — plus the templates that spawn them</p>

      <div className="searchbar">
        <input type="search" placeholder="Search documents — title, type, engagement code…"
          value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {actionFlags.length > 0 && !ql && (
        <Card title="Needs action">
          {actionFlags.map((f) => (
            <Row key={f.id} icon="⚠️" name={f.title.split('—')[0].trim()}
              meta={`Compliance · ${f.title.includes('—') ? f.title.split('—')[1].trim() : 'unresolved'}`}
              right={<Badge tone="bad">Verify</Badge>} />
          ))}
        </Card>
      )}

      {ql ? (
        <Card title={`Search — ${hits.length} match${hits.length === 1 ? '' : 'es'}`}
          action={<button className="link" type="button" onClick={() => setQ('')}>Clear</button>}>
          {hits.map((d) => <DocRow key={d.id} d={d} />)}
          {hits.length === 0 && (
            <div className="empty"><b>No matches</b>Nothing in the registry matches “{q}”.</div>
          )}
        </Card>
      ) : (
        <Card title="Document folders"
          action={<button className="link" type="button" onClick={() => setUploadOpen(true)}>Upload</button>}>
          {folders.map((f) => {
            const isOpen = open.has(f.key)
            const withFile = f.docs.filter((d) => d.has_file).length
            return (
              <div key={f.key}>
                <button type="button" className={`folder${isOpen ? ' open' : ''}`} onClick={() => toggle(f.key)}>
                  <span className="fic">{isOpen ? '📂' : f.icon}</span>
                  <span className="grow">
                    <span className="fn">{f.name}</span>
                    <span className="fm">{f.meta}</span>
                  </span>
                  <Badge tone={withFile === f.docs.length ? 'ok' : 'mute'}>
                    {withFile === f.docs.length ? f.docs.length : `${withFile}/${f.docs.length}`} 📄
                  </Badge>
                  <span className="chev">▶</span>
                </button>
                {isOpen && (
                  <div className="folder-docs">
                    {f.docs.map((d) => <DocRow key={d.id} d={d} />)}
                    {f.docs.length === 0 && (
                      <div className="empty"><b>Empty folder</b>No documents filed here yet.</div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </Card>
      )}

      <Card title="Template library">
        {(library.data || []).map((t) => {
          const expanded = tplOpen === t.doc_type
          return (
            <div className="tpl-wrap" key={t.doc_type}>
              <div className="tpl">
                <span className="grow">
                  <span className="tn">{t.label}{t.signed ? ' ✍' : ''}</span>
                  <span className="td">{t.description}</span>
                </span>
                <span className="acts">
                  <a className="mini teal" href={t.preview} target="_blank" rel="noreferrer">Preview</a>
                  <button type="button" className="mini" aria-label="Details"
                    onClick={() => setTplOpen(expanded ? null : t.doc_type)}>
                    {expanded ? '▴' : 'ⓘ'}
                  </button>
                </span>
              </div>
              {expanded && (
                <div className="tpl-detail">
                  <div className="fh">Generation fields — all optional, defaults fill the gaps</div>
                  {t.fields.length
                    ? t.fields.map((f) => (
                        <div className="fld" key={f.name}>
                          <b>{f.label}</b>{f.hint && <small> — {f.hint}</small>}
                        </div>
                      ))
                    : <div className="fld"><small>None — generates entirely from the engagement record.</small></div>}
                  <div className="fh">Record facts</div>
                  <div className="fld"><small>
                    {t.signed ? 'Carries the e-signature when generated' : 'Unsigned by design'} ·
                    generated {t.generated_count}× so far · Preview renders a watermarked specimen
                    with sample data (never a record) · generate the real thing from
                    Work → engagement → Documents
                  </small></div>
                </div>
              )}
            </div>
          )
        })}
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
