import PageHeader from '../components/PageHeader'
import ProjectCard from '../components/ProjectCard'
import { CLIENT, COMMUNITY, ECOSYSTEM, INTERNAL } from '../data/site'

function Group({ eyebrow, title, note, items }) {
  return (
    <section className="section wrap">
      <div className="group-head">
        <span className="eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
        {note && <p>{note}</p>}
      </div>
      <div className="work">
        {items.map((p) => <ProjectCard key={p.name} project={p} />)}
      </div>
    </section>
  )
}

export default function Work() {
  return (
    <>
      <PageHeader
        eyebrow="Selected work"
        title="What we've built"
        lede="Products designed, built, and deployed by Voyager's Haven — from the data model to the server they run on."
      />
      <Group
        eyebrow="Haven ecosystem"
        title="The community platform"
        note="An interlocking set of tools for the No Man's Sky community: an atlas, an archive, a virtual economy, and the extractor that feeds them."
        items={ECOSYSTEM}
      />
      <Group
        eyebrow="Community & events"
        title="Built for the community"
        note="Sites, trackers, and automation we built and keep running for the community."
        items={COMMUNITY}
      />
      <Group
        eyebrow="Client work"
        title="Built under contract"
        note="Delivered for a client, isolated from everything else we run."
        items={CLIENT}
      />
      <Group
        eyebrow="Internal & R&D"
        title="Our own experiments"
        note="Private by design — shown here as proof of range, not products for sale."
        items={INTERNAL}
      />
    </>
  )
}
