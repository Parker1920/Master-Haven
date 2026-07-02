import PageHeader from '../components/PageHeader'
import { PRINCIPLES, STATS } from '../data/site'

export default function About() {
  return (
    <>
      <PageHeader eyebrow="Who's behind this" title="One studio, end to end" />

      <section className="section wrap">
        <div className="about-grid">
          <div>
            <p>
              Voyager's Haven is a single-member Pennsylvania LLC run by one
              full-stack builder. Every product here was designed, built, and
              deployed by the same hands — from the data model to the server it
              runs on.
            </p>
            <p>
              That's the whole idea: no handoffs, no cloud middlemen, and no
              surprise bill down the line. When something breaks, one person knows
              the entire stack — and owns the box it lives on.
            </p>
            <p>
              The studio grew out of a real community project — a No Man's Sky
              atlas that now catalogues thousands of star systems — and turned into
              a home for building, hosting, and keeping software online for
              ourselves, the community, and clients.
            </p>
          </div>
          <div className="stats about-stats">
            {STATS.map((s) => (
              <div className="stat" key={s.l}>
                <div className="n">{s.n}</div>
                <div className="l">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="band">
        <section className="section wrap">
          <div className="group-head">
            <span className="eyebrow">How we work</span>
            <h2>Three commitments</h2>
          </div>
          <div className="principles">
            {PRINCIPLES.map((p, i) => (
              <div className="principle" key={p.title}>
                <div className="pn">{String(i + 1).padStart(2, '0')}</div>
                <h3>{p.title}</h3>
                <p>{p.body}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  )
}
