import { SERVICES } from '../data/site'
import { ServiceIcon } from './icons'

// Reusable "what we do" grid (used on the Home page).
export default function Services() {
  return (
    <section className="section wrap">
      <div className="sec-head">
        <span className="eyebrow">What we build</span>
        <h2>Software, and the machine it runs on</h2>
        <p>
          We don't hand off a repo and vanish. We build the product and own the
          hosting — which keeps costs predictable and the whole system in one pair
          of hands.
        </p>
      </div>
      <div className="services">
        {SERVICES.map((s) => (
          <div className="svc" key={s.title}>
            <ServiceIcon name={s.icon} />
            <h3>{s.title}</h3>
            <p>{s.body}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
