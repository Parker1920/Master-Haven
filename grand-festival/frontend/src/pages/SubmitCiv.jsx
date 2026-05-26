import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { submitCiv } from '../api.js'

const MAX_LOGO_BYTES = 2 * 1024 * 1024

const EMPTY = {
  name: '',
  role: '',
  description: '',
  status: 'tentative',
  submitter_discord: '',
  submitter_notes: '',
}

export default function SubmitCiv() {
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [logo, setLogo] = useState(null)
  const [logoError, setLogoError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const onLogo = (e) => {
    const file = e.target.files?.[0] || null
    setLogoError(null)
    if (file) {
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
        setLogoError('Use a PNG, JPEG, or WebP image.')
        e.target.value = ''
        return
      }
      if (file.size > MAX_LOGO_BYTES) {
        setLogoError('Image must be under 2 MB.')
        e.target.value = ''
        return
      }
    }
    setLogo(file)
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!form.name.trim() || !form.role.trim() || !form.description.trim()) {
      setError('Name, role, and description are required.')
      return
    }
    setSubmitting(true)
    try {
      const fd = new FormData()
      fd.append('name', form.name.trim())
      fd.append('role', form.role.trim())
      fd.append('description', form.description.trim())
      fd.append('status', form.status)
      if (form.submitter_discord.trim()) fd.append('submitter_discord', form.submitter_discord.trim())
      if (form.submitter_notes.trim()) fd.append('submitter_notes', form.submitter_notes.trim())
      if (logo) fd.append('logo', logo)
      await submitCiv(fd)
      setDone(true)
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="page active">
      <section className="signup-hero">
        <h1>Add Your Civilization</h1>
        <p>
          Tell us who you are and what you'd bring to the festival. Submissions are reviewed by an
          organizer before they appear on the Who's Going roster.
        </p>
      </section>

      <section className="signup-body">
        <div className="signup-inner" style={{ gridTemplateColumns: '1fr' }}>
          <div className="signup-card">
            {done ? (
              <div className="submit-success">
                <div className="submit-success-mark">✓</div>
                <h2>Submission received</h2>
                <p>
                  Thanks! Your civilization has been sent to the organizers for review. Once it's
                  approved, it'll show up on the Who's Going roster.
                </p>
                <div className="submit-actions">
                  <button className="hero-cta" onClick={() => navigate('/whos-going')}>
                    Back to Who's Going
                  </button>
                  <button
                    className="link-btn"
                    onClick={() => {
                      setForm(EMPTY)
                      setLogo(null)
                      setDone(false)
                    }}
                  >
                    Submit another
                  </button>
                </div>
              </div>
            ) : (
              <form className="civ-form" onSubmit={onSubmit}>
                <h2>Civilization details</h2>

                <label className="field">
                  <span>Civilization name <em>*</em></span>
                  <input type="text" value={form.name} onChange={update('name')} maxLength={120} placeholder="e.g. Galactic Hub Project" required />
                </label>

                <label className="field">
                  <span>Role / district <em>*</em></span>
                  <input type="text" value={form.role} onChange={update('role')} maxLength={120} placeholder="e.g. Race Track Hosts, Pavilion District" required />
                </label>

                <label className="field">
                  <span>What you'll bring <em>*</em></span>
                  <textarea value={form.description} onChange={update('description')} maxLength={2000} rows={4} placeholder="A sentence or two about your builds, events, or what your community is contributing." required />
                </label>

                <label className="field">
                  <span>Status</span>
                  <select value={form.status} onChange={update('status')}>
                    <option value="tentative">Tentative — interested, not locked in</option>
                    <option value="confirmed">Confirmed — we're in</option>
                  </select>
                </label>

                <label className="field">
                  <span>Your Discord handle</span>
                  <input type="text" value={form.submitter_discord} onChange={update('submitter_discord')} maxLength={100} placeholder="e.g. traveler#0001 (so we can reach you)" />
                </label>

                <label className="field">
                  <span>Notes for the organizers</span>
                  <textarea value={form.submitter_notes} onChange={update('submitter_notes')} maxLength={2000} rows={3} placeholder="Anything else we should know? Build size, special requests, questions…" />
                </label>

                <label className="field">
                  <span>Logo / emblem <small>(optional · PNG, JPEG or WebP · max 2 MB)</small></span>
                  <input type="file" accept="image/png,image/jpeg,image/webp" onChange={onLogo} />
                  {logoError && <span className="field-error">{logoError}</span>}
                </label>

                {error && <div className="state-msg error">{error}</div>}

                <button className="hero-cta submit-btn" type="submit" disabled={submitting}>
                  {submitting ? 'Submitting…' : 'Submit for review ▸'}
                </button>
                <p className="submit-fineprint">
                  Submissions are held for organizer approval and never appear on the public site
                  automatically.
                </p>
              </form>
            )}
          </div>
        </div>
      </section>
    </main>
  )
}
