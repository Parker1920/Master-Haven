/**
 * SearchBar — debounced search input with categorized dropdown results.
 *
 * Hits GET /api/v1/search?q=… (300ms debounce), groups the SearchHit
 * results by kind, and renders a dropdown popover. Clicking a result
 * navigates to the matching detail page and closes the dropdown.
 *
 * Closes on: outside click, Escape, navigation, or input blur (with a
 * short delay so click-on-result still fires).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api, SearchHit } from "../api/client";
import { navigate } from "../router";

const KIND_LABEL: Record<string, string> = {
  story: "Stories",
  inquisition: "Inquisitions",
  civilization: "Civilizations",
  person: "People",
};
const KIND_ORDER = ["story", "inquisition", "civilization", "person"];

function hrefFor(hit: SearchHit): string {
  switch (hit.kind) {
    case "story": return `/story/${hit.id}`;
    case "inquisition": return `/inquisition/${hit.id}`;
    case "civilization": return `/civ/${hit.slug}`;
    case "person": return `/profile/${hit.slug}`;
    default: return "/";
  }
}

export function SearchBar() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const debounceRef = useRef<number | null>(null);
  const reqIdRef = useRef(0);

  useEffect(() => {
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
    const trimmed = q.trim();
    if (trimmed.length < 2) {
      setHits(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    const myReq = ++reqIdRef.current;
    debounceRef.current = window.setTimeout(async () => {
      try {
        const res = await api<SearchHit[]>("/search", { query: { q: trimmed, limit: 20 } });
        if (reqIdRef.current === myReq) {
          setHits(res);
          setLoading(false);
        }
      } catch {
        if (reqIdRef.current === myReq) {
          setHits([]);
          setLoading(false);
        }
      }
    }, 300);
    return () => {
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
    };
  }, [q]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const pick = useCallback((hit: SearchHit) => {
    setOpen(false);
    setQ("");
    setHits(null);
    navigate(hrefFor(hit));
  }, []);

  const grouped = (hits ?? []).reduce<Record<string, SearchHit[]>>((acc, h) => {
    (acc[h.kind] ||= []).push(h);
    return acc;
  }, {});

  const showDropdown = open && q.trim().length >= 2;

  return (
    <div className="ta-search-wrap" ref={wrapRef}>
      <span className="ta-search-icon">⌕</span>
      <input
        className="ta-search-input"
        type="text"
        value={q}
        placeholder="Search stories, civs, people…"
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        aria-label="Search the archive"
      />
      {showDropdown && (
        <div className="ta-search-dropdown" role="listbox">
          {loading && hits === null ? (
            <div className="ta-search-empty">Searching…</div>
          ) : (hits?.length ?? 0) === 0 ? (
            <div className="ta-search-empty">No results for "{q.trim()}"</div>
          ) : (
            KIND_ORDER.filter((k) => grouped[k]?.length).map((kind) => (
              <div key={kind} className="ta-search-dropdown-section">
                <div className="ta-search-section-label">{KIND_LABEL[kind]} ({grouped[kind].length})</div>
                {grouped[kind].slice(0, 5).map((h) => (
                  <a
                    key={`${h.kind}-${h.id}`}
                    href={"#" + hrefFor(h)}
                    className="ta-search-hit"
                    onClick={(e) => {
                      e.preventDefault();
                      pick(h);
                    }}
                  >
                    <div className="ta-search-hit-title">{h.title}</div>
                    {h.snippet && <div className="ta-search-hit-snippet">{h.snippet}</div>}
                  </a>
                ))}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
