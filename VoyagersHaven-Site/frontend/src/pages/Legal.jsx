import { Link } from 'react-router-dom'
import { CONTACT_EMAIL } from '../data/site'

const UPDATED = 'July 1, 2026'
const mail = { color: 'var(--teal-bright)' }

export function Privacy() {
  return (
    <div className="page">
      <h1>Privacy Policy</h1>
      <p style={{ color: 'var(--faint)', fontSize: 13 }}>Last updated {UPDATED}</p>
      <p>
        Voyager's Haven LLC ("we", "us") operates this site. We keep data
        collection to the minimum needed to talk with you and run the business,
        and we don't sell it to anyone.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li><b>Project inquiries.</b> When you use the "Start a project" form, we store the name, email, project type, budget, and message you submit.</li>
        <li><b>Payments.</b> If you support us or pay an invoice, we store a payment reference, amount, status, and (if you provide it) an email for the receipt.</li>
        <li><b>Admin session.</b> A single httpOnly cookie is used only to keep the site owner logged into the private admin area. Visitors are not tracked with cookies.</li>
      </ul>

      <h2>How we use it</h2>
      <p>
        To reply to your inquiry, deliver and account for work, and issue receipts.
        We do not use your information for advertising and we do not sell or rent it.
      </p>

      <h2>Payments &amp; third parties</h2>
      <p>
        Card payments are processed by <b>Stripe</b>. Your card number is entered
        on Stripe's systems and never touches our servers — we retain only a
        reference, amount, and status. Stripe's handling of your data is governed
        by their own privacy policy. If email notifications or receipts are
        enabled, an email provider processes those messages on our behalf.
      </p>

      <h2>Where it lives &amp; how long</h2>
      <p>
        Data is stored in a database on hardware we own and operate ourselves
        (self-hosted), not a third-party cloud. We keep inquiries and payment
        records only as long as needed for correspondence, accounting, and legal
        obligations, then remove them. You can ask us to delete your inquiry at any
        time.
      </p>

      <h2>Your choices</h2>
      <p>
        Email us to access, correct, or delete the information you've sent us.
        We'll respond within a reasonable time.
      </p>

      <h2>Contact</h2>
      <p>Questions? Email <a href={`mailto:${CONTACT_EMAIL}`} style={mail}>{CONTACT_EMAIL}</a>.</p>
      <Link className="back" to="/">← Back home</Link>
    </div>
  )
}

export function Terms() {
  return (
    <div className="page">
      <h1>Terms of Use</h1>
      <p style={{ color: 'var(--faint)', fontSize: 13 }}>Last updated {UPDATED}</p>
      <p>
        This site is operated by Voyager's Haven LLC, a Pennsylvania single-member
        limited liability company. By using it you agree to these terms.
      </p>

      <h2>Support contributions</h2>
      <p>
        Contributions made in the Support section are voluntary and help cover the
        cost of hosting our free community projects. They are not tax-deductible,
        carry no perks or obligations, and are generally <b>non-refundable</b>. If
        a contribution was made in error, email us and we'll do our best to help.
      </p>

      <h2>Client work &amp; invoices</h2>
      <p>
        Contracted projects are governed by a separate written agreement or
        Statement of Work between us and the client. Invoice payments made through
        this site settle amounts billed under that agreement; the agreement's terms
        control in the event of any conflict with this page.
      </p>

      <h2>Inquiries</h2>
      <p>
        Submitting the "Start a project" form is a request to talk, not a binding
        contract. No work begins, and no obligation exists on either side, until we
        both agree to a scope and terms in writing.
      </p>

      <h2>Portfolio &amp; trademarks</h2>
      <p>
        Projects shown here are credited to their makers. Products marked as built
        for the community or by collaborators (for example, the community bots and
        docs) remain the work of their respective authors; we host or maintain them
        as noted. No affiliation or endorsement is implied by any name or mark
        referenced.
      </p>

      <h2>No warranty; limitation of liability</h2>
      <p>
        This site and its content are provided "as is" without warranties of any
        kind. To the fullest extent permitted by law, Voyager's Haven LLC is not
        liable for indirect or consequential damages arising from use of the site.
      </p>

      <h2>Changes &amp; governing law</h2>
      <p>
        We may update these terms; the "last updated" date above reflects the
        current version. These terms are governed by the laws of the Commonwealth
        of Pennsylvania.
      </p>

      <p>Questions? Email <a href={`mailto:${CONTACT_EMAIL}`} style={mail}>{CONTACT_EMAIL}</a>.</p>
      <Link className="back" to="/">← Back home</Link>
    </div>
  )
}
