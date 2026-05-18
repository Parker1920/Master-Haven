/**
 * Search — full-text across stories, inquisitions, civs, people.
 *
 * Reads ?q= from the hash (#/search?q=foo) so a query is bookmarkable
 * and the back button works. Empty q renders an empty-state with a
 * prompt rather than auto-fetching nothing.
 */

import { useEffect, useMemo, useState } from "react";
import { api, ApiError, SearchHit } from "../api/client";
import { Avatar } from "../components/Avatar";

function readQ(): string {
  // We can't use URLSearchParams against the hash because the hash itself
  // contains the path. Just split on "?".
  const h = window.location.hash;
  const i = h.indexOf("?");
  if (i < 0) return "";
  return new URLSearchParams(h.slice(i)).get("q") || "";
}

function writeQ(q: string) {
  const base = "#/search";
  const next = q.trim() ? `${base}?q=${encodeURIComponent(q.trim())}` : base;
  if (window.location.hash === next) return;
  window.location.hash = next;
}

export function Search() {
  const [q, setQ] = useState<string>(() => readQ());
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Sync from hash changes (back/forward buttons).
  useEffect(() => {
    const onHash = () => setQ(readQ());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // Debounce fetch on q change.
  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) { setHits(null); setErr(null); return; }
    setBusy(true);
    const tid = window.setTimeout(async () => {
      try {
        const data = await api<SearchHit[]>("/search", { query: { q: term } });
        setHits(data);
        setErr(null);
      } catch (e) {
        setHits([]);
        setErr(e instanceof ApiError ? String(e.detail) : "search failed");
      } finally {
        setBusy(false);
      }
    }, 250);
    return () => window.clearTimeout(tid);
  }, [q]);

  const grouped = useMemo(() => {
    const buckets: Record<string, SearchHit[]> = {
      story: [], inquisition: [], civilization: [], person: [],
    };
    (hits ?? []).forEach((h) => {
      (buckets[h.kind] ?? (buckets[h.kind] = [])).push(h);
    });
    return buckets;
  }, [hits]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    writeQ(q);
  };

  return (
    <div className="ta-search-page">
      <h1 className="ta-drafts-title">Search the archive</h1>
      <form onSubmit={submit} className="ta-search-form">
        <input
          autoFocus
          className="ta-form-input"
          placeholder="Search stories, inquisitions, civilizations, people…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button type="submit" className="ta-btn ta-btn-primary" disabled={!q.trim()}>
          {busy ? "…" : "Search"}
        </button>
      </form>

      {q.trim().length < 2 ? (
        <div className="ta-empty">Type at least two characters to search.</div>
      ) : busy && hits === null ? (
        <div className="ta-loading">Searching…</div>
      ) : err ? (
        <div className="ta-empty">{err}</div>
      ) : (hits?.length ?? 0) === 0 ? (
        <div className="ta-empty">No matches for "{q.trim()}".</div>
      ) : (
        <>
          <Section
            title="Stories"
            hits={grouped.story}
            href={(h) => `#/story/${h.id}`}
          />
          <Section
            title="Inquisitions"
            hits={grouped.inquisition}
            href={(h) => `#/inquisition/${h.id}`}
            numeral
          />
          <Section
            title="Civilizations"
            hits={grouped.civilization}
            href={(h) => `#/civ/${h.slug}`}
          />
          <PeopleSection hits={grouped.person} />
        </>
      )}
    </div>
  );
}

function Section({ title, hits, href, numeral }: {
  title: string;
  hits: SearchHit[];
  href: (h: SearchHit) => string;
  numeral?: boolean;
}) {
  if (!hits || hits.length === 0) return null;
  return (
    <div className="ta-search-section">
      <div className="ta-section-divider">
        <div className="ta-section-name">{title}</div>
        <div className="ta-section-sub">{hits.length} match{hits.length === 1 ? "" : "es"}</div>
      </div>
      {hits.map((h) => (
        <a key={`${h.kind}-${h.id}`} href={href(h)} className="ta-search-row">
          <div className="ta-search-row-title">
            {numeral && <span className="ta-search-row-numeral">·</span>}
            {h.title}
          </div>
          {h.snippet && <div className="ta-search-row-snippet">{h.snippet}</div>}
        </a>
      ))}
    </div>
  );
}

function PeopleSection({ hits }: { hits: SearchHit[] }) {
  if (!hits || hits.length === 0) return null;
  return (
    <div className="ta-search-section">
      <div className="ta-section-divider">
        <div className="ta-section-name">People</div>
        <div className="ta-section-sub">{hits.length} match{hits.length === 1 ? "" : "es"}</div>
      </div>
      {hits.map((h) => (
        <a key={`person-${h.id}`} href={`#/profile/${h.slug}`} className="ta-search-row ta-search-row-person">
          <Avatar author={{ name: h.title, avatar_letter: h.title[0], avatar_color: "teal" }} size="md" />
          <div>
            <div className="ta-search-row-title">{h.title}</div>
            {h.snippet && <div className="ta-search-row-snippet">{h.snippet}</div>}
          </div>
        </a>
      ))}
    </div>
  );
}
