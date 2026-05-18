/** Civilizations index grid. */
import { useEffect, useState } from "react";
import {
  api,
  CivilizationDetail,
  CivilizationSummary,
  CivilizationWrite,
} from "../api/client";
import { CivCard } from "../components/CivCard";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { navigate } from "../router";
import { Field } from "./CivPage";

const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;

function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .slice(0, 64);
}

export function Civs() {
  const { user } = useAuth();
  const [civs, setCivs] = useState<CivilizationSummary[] | null>(null);
  const [creating, setCreating] = useState(false);

  const load = () => {
    api<CivilizationSummary[]>("/civilizations", { query: { page_size: 500 } })
      .then(setCivs)
      .catch(() => setCivs([]));
  };

  useEffect(() => { load(); }, []);

  return (
    <>
      <div className="ta-civ-index-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div>
            <h2 className="ta-civ-index-title">Civilizations</h2>
            <p className="ta-civ-index-sub">
              {civs === null ? "Loading…" : `${civs.length} civs documented · all sizes, all states · same structural treatment`}
            </p>
          </div>
          {user?.is_admin && (
            <button
              className="ta-btn ta-btn-primary"
              onClick={() => setCreating(true)}
              style={{ padding: "6px 14px" }}
            >
              + New Civilization
            </button>
          )}
        </div>
      </div>
      <div className="ta-civ-grid">
        {civs?.map((c) => <CivCard key={c.slug} civ={c} />)}
      </div>
      {creating && (
        <CreateCivModal
          onCancel={() => setCreating(false)}
          onCreated={(c) => {
            setCreating(false);
            showToast(`Created ${c.name}`);
            navigate(`/civ/${c.slug}`);
          }}
        />
      )}
    </>
  );
}

function CreateCivModal({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (c: CivilizationDetail) => void;
}) {
  const [draft, setDraft] = useState<CivilizationWrite>({
    slug: "",
    name: "",
    status: "active",
    galaxy: "",
    tagline: "",
    description: "",
    color_primary: "#534AB7",
    color_secondary: "#1D9E75",
  });
  const [slugTouched, setSlugTouched] = useState(false);
  const [saving, setSaving] = useState(false);

  const set = <K extends keyof CivilizationWrite>(k: K, v: CivilizationWrite[K]) =>
    setDraft((d) => ({ ...d, [k]: v }));

  const onNameChange = (v: string) => {
    setDraft((d) => ({
      ...d,
      name: v,
      // Auto-generate slug until the user types in the slug field themselves
      slug: slugTouched ? d.slug : slugify(v),
    }));
  };

  const slugValid = SLUG_RE.test(draft.slug);
  const canSave = draft.name.trim() && slugValid && !saving;

  const save = async () => {
    if (!canSave) return;
    setSaving(true);
    try {
      const c = await api<CivilizationDetail>("/civilizations", {
        method: "POST",
        body: draft,
      });
      onCreated(c);
    } catch (e) {
      showToast(`Create failed: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="ta-modal-backdrop" onClick={onCancel}>
      <div className="ta-modal" onClick={(e) => e.stopPropagation()}>
        <h3 style={{ fontFamily: "Georgia, serif", fontSize: 22, margin: "0 0 16px" }}>New civilization</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Field label="Name" required>
            <input
              className="ta-form-input"
              value={draft.name}
              onChange={(e) => onNameChange(e.target.value)}
              autoFocus
            />
          </Field>
          <Field label="Slug" required>
            <input
              className="ta-form-input"
              value={draft.slug}
              onChange={(e) => { setSlugTouched(true); set("slug", e.target.value); }}
              placeholder="lowercase, hyphens, max 64 chars"
            />
            {draft.slug && !slugValid && (
              <span style={{ fontSize: 11, color: "var(--ta-accent-red)" }}>
                Slug must start with a letter or digit and contain only lowercase letters, digits, and hyphens.
              </span>
            )}
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
              rows={4}
              style={{ minHeight: 100 }}
            />
          </Field>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="Primary color">
              <input
                type="color"
                className="ta-form-input"
                value={draft.color_primary ?? "#534AB7"}
                onChange={(e) => set("color_primary", e.target.value)}
                style={{ height: 40, padding: 4 }}
              />
            </Field>
            <Field label="Secondary color">
              <input
                type="color"
                className="ta-form-input"
                value={draft.color_secondary ?? "#1D9E75"}
                onChange={(e) => set("color_secondary", e.target.value)}
                style={{ height: 40, padding: 4 }}
              />
            </Field>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
          <button className="ta-btn" onClick={onCancel} disabled={saving} style={{ padding: "6px 14px" }}>
            Cancel
          </button>
          <button
            className="ta-btn ta-btn-primary"
            onClick={save}
            disabled={!canSave}
            style={{ padding: "6px 14px" }}
          >
            {saving ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
