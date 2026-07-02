import { Link } from 'react-router-dom'
import Hero from '../components/Hero'
import Services from '../components/Services'
import ProjectCard from '../components/ProjectCard'
import { ECOSYSTEM, STATS } from '../data/site'

export default function Home() {
  const featured = ECOSYSTEM.slice(0, 3)
  return (
    <>
      <Hero />
      <Services />

      {/* Featured work — teaser into the Work page */}
      <section className="section wrap">
        <div className="sec-head with-link">
          <div>
            <span className="eyebrow">Selected work</span>
            <h2>Things we've shipped</h2>
          </div>
          <Link className="head-link" to="/work">See all work →</Link>
        </div>
        <div className="work">
          {featured.map((p) => <ProjectCard key={p.name} project={p} />)}
        </div>
      </section>

      {/* Hosting teaser band */}
      <div className="band">
        <section className="section wrap">
          <div className="teaser">
            <div className="teaser-copy">
              <span className="eyebrow">Self-hosted</span>
              <h2>One box. Twelve services. Eight domains.</h2>
              <p>
                The atlas, the archive, a whole virtual economy, community event
                sites, a client dashboard, and the bots — all run on hardware we
                own, behind one reverse proxy, with no cloud bill scaling against
                us. That's the difference you're paying for.
              </p>
              <Link className="btn btn-ghost" to="/hosting">Explore the stack →</Link>
            </div>
            <div className="teaser-stats">
              {STATS.map((s) => (
                <div className="stat" key={s.l}>
                  <div className="n">{s.n}</div>
                  <div className="l">{s.l}</div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      {/* Support / hire CTA */}
      <section className="section wrap">
        <div className="cta-split">
          <div className="cta-card">
            <h3>Have something you need built?</h3>
            <p>Tell us what you're making. If it's a fit, we'll scope it, build it, and host it.</p>
            <Link className="btn btn-primary" to="/contact">Start a project</Link>
          </div>
          <div className="cta-card">
            <h3>Use the community work?</h3>
            <p>The atlas, the archive, the exchange, and the bots stay free. Help cover the servers that keep them online.</p>
            <Link className="btn btn-ghost" to="/support">Support the work</Link>
          </div>
        </div>
      </section>
    </>
  )
}
