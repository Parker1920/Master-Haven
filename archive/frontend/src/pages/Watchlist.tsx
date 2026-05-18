/**
 * Watchlist — list of entities the current user follows.
 *
 * The backend stores polymorphic rows (target_type + target_id) but no
 * denormalized display fields. We resolve each row to a link + label
 * lazily on render based on type — for inquisitions, we fetch the
 * detail so we can show the title; for civilizations we don't need to
 * since the URL is keyed by slug-but-we-only-have-id... so we just
 * show the link target generically and let the user click through.
 */

import { useEffect, useState } from "react";
import { api, apiRaw, WatchlistItem } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";

export function Watchlist() {
  const { user, loading } = useAuth();
  const [items, setItems] = useState<WatchlistItem[] | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) { setItems([]); return; }
    setItems(null);
    api<WatchlistItem[]>("/watchlist").then(setItems).catch(() => setItems([]));
  }, [user, loading]);

  if (loading) return <div className="ta-loading">Loading…</div>;
  if (!user) {
    return (
      <div className="ta-empty">
        Not signed in.&nbsp;
        <a href="#/login" style={{ color: "var(--ta-accent-blue)" }}>Sign in</a> to use your watchlist.
      </div>
    );
  }

  const unwatch = async (id: number) => {
    try {
      await apiRaw(`/watchlist/${id}`, { method: "DELETE" });
      setItems((cur) => (cur ?? []).filter((i) => i.id !== id));
      showToast("Removed");
    } catch {
      showToast("Remove failed");
    }
  };

  return (
    <>
      <div className="ta-civ-index-header">
        <h2 className="ta-civ-index-title">Watchlist</h2>
        <p className="ta-civ-index-sub">
          {items === null
            ? "Loading…"
            : `${items.length} watched item${items.length === 1 ? "" : "s"}`}
        </p>
      </div>

      {items === null ? (
        <div className="ta-loading">…</div>
      ) : items.length === 0 ? (
        <div className="ta-empty">
          Nothing here yet. Open a civilization, story, or inquisition and click "Watch" to add it.
        </div>
      ) : (
        <div className="ta-watch-list">
          {items.map((item) => (
            <WatchRow key={item.id} item={item} onRemove={() => unwatch(item.id)} />
          ))}
        </div>
      )}
    </>
  );
}

function WatchRow({ item, onRemove }: { item: WatchlistItem; onRemove: () => void }) {
  // Build the best link we can per type. For civilizations/people we'd
  // need the slug — for now we link to the type index and the user can
  // click through. (When the watchlist API grows a denormalized label/
  // slug field we can show a direct link.)
  const typeLabel: Record<string, string> = {
    civilization: "Civilization",
    person: "Person",
    event: "Event",
    place: "Place",
    inquisition: "Inquisition",
    user: "User",
  };
  let href = "#/";
  switch (item.target_type) {
    case "inquisition": href = `#/inquisition/${item.target_id}`; break;
    case "civilization": href = `#/civs`; break;
    case "person": href = `#/people`; break;
    case "event": href = `#/events`; break;
    case "place": href = `#/places`; break;
    case "user": href = `#/dashboard`; break;
  }

  return (
    <div className="ta-watch-row">
      <a href={href} className="ta-watch-row-body">
        <div className="ta-watch-row-type">{typeLabel[item.target_type] ?? item.target_type}</div>
        <div className="ta-watch-row-id">#{item.target_id}</div>
        <div className="ta-watch-row-date">
          added {new Date(item.created_at).toLocaleDateString()}
        </div>
      </a>
      <button className="ta-btn" onClick={onRemove}
              style={{ padding: "4px 12px", fontSize: 11 }}>Remove</button>
    </div>
  );
}
