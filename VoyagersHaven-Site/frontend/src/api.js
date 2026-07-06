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

// --- public: pay an invoice ---
export const lookupInvoice = (number) => req(`/invoices/lookup?number=${encodeURIComponent(number)}`)
export const payInvoiceSimulated = (number) =>
  req('/invoices/pay-simulated', { method: 'POST', body: JSON.stringify({ number }) })
export const getReceipt = (number) => req(`/invoices/receipt?number=${encodeURIComponent(number)}`)

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

// --- shop (public) ---
export const getShopProducts = () => req('/shop/products')
export const shopCheckout = (payload) =>
  req('/shop/checkout', { method: 'POST', body: JSON.stringify(payload) })

// --- products (admin) ---
export const getAdminProducts = () => req('/admin/products')
export const createProduct = (p) => req('/admin/products', { method: 'POST', body: JSON.stringify(p) })
export const updateProduct = (id, p) => req(`/admin/products/${id}`, { method: 'PUT', body: JSON.stringify(p) })
export const deleteProduct = (id) => req(`/admin/products/${id}`, { method: 'DELETE' })

// --- shop order completion (simulated path) ---
export const shopComplete = (payload) =>
  req('/shop/complete', { method: 'POST', body: JSON.stringify(payload) })

// --- admin orders ---
export const getAdminOrders = () => req('/admin/orders')
export const setOrderFulfilled = (id, fulfilled) =>
  req(`/admin/orders/${id}`, { method: 'PATCH', body: JSON.stringify({ fulfilled }) })

// --- admin invoices ---
export const getAdminInvoices = () => req('/admin/invoices')
export const createInvoice = (p) => req('/admin/invoices', { method: 'POST', body: JSON.stringify(p) })
export const recordPaidInvoice = (p) => req('/admin/invoices/record-paid', { method: 'POST', body: JSON.stringify(p) })
export const markInvoicePaid = (id) => req(`/admin/invoices/${id}/mark-paid`, { method: 'POST' })
export const voidInvoice = (id) => req(`/admin/invoices/${id}/void`, { method: 'POST' })
