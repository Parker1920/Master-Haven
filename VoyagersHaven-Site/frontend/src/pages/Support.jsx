import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import SupportPanel from '../components/SupportPanel'
import InvoicePay from '../components/InvoicePay'
import { getConfig } from '../api'

export default function Support() {
  const [simulated, setSimulated] = useState(false)
  const [mode, setMode] = useState('support')

  useEffect(() => {
    getConfig().then((c) => setSimulated(c.stripe_mode !== 'live')).catch(() => {})
  }, [])

  return (
    <>
      <PageHeader
        eyebrow="Support"
        title="Keep the community work free"
        lede="Everything we build for the No Man's Sky community — the atlas, the archive, the exchange, the bots — stays free and self-hosted. If it's useful to you, help cover the servers and domains that keep it online."
      >
        <p className="fine" style={{ textAlign: 'left', marginTop: 4 }}>
          Not a nonprofit. No perks, no obligation. Have an invoice from us? Pay it in the tab above.
        </p>
      </PageHeader>

      <section className="section wrap">
        <div className="mode-switch" style={{ margin: '0 auto 24px' }}>
          <button className={mode === 'support' ? 'on' : ''} onClick={() => setMode('support')}>Support</button>
          <button className={mode === 'invoice' ? 'on' : ''} onClick={() => setMode('invoice')}>Pay an invoice</button>
        </div>

        {mode === 'support' && (
          <>
            {simulated && (
              <div className="notice" style={{ maxWidth: 620, margin: '0 auto 20px' }}>
                Payment processing is being finalized — this is a live preview and no card is charged yet.
              </div>
            )}
            <SupportPanel />
          </>
        )}
        {mode === 'invoice' && <InvoicePay />}
      </section>
    </>
  )
}
