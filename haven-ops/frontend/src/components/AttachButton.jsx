import { useRef, useState } from 'react'
import { api } from '../api'
import { useToast } from '../toast.jsx'

// One-tap file attach: opens the picker, uploads multipart to `path`
// (e.g. /documents/{id}/file or /assets/{id}/receipt), reloads the caller.
export default function AttachButton({ path, onDone, label = 'Attach' }) {
  const ref = useRef()
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  const onChange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setBusy(true)
    try {
      await api.upload(path, file)
      toast('File attached · frozen')
      onDone?.()
    } catch (err) {
      toast(err.message)
    } finally {
      setBusy(false)
      e.target.value = ''
    }
  }

  return (
    <>
      <button type="button" className="mini teal" disabled={busy} onClick={() => ref.current.click()}>
        {busy ? '…' : label}
      </button>
      <input ref={ref} type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" hidden onChange={onChange} />
    </>
  )
}
