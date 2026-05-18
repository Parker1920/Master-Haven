/** Places index — known galactic locations. */
import { useEffect, useState } from "react";
import { api, PlaceSummary } from "../api/client";

export function Places() {
  const [places, setPlaces] = useState<PlaceSummary[] | null>(null);

  useEffect(() => {
    api<PlaceSummary[]>("/places", { query: { page_size: 200 } })
      .then(setPlaces)
      .catch(() => setPlaces([]));
  }, []);

  return (
    <>
      <div className="ta-civ-index-header">
        <h2 className="ta-civ-index-title">Places</h2>
        <p className="ta-civ-index-sub">
          {places === null
            ? "Loading…"
            : `${places.length} place${places.length === 1 ? "" : "s"} catalogued`}
        </p>
      </div>

      {places === null ? (
        <div className="ta-loading">Loading…</div>
      ) : places.length === 0 ? (
        <div className="ta-empty">No places catalogued yet.</div>
      ) : (
        <div className="ta-place-grid">
          {places.map((p) => (
            <a key={p.slug} href={`#/place/${p.slug}`} className="ta-place-card">
              <div className="ta-place-card-name">{p.name}</div>
              <div className="ta-place-card-meta">
                {p.galaxy ?? "—"}{p.region ? ` · ${p.region}` : ""}
              </div>
            </a>
          ))}
        </div>
      )}
    </>
  );
}
