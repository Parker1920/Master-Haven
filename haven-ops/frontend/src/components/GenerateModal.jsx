import { useState } from 'react'
import { useToast } from '../toast.jsx'

/* Generate & freeze sheet — pick a doc type, get THAT type's fields.
   Field specs come from the backend (generatable[].fields, mirroring
   docgen.DOC_FIELDS); every field is optional — the templates carry
   sensible defaults, so a blank sheet still produces a valid document.
   Only non-empty values are sent (as body.fields → Jinja `extra`). */
export default function GenerateModal({ generatable, initialType = '', onGenerate, onClose }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [docType, setDocType] = useState(initialType)
  const [vals, setVals] = useState({})

  const spec = generatable.find((g) => g.doc_type === docType)
  const fields = spec?.fields || []
  const set = (name, value) => setVals((s) => ({ ...s, [name]: value }))

  const pick = (t) => {
    setDocType(t)
    setVals({}) // field values don't carry across types
  }

  const submit = async () => {
    if (!docType) { toast('Pick a document type'); return }
    const out = {}
    for (const f of fields) {
      const v = typeof vals[f.name] === 'string' ? vals[f.name].trim() : vals[f.name]
      if (v) out[f.name] = v
    }
    setBusy(true)
    try {
      await onGenerate(docType, Object.keys(out).length ? out : null)
      onClose()
    } catch (e) {
      toast(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal show">
      <div className="modal-bar">
        <span>Generate document</span>
        <button type="button" aria-label="Close" onClick={onClose}>✕</button>
      </div>
      <div className="sheet-body">
        <div className="field">
          <label htmlFor="gen-type">Document type *</label>
          <select id="gen-type" value={docType} onChange={(e) => pick(e.target.value)}>
            <option value="">—</option>
            {generatable.map((g) => <option key={g.doc_type} value={g.doc_type}>{g.label}</option>)}
          </select>
          <div className="hint">
            lifecycle order — an existing type re-issues as a new version, nothing is overwritten
          </div>
        </div>

        {docType && fields.length > 0 && (
          <div className="field">
            <div className="hint" style={{ marginBottom: 10 }}>
              All optional — leave anything blank and the template's default fills it.
            </div>
          </div>
        )}
        {docType && fields.map((f) => (
          <div className="field" key={f.name}>
            <label htmlFor={`gf-${f.name}`}>{f.label}</label>
            {f.kind === 'textarea' ? (
              <textarea id={`gf-${f.name}`} value={vals[f.name] ?? ''}
                onChange={(e) => set(f.name, e.target.value)} />
            ) : (
              <input id={`gf-${f.name}`} type={f.kind === 'date' ? 'date' : 'text'}
                value={vals[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)} />
            )}
            {f.hint && <div className="hint">{f.hint}</div>}
          </div>
        ))}
        {docType && fields.length === 0 && (
          <div className="field">
            <div className="hint">
              This type has no extra fields — it generates entirely from the engagement record.
            </div>
          </div>
        )}
      </div>
      <div className="modal-actions">
        <button type="button" disabled={busy} onClick={submit}>
          {busy ? '…' : 'Generate & freeze'}
        </button>
      </div>
    </div>
  )
}
