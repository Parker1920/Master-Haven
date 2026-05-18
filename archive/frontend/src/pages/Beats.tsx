/** Beats — index of the editorial sections briefs/features get filed under. */

import { useEffect, useState } from "react";
import { api, BeatSummary } from "../api/client";

export function Beats() {
  const [beats, setBeats] = useState<BeatSummary[] | null>(null);
  useEffect(() => {
    api<BeatSummary[]>("/beats").then(setBeats).catch(() => setBeats([]));
  }, []);

  return (
    <>
      <div className="ta-civ-index-header">
        <h2 className="ta-civ-index-title">Beats</h2>
        <p className="ta-civ-index-sub">
          {beats === null
            ? "Loading…"
            : `${beats.length} beats · how briefs and features get filed`}
        </p>
      </div>
      {beats && beats.length > 0 ? (
        <div
          className="ta-beats-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: 14,
            padding: "12px 0",
          }}
        >
          {beats.map((b) => (
            <a
              key={b.slug}
              href={`#/beat/${b.slug}`}
              className="ta-beat-card"
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 6,
                padding: "16px 18px",
                background: "var(--ta-surface)",
                border: "1px solid var(--ta-border)",
                borderRadius: 10,
                textDecoration: "none",
                color: "var(--ta-text)",
              }}
            >
              <div style={{
                fontFamily: "Georgia, serif",
                fontSize: 20,
                fontWeight: 500,
                textTransform: "capitalize",
              }}>
                {b.name}
              </div>
              <div style={{ fontSize: 12, color: "var(--ta-text-faint)" }}>
                {b.count} {b.count === 1 ? "story" : "stories"}
                {b.last_published && (
                  <> · last {new Date(b.last_published).toLocaleDateString("en-US", { dateStyle: "medium" })}</>
                )}
              </div>
            </a>
          ))}
        </div>
      ) : beats && beats.length === 0 ? (
        <div className="ta-empty">No beats yet — stories will populate as they're published.</div>
      ) : null}
    </>
  );
}
