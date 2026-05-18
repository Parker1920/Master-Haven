/**
 * WatchButton — toggle watchlist for a target entity.
 *
 * Loads the current user's watchlist on mount, finds the matching entry
 * (if any), and renders a "Watch" / "Watching" toggle. POST/DELETE
 * hit /api/v1/watchlist.
 *
 * If the user isn't logged in we render nothing — the watchlist is a
 * personal feature.
 */

import { useEffect, useState } from "react";
import { api, apiRaw, WatchlistItem } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";

type Target = "civilization" | "person" | "event" | "place" | "inquisition" | "user";

interface Props {
  targetType: Target;
  targetId: number;
  size?: "sm" | "md";
}

export function WatchButton({ targetType, targetId, size = "md" }: Props) {
  const { user } = useAuth();
  const [watchId, setWatchId] = useState<number | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) { setLoaded(true); return; }
    api<WatchlistItem[]>("/watchlist")
      .then((items) => {
        const hit = items.find((i) => i.target_type === targetType && i.target_id === targetId);
        setWatchId(hit?.id ?? null);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, [user, targetType, targetId]);

  if (!user) return null;
  if (!loaded) return null;

  const toggle = async () => {
    if (busy) return;
    setBusy(true);
    try {
      if (watchId !== null) {
        await apiRaw(`/watchlist/${watchId}`, { method: "DELETE" });
        setWatchId(null);
        showToast("Removed from watchlist");
      } else {
        const item = await api<WatchlistItem>("/watchlist", {
          method: "POST",
          body: { target_type: targetType, target_id: targetId },
        });
        setWatchId(item.id);
        showToast("Added to watchlist");
      }
    } catch {
      showToast("Watchlist update failed");
    } finally {
      setBusy(false);
    }
  };

  const isWatching = watchId !== null;
  const klass = size === "sm"
    ? "ta-btn"
    : (isWatching ? "ta-btn ta-btn-primary" : "ta-btn");
  return (
    <button
      className={klass}
      onClick={toggle}
      disabled={busy}
      style={size === "sm" ? { padding: "4px 10px", fontSize: 11 } : undefined}
      title={isWatching ? "Stop watching this" : "Add to your watchlist"}
    >
      {isWatching ? "★ Watching" : "☆ Watch"}
    </button>
  );
}
