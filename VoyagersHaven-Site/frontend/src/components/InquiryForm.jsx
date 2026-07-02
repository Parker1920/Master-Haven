import { useState } from 'react'
import { sendInquiry } from '../api'
import { BUDGETS, PROJECT_TYPES } from '../data/site'
import { useToast } from './Toast'

const EMPTY = { name: '', email: '', project_type: '', budget: '', message: '', website: '' }

// Backend-backed "start a project" form. Rows land in the inquiries table.
export default function InquiryForm() {
  const toast = useToast()
  const [form, setForm] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    if (!form.name.trim() || !form.email.trim() || !form.message.trim()) {
      toast('Name, email, and a short message are required', 'err')
      return
    }
    setBusy(true)
    try {
      await sendInquiry({
        name: form.name.trim(),
        email: form.email.trim(),
        project_type: form.project_type || null,
        budget: form.budget || null,
        message: form.message.trim(),
        website: form.website, // honeypot — real users leave this blank
      })
      setSent(true)
    } catch (err) {
      toast(err.message, 'err')
    } finally {
      setBusy(false)
    }
  }

  if (sent) {
    return (
      <div className="form-card">
        <div className="form-ok">
          <div className="r-check">✓</div>
          <h3>Message received.</h3>
          <p>Thanks, {form.name.split(' ')[0] || 'there'}. We'll get back to you at {form.email} soon.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="form-card">
      <form onSubmit={submit}>
        {/* Honeypot: hidden from humans, tempting to bots. */}
        <div className="hp" aria-hidden="true">
          <label>Website</label>
          <input type="text" tabIndex={-1} autoComplete="off" value={form.website} onChange={set('website')} />
        </div>
        <div className="form-row">
          <div className="field">
            <label>Name</label>
            <input type="text" value={form.name} onChange={set('name')} placeholder="Your name" />
          </div>
          <div className="field">
            <label>Email</label>
            <input type="email" value={form.email} onChange={set('email')} placeholder="you@example.com" />
          </div>
        </div>
        <div className="form-row">
          <div className="field">
            <label>Project type</label>
            <select value={form.project_type} onChange={set('project_type')}>
              <option value="">Select…</option>
              {PROJECT_TYPES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Budget</label>
            <select value={form.budget} onChange={set('budget')}>
              <option value="">Select…</option>
              {BUDGETS.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
        </div>
        <div className="field">
          <label>What are you building?</label>
          <textarea value={form.message} onChange={set('message')} placeholder="A few sentences about the project…" />
        </div>
        <button className="pay-primary" type="submit" disabled={busy}>
          {busy ? 'Sending…' : 'Send inquiry'}
        </button>
      </form>
    </div>
  )
}
