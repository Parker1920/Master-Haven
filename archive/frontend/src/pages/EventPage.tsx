/** Event detail page with historian/admin edit. */
import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";

interface EventDetail {
  slug: string;
  title: string;
  event_date?: string | null;
  event_year?: number | null;
  description?: string | null;
}

export function EventPage({ slug }: { slug: string }) {
  const { user } = useAuth();
  const [event, setEvent] = useState<EventDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<EventDetail | null>(null);

  const canEdit = !!user && (user.base_role === "historian" || user.is_admin);

  useEffect(() => {
    setEvent(null); setNotFound(false); setEditing(false);
    api<EventDetail>(`/events/${slug}`)
      .then((e) => { setEvent(e); setDraft(e); })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
      });
  }, [slug]);

  if (notFound) return <div className="ta-empty">Event not found.</div>;
  if (!event) return <div className="ta-loading">Loading…</div>;

  const save = async () => {
    if (!draft) return;
    try {
      const updated = await api<EventDetail>(`/events/${slug}`, {
        method: "PATCH",
        body: {
          title: draft.title,
          event_date: draft.event_date || null,
          event_year: draft.event_year ?? null,
          description: draft.description || null,
        },
      });
      setEvent(updated);
      setDraft(updated);
      setEditing(false);
      showToast("Saved");
    } catch (e) {
      showToast(e instanceof ApiError ? String(e.detail) : "Save failed");
    }
  };

  return (
    <div className="ta-story-reader">
      <a href="#/events" className="ta-back-link">← all events</a>
      <div style={{
        fontSize: 11, textTransform: "uppercase", letterSpacing: 1,
        color: "var(--ta-text-faint)", marginBottom: 4,
      }}>
        Event · {event.event_year ?? "year unknown"}
      </div>

      {editing && draft ? (
        <>
          <input className="ta-form-input" style={{ fontSize: 22, marginBottom: 8 }}
                 value={draft.title}
                 onChange={(e) => setDraft({ ...draft, title: e.target.value })}/>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <input className="ta-form-input" placeholder="display date (free-form)"
                   value={draft.event_date ?? ""}
                   onChange={(e) => setDraft({ ...draft, event_date: e.target.value })}/>
            <input className="ta-form-input" type="number" placeholder="year"
                   value={draft.event_year ?? ""}
                   onChange={(e) => setDraft({ ...draft, event_year: e.target.value ? parseInt(e.target.value, 10) : null })}/>
          </div>
          <textarea className="ta-form-textarea" value={draft.description ?? ""}
                    onChange={(e) => setDraft({ ...draft, description: e.target.value })}/>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button className="ta-btn ta-btn-primary" onClick={save}>Save</button>
            <button className="ta-btn" onClick={() => { setDraft(event); setEditing(false); }}>Cancel</button>
          </div>
        </>
      ) : (
        <>
          <h1>{event.title}</h1>
          {event.event_date && (
            <div style={{ color: "var(--ta-text-dim)", marginBottom: 16, fontStyle: "italic" }}>
              {event.event_date}
            </div>
          )}
          {event.description ? (
            <p style={{ fontFamily: "Georgia, serif", fontSize: 16, lineHeight: 1.65 }}>
              {event.description}
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
