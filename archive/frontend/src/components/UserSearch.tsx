/**
 * UserSearch — typeahead for picking an archive_user.
 *
 * Hits /search?q= (which returns SearchHit rows with kind='person'
 * containing archive_user.id, discord_username, display_name) and
 * surfaces matches as a dropdown. Caller gets (user_id, name) on
 * select. Used by the coauthor picker on the draft editor.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { api, SearchHit } from "../api/client";

interface Props {
  excludeUserIds?: number[];
  onSelect: (userId: number, name: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function UserSearch({ excludeUserIds, onSelect, placeholder, disabled }: Props) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const debounceRef = useRef<number | null>(null);

  const exclude = useMemo(() => new Set(excludeUserIds ?? []), [excludeUserIds]);

  useEffect(() => {
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
    const term = q.trim();
    if (term.length < 2) {
      setHits([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    debounceRef.current = window.setTimeout(async () => {
      try {
        const rows = await api<SearchHit[]>("/search", { query: { q: term, limit: 20 } });
        setHits(rows.filter((r) => r.kind === "person" && !exclude.has(r.id)));
      } catch {
        setHits([]);
      } finally {
        setLoading(false);
      }
    }, 250);
  }, [q, exclude]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const pick = (h: SearchHit) => {
    onSelect(h.id, h.title);
    setQ("");
    setHits([]);
    setOpen(false);
  };

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <input
        type="text"
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder ?? "Search users…"}
        disabled={disabled}
        style={{
          width: "100%",
          padding: "8px 10px",
          background: "var(--ta-surface)",
          border: "1px solid var(--ta-border)",
          borderRadius: 6,
          color: "var(--ta-text)",
          fontSize: 13,
          outline: "none",
        }}
      />
      {open && q.trim().length >= 2 && (
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
          {loading ? (
            <div style={{ padding: 10, fontSize: 12, color: "var(--ta-text-faint)" }}>Searching…</div>
          ) : hits.length === 0 ? (
            <div style={{ padding: 10, fontSize: 12, color: "var(--ta-text-faint)" }}>No matching users</div>
          ) : (
            hits.map((h) => (
              <button
                key={h.id}
                type="button"
                onClick={() => pick(h)}
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
                <span>{h.title}</span>
                <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--ta-text-faint)" }}>
                  @{h.slug}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export const KNOWN_BEATS = ["conflicts", "diplomacy", "events", "civupdates", "projects"] as const;
