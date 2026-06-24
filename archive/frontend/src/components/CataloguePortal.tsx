/**
 * CataloguePortal — the namespace navigator.
 *
 *  variant="portal"  → grouped tile grid (Catalogue page)
 *  variant="spine"   → compact grouped link list (home left spine)
 *
 * Live per-namespace counts come from /articles/namespaces; civ counts
 * the civilization table, system/planet read "atlas".
 */

import { useEffect, useState } from "react";
import { api, NamespaceCount } from "../api/client";
import { NAMESPACE_GROUPS, NS_BY_KEY } from "../data/namespaces";

export function CataloguePortal({ variant = "portal" }: { variant?: "portal" | "spine" }) {
  const [counts, setCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    let alive = true;
    api<NamespaceCount[]>("/articles/namespaces")
      .then((rows) => { if (alive) setCounts(Object.fromEntries(rows.map((r) => [r.namespace, r.count]))); })
      .catch(() => { /* tiles still render */ });
    return () => { alive = false; };
  }, []);

  if (variant === "spine") {
    return (
      <nav className="ta-cat-spine">
        {NAMESPACE_GROUPS.map((g) => (
          <div className="ta-cat-spine-group" key={g.label}>
            <div className="ta-cat-spine-label">{g.label}</div>
            {g.keys.map((k) => {
              const n = NS_BY_KEY[k];
              if (!n) return null;
              const c = counts[k] ?? 0;
              return (
                <a key={k} href={n.href} className="ta-cat-spine-item" style={{ "--cat-accent": n.accent } as React.CSSProperties}>
                  <span className="ta-cat-spine-glyph">{n.glyph}</span>
                  <span className="ta-cat-spine-name">{n.label}</span>
                  <span className="ta-cat-spine-count">{n.kind === "synced" ? "atlas" : c}</span>
                </a>
              );
            })}
          </div>
        ))}
      </nav>
    );
  }

  return (
    <div className="ta-cat-portal-groups">
      {NAMESPACE_GROUPS.map((g) => (
        <section className="ta-cat-pgroup" key={g.label}>
          <h3 className="ta-cat-pgroup-title">{g.label}</h3>
          <div className="ta-cat-portal">
            {g.keys.map((k) => {
              const n = NS_BY_KEY[k];
              if (!n) return null;
              const c = counts[k] ?? 0;
              return (
                <a key={k} href={n.href} className="ta-cat-tile" style={{ "--cat-accent": n.accent } as React.CSSProperties}>
                  {n.kind === "synced" && <div className="ta-cat-tile-badge">atlas</div>}
                  <div className="ta-cat-tile-glyph">{n.glyph}</div>
                  <div className="ta-cat-tile-title">{n.label}</div>
                  <div className="ta-cat-tile-count">
                    {n.kind === "synced" ? "from the atlas" : `${c} ${c === 1 ? "page" : "pages"}`}
                  </div>
                  <div className="ta-cat-tile-blurb">{n.blurb}</div>
                </a>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
