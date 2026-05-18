/**
 * Login — claim-based login (v0.6).
 *
 * Flow:
 *   1. User types a Discord-style handle (lowercase, dots/underscores ok).
 *   2. We POST /auth/claim {username}.
 *   3a. 200 OK → cookie set, redirect to Dashboard.
 *   3b. 401 "password required" → show password field, retry with password.
 *
 * First-visit special case: if NO admin exists yet on this archive,
 * the first claimer becomes admin (the backend handles this). The
 * Login page shows a small "you'll be the first admin" hint when
 * that's about to happen — but we can't know that without an extra
 * GET, so we just mention it in the helper text.
 */

import { useState } from "react";
import { apiRaw, ApiError } from "../api/client";
import { refreshAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { navigate } from "../router";

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [needsPassword, setNeedsPassword] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const u = username.trim().toLowerCase();
    if (!u) return;
    setBusy(true);
    setErr(null);
    try {
      const env = await apiRaw<{ id: number; is_new: boolean; is_bootstrap_admin?: boolean }>(
        "/auth/claim",
        {
          method: "POST",
          body: needsPassword ? { username: u, password } : { username: u },
        },
      );
      await refreshAuth();
      if (env?.data?.is_bootstrap_admin) {
        showToast("Welcome — you're the first admin");
      } else if (env?.data?.is_new) {
        showToast(`Welcome, ${u}`);
      } else {
        showToast(`Logged in as ${u}`);
      }
      navigate("/dashboard");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        // Password required for this name
        setNeedsPassword(true);
        setErr("This name is protected. Enter the password.");
      } else if (e instanceof ApiError) {
        setErr(String(e.detail) || "Login failed");
      } else {
        setErr("Network error");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 380, margin: "60px auto", padding: "0 16px" }}>
      <h1 style={{ fontFamily: "Georgia, serif", fontSize: 28, fontWeight: 500, marginBottom: 4 }}>
        Sign in
      </h1>
      <p style={{ fontSize: 13, color: "var(--ta-text-dim)", marginBottom: 24, lineHeight: 1.5 }}>
        Type your Discord username. If it's never been claimed, you'll
        log in immediately. If you've protected it with a password,
        you'll need that too.
      </p>

      <form onSubmit={submit}>
        <div className="ta-form-row">
          <label className="ta-form-label" htmlFor="username">Discord username</label>
          <input
            id="username"
            className="ta-form-input"
            type="text"
            autoCapitalize="none"
            autoCorrect="off"
            autoComplete="username"
            placeholder="ekimo"
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
              setNeedsPassword(false);
              setErr(null);
            }}
            disabled={busy}
            required
          />
        </div>

        {needsPassword && (
          <div className="ta-form-row">
            <label className="ta-form-label" htmlFor="password">Password</label>
            <input
              id="password"
              className="ta-form-input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
              autoFocus
              required
            />
          </div>
        )}

        {err && (
          <div style={{
            fontSize: 12, color: "#ff9090",
            background: "rgba(160,48,48,0.12)",
            border: "1px solid rgba(160,48,48,0.35)",
            padding: "8px 12px", borderRadius: 6,
            marginBottom: 14,
          }}>{err}</div>
        )}

        <button
          type="submit"
          className="ta-btn ta-btn-primary"
          disabled={busy || !username.trim()}
          style={{ width: "100%" }}
        >
          {busy ? "…" : needsPassword ? "Sign in with password" : "Continue"}
        </button>
      </form>

      <div style={{
        marginTop: 20, fontSize: 11, color: "var(--ta-text-faint)",
        lineHeight: 1.5, padding: "12px 0", borderTop: "1px solid var(--ta-border)",
      }}>
        Plain reader/diplomat accounts don't need a password. Anyone who
        knows your handle can claim it once it's free. Admins and
        editors are required to set a password — accounts without one
        can't perform privileged actions.
      </div>
    </div>
  );
}
