// Thin fetch wrapper. Same-origin in prod (FastAPI serves the SPA); Vite
// proxies /api to :8090 in dev.

async function req(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    const msg = (data && data.detail) || `Request failed (${res.status})`
    throw new Error(msg)
  }
  return data
}

export const getConfig = () => req('/config')

export const createCheckout = (payload) =>
  req('/checkout', { method: 'POST', body: JSON.stringify(payload) })

export const completeCheckout = (reference) =>
  req(`/checkout/${reference}/complete`, { method: 'POST' })

export const sendInquiry = (payload) =>
  req('/inquiries', { method: 'POST', body: JSON.stringify(payload) })

// --- admin (cookie session; same-origin fetch sends the cookie) ---
export const adminMe = () => req('/admin/me')
export const adminLogin = (password) =>
  req('/admin/login', { method: 'POST', body: JSON.stringify({ password }) })
export const adminLogout = () => req('/admin/logout', { method: 'POST' })
export const getAdminSummary = () => req('/admin/summary')
export const getAdminInquiries = () => req('/admin/inquiries')
export const getAdminPayments = () => req('/admin/payments')
export const setInquiryHandled = (id, handled) =>
  req(`/admin/inquiries/${id}`, { method: 'PATCH', body: JSON.stringify({ handled }) })
