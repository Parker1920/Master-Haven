/** Dashboard — greeting + impact strip + quick actions + notifications inbox + password prompt. */
import { useEffect, useState } from "react";
import { api, apiRaw, NotificationDetail } from "../api/client";
import { PasswordPrompt } from "../components/PasswordPrompt";
import { refreshAuth, useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { navigate } from "../router";

export function Dashboard() {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState<NotificationDetail[] | null>(null);

  useEffect(() => {
    if (!user) {
      setNotifications([]);
      return;
    }
    api<NotificationDetail[]>("/notifications").then(setNotifications).catch(() => setNotifications([]));
  }, [user]);

  const logout = async () => {
    try {
      await apiRaw("/auth/logout", { method: "POST" });
      await refreshAuth();
      showToast("Logged out");
      navigate("/");
    } catch {
      showToast("Logout failed");
    }
  };

  if (!user) {
    return (
      <div className="ta-empty">
        Not signed in. <a href="#/login" style={{ color: "var(--ta-accent-blue)" }}>Sign in</a> to see your dashboard.
      </div>
    );
  }

  const unread = (notifications ?? []).filter((n) => !n.is_read);

  return (
    <>
      <div className="ta-dash-greeting">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
          <div>
            <div className="ta-dash-greet-text">Welcome back, {user.display_name}.</div>
            <div className="ta-dash-greet-sub">
              Role: {user.base_role}{user.is_editor ? " · editor" : ""}{user.is_admin ? " · admin" : ""}
              {user.civ_slug ? ` · ${user.civ_slug}` : ""}
            </div>
          </div>
          <button
            className="ta-btn"
            onClick={logout}
            style={{ padding: "5px 12px", fontSize: 11 }}
          >Log out</button>
        </div>
      </div>

      <div className="ta-dash-impact-strip">
        <ImpactCell n={unread.length} label="unread" />
        <ImpactCell n={notifications?.length ?? 0} label="all notif." />
        <ImpactCell n={user.is_editor || user.is_admin ? "✎" : "—"} label="editor" />
        <ImpactCell n={user.is_admin ? "★" : "—"} label="admin" />
      </div>

      <div style={{ padding: "0 16px" }}>
        <PasswordPrompt />
      </div>

      <div className="ta-dash-content">
        <div>
          <div className="ta-dash-section">
            <div className="ta-dash-section-title">
              Notifications
              <span className="ta-dash-section-count">{unread.length} unread</span>
            </div>
            {notifications === null ? (
              <div className="ta-loading">Loading…</div>
            ) : notifications.length === 0 ? (
              <p style={{ fontSize: 13, color: "var(--ta-text-faint)" }}>
                Nothing here yet. Notifications appear when you're added as a
                co-author, when a draft you wrote is reviewed, or when you're
                mentioned in a comment.
              </p>
            ) : (
              <>
                {notifications.slice(0, 10).map((n) => (
                  <a key={n.id} href={n.link || "#"} className="ta-dash-item">
                    <div className="ta-dash-item-title">
                      {n.is_read ? n.title : <b>{n.title}</b>}
                    </div>
                    {n.body && <div className="ta-dash-item-meta">{n.body}</div>}
                  </a>
                ))}
              </>
            )}
          </div>
        </div>

        <div>
          <div className="ta-dash-section">
            <div className="ta-dash-section-title">Quick actions</div>
            <div className="ta-dash-quick-actions">
              {(user.base_role === "diplomat" || user.base_role === "historian" || user.is_admin) && (
                <>
                  <a href="#/compose/brief" className="ta-dash-quick-btn">+ Start a new brief</a>
                  <a href="#/compose/feature" className="ta-dash-quick-btn">+ Start a new feature</a>
                </>
              )}
              {(user.base_role === "historian" || user.is_admin) && (
                <a href="#/compose/inquisition" className="ta-dash-quick-btn">+ Begin an inquisition</a>
              )}
              <a href="#/drafts" className="ta-dash-quick-btn">📝 Open drafts</a>
              <a href="#/civs" className="ta-dash-quick-btn">⸢ Browse civilizations</a>
              <a href="#/timeline" className="ta-dash-quick-btn">🕒 View timeline</a>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function ImpactCell({ n, label }: { n: number | string; label: string }) {
  return (
    <div className="ta-dash-impact-cell">
      <div className="ta-dash-impact-num">{n}</div>
      <div className="ta-dash-impact-label">{label}</div>
    </div>
  );
}
