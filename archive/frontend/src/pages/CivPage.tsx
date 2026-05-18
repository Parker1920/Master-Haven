/** Civilization detail page — hero + stat strip + coverage list + admin edit. */
import { useEffect, useState } from "react";
import {
  api,
  apiRaw,
  CivilizationDetail,
  CivilizationPatch,
  CoverageItem,
} from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { navigate } from "../router";

export function CivPage({ slug }: { slug: string }) {
  const { user } = useAuth();
  const [civ, setCiv] = useState<CivilizationDetail | null>(null);
  const [coverage, setCoverage] = useState<CoverageItem[]>([]);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<CivilizationPatch>({});
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    setCiv(null);
    setCoverage([]);
    setNotFound(false);
    setEditing(false);
    setConfirmDelete(false);
    Promise.all([
      api<CivilizationDetail>(`/civilizations/${slug}`),
      api<CoverageItem[]>(`/civilizations/${slug}/coverage`),
    ])
      .then(([c, cov]) => {
        setCiv(c);
        setCoverage(cov);
      })
      .catch(() => setNotFound(true));
  }, [slug]);

  if (notFound) return <div className="ta-empty">Civilization not found.</div>;
  if (!civ) return <div className="ta-loading">Loading civilization…</div>;

  const startEdit = () => {
    setDraft({
      name: civ.name,
      status: civ.status as "active" | "dormant" | "archived",
      galaxy: civ.galaxy ?? "",
      founded: civ.founded ?? "",
      founded_year: civ.founded_year ?? null,
      ended: civ.ended ?? "",
      ended_year: civ.ended_year ?? null,
      tagline: civ.tagline ?? "",
      description: civ.description ?? "",
      color_primary: civ.color_primary,
      color_secondary: civ.color_secondary,
    });
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api<CivilizationDetail>(`/civilizations/${slug}`, {
        method: "PATCH",
        body: draft,
      });
      setCiv(updated);
      setEditing(false);
      showToast("Civilization saved");
    } catch (e) {
      showToast(`Save failed: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async () => {
    try {
      await apiRaw(`/civilizations/${slug}`, { method: "DELETE" });
      showToast(`${civ.name} deleted`);
      navigate("/civs");
    } catch (e) {
      showToast(`Delete failed: ${(e as Error).message}`);
    }
  };

  const heroStyles = {
    "--c1": editing ? draft.color_primary || civ.color_primary : civ.color_primary,
    "--c2": editing ? draft.color_secondary || civ.color_secondary : civ.color_secondary,
  } as React.CSSProperties;

  return (
    <>
      <div className="ta-civ-hero" style={heroStyles}>
        <div className="ta-civ-hero-eyebrow">Civilization</div>
        <h1 className="ta-civ-hero-name">{editing ? (draft.name || civ.name) : civ.name}</h1>
        <div className="ta-civ-hero-tagline">
          {civ.galaxy} galaxy · founded {civ.founded}
          {civ.ended ? ` – ${civ.ended}` : ""} · {civ.tagline}
        </div>
        {user?.is_admin && !editing && (
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button className="ta-btn" onClick={startEdit} style={{ padding: "5px 14px" }}>
              Edit
            </button>
            <button
              className="ta-btn"
              onClick={() => setConfirmDelete(true)}
              style={{ padding: "5px 14px", borderColor: "var(--ta-accent-red, #c0392b)" }}
            >
              Delete
            </button>
          </div>
        )}
      </div>

      <div className="ta-civ-stats-strip">
        <CivStat n={civ.stats.entries} label="Entries" />
        <CivStat n={civ.stats.inquisitions} label="Inquisitions" />
        <CivStat n={civ.stats.people} label="People" />
        <CivStat n={civ.stats.years} label="Years" />
      </div>

      {editing ? (
        <div className="ta-civ-body">
          <CivEditForm
            draft={draft}
            setDraft={setDraft}
            onCancel={() => setEditing(false)}
            onSave={save}
            saving={saving}
          />
        </div>
      ) : (
        <div className="ta-civ-body">
          <div className="ta-civ-body-eyebrow">
            All coverage tagged {civ.name} · {coverage.length} entries
          </div>

          {civ.description && (
            <p style={{
              fontFamily: "Georgia, serif", fontSize: 15, lineHeight: 1.6,
              color: "var(--ta-text-dim)", marginBottom: 18,
            }}>
              {civ.description}
            </p>
          )}

          {coverage.length === 0 ? (
            <p style={{ color: "var(--ta-text-faint)", fontSize: 13 }}>
              No coverage yet. {civ.name} is documented but has no published stories.
            </p>
          ) : (
            <div className="ta-coverage-list">
              {coverage.map((c) => <CoverageRow key={`${c.kind}-${c.id}`} item={c} />)}
            </div>
          )}
        </div>
      )}

      {confirmDelete && (
        <ConfirmDeleteModal
          civName={civ.name}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={doDelete}
        />
      )}
    </>
  );
}

function CivStat({ n, label }: { n: number; label: string }) {
  return (
    <div className="ta-civ-stat">
      <div className="ta-civ-stat-num">{n}</div>
      <div className="ta-civ-stat-label">{label}</div>
    </div>
  );
}

function CoverageRow({ item }: { item: CoverageItem }) {
  const href = item.kind === "story" ? `#/story/${item.id}` : `#/inquisition/${item.id}`;
  const dateStr = item.published_at || item.started_at || "";
  const niceDate = dateStr
    ? new Date(dateStr).toLocaleDateString("en-US", { dateStyle: "medium" })
    : "";
  return (
    <a href={href} className="ta-coverage-item">
      <div className="ta-coverage-date">
        {niceDate} · {item.kind} · {item.beat || item.state || ""}
      </div>
      <h3 className="ta-coverage-title">{item.headline}</h3>
      {item.deck && <p className="ta-coverage-deck">{item.deck}</p>}
      {item.author && (
        <div className="ta-byline-row"><span>By <b>{item.author.name}</b></span></div>
      )}
    </a>
  );
}

interface CivEditFormProps {
  draft: CivilizationPatch;
  setDraft: (d: CivilizationPatch) => void;
  onCancel: () => void;
  onSave: () => void;
  saving: boolean;
}

export function CivEditForm({ draft, setDraft, onCancel, onSave, saving }: CivEditFormProps) {
  const set = <K extends keyof CivilizationPatch>(k: K, v: CivilizationPatch[K]) =>
    setDraft({ ...draft, [k]: v });
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <h3 style={{ fontFamily: "Georgia, serif", fontSize: 18, margin: 0 }}>Edit civilization</h3>
      <Field label="Name" required>
        <input
          className="ta-form-input"
          value={draft.name ?? ""}
          onChange={(e) => set("name", e.target.value)}
        />
      </Field>
      <Field label="Status">
        <select
          className="ta-form-select"
          value={draft.status ?? "active"}
          onChange={(e) => set("status", e.target.value as "active" | "dormant" | "archived")}
        >
          <option value="active">Active</option>
          <option value="dormant">Dormant</option>
          <option value="archived">Archived</option>
        </select>
      </Field>
      <Field label="Galaxy">
        <input
          className="ta-form-input"
          value={draft.galaxy ?? ""}
          onChange={(e) => set("galaxy", e.target.value)}
          placeholder="Euclid, Hilbert, Multi-galaxy…"
        />
      </Field>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
        <Field label="Founded (display)">
          <input
            className="ta-form-input"
            value={draft.founded ?? ""}
            onChange={(e) => set("founded", e.target.value)}
            placeholder="Year 1, 2020…"
          />
        </Field>
        <Field label="Founded year">
          <input
            type="number"
            className="ta-form-input"
            value={draft.founded_year ?? ""}
            onChange={(e) => set("founded_year", e.target.value ? parseInt(e.target.value, 10) : null)}
          />
        </Field>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
        <Field label="Ended (display)">
          <input
            className="ta-form-input"
            value={draft.ended ?? ""}
            onChange={(e) => set("ended", e.target.value)}
          />
        </Field>
        <Field label="Ended year">
          <input
            type="number"
            className="ta-form-input"
            value={draft.ended_year ?? ""}
            onChange={(e) => set("ended_year", e.target.value ? parseInt(e.target.value, 10) : null)}
          />
        </Field>
      </div>
      <Field label="Tagline">
        <input
          className="ta-form-input"
          value={draft.tagline ?? ""}
          onChange={(e) => set("tagline", e.target.value)}
        />
      </Field>
      <Field label="Description">
        <textarea
          className="ta-form-textarea"
          value={draft.description ?? ""}
          onChange={(e) => set("description", e.target.value)}
          rows={6}
          style={{ minHeight: 120 }}
        />
      </Field>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Field label="Primary color">
          <input
            type="color"
            className="ta-form-input"
            value={draft.color_primary ?? "#534AB7"}
            onChange={(e) => set("color_primary", e.target.value)}
            style={{ height: 36 }}
          />
        </Field>
        <Field label="Secondary color">
          <input
            type="color"
            className="ta-form-input"
            value={draft.color_secondary ?? "#1D9E75"}
            onChange={(e) => set("color_secondary", e.target.value)}
            style={{ height: 36 }}
          />
        </Field>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button
          className="ta-btn ta-btn-primary"
          onClick={onSave}
          disabled={saving}
          style={{ padding: "6px 16px" }}
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          className="ta-btn"
          onClick={onCancel}
          disabled={saving}
          style={{ padding: "6px 16px" }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: 11, color: "var(--ta-text-dim)", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
        {label}{required && <span style={{ color: "var(--ta-accent-red, #c0392b)" }}> *</span>}
      </span>
      {children}
    </label>
  );
}

function ConfirmDeleteModal({
  civName, onCancel, onConfirm,
}: { civName: string; onCancel: () => void; onConfirm: () => void }) {
  return (
    <div className="ta-modal-backdrop" onClick={onCancel}>
      <div className="ta-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420 }}>
        <h3 style={{ fontFamily: "Georgia, serif", fontSize: 20, margin: "0 0 12px" }}>Delete {civName}?</h3>
        <p style={{ fontSize: 13, color: "var(--ta-text-dim)", marginBottom: 16 }}>
          This soft-deletes the civilization. It will disappear from the index
          and detail pages. Coverage tagged with it stays in place but the civ
          link will 404.
        </p>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="ta-btn" onClick={onCancel} style={{ padding: "6px 14px" }}>Cancel</button>
          <button
            className="ta-btn"
            onClick={onConfirm}
            style={{
              padding: "6px 14px",
              borderColor: "var(--ta-accent-red, #c0392b)",
              color: "var(--ta-accent-red, #c0392b)",
            }}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
