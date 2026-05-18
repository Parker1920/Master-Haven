/** Profile — person detail (works for archive_user and person rows). */
import { useEffect, useState } from "react";
import {
  api,
  apiRaw,
  ApiError,
  CivilizationSummary,
  MeUser,
  PersonDetail,
} from "../api/client";
import { Avatar } from "../components/Avatar";
import { refreshAuth, useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { Field } from "./CivPage";

interface SelfEditDraft {
  display_name?: string;
  bio?: string;
  civ_slug?: string;
  beat?: string;
}

export function Profile({ slug }: { slug: string }) {
  const { user } = useAuth();
  const [person, setPerson] = useState<PersonDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    setPerson(null);
    setNotFound(false);
    setEditing(false);
    api<PersonDetail>(`/people/${slug}`)
      .then(setPerson)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
      });
  }, [slug]);

  if (notFound) return <div className="ta-empty">Person not found.</div>;
  if (!person) return <div className="ta-loading">Loading profile…</div>;

  const isSelf = !!user && user.discord_username === person.discord_username;

  return (
    <>
      <div className="ta-profile-hero">
        <Avatar author={{ avatar_letter: person.name[0], avatar_color: "teal", name: person.name }} size="xl" />
        <h1 className="ta-profile-name">{person.name}</h1>
        <div className="ta-profile-meta">
          {person.role_in_civ || "—"}{person.civ_slug ? ` · ${person.civ_slug}` : ""}
        </div>
        {isSelf && !editing && (
          <div style={{ marginTop: 12 }}>
            <button
              className="ta-btn"
              onClick={() => setEditing(true)}
              style={{ padding: "5px 14px" }}
            >
              Edit Profile
            </button>
          </div>
        )}
      </div>
      <div className="ta-profile-body">
        {editing && user ? (
          <SelfEditForm
            user={user}
            person={person}
            onCancel={() => setEditing(false)}
            onSaved={(updatedPerson) => {
              setPerson(updatedPerson);
              setEditing(false);
            }}
          />
        ) : (
          <>
            {person.bio && (
              <p style={{ fontFamily: "Georgia, serif", fontSize: 15, lineHeight: 1.65 }}>
                {person.bio}
              </p>
            )}
            {!person.bio && (
              <p style={{ color: "var(--ta-text-faint)", fontSize: 13 }}>No bio yet.</p>
            )}
          </>
        )}
      </div>
    </>
  );
}

function SelfEditForm({
  user,
  person,
  onCancel,
  onSaved,
}: {
  user: MeUser;
  person: PersonDetail;
  onCancel: () => void;
  onSaved: (p: PersonDetail) => void;
}) {
  const [draft, setDraft] = useState<SelfEditDraft>({
    display_name: user.display_name,
    bio: person.bio ?? user.bio ?? "",
    civ_slug: user.civ_slug ?? "",
    beat: user.beat ?? "",
  });
  const [civs, setCivs] = useState<CivilizationSummary[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api<CivilizationSummary[]>("/civilizations", { query: { page_size: 500 } })
      .then(setCivs)
      .catch(() => setCivs([]));
  }, []);

  const set = <K extends keyof SelfEditDraft>(k: K, v: SelfEditDraft[K]) =>
    setDraft((d) => ({ ...d, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      // PATCH /auth/me — send empty strings as null so the backend can clear them
      const body = {
        display_name: draft.display_name,
        bio: draft.bio,
        civ_slug: draft.civ_slug || null,
        beat: draft.beat || null,
      };
      const env = await apiRaw<MeUser>("/auth/me", { method: "PATCH", body });
      const updated = env?.data;
      await refreshAuth();
      onSaved({
        ...person,
        name: updated?.display_name ?? person.name,
        civ_slug: updated?.civ_slug ?? person.civ_slug,
        bio: updated?.bio ?? draft.bio ?? null,
      });
      showToast("Profile saved");
    } catch (e) {
      showToast(`Save failed: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <h3 style={{ fontFamily: "Georgia, serif", fontSize: 18, margin: 0 }}>Edit profile</h3>
      <Field label="Display name">
        <input
          className="ta-form-input"
          value={draft.display_name ?? ""}
          onChange={(e) => set("display_name", e.target.value)}
        />
      </Field>
      <Field label="Civilization">
        <select
          className="ta-form-select"
          value={draft.civ_slug ?? ""}
          onChange={(e) => set("civ_slug", e.target.value)}
        >
          <option value="">— none —</option>
          {civs.map((c) => (
            <option key={c.slug} value={c.slug}>{c.name}</option>
          ))}
        </select>
      </Field>
      <Field label="Beat">
        <input
          className="ta-form-input"
          value={draft.beat ?? ""}
          onChange={(e) => set("beat", e.target.value)}
          placeholder="e.g., The Galactic Hub"
        />
      </Field>
      <Field label="Bio">
        <textarea
          className="ta-form-textarea"
          value={draft.bio ?? ""}
          onChange={(e) => set("bio", e.target.value)}
          rows={5}
          style={{ minHeight: 120 }}
        />
      </Field>
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button
          className="ta-btn ta-btn-primary"
          onClick={save}
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
