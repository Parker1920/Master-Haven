// One card for any portfolio item. The role pill + maker credit carry the
// "who built / who runs it" distinction the studio cares about.

const ROLE = {
  built: { cls: 'p-built', label: 'Built' },
  client: { cls: 'p-client', label: 'Client work' },
  community: { cls: 'p-dev', label: 'Community' },
  hosted: { cls: 'p-hosted', label: 'Hosted' },
  internal: { cls: 'p-internal', label: 'Internal' },
}

export default function ProjectCard({ project }) {
  const role = ROLE[project.role] || ROLE.built
  return (
    <div className="case">
      <div className="case-top">
        <span className="link">{project.domain}</span>
        <span className={`pill ${role.cls}`}>{role.label}</span>
      </div>
      <h3>{project.name}</h3>
      {project.maker && <div className="credit">{project.maker}</div>}
      {project.status === 'dev' && <span className="status-chip">In development</span>}
      <p>{project.body}</p>
      <div className="tags">
        {project.tags.map((t) => (
          <span className="tag" key={t}>{t}</span>
        ))}
      </div>
    </div>
  )
}
