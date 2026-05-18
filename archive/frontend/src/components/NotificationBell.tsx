/**
 * NotificationBell — desktop nav bell + unread count badge.
 *
 * Polls GET /notifications/count every 60s while a user is signed in.
 * Click navigates to the Dashboard (where notifications render).
 *
 * The shared count is exposed through a tiny event bus so the Dashboard
 * can decrement it locally after mark-read without forcing a refetch.
 */

import { useEffect, useState } from "react";
import { apiRaw } from "../api/client";
import { useAuth } from "../hooks/useAuth";

const listeners = new Set<(n: number) => void>();
let cachedUnread = 0;

export function broadcastUnread(n: number) {
  cachedUnread = Math.max(0, n);
  listeners.forEach((fn) => fn(cachedUnread));
}

async function fetchUnread(): Promise<number> {
  try {
    const env = await apiRaw<{ unread: number }>("/notifications/count");
    return env?.data?.unread ?? 0;
  } catch {
    return 0;
  }
}

export function NotificationBell() {
  const { user } = useAuth();
  const [unread, setUnread] = useState(cachedUnread);

  useEffect(() => {
    const onChange = (n: number) => setUnread(n);
    listeners.add(onChange);
    return () => {
      listeners.delete(onChange);
    };
  }, []);

  useEffect(() => {
    if (!user) {
      broadcastUnread(0);
      return;
    }
    let cancelled = false;
    const tick = async () => {
      const n = await fetchUnread();
      if (!cancelled) broadcastUnread(n);
    };
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [user]);

  if (!user) return null;

  return (
    <a
      href="#/dashboard"
      className="ta-notif-bell"
      title={unread > 0 ? `${unread} unread notification${unread === 1 ? "" : "s"}` : "Notifications"}
      aria-label={`Notifications (${unread} unread)`}
    >
      <span aria-hidden="true">🔔</span>
      {unread > 0 && (
        <span className="ta-notif-badge">{unread > 99 ? "99+" : unread}</span>
      )}
    </a>
  );
}
