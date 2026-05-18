/** Admin — super-admin-only page with Users + Audit Log tabs. */
import { useEffect, useState } from "react";
import {
  AdminUserRow,
  AuditLogEntry,
  CivilizationSummary,
  api,
  apiRaw,
} from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { Field } from "./CivPage";

type Tab = "users" | "audit";

export function Admin() {
  const { user, loading } = useAuth();
  const [tab, setTab] = useState<Tab>("users");

  if (loading) return <div className="ta-loading">Loading…</div>;
  if (!user?.is_admin) {
    return (
      <div className="ta-empty">
        Admin access required. <a href="#/" style={{ color: "var(--ta-accent-blue)" }}>Back to newsroom</a>
      </div>
    );
  }

  return (
    <>
      <div style={{ padding: "22px 16px 14px", borderBottom: "1px solid var(--ta-border)" }}>
        <h2 style={{ fontFamily: "Georgia, serif", fontSize: 28, marginBottom: 6 }}>Admin</h2>
        <p style={{ fontSize: 13, color: "var(--ta-text-dim)" }}>
          User roles and audit log. Super-admin only.
        </p>
      </div>
      <div style={{ padding: "0 16px" }}>
        <div className="ta-tabs">
          <button className={`ta-tab${tab === "users" ? " active" : ""}`} onClick={() => setTab("users")}>
            Users
          </button>
          <button className={`ta-tab${tab === "audit" ? " active" : ""}`} onClick={() => setTab("audit")}>
            Audit Log
          </button>
        </div>
        {tab === "users" ? <UsersTab /> : <AuditLogTab />}
      </div>
    </>
  );
}

// ===================================================================
// Users tab
// ===================================================================

function UsersTab() {
  const [users, setUsers] = useState<AdminUserRow[] | null>(null);
  const [civs, setCivs] = useState<CivilizationSummary[]>([]);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    api<CivilizationSummary[]>("/civilizations", { query: { page_size: 500 } })
      .then(setCivs)
      .catch(() => setCivs([]));
  }, []);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQ(q), 250);
    return () => window.clearTimeout(t);
  }, [q]);

  const load = () => {
    setUsers(null);
    api<AdminUserRow[]>("/admin/users", { query: { page_size: 500, q: debouncedQ || undefined } })
      .then(setUsers)
      .catch(() => setUsers([]));
  };

  useEffect(() => { load(); }, [debouncedQ]);

  const updateUser = (updated: AdminUserRow) => {
    setUsers((cur) => (cur ?? []).map((u) => (u.id === updated.id ? updated : u)));
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <input
          className="ta-form-input"
          placeholder="Search by username or display name…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      {users === null ? (
        <div className="ta-loading">Loading users…</div>
      ) : users.length === 0 ? (
        <p style={{ color: "var(--ta-text-faint)", fontSize: 13 }}>No users match.</p>
      ) : (
        <table className="ta-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Civ</th>
              <th>Beat</th>
              <th style={{ width: 80 }}></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <UserRow
                key={u.id}
                user={u}
                civs={civs}
                expanded={expandedId === u.id}
                onToggle={() => setExpandedId(expandedId === u.id ? null : u.id)}
                onSaved={updateUser}
              />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

interface UserRowProps {
  user: AdminUserRow;
  civs: CivilizationSummary[];
  expanded: boolean;
  onToggle: () => void;
  onSaved: (updated: AdminUserRow) => void;
}

function UserRow({ user, civs, expanded, onToggle, onSaved }: UserRowProps) {
  return (
    <>
      <tr onClick={onToggle} style={{ cursor: "pointer" }}>
        <td>
          <div style={{ fontWeight: 600 }}>{user.display_name}</div>
          <div style={{ fontSize: 11, color: "var(--ta-text-faint)" }}>@{user.discord_username}</div>
        </td>
        <td>
          <RoleBadges user={user} />
        </td>
        <td style={{ fontSize: 12 }}>{user.civ_slug || "—"}</td>
        <td style={{ fontSize: 12 }}>{user.beat || "—"}</td>
        <td style={{ textAlign: "right", color: "var(--ta-text-faint)", fontSize: 11 }}>
          {expanded ? "▾ close" : "▸ edit"}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={5} style={{ background: "var(--ta-bg)", padding: 16 }}>
            <UserEditForm user={user} civs={civs} onSaved={onSaved} onCancel={onToggle} />
          </td>
        </tr>
      )}
    </>
  );
}

