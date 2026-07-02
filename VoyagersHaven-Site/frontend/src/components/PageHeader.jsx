// Shared hero band for interior pages: eyebrow + title + optional lede.
export default function PageHeader({ eyebrow, title, lede, children }) {
  return (
    <div className="pagehead wrap">
      {eyebrow && <div className="eyebrow">{eyebrow}</div>}
      <h1>{title}</h1>
      {lede && <p className="lede">{lede}</p>}
      {children}
    </div>
  )
}
