/** ArticleCard — a catalogue result/preview card with facet chips. */
import { ArticleSummary } from "../api/client";
import { NS_BY_KEY } from "../data/namespaces";

export function facetChips(a: ArticleSummary, max = 3): string[] {
  const out: string[] = [];
  for (const vals of Object.values(a.facets ?? {})) {
    for (const v of vals) {
      if (v !== "true" && !out.includes(v) && out.length < max) out.push(v);
    }
  }
  return out;
}

export function ArticleCard({ a }: { a: ArticleSummary }) {
  const def = NS_BY_KEY[a.namespace];
  const chips = facetChips(a);
  return (
    <a href={`#/wiki/${a.slug}`} className="ta-cat-card" style={{ "--cat-accent": def?.accent } as React.CSSProperties}>
      <div className="ta-cat-card-top">
        <span className="ta-cat-card-glyph">{def?.glyph ?? "✦"}</span>
        <span className="ta-cat-card-ns">{def?.label ?? a.namespace}</span>
      </div>
      <div className="ta-cat-card-title">{a.title}</div>
      {a.subtitle && <div className="ta-cat-card-sub">{a.subtitle}</div>}
      {chips.length > 0 && (
        <div className="ta-cat-card-chips">
          {chips.map((c, i) => <span key={i} className="ta-cat-chip">{c}</span>)}
        </div>
      )}
    </a>
  );
}