function RoleBadges({ user }: { user: AdminUserRow }) {
  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
      <span className={`ta-role-badge ${user.base_role}`}>{user.base_role}</span>
      {user.is_editor && <span className="ta-role-badge editor">editor</span>}
      {user.is_admin && <span className="ta-role-badge admin">admin</span>}
    </div>
  );
}

interface UserEditFormProps {
  user: AdminUserRow;
  civs: CivilizationSummary[];
  onSaved: (updated: AdminUserRow) => void;
  onCancel: () => void;
}

function UserEditForm({ user, civs, onSaved, onCancel }: UserEditFormProps) {
  const [baseRole, setBaseRole] = useState<"reader" | "diplomat" | "historian">(user.base_role);
  const [isEditor, setIsEditor] = useState(user.is_editor);
  const [isAdmin, setIsAdmin] = useState(user.is_admin);
  const [civSlug, setCivSlug] = useState(user.civ_slug ?? "");
  const [beat, setBeat] = useState(user.beat ?? "");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api<AdminUserRow>(`/admin/users/${user.id}`, {
        method: "PATCH",
        body: {
          base_role: baseRole,
          is_editor: isEditor,
          is_admin: isAdmin,
          civ_slug: civSlug || null,
          beat: beat || null,
        },
      });
      onSaved(updated);
      showToast("User updated");
      onCancel();
    } catch (e) {
      showToast(`Save failed: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Field label="Base role">
          <select
            className="ta-form-select"
            value={baseRole}
            onChange={(e) => setBaseRole(e.target.value as "reader" | "diplomat" | "historian")}
          >
            <option value="reader">Reader</option>
            <option value="diplomat">Diplomat</option>
            <option value="historian">Historian</option>
          </select>
        </Field>
        <Field label="Civilization">
          <select
            className="ta-form-select"
            value={civSlug}
            onChange={(e) => setCivSlug(e.target.value)}
          >
            <option value="">— none —</option>
            {civs.map((c) => (
              <option key={c.slug} value={c.slug}>{c.name}</option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Beat">
        <input
          className="ta-form-input"
          value={beat}
          onChange={(e) => setBeat(e.target.value)}
          placeholder="e.g., The Galactic Hub"
        />
      </Field>
      <div style={{ display: "flex", gap: 16, padding: "6px 0" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={isEditor}
            onChange={(e) => setIsEditor(e.target.checked)}
          />
          Editor
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={isAdmin}
            onChange={(e) => setIsAdmin(e.target.checked)}
          />
          Admin
        </label>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          className="ta-btn ta-btn-primary"
          onClick={save}
          disabled={saving}
          style={{ padding: "6px 14px" }}
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          className="ta-btn"
          onClick={onCancel}
          disabled={saving}
          style={{ padding: "6px 14px" }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ===================================================================
// Audit log tab
// ===================================================================

function AuditLogTab() {
  const [entries, setEntries] = useState<AuditLogEntry[] | null>(null);
  const [actionFilter, setActionFilter] = useState("");

  useEffect(() => {
    setEntries(null);
    apiRaw<AuditLogEntry[]>("/admin/audit_log", {
      query: { limit: 200, action: actionFilter || undefined },
    })
      .then((env) => setEntries(env?.data ?? []))
      .catch(() => setEntries([]));
  }, [actionFilter]);

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <input
          className="ta-form-input"
          placeholder="Filter by action (e.g., civilization.delete, draft.publish)…"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
        />
      </div>
      {entries === null ? (
        <div className="ta-loading">Loading audit log…</div>
      ) : entries.length === 0 ? (
        <p style={{ color: "var(--ta-text-faint)", fontSize: 13 }}>No entries.</p>
      ) : (
        <table className="ta-table">
          <thead>
            <tr>
              <th style={{ width: 160 }}>When</th>
              <th style={{ width: 140 }}>Actor</th>
              <th>Action</th>
              <th>Target</th>
              <th>Metadata</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id}>
                <td style={{ fontSize: 11, color: "var(--ta-text-faint)", whiteSpace: "nowrap" }}>
                  {new Date(e.created_at).toLocaleString()}
                </td>
                <td style={{ fontSize: 12 }}>{e.user_name ?? "—"}</td>
                <td style={{ fontFamily: "Menlo, monospace", fontSize: 12 }}>{e.action}</td>
                <td style={{ fontSize: 12 }}>
                  {e.target_type ? `${e.target_type}:${e.target_id ?? "—"}` : "—"}
                </td>
                <td style={{ fontFamily: "Menlo, monospace", fontSize: 11, color: "var(--ta-text-dim)" }}>
                  {e.metadata ? JSON.stringify(e.metadata) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
