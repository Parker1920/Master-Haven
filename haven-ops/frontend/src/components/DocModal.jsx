import { useEffect, useState } from 'react'
import { useToast } from '../toast.jsx'

// The emit modal — fetches the live doc from the backend (which replaced the
// mockup's client-side emitDoc()) and offers Copy / Download.
export default function DocModal({ open, onClose }) {
  const [text, setText] = useState('')
  const toast = useToast()

  useEffect(() => {
    if (!open) return
    setText('Generating from live state…')
    fetch('/api/emit/project-instructions')
      .then((r) => { if (!r.ok) throw new Error(`${r.status}`); return r.text() })
      .then(setText)
      .catch((e) => setText(`Failed to emit: ${e.message}`))
  }, [open])

  if (!open) return null

  const copy = () => {
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text)
        .then(() => toast('Copied full doc'))
        .catch(() => fallbackCopy())
    } else fallbackCopy()
  }
  const fallbackCopy = () => {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy'); toast('Copied') } catch { toast('Select the text to copy') }
    ta.remove()
  }
  const download = () => {
    try {
      const blob = new Blob([text], { type: 'text/markdown' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = 'haven-project-instructions.md'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(a.href)
      toast('Downloaded .md')
    } catch { toast('Download blocked here — use Copy') }
  }

  return (
    <div className="modal show">
      <div className="modal-bar">
        <span>Project Instructions — generated live</span>
        <button type="button" aria-label="Close" onClick={onClose}>✕</button>
      </div>
      <pre id="docOut">{text}</pre>
      <div className="modal-actions">
        <button type="button" onClick={copy}>Copy</button>
        <button type="button" onClick={download}>Download .md</button>
      </div>
    </div>
  )
}
