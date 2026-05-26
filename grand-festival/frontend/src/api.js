// Thin fetch wrapper. Same-origin in production (FastAPI serves the SPA);
// in dev, Vite proxies /api to the backend. credentials:'include' carries the
// admin session cookie.

const BASE = '/api'

async function handle(res) {
  let body = null
  const text = await res.text()
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }
  if (!res.ok) {
    const detail =
      (body && body.detail) ||
      (typeof body === 'string' ? body : null) ||
      `Request failed (${res.status})`
    const err = new Error(detail)
    err.status = res.status
    throw err
  }
  return body
}

const opts = (extra = {}) => ({ credentials: 'include', ...extra })
const jsonOpts = (method, payload) =>
  opts({
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

// ---- Public ----
export const getCivs = async () => handle(await fetch(`${BASE}/civs`, opts()))
export const getSchedule = async () => handle(await fetch(`${BASE}/schedule`, opts()))
export const submitCiv = async (formData) =>
  handle(await fetch(`${BASE}/civs/submit`, opts({ method: 'POST', body: formData })))

// ---- Admin ----
export const adminLogin = async (password) =>
  handle(await fetch(`${BASE}/admin/login`, jsonOpts('POST', { password })))
export const adminLogout = async () =>
  handle(await fetch(`${BASE}/admin/logout`, opts({ method: 'POST' })))
export const adminMe = async () => handle(await fetch(`${BASE}/admin/me`, opts()))
export const adminListCivs = async () => handle(await fetch(`${BASE}/admin/civs`, opts()))
export const adminApprove = async (id) =>
  handle(await fetch(`${BASE}/admin/civs/${id}/approve`, opts({ method: 'POST' })))
export const adminReject = async (id, notes) =>
  handle(await fetch(`${BASE}/admin/civs/${id}/reject`, jsonOpts('POST', { notes: notes || null })))
export const adminEdit = async (id, patch) =>
  handle(await fetch(`${BASE}/admin/civs/${id}`, jsonOpts('PATCH', patch)))
export const adminDelete = async (id) =>
  handle(await fetch(`${BASE}/admin/civs/${id}`, opts({ method: 'DELETE' })))
export const adminSetLogo = async (id, file) => {
  const fd = new FormData()
  fd.append('logo', file)
  return handle(await fetch(`${BASE}/admin/civs/${id}/logo`, opts({ method: 'POST', body: fd })))
}
export const adminClearLogo = async (id) =>
  handle(await fetch(`${BASE}/admin/civs/${id}/logo`, opts({ method: 'DELETE' })))
export const adminLog = async () => handle(await fetch(`${BASE}/admin/log`, opts()))
