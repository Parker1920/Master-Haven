import { useState } from 'react'
import { useToast } from '../toast.jsx'

/* The one reusable edit sheet. Field spec:
   { name, label, type?: 'text'|'textarea'|'number'|'money'|'select'|'date'|'checkbox'|'file',
     required?, options?: [[value,label]], hint?, accept?, placeholder? }
   money renders dollars, submits integer CENTS. checkbox submits 0/1.
   select '' submits null. file submits the File object (caller api.upload's it). */
export default function FormModal({ title, fields, initial = {}, submitLabel = 'Save',
                                    onSubmit, onDelete, onClose }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [vals, setVals] = useState(() => {
    const v = {}
    for (const f of fields) {
      const raw = initial[f.name]
      if (f.type === 'money') v[f.name] = raw == null ? '' : (raw / 100).toFixed(2)
      else if (f.type === 'checkbox') v[f.name] = !!raw
      else if (f.type === 'file') v[f.name] = null
      else if (f.type === 'date') v[f.name] = raw ? String(raw).slice(0, 10) : ''
      else v[f.name] = raw ?? ''
    }
    return v
  })
  const set = (name, value) => setVals((s) => ({ ...s, [name]: value }))

  const submit = async () => {
    const out = {}
    for (const f of fields) {
      let v = vals[f.name]
      if (f.required && (v === '' || v == null || (f.type === 'file' && !v))) {
        toast(`${f.label} is required`)
        return
      }
      if (f.type === 'money') v = v === '' ? null : Math.round(parseFloat(v) * 100)
      else if (f.type === 'number') v = v === '' ? null : Number(v)
      else if (f.type === 'checkbox') v = v ? 1 : 0
      else if (f.type === 'select') v = v === '' ? null : (f.numeric ? Number(v) : v)
      else if (f.type === 'date' && v === '') v = null
      if (f.type === 'money' && v != null && Number.isNaN(v)) {
        toast(`${f.label} must be a dollar amount`)
        return
      }
      out[f.name] = v
    }
    setBusy(true)
    try {
      await onSubmit(out)
      onClose()
    } catch (e) {
      toast(e.message)
    } finally {
      setBusy(false)
    }
  }

  const doDelete = async () => {
    if (!window.confirm('Delete this record?')) return
    setBusy(true)
    try {
      await onDelete()
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
        <span>{title}</span>
        <button type="button" aria-label="Close" onClick={onClose}>✕</button>
      </div>
      <div className="sheet-body">
        {fields.map((f) => (
          <div className={`field${f.type === 'checkbox' ? ' checkbox' : ''}`} key={f.name}>
            {f.type === 'checkbox' ? (
              <>
                <input id={`f-${f.name}`} type="checkbox" checked={vals[f.name]}
                  onChange={(e) => set(f.name, e.target.checked)} />
                <label htmlFor={`f-${f.name}`} style={{ margin: 0 }}>{f.label}</label>
              </>
            ) : (
              <>
                <label htmlFor={`f-${f.name}`}>{f.label}{f.required ? ' *' : ''}</label>
                {f.type === 'textarea' ? (
                  <textarea id={`f-${f.name}`} value={vals[f.name]}
                    placeholder={f.placeholder} onChange={(e) => set(f.name, e.target.value)} />
                ) : f.type === 'select' ? (
                  <select id={`f-${f.name}`} value={vals[f.name] ?? ''}
                    onChange={(e) => set(f.name, e.target.value)}>
                    {!f.required && <option value="">—</option>}
                    {(f.options || []).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                ) : f.type === 'file' ? (
                  <input id={`f-${f.name}`} type="file" accept={f.accept || '.pdf,.png,.jpg,.jpeg,.webp'}
                    onChange={(e) => set(f.name, e.target.files[0] || null)} />
                ) : (
                  <input id={`f-${f.name}`}
                    type={f.type === 'money' ? 'text' : f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'}
                    inputMode={f.type === 'money' ? 'decimal' : undefined}
                    value={vals[f.name]} placeholder={f.type === 'money' ? '0.00' : f.placeholder}
                    onChange={(e) => set(f.name, e.target.value)} />
                )}
                {f.hint && <div className="hint">{f.hint}</div>}
              </>
            )}
          </div>
        ))}
      </div>
      <div className="modal-actions">
        {onDelete && <button type="button" className="danger-btn" disabled={busy} onClick={doDelete}>Delete</button>}
        <button type="button" disabled={busy} onClick={submit}>{busy ? '…' : submitLabel}</button>
      </div>
    </div>
  )
}
