/**
 * Person detail — full bio + civ link.
 *
 * Historians and admins see an inline edit form (PATCH /people/{slug}).
 */

import { useEffect, useState } from "react";
import { api, ApiError, PersonDetail } from "../api/client";
import { Avatar } from "../components/Avatar";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";

export function PersonPage({ slug }: { slug: string }) {
  const { user } = useAuth();
  const [person, setPerson] = useState<PersonDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Partial<PersonDetail>>({});

  const canEdit = !!user && ((user.base_role === "historian") || user.is_admin);

  useEffect(() => {
    setPerson(null);
    setNotFound(false);
    setEditing(false);
    api<PersonDetail>(`/people/${slug}`)
      .then((p) => { setPerson(p); setDraft(p); })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
      });
  }, [slug]);

  if (notFound) return <div className="ta-empty">Person not found.</div>;
  if (!person) return <div className="ta-loading">Loading…</div>;

  // Person.id is not on the schema; we omit Watch for unknown ids.
  // (Watchlist row matching is by id; without one we'd show a button
  // that watches the wrong thing — better to hide.)
  return (
    <>
      <div className="ta-profile-hero">
        <Avatar author={{ avatar_letter: person.name[0], avatar_color: "teal", name: person.name }} size="xl" />
        <h1 className="ta-profile-name">{person.name}</h1>
        <div className="ta-profile-meta">
          {person.role_in_civ || "—"}
          {person.civ_slug ? (
            <> · <a href={`#/civ/${person.civ_slug}`} style={{ color: "inherit", textDecoration: "underline" }}>{person.civ_slug}</a></>
          ) : null}
        </div>
        {canEdit && (
          <div style={{ marginTop: 14, display: "flex", gap: 8, justifyContent: "center" }}>
            {!editing ? (
              <button className="ta-btn" onClick={() => setEditing(true)}>Edit</button>
            ) : (
              <>
                <button
                  className="ta-btn ta-btn-primary"
                  onClick={async () => {
                    try {
                      const updated = await api<PersonDetail>(`/people/${slug}`, {
                        method: "PATCH",
                        body: {
                          name: draft.name,
                          discord_username: draft.discord_username || null,
                          civ_slug: draft.civ_slug || null,
                          role_in_civ: draft.role_in_civ || null,
                          bio: draft.bio || null,
                        },
                      });
                      setPerson(updated);
                      setDraft(updated);
                      setEditing(false);
                      showToast("Saved");
                    } catch (e) {
                      showToast(e instanceof ApiError ? String(e.detail) : "Save failed");
                    }
                  }}
                >Save</button>
                <button className="ta-btn" onClick={() => { setDraft(person); setEditing(false); }}>Cancel</button>
              </>
            )}
          </div>
        )}
      </div>

      <div className="ta-profile-body">
        {editing ? (
          <EditForm draft={draft} onChange={setDraft} />
        ) : (
          <>
            {person.bio ? (
              <p style={{ fontFamily: "Georgia, serif", fontSize: 15, lineHeight: 1.65 }}>
                {person.bio}
              </p>
            ) : (
              <p style={{ color: "var(--ta-text-faint)", fontSize: 13 }}>No bio yet.</p>
            )}
          </>
        )}

        {!editing && (
          <div style={{ marginTop: 24 }}>
            <a href="#/people" className="ta-back-link">← all people</a>
          </div>
        )}
      </div>
    </>
  );
}

function EditForm({ draft, onChange }: {
  draft: Partial<PersonDetail>;
  onChange: (next: Partial<PersonDetail>) => void;
}) {
  return (
    <div>
      <Row label="Name">
        <input className="ta-form-input" value={draft.name ?? ""}
               onChange={(e) => onChange({ ...draft, name: e.target.value })}/>
      </Row>
      <Row label="Discord username">
        <input className="ta-form-input" value={draft.discord_username ?? ""}
               onChange={(e) => onChange({ ...draft, discord_username: e.target.value })}/>
      </Row>
      <Row label="Civilization slug">
        <input className="ta-form-input" value={draft.civ_slug ?? ""}
               onChange={(e) => onChange({ ...draft, civ_slug: e.target.value })}/>
      </Row>
      <Row label="Role in civ">
        <input className="ta-form-input" value={draft.role_in_civ ?? ""}
               onChange={(e) => onChange({ ...draft, role_in_civ: e.target.value })}/>
      </Row>
      <Row label="Bio">
        <textarea className="ta-form-textarea" value={draft.bio ?? ""}
               onChange={(e) => onChange({ ...draft, bio: e.target.value })}/>
      </Row>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="ta-form-row">
      <label className="ta-form-label">{label}</label>
      {children}
    </div>
  );
}
