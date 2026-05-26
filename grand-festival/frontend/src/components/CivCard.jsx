const STATUS = {
  host: { cls: 'host', label: '★ Host' },
  confirmed: { cls: 'confirmed', label: 'Confirmed' },
  tentative: { cls: 'tentative', label: 'Tentative' },
}

export default function CivCard({ civ }) {
  const s = STATUS[civ.status] || STATUS.tentative
  return (
    <div className="civ-card">
      {civ.logo_url && (
        <img className="civ-logo" src={civ.logo_url} alt={`${civ.name} emblem`} loading="lazy" />
      )}
      <div className={`badge ${s.cls}`}>{s.label}</div>
      <h3>{civ.name}</h3>
      <div className="role">{civ.role}</div>
      <p>{civ.description}</p>
    </div>
  )
}
