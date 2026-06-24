/**
 * FilterRail — the Browse filter sidebar.
 *
 * Fetches the namespace's facet schema. Non-boolean facets render as
 * collapsible groups (open when they have an active selection); boolean
 * facets are grouped into one "Attributes" row of toggle pills.
 */

import { useEffect, useState } from "react";
import { api, FacetDef, FacetSchema } from "../api/client";
import { FacetControl } from "./FacetControl";

export function FilterRail({
  namespace, selected, onChange, onClose,
}: {
  namespace: string;
  selected: Record<string, string[]>;
  onChange: (next: Record<string, string[]>) => void;
  onClose?: () => void;
}) {
  const [facets, setFacets] = useState<FacetDef[] | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let alive = true;
    api<FacetSchema>(`/articles/facets/${namespace}`)
      .then((s) => { if (alive) setFacets(s.facets); })
      .catch(() => { if (alive) setFacets([]); });
    return () => { alive = false; };
  }, [namespace]);

  if (!facets || facets.length === 0) return null;

  const setFacet = (key: string, v: string[]) => {
    const next = { ...selected };
    if (v.length) next[key] = v; else delete next[key];
    onChange(next);
  };
  const isOpen = (key: string) => (key in open ? open[key] : (selected[key]?.length ?? 0) > 0);
  const toggle = (key: string) => setOpen((o) => ({ ...o, [key]: !isOpen(key) }));

  const bools = facets.filter((f) => f.control === "boolean");
  // Date facets are captured on the form + drive the timeline, but aren't
  // useful as checkbox filters, so they're omitted from the rail.
  const rest = facets.filter((f) => f.control !== "boolean" && f.control !== "date");
  const activeCount = Object.values(selected).reduce((n, v) => n + v.length, 0);

  return (
    <aside className="ta-cat-rail">
      <div className="ta-cat-rail-head">
        <span>Filters{activeCount > 0 ? ` · ${activeCount}` : ""}</span>
        <div className="ta-cat-rail-head-actions">
          {activeCount > 0 && <button className="ta-cat-rail-clear" onClick={() => onChange({})}>Clear</button>}
          {onClose && <button className="ta-cat-rail-done" onClick={onClose}>Done</button>}
        </div>
      </div>

      {rest.map((def) => {
        const sel = selected[def.key]?.length ?? 0;
        const o = isOpen(def.key);
        return (
          <div className="ta-cat-rail-group" key={def.key}>
            <button type="button" className="ta-cat-rail-grouphd" onClick={() => toggle(def.key)}>
              <span className="ta-cat-rail-label">
                {def.label}{sel > 0 && <span className="ta-cat-rail-badge">{sel}</span>}
              </span>
              <span className={`ta-cat-rail-chev${o ? " open" : ""}`}>›</span>
            </button>
            {o && (
              <div className="ta-cat-rail-body">
                <FacetControl def={def} value={selected[def.key] ?? []} onChange={(v) => setFacet(def.key, v)} />
              </div>
            )}
          </div>
        );
      })}

      {bools.length > 0 && (
        <div className="ta-cat-rail-group">
          <div className="ta-cat-rail-label" style={{ marginBottom: 7 }}>Attributes</div>
          <div className="ta-cat-rail-bools">
            {bools.map((def) => {
              const on = (selected[def.key] ?? []).includes("true");
              return (
                <button
                  key={def.key}
                  type="button"
                  className={`ta-cat-bool-pill${on ? " on" : ""}`}
                  onClick={() => setFacet(def.key, on ? [] : ["true"])}
                >
                  {def.label}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </aside>
  );
}
