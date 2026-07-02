import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import ProjectCard from '../components/ProjectCard'
import { FLEET, HOSTED, STACK } from '../data/site'

const ROLE = {
  built: { cls: 'p-built', label: 'Built' },
  client: { cls: 'p-client', label: 'Client' },
  hosted: { cls: 'p-hosted', label: 'Hosted' },
  internal: { cls: 'p-internal', label: 'Internal' },
}

export default function Hosting() {
  return (
    <>
      <PageHeader
        eyebrow="Hosting & infrastructure"
        title="Everything, on hardware we own"
        lede="Our products, a client dashboard, and a handful of community sites and bots all run from one box behind one reverse proxy. Owning the whole stack is what keeps it fast, cheap, and in one pair of hands."
      />

      {/* The self-hosting stack */}
      <section className="section wrap">
        <div className="group-head">
          <span className="eyebrow">The stack</span>
          <h2>One box, one compose file</h2>
        </div>
        <div className="stack">
          {STACK.map((s) => (
            <div className="stack-item" key={s.k}>
              <div className="k">{s.k}</div>
              <div className="v">{s.v}</div>
            </div>
          ))}
        </div>
      </section>

      {/* The full fleet running on the box */}
      <section className="section wrap">
        <div className="group-head">
          <span className="eyebrow">Running on the box</span>
          <h2>The whole fleet</h2>
          <p>Every service below is served from the same self-hosted machine. Credit stays with the makers — the uptime is ours.</p>
        </div>
        <div className="fleet">
          {FLEET.map((f) => {
            const r = ROLE[f.role] || ROLE.built
            return (
              <div className="fleet-row" key={f.name}>
                <div className="fleet-name">
                  {f.name}
                  {f.maker && <span className="fleet-maker"> · {f.maker}</span>}
                </div>
                <div className="fleet-domain">{f.domain}</div>
                <span className={`pill ${r.cls}`}>{r.label}</span>
              </div>
            )
          })}
        </div>
      </section>

      {/* Collaborator projects, credited */}
      <div className="band">
        <section className="section wrap">
          <div className="group-head">
            <span className="eyebrow">Kept online for others</span>
            <h2>Community & collaborators</h2>
            <p>Projects by other makers that we host and keep running. We didn't build these — we keep them online.</p>
          </div>
          <div className="work">
            {HOSTED.map((p) => <ProjectCard key={p.name} project={p} />)}
          </div>
        </section>
      </div>

      <section className="section wrap">
        <div className="closing">
          <p>
            Everything on our <Link to="/work">Work page</Link> runs on this same
            infrastructure — self-hosted end to end, no cloud margin.
          </p>
          <Link className="btn btn-primary" to="/contact">Get your project hosted →</Link>
        </div>
      </section>
    </>
  )
}
