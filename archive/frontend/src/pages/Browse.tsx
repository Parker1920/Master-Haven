/** Browse — one catalogue namespace: filter rail + card grid. */
import { useEffect, useState } from "react";
import { api, ArticleSummary } from "../api/client";
import { NamespaceDef, NS_BY_KEY } from "../data/namespaces";
import { useAuth } from "../hooks/useAuth";
import { Loading } from "../components/Loading";
import { FilterRail } from "../components/FilterRail";
import { ArticleCard } from "../components/ArticleCard";

function parseFiltersFromHash(): Record<string, string[]> {
  const q = window.location.hash.split("?")[1] || "";
  const sp = new URLSearchParams(q);
  const out: Record<string, string[]> = {};
  for (const f of sp.getAll("f")) {
    const i = f.indexOf(":");
    if (i < 0) continue;
    const k = f.slice(0, i);
    const v = f.slice(i + 1);
    if (!out[k]) out[k] = [];
    out[k].push(v);
  }
  return out;
}

function facetParams(filters: Record<string, string[]>): string[] {
  const parts: string[] = [];
  for (const [k, vals] of Object.entries(filters)) {
    for (const v of vals) parts.push(`f=${encodeURIComponent(`${k}:${v}`)}`);
  }
  return parts;
}

function syncHash(namespace: string, filters: Record<string, string[]>) {
  const qs = facetParams(filters);
  window.history.replaceState(null, "", `#/browse/${namespace}${qs.length ? `?${qs.join("&")}` : ""}`);
}

function buildPath(namespace: string, filters: Record<string, string[]>): string {
  const parts = [`namespace=${encodeURIComponent(namespace)}`, "page_size=200", ...facetParams(filters)];
  return `/articles?${parts.join("&")}`;
}

export function Browse({ namespace }: { namespace: string }) {
  const def = NS_BY_KEY[namespace];
  const { user } = useAuth();
  const canCreate = !!user && (user.base_role !== "reader" || user.is_admin);
  const [items, setItems] = useState<ArticleSummary[] | null>(null);
  const [filters, setFilters] = useState<Record<string, string[]>>(() => parseFiltersFromHash());
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => { setFilters(parseFiltersFromHash()); }, [namespace]);

  useEffect(() => {
    if (!def || def.kind !== "article") { setItems([]); return; }
    setItems(null);
    syncHash(namespace, filters);
    api<ArticleSummary[]>(buildPath(namespace, filters)).then(setItems).catch(() => setItems([]));
  }, [namespace, def, filters]);

  if (!def) {
    return (
      <div className="ta-empty">
        Unknown catalogue category. <a className="ta-cat-link" href="#/catalogue">Back to the catalogue</a>
      </div>
    );
  }

  if (def.kind === "special") {
    return (
      <div className="ta-empty">
        <b>{def.label}</b> live on their own page. <a className="ta-cat-link" href="#/civs">Open {def.label} →</a>
      </div>
    );
  }

  if (def.kind === "synced") {
    return (
      <>
        <BrowseHeader def={def} canCreate={false} />
        <div className="ta-empty">
          <b>{def.label}</b> are synced live from the Haven atlas. A browsable catalogue view lands in a later
          phase — for now, explore them on the{" "}
          <a className="ta-cat-link" href="https://havenmap.online" target="_blank" rel="noreferrer">Haven map</a>.
        </div>
      </>
    );
  }

  const chips: { key: string; value: string }[] = [];
  for (const [k, vals] of Object.entries(filters)) for (const v of vals) chips.push({ key: k, value: v });
  const removeChip = (key: string, value: string) => {
    const next = { ...filters };
    next[key] = (next[key] || []).filter((v) => v !== value);
    if (!next[key].length) delete next[key];
    setFilters(next);
  };

  return (
    <>
      <BrowseHeader def={def} canCreate={canCreate} onFilters={() => setShowFilters(true)} />
      <div className="ta-cat-browse-body">
        <div className={`ta-cat-rail-wrap${showFilters ? " open" : ""}`}>
          <div className="ta-cat-rail-scrim" onClick={() => setShowFilters(false)} />
          <FilterRail namespace={namespace} selected={filters} onChange={setFilters} onClose={() => setShowFilters(false)} />
        </div>

        <div className="ta-cat-browse-main">
          {chips.length > 0 && (
            <div className="ta-cat-active-chips">
              {chips.map((c) => (
                <button key={`${c.key}:${c.value}`} className="ta-cat-active-chip" onClick={() => removeChip(c.key, c.value)}>
                  {c.value === "true" ? c.key.replace(/_/g, " ") : c.value}<span aria-hidden> ✕</span>
                </button>
              ))}
              <button className="ta-cat-active-clear" onClick={() => setFilters({})}>Clear all</button>
            </div>
          )}

          {items === null ? (
            <Loading />
          ) : items.length === 0 ? (
            <div className="ta-empty">
              {chips.length > 0 ? (
                <>No {def.label.toLowerCase()} match these filters.{" "}
                  <span className="ta-cat-link" style={{ cursor: "pointer" }} onClick={() => setFilters({})}>Clear filters</span>.</>
              ) : (
                <>No {def.label.toLowerCase()} yet.
                  {canCreate && <> Be the first — <a className="ta-cat-link" href={`#/new-article?namespace=${namespace}`}>add a {def.singular.toLowerCase()}</a>.</>}</>
              )}
            </div>
          ) : (
            <>
              <div className="ta-cat-result-count">{items.length} {items.length === 1 ? "page" : "pages"}</div>
              <div className="ta-cat-grid">
                {items.map((a) => <ArticleCard key={a.slug} a={a} />)}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

function BrowseHeader({ def, canCreate, onFilters }: { def: NamespaceDef; canCreate: boolean; onFilters?: () => void }) {
  return (
    <div className="ta-cat-browse-head" style={{ "--cat-accent": def.accent } as React.CSSProperties}>
      <div>
        <div className="ta-cat-browse-eyebrow"><a className="ta-cat-link" href="#/catalogue">Catalogue</a> ›</div>
        <h2 className="ta-cat-browse-title"><span className="ta-cat-browse-glyph">{def.glyph}</span> {def.label}</h2>
        <p className="ta-cat-browse-blurb">{def.blurb}</p>
      </div>
      <div className="ta-cat-browse-actions">
        {onFilters && def.kind === "article" && (
          <button className="ta-btn ta-cat-filter-toggle" onClick={onFilters}>Filters</button>
        )}
        {canCreate && def.kind === "article" && (
          <a className="ta-btn ta-btn-primary" href={`#/new-article?namespace=${def.ns}`} style={{ whiteSpace: "nowrap" }}>
            + New {def.singular}
          </a>
        )}
      </div>
    </div>
  );
}
