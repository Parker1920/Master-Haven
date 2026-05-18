/**
 * PasswordPrompt — inline set-password form.
 *
 * Renders two ways depending on user state:
 *  - needs_password=true: a red-ish banner urging them to set one.
 *  - has_password=true: a quieter "change password" form.
 *  - else (plain reader/diplomat with no password): an "optional" form.
 *
 * Posts to /api/v1/auth/set-password and refreshes auth on success.
 */

import { useState } from "react";
import { apiRaw, ApiError } from "../api/client";
import { refreshAuth, useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";

export function PasswordPrompt() {
  const { user } = useAuth();
  const [open, setOpen] = useState<boolean>(Boolean(user?.needs_password));
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!user) return null;

  const needs = !!user.needs_password;
  const has = !!user.has_password;

  // If they don't need it AND don't have one, just show a tiny CTA
  // (collapsed by default for plain users).
  if (!needs && !has && !open) {
    return (
      <button
        className="ta-btn"
        onClick={() => setOpen(true)}
        style={{ marginTop: 8 }}
      >
        Set a password (optional)
      </button>
    );
  }
  if (!needs && has && !open) {
    return (
      <button
        className="ta-btn"
        onClick={() => setOpen(true)}
        style={{ marginTop: 8 }}
      >
        Change password
      </button>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (next.length < 6) {
      setErr("Password must be at least 6 characters");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await apiRaw("/auth/set-password", {
        method: "POST",
        body: has ? { current_password: current, new_password: next } : { new_password: next },
      });
      await refreshAuth();
      showToast(has ? "Password changed" : "Password set");
      setCurrent("");
      setNext("");
      setOpen(false);
    } catch (e) {
      setErr(e instanceof ApiError ? String(e.detail) : "Failed to update password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        marginTop: 12, marginBottom: 12,
        padding: 14,
        background: needs ? "rgba(160,48,48,0.10)" : "var(--ta-surface)",
        border: `1px solid ${needs ? "rgba(160,48,48,0.45)" : "var(--ta-border)"}`,
        borderRadius: 8,
      }}
    >
      <div style={{ fontWeight: 500, fontSize: 13, marginBottom: 6 }}>
        {needs
          ? `Set a password — required for ${user.is_admin ? "admin" : "editor"} actions`
          : has
            ? "Change password"
            : "Set a password (optional)"}
      </div>
      <div style={{ fontSize: 11, color: "var(--ta-text-dim)", marginBottom: 10, lineHeight: 1.5 }}>
        {needs
          ? "Until you set one, the archive will block your writes. Without a password, anyone could claim your username and inherit your role."
          : has
            ? "Update your password. You'll be asked to enter the current one."
            : "Optional. If set, no-one else can claim your username without it."}
      </div>
      <form onSubmit={submit}>
        {has && (
          <div className="ta-form-row">
            <label className="ta-form-label" htmlFor="cur">Current password</label>
            <input
              id="cur"
              className="ta-form-input"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              required
              disabled={busy}
            />
          </div>
        )}
        <div className="ta-form-row">
          <label className="ta-form-label" htmlFor="new">New password (min 6 chars)</label>
          <input
            id="new"
            className="ta-form-input"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            required
            minLength={6}
            disabled={busy}
          />
        </div>
        {err && (
          <div style={{ fontSize: 12, color: "#ff9090", marginBottom: 8 }}>{err}</div>
        )}
        <div style={{ display: "flex", gap: 8 }}>
          <button type="submit" className="ta-btn ta-btn-primary" disabled={busy}>
            {busy ? "…" : has ? "Change password" : "Set password"}
          </button>
          {!needs && (
            <button type="button" className="ta-btn" onClick={() => setOpen(false)} disabled={busy}>
              Cancel
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
