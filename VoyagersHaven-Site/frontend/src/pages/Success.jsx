import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

// Stripe (live mode) redirects here as success_url=/success?ref=HVN-XXXX.
// We look the payment up to show its confirmed amount/reference.
export default function Success() {
  const [params] = useSearchParams()
  const ref = params.get('ref')
  const [receipt, setReceipt] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!ref) {
      setErr('No reference provided.')
      return
    }
    fetch(`/api/checkout/${ref}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('Payment not found.'))))
      .then(setReceipt)
      .catch((e) => setErr(e.message))
  }, [ref])

  const amount = receipt ? (receipt.amount_cents / 100).toFixed(2) : null

  return (
    <div className="page">
      <div className="success-card">
        <div className="big-check">✓</div>
        <h1 style={{ fontSize: 26, marginBottom: 10 }}>Thank you</h1>
        {err && <p>{err}</p>}
        {receipt && (
          <>
            <p style={{ marginBottom: 20 }}>
              {receipt.kind === 'invoice' ? 'Your invoice payment is confirmed.' : 'Your support is confirmed and keeps the work online.'}
            </p>
            <div className="sr-row"><span>Amount</span><b>${amount}</b></div>
            <div className="sr-row"><span>Reference</span><b>{receipt.reference}</b></div>
            <div className="sr-row" style={{ borderBottom: 'none' }}><span>Status</span><b>{receipt.status}</b></div>
          </>
        )}
        <Link className="back" to="/">← Back to Voyager's Haven</Link>
      </div>
    </div>
  )
}
