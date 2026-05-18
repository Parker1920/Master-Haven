/**
 * RevisionHistory — collapsible list of entity_revision rows for a given
 * resource (civ / person / event / place / story / inquisition).
 *
 * Reads `GET /api/v1/revisions/{target_type}/{target_id}` and renders
 * each row as a single line with date · author · change summary. Click
 * the header to expand/collapse; collapsed by default.
 *
 * Story + inquisition targets currently return empty arrays because
 * the schema doesn't record revisions for those types — the component
 * still mounts and shows a friendly "no edits recorded" message so the
 * UX stays uniform.
 */

import { useEffect, useState } from "react";
import { api, RevisionEntry, RevisionTarget } from "../api/client";
import { Avatar } from "./Avatar";

interface Props {
  targetType: RevisionTarget;
  targetId: string | number;
}

export function RevisionHistory({ targetType, targetId }: Props) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<RevisionEntry[] | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!open || loaded) return;
    api<RevisionEntry[]>(`/revisions/${targetType}/${targetId}`)
      .then((r) => { setRows(r); setLoaded(true); })
      .catch(() => { setRows([]); setLoaded(true); });
  }, [open, loaded, targetType, targetId]);

  return (
    <details
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      style={{
        marginTop: 24,
        padding: "10px 14px",
        background: "var(--ta-surface)",
        borderRadius: 8,
        border: "1px solid var(--ta-border)",
      }}
    >
      <summary style={{
        cursor: "pointer",
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: 1,
        color: "var(--ta-text-faint)",
        fontWeight: 500,
        userSelect: "none",
      }}>
        Revision history {rows ? `(${rows.length})` : ""}
      </summary>
      <div style={{ marginTop: 10 }}>
        {!loaded && <div style={{ fontSize: 12, color: "var(--ta-text-faint)" }}>Loading…</div>}
        {loaded && rows && rows.length === 0 && (
          <div style={{ fontSize: 12, color: "var(--ta-text-faint)", fontStyle: "italic" }}>
            No edits recorded.
          </div>
        )}
        {loaded && rows && rows.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {rows.map((r) => (
              <div
                key={r.id}
                style={{
                  display: "flex",
                  gap: 10,
                  alignItems: "flex-start",
                  fontSize: 12,
                  padding: "6px 0",
                  borderBottom: "1px solid var(--ta-border)",
                }}
              >
                <div style={{ flexShrink: 0 }}>
                  <Avatar author={r.changed_by} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ color: "var(--ta-text)", fontWeight: 500 }}>
                    {r.changed_by.name}{" "}
                    <span style={{ color: "var(--ta-text-faint)", fontWeight: 400 }}>
                      · {fmt(r.created_at)}
                    </span>
                  </div>
                  {r.change_summary && (
                    <div style={{ color: "var(--ta-text-dim)", marginTop: 2 }}>
                      {r.change_summary}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}

function fmt(d: string): string {
  if (!d) return "";
  try {
    return new Date(d).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return d;
  }
}
