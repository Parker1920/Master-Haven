/**
 * CivPicker — multi-select civilization tag picker.
 *
 * Fetches the full civilization list once on mount (cached module-level
 * across instances), renders the selected slugs as removable colored
 * chips, and exposes a filterable dropdown to add more.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { api, CivilizationSummary } from "../api/client";

let cachedCivs: CivilizationSummary[] | null = null;
let inflight: Promise<CivilizationSummary[]> | null = null;

async function fetchAllCivs(): Promise<CivilizationSummary[]> {
  if (cachedCivs) return cachedCivs;
  if (inflight) return inflight;
  inflight = api<CivilizationSummary[]>("/civilizations", { query: { page_size: 500 } })
    .then((rows) => {
      cachedCivs = rows;
      return rows;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

interface Props {
  selected: string[];
  onChange: (slugs: string[]) => void;
  disabled?: boolean;
  label?: string;
}

export function CivPicker({ selected, onChange, disabled, label }: Props) {
  const [civs, setCivs] = useState<CivilizationSummary[] | null>(cachedCivs);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!civs) {
      fetchAllCivs().then(setCivs).catch(() => setCivs([]));
    }
  }, [civs]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setFilter("");
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const civBySlug = useMemo(() => {
    const m = new Map<string, CivilizationSummary>();
    (civs ?? []).forEach((c) => m.set(c.slug, c));
    return m;
  }, [civs]);

  const available = useMemo(() => {
    const sel = new Set(selected);
    const term = filter.trim().toLowerCase();
    return (civs ?? [])
      .filter((c) => !sel.has(c.slug))
      .filter((c) => !term || c.name.toLowerCase().includes(term) || c.slug.toLowerCase().includes(term))
      .slice(0, 50);
  }, [civs, selected, filter]);

  const add = (slug: string) => {
    if (selected.includes(slug)) return;
    onChange([...selected, slug]);
    setFilter("");
  };

  const remove = (slug: string) => {
    onChange(selected.filter((s) => s !== slug));
  };

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      {label && (
        <div style={{
          fontSize: 11, color: "var(--ta-text-faint)",
          textTransform: "uppercase", letterSpacing: 0.6,
          marginBottom: 6, fontWeight: 500,
        }}>
          {label}
        </div>
      )}
      <div style={{
        display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center",
        padding: "8px 10px",
        background: "var(--ta-surface)",
        border: "1px solid var(--ta-border)",
        borderRadius: 6,
        minHeight: 38,
        cursor: disabled ? "not-allowed" : "text",
        opacity: disabled ? 0.6 : 1,
      }} onClick={() => !disabled && setOpen(true)}>
        {selected.map((slug) => {
          const civ = civBySlug.get(slug);
          const c1 = civ?.color_primary || "#888";
          const c2 = civ?.color_secondary || "#555";
          return (
            <span
              key={slug}
              style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                padding: "3px 4px 3px 10px",
                background: `linear-gradient(90deg, ${c1}26, ${c2}26)`,
                border: `1px solid ${c1}66`,
                borderRadius: 12,
                fontSize: 12, lineHeight: 1.2,
                color: "var(--ta-text)",
              }}
            >
              <span style={{
                display: "inline-block", width: 8, height: 8,
                borderRadius: "50%", background: c1,
              }} />
              {civ?.name ?? slug}
              {!disabled && (
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); remove(slug); }}
                  title="Remove"
                  style={{
                    background: "transparent", border: "none",
                    color: "var(--ta-text-dim)", cursor: "pointer",
                    fontSize: 14, lineHeight: 1, padding: "0 4px",
                  }}
                >×</button>
              )}
            </span>
          );
        })}
        {!disabled && (
          <input
            value={filter}
            onChange={(e) => { setFilter(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            placeholder={selected.length === 0 ? "Add civilizations…" : ""}
            style={{
              flex: "1 1 120px", minWidth: 80,
              background: "transparent", border: "none", outline: "none",
              color: "var(--ta-text)", fontSize: 13, padding: "2px 4px",
            }}
          />
        )}
      </div>
      {open && !disabled && (
        <div style={{
          position: "absolute", top: "100%", left: 0, right: 0,
          marginTop: 4,
          background: "var(--ta-bg)",
          border: "1px solid var(--ta-border)",
          borderRadius: 6,
          maxHeight: 260, overflowY: "auto",
          zIndex: 50,
          boxShadow: "0 6px 24px rgba(0,0,0,0.35)",
        }}>
          {civs === null ? (
            <div style={{ padding: 10, fontSize: 12, color: "var(--ta-text-faint)" }}>Loading…</div>
          ) : available.length === 0 ? (
            <div style={{ padding: 10, fontSize: 12, color: "var(--ta-text-faint)" }}>
              {filter ? "No matching civs" : "All civs already selected"}
            </div>
          ) : (
            available.map((c) => (
              <button
                key={c.slug}
                type="button"
                onClick={() => add(c.slug)}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  width: "100%", textAlign: "left",
                  padding: "6px 10px",
                  background: "transparent", border: "none",
                  color: "var(--ta-text)", fontSize: 13, cursor: "pointer",
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "var(--ta-surface)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
              >
                <span style={{
                  display: "inline-block", width: 8, height: 8,
                  borderRadius: "50%", background: c.color_primary,
                }} />
                <span>{c.name}</span>
                <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--ta-text-faint)" }}>
                  {c.slug}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
