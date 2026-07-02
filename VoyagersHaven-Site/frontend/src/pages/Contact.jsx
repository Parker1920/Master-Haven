import PageHeader from '../components/PageHeader'
import InquiryForm from '../components/InquiryForm'
import { CONTACT_EMAIL } from '../data/site'

export default function Contact() {
  return (
    <>
      <PageHeader
        eyebrow="Work with us"
        title="Start a project"
        lede="Tell us what you're trying to make. If it's a fit, we'll scope it, build it, and host it — one team from data model to deploy."
      />

      <section className="section wrap">
        <div className="hire-grid">
          <div className="hire-copy">
            <h3>What to expect</h3>
            <ul className="expect">
              <li>A reply within a couple of days.</li>
              <li>A short call to scope what you actually need.</li>
              <li>A fixed quote and timeline before any work starts.</li>
              <li>Hosting included — we keep it online after launch.</li>
            </ul>
            <p style={{ marginTop: 18 }}>
              Prefer email? <a className="mail" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
            </p>
          </div>
          <InquiryForm />
        </div>
      </section>
    </>
  )
}
