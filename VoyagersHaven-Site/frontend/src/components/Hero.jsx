import { Link } from 'react-router-dom'
import { CAPABILITIES } from '../data/site'

export default function Hero() {
  return (
    <header className="hero wrap" id="top">
      <div className="eyebrow">Voyager's Haven LLC · Pennsylvania</div>
      <h1>Custom software, built and <em>hosted on hardware we own.</em></h1>
      <p className="lede">
        A small, vertically-integrated studio. We design web apps, dashboards, and
        AI tools — then run them on our own infrastructure, so you're not renting
        cloud margin for the life of the project.
      </p>
      <div className="cta-row">
        <Link className="btn btn-primary" to="/work">See our work</Link>
        <Link className="btn btn-ghost" to="/hosting">What we host</Link>
      </div>

      <div className="strip">
        {CAPABILITIES.map((c) => (
          <div key={c.k}>
            <div className="k">{c.k}</div>
            <div className="v">{c.v}</div>
          </div>
        ))}
      </div>
    </header>
  )
}
