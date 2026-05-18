/** Place detail with historian/admin edit. */
import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";

interface PlaceDetail {
  slug: string;
  name: string;
  galaxy?: string | null;
  region?: string | null;
  coordinates?: string | null;
  description?: string | null;
}

export function PlacePage({ slug }: { slug: string }) {
  const { user } = useAuth();
  const [place, setPlace] = useState<PlaceDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<PlaceDetail | null>(null);

  const canEdit = !!user && (user.base_role === "historian" || user.is_admin);

  useEffect(() => {
    setPlace(null); setNotFound(false); setEditing(false);
    api<PlaceDetail>(`/places/${slug}`)
      .then((p) => { setPlace(p); setDraft(p); })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
      });
  }, [slug]);

  if (notFound) return <div className="ta-empty">Place not found.</div>;
  if (!place) return <div className="ta-loading">Loading…</div>;

  const save = async () => {
    if (!draft) return;
    try {
      const updated = await api<PlaceDetail>(`/places/${slug}`, {
        method: "PATCH",
        body: {
          name: draft.name,
          galaxy: draft.galaxy || null,
          region: draft.region || null,
          coordinates: draft.coordinates || null,
          description: draft.description || null,
        },
      });
      setPlace(updated); setDraft(updated); setEditing(false);
      showToast("Saved");
    } catch (e) {
      showToast(e instanceof ApiError ? String(e.detail) : "Save failed");
    }
  };

  return (
    <div className="ta-story-reader">
      <a href="#/places" className="ta-back-link">← all places</a>
      <div style={{
        fontSize: 11, textTransform: "uppercase", letterSpacing: 1,
        color: "var(--ta-text-faint)", marginBottom: 4,
      }}>
        Place {place.galaxy ? `· ${place.galaxy}` : ""}
      </div>

      {editing && draft ? (
        <>
          <input className="ta-form-input" style={{ fontSize: 22, marginBottom: 8 }}
                 value={draft.name}
                 onChange={(e) => setDraft({ ...draft, name: e.target.value })}/>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <input className="ta-form-input" placeholder="galaxy" value={draft.galaxy ?? ""}
                   onChange={(e) => setDraft({ ...draft, galaxy: e.target.value })}/>
            <input className="ta-form-input" placeholder="region" value={draft.region ?? ""}
                   onChange={(e) => setDraft({ ...draft, region: e.target.value })}/>
          </div>
          <input className="ta-form-input" placeholder="coordinates / glyphs"
                 style={{ marginBottom: 12 }}
                 value={draft.coordinates ?? ""}
                 onChange={(e) => setDraft({ ...draft, coordinates: e.target.value })}/>
          <textarea className="ta-form-textarea" value={draft.description ?? ""}
                    onChange={(e) => setDraft({ ...draft, description: e.target.value })}/>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button className="ta-btn ta-btn-primary" onClick={save}>Save</button>
            <button className="ta-btn" onClick={() => { setDraft(place); setEditing(false); }}>Cancel</button>
          </div>
        </>
      ) : (
        <>
          <h1>{place.name}</h1>
          <div style={{ color: "var(--ta-text-dim)", marginBottom: 16, fontStyle: "italic" }}>
            {place.region ? `${place.region} · ` : ""}{place.coordinates ?? "—"}
          </div>
          {place.description ? (
            <p style={{ fontFamily: "Georgia, serif", fontSize: 16, lineHeight: 1.65 }}>
              {place.description}
            </p>
          ) : (
            <p style={{ color: "var(--ta-text-faint)" }}>No description yet.</p>
          )}
          {canEdit && (
            <div style={{ marginTop: 16 }}>
              <button className="ta-btn" onClick={() => setEditing(true)}>Edit</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
