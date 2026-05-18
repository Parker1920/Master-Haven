/** People index — paginated grid of person rows. */
import { useEffect, useState } from "react";
import { api, PersonSummary } from "../api/client";
import { Avatar } from "../components/Avatar";

export function People() {
  const [people, setPeople] = useState<PersonSummary[] | null>(null);

  useEffect(() => {
    api<PersonSummary[]>("/people", { query: { page_size: 200 } })
      .then(setPeople)
      .catch(() => setPeople([]));
  }, []);

  return (
    <>
      <div className="ta-civ-index-header">
        <h2 className="ta-civ-index-title">People</h2>
        <p className="ta-civ-index-sub">
          {people === null
            ? "Loading…"
            : `${people.length} ${people.length === 1 ? "person" : "people"} documented`}
        </p>
      </div>

      {people === null ? (
        <div className="ta-loading">Loading…</div>
      ) : people.length === 0 ? (
        <div className="ta-empty">No people on record yet.</div>
      ) : (
        <div className="ta-people-grid">
          {people.map((p) => (
            <a key={p.slug} href={`#/person/${p.slug}`} className="ta-people-card">
              <Avatar
                author={{ name: p.name, avatar_letter: p.name[0], avatar_color: "teal" }}
                size="lg"
              />
              <div className="ta-people-card-name">{p.name}</div>
              <div className="ta-people-card-meta">
                {p.role_in_civ || "—"}{p.civ_slug ? ` · ${p.civ_slug}` : ""}
              </div>
            </a>
          ))}
        </div>
      )}
    </>
  );
}
