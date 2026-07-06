// Tiny fetch layer — one origin (FastAPI serves the bundle), no CORS.
async function handle(r) {
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try {
      const body = await r.json()
      if (body.detail) msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* non-JSON error body */ }
    throw new Error(msg)
  }
  const ct = r.headers.get('content-type') || ''
  return ct.includes('application/json') ? r.json() : r.text()
}

const json = (method) => (path, body) =>
  fetch('/api' + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  }).then(handle)

export const api = {
  get: (path) => fetch('/api' + path).then(handle),
  post: json('POST'),
  put: json('PUT'),
  del: (path) => fetch('/api' + path, { method: 'DELETE' }).then(handle),
  // multipart upload — no Content-Type header (browser sets the boundary)
  upload: (path, file, fields = {}) => {
    const fd = new FormData()
    Object.entries(fields).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') fd.append(k, v)
    })
    fd.append('file', file)
    return fetch('/api' + path, { method: 'POST', body: fd }).then(handle)
  },
}

// Integer cents → "$1,234.56" (backend convention: no floats near money).
export function money(cents) {
  if (cents == null) return '—'
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(cents)
  return `${sign}$${Math.floor(abs / 100).toLocaleString('en-US')}.${String(abs % 100).padStart(2, '0')}`
}

// ISO date → short label for the calendar/when columns.
export function shortDate(iso) {
  if (!iso) return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return iso
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const label = `${months[Number(m[2]) - 1]} ${Number(m[3])}`
  return Number(m[1]) === new Date().getFullYear() ? label : `${label} '${m[1].slice(2)}`
}
