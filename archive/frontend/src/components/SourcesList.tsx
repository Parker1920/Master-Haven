/**
 * SourcesList — render and (optionally) edit citations on a target.
 *
 * Mounted on InquisitionPage and any encyclopedia detail page that
 * wants to show sources. Read-only for everyone by default; if the
 * caller passes canEdit, we also render an add-source mini form
 * (which lets the user create a new source + attach it in one shot).
 */

import { useEffect, useState } from "react";
import { api, apiRaw, ApiError, SourceCitation, SourceQuality, SourceType } from "../api/client";
import { showToast } from "../hooks/useToast";

interface Props {
  targetType: "inquisition" | "civilization" | "person" | "event" | "place";
  targetId: number;
  canEdit?: boolean;
}

const SOURCE_TYPES: SourceType[] = ["discord", "reddit", "forum", "wiki", "video", "screenshot", "interview", "other"];
const QUALITIES: SourceQuality[] = ["primary", "secondary", "community", "rotted"];

export function SourcesList({ targetType, targetId, canEdit = false }: Props) {
  const [items, setItems] = useState<SourceCitation[] | null>(null);
  const [adding, setAdding] = useState(false);

  const reload = async () => {
    try {
      const data = await api<SourceCitation[]>(`/sources/for/${targetType}/${targetId}`);
      setItems(data);
    } catch {
      setItems([]);
    }
  };

  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [targetType, targetId]);

  const remove = async (citationId: number) => {
    try {
      await apiRaw(`/sources/citations/${citationId}`, { method: "DELETE" });
      setItems((cur) => (cur ?? []).filter((c) => c.id !== citationId));
      showToast("Removed");
    } catch {
      showToast("Remove failed");
    }
  };

  if (items === null) return <div className="ta-loading" style={{ padding: 12 }}>Loading sources…</div>;

  return (
    <div className="ta-sources-panel">
      <div className="ta-sources-panel-head">
        <div className="ta-sources-panel-title">
          Sources <span className="ta-sources-panel-count">{items.length}</span>
        </div>
        {canEdit && !adding && (
          <button className="ta-btn" onClick={() => setAdding(true)}
                  style={{ padding: "4px 12px", fontSize: 11 }}>+ Add source</button>
        )}
      </div>

      {adding && canEdit && (
        <AddSourceForm
          onAdded={() => { setAdding(false); reload(); }}
          onCancel={() => setAdding(false)}
          targetType={targetType}
          targetId={targetId}
        />
      )}

      {items.length === 0 && !adding && (
        <div style={{ color: "var(--ta-text-faint)", fontSize: 13, padding: "10px 0" }}>
          No sources cited yet.
        </div>
      )}

      {items.map((c) => (
        <div key={c.id} className="ta-source-row">
          <div className="ta-source-row-head">
            <span className={`ta-source-quality ta-source-quality-${c.source.quality}`}>
              {c.source.quality}
            </span>
            <span className="ta-source-type">{c.source.source_type}</span>
            <div className="ta-source-title">
              {c.source.url ? (
                <a href={c.source.url} target="_blank" rel="noreferrer">{c.source.title}</a>
              ) : c.source.title}
            </div>
            {canEdit && (
              <button className="ta-btn" onClick={() => remove(c.id)}
                      style={{ padding: "2px 8px", fontSize: 11 }}>×</button>
            )}
          </div>
          {c.note && <div className="ta-source-note">{c.note}</div>}
          {c.source.notes && <div className="ta-source-meta">{c.source.notes}</div>}
        </div>
      ))}
    </div>
  );
}

function AddSourceForm({ onAdded, onCancel, targetType, targetId }: {
  onAdded: () => void;
  onCancel: () => void;
  targetType: Props["targetType"];
  targetId: number;
}) {
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("other");
  const [quality, setQuality] = useState<SourceQuality>("community");
  const [notes, setNotes] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!title.trim()) return;
    setBusy(true);
    try {
      const src = await api<{ id: number }>("/sources", {
        method: "POST",
        body: {
          title: title.trim(),
          url: url.trim() || null,
          source_type: sourceType,
          quality,
          notes: notes.trim() || null,
        },
      });
      await api(`/sources/citations`, {
        method: "POST",
        body: {
          source_id: src.id,
          target_type: targetType,
          target_id: targetId,
          note: note.trim() || null,
        },
      });
      showToast("Source added");
      onAdded();
    } catch (e) {
      showToast(e instanceof ApiError ? String(e.detail) : "Add failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ta-add-source-form">
      <div className="ta-form-row">
        <label className="ta-form-label">Title</label>
        <input className="ta-form-input" value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="ta-form-row">
        <label className="ta-form-label">URL (optional)</label>
        <input className="ta-form-input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <div className="ta-form-row" style={{ flex: 1 }}>
          <label className="ta-form-label">Type</label>
          <select className="ta-form-select" value={sourceType}
                  onChange={(e) => setSourceType(e.target.value as SourceType)}>
            {SOURCE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="ta-form-row" style={{ flex: 1 }}>
          <label className="ta-form-label">Quality</label>
          <select className="ta-form-select" value={quality}
                  onChange={(e) => setQuality(e.target.value as SourceQuality)}>
            {QUALITIES.map((q) => <option key={q} value={q}>{q}</option>)}
          </select>
        </div>
      </div>
      <div className="ta-form-row">
        <label className="ta-form-label">Notes about the source (optional)</label>
        <input className="ta-form-input" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
      <div className="ta-form-row">
        <label className="ta-form-label">Which claim does this support? (optional)</label>
        <input className="ta-form-input" value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="ta-btn ta-btn-primary" onClick={submit} disabled={busy || !title.trim()}>
          {busy ? "…" : "Add"}
        </button>
        <button className="ta-btn" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
    </div>
  );
}
