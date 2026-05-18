/**
 * Draft editor + reviewer view.
 *
 * - Authors / co-authors get editable headline+deck+body with 800ms
 *   debounced auto-save (PATCH /drafts/{id})
 * - Anyone with a team role can read + comment
 * - Editors see Return / Mark Ready buttons when status=in_review
 * - Authors see Submit (draft/returned) and Publish (ready) buttons
 *
 * Phase 5b: inline comment quoting.
 *   - Select text in the body (works in both edit textarea and
 *     read-only rendered body)
 *   - A hint banner above the comment composer shows the attached quote
 *   - Post comment with the quote → server stores it as quoted_text
 *   - Existing comments with quoted_text get their span highlighted
 *     in the rendered body
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  apiRaw,
  ApiError,
  CommentDetail,
  DraftDetail,
} from "../api/client";
import { Avatar } from "../components/Avatar";
import { CivPicker } from "../components/CivPicker";
import { StatusPill } from "../components/StatusPill";
import { KNOWN_BEATS, UserSearch } from "../components/UserSearch";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { navigate } from "../router";

interface Props {
  id: string;
}

export function Draft({ id }: Props) {
  const { user } = useAuth();
  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [comments, setComments] = useState<CommentDetail[]>([]);
  const [notFound, setNotFound] = useState(false);
  const [savedAt, setSavedAt] = useState<string>("");
  const [commentBody, setCommentBody] = useState("");
  const [pendingQuote, setPendingQuote] = useState<string | null>(null);
  const saveTimer = useRef<number | null>(null);
  const bodyRef = useRef<HTMLTextAreaElement | null>(null);
  const readonlyBodyRef = useRef<HTMLDivElement | null>(null);

  const reload = useCallback(async () => {
    try {
      const d = await api<DraftDetail>(`/drafts/${id}`);
      setDraft(d);
      const c = await api<CommentDetail[]>(`/drafts/${id}/comments`);
      setComments(c);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 401 || e.status === 403)) {
        setNotFound(true);
      }
    }
  }, [id]);

  useEffect(() => { reload(); }, [reload]);

  // Selection capture — works in both the textarea (edit mode) and
  // the read-only rendered body. Captured only when the selection is
  // non-empty and inside one of those two regions.
  const captureSelection = useCallback(() => {
    // Edit-mode textarea selection
    const ta = bodyRef.current;
    if (ta && document.activeElement === ta) {
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      if (end > start) {
        const text = ta.value.substring(start, end).trim();
        if (text && text.length >= 3) {
          setPendingQuote(text);
        }
        return;
      }
    }
    // Read-only body selection
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0) {
      const range = sel.getRangeAt(0);
      const text = sel.toString().trim();
      if (
        text &&
        text.length >= 3 &&
        readonlyBodyRef.current &&
        readonlyBodyRef.current.contains(range.commonAncestorContainer)
      ) {
        setPendingQuote(text);
      }
    }
  }, []);

  useEffect(() => {
    document.addEventListener("mouseup", captureSelection);
    document.addEventListener("keyup", captureSelection);
    return () => {
      document.removeEventListener("mouseup", captureSelection);
      document.removeEventListener("keyup", captureSelection);
    };
  }, [captureSelection]);

  if (notFound) return <div className="ta-empty">Draft not found, or you don't have access.</div>;
  if (!user) return <div className="ta-empty">Log in to view drafts.</div>;
  if (!draft) return <div className="ta-loading">Loading draft…</div>;

  const isAuthor = draft.author.id === user.id;
  const isCoauthor = draft.coauthors.some((c) => c.user_id === user.id);
  const canEdit = isAuthor || isCoauthor;
  const isEditor = user.is_editor || user.is_admin;
  const isPublished = draft.status === "published";

  // Auto-save on field change (800ms debounce)
  const scheduleSave = (patch: Record<string, unknown>) => {
    if (!canEdit || isPublished) return;
    if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(async () => {
      try {
        const updated = await api<DraftDetail>(`/drafts/${id}`, { method: "PATCH", body: patch });
        setDraft(updated);
        setSavedAt("just now");
      } catch {
        showToast("Auto-save failed");
      }
    }, 800);
  };

  const transition = async (path: string, label: string) => {
    try {
      const updated = await apiRaw<DraftDetail>(`/drafts/${id}/${path}`, { method: "POST" });
      if (updated?.data) setDraft(updated.data);
      showToast(label);
      if (path === "publish" && updated?.data) {
        if (updated.data.published_as_story_id) {
          navigate(`/story/${updated.data.published_as_story_id}`);
        } else if (updated.data.published_as_inquisition_id) {
          navigate(`/inquisition/${updated.data.published_as_inquisition_id}`);
        }
      }
    } catch (e) {
      if (e instanceof ApiError) showToast(`${label} failed: ${e.detail}`);
      else showToast(`${label} failed`);
    }
  };

  const addCoauthor = async (userId: number, name: string) => {
    try {
      await apiRaw(`/drafts/${id}/coauthors`, {
        method: "POST",
        body: { user_id: userId },
      });
      showToast(`Added ${name} as co-author`);
      await reload();
    } catch (e) {
      if (e instanceof ApiError) showToast(`Add failed: ${e.detail}`);
      else showToast("Add failed");
    }
  };

  const removeCoauthor = async (userId: number, name: string) => {
    if (!window.confirm(`Remove ${name} as a co-author?`)) return;
    try {
      await apiRaw(`/drafts/${id}/coauthors/${userId}`, { method: "DELETE" });
      showToast(`Removed ${name}`);
      await reload();
    } catch (e) {
      if (e instanceof ApiError) showToast(`Remove failed: ${e.detail}`);
      else showToast("Remove failed");
    }
  };

  const deleteDraft = async () => {
    if (!window.confirm(
      "Delete this draft? Drafts that have been submitted, marked ready, or published cannot be deleted."
    )) return;
    try {
      await apiRaw(`/drafts/${id}`, { method: "DELETE" });
      showToast("Draft deleted");
      navigate("/drafts");
    } catch (e) {
      if (e instanceof ApiError) showToast(`Delete failed: ${e.detail}`);
      else showToast("Delete failed");
    }
  };

  const postComment = async () => {
    const body = commentBody.trim();
    if (!body) return;
    try {
      const env = await apiRaw<CommentDetail>(
        `/drafts/${id}/comments`,
        {
          method: "POST",
          body: pendingQuote
            ? { body, quoted_text: pendingQuote }
            : { body },
        },
      );
      if (env?.data) setComments((prev) => [...prev, env.data]);
      setCommentBody("");
      setPendingQuote(null);
      showToast("Comment posted");
    } catch {
      showToast("Comment failed");
    }
  };

  return (
    <div className="ta-draft-page">
      <a href="#/drafts" className="ta-back-link">← Back to drafts</a>

      {!canEdit && (
        <div style={{
          background: "var(--ta-surface)",
          borderLeft: "3px solid var(--ta-accent-blue)",
          padding: "10px 14px",
          borderRadius: "0 6px 6px 0",
          fontSize: 12, color: "var(--ta-text-dim)",
          marginBottom: 14, lineHeight: 1.45,
        }}>
          <b>Read-only.</b> You're viewing as a team member. You can leave
          comments. Edit access is held by {draft.author.name}
          {draft.coauthors.length > 0 ? " and co-authors" : ""}.
        </div>
      )}

      <div className="ta-draft-status-strip">
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <StatusPill status={draft.status} />
          {canEdit && savedAt && (
            <span className="ta-draft-saved">Saved {savedAt}</span>
          )}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {canEdit && (draft.status === "draft" || draft.status === "returned") && (
            <button className="ta-btn" onClick={() => transition("submit", "Submitted for review")}>
              {draft.status === "returned" ? "Resubmit" : "Submit for review"}
            </button>
          )}
          {isEditor && draft.status === "in_review" && (
            <>
              <button className="ta-btn ta-btn-warn" onClick={() => transition("return", "Returned to author")}>
                Return with notes
              </button>
              <button className="ta-btn ta-btn-primary" onClick={() => transition("mark_ready", "Marked ready")}>
                Mark ready
              </button>
            </>
          )}
          {canEdit && draft.status === "ready" && (
            <button className="ta-btn ta-btn-publish" onClick={() => transition("publish", "Published")}>
              Publish now
            </button>
          )}
          {isAuthor && (draft.status === "draft" || draft.status === "returned") && (
            <button
              className="ta-btn ta-btn-warn"
              onClick={deleteDraft}
              title="Delete this draft"
            >
              Delete
            </button>
          )}
        </div>
      </div>

      <div className="ta-story-tags" style={{ margin: "0 0 12px" }}>
        <span className={`ta-doctype ta-doctype-${draft.doctype}`}>{draft.doctype}</span>
        {draft.numeral && (
          <span style={{ fontSize: 11, color: "var(--ta-text-faint)", marginLeft: 8 }}>
            Inquisition {draft.numeral}
          </span>
        )}
      </div>

      {canEdit ? (
        <>
          <div style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1fr) 220px",
            gap: 12,
            marginBottom: 12,
          }}>
            <CivPicker
              label="Tagged civilizations"
              selected={draft.civs}
              onChange={(civs) => {
                setDraft({ ...draft, civs });
                scheduleSave({ civs });
              }}
              disabled={isPublished}
            />
            <div>
              <div style={{
                fontSize: 11, color: "var(--ta-text-faint)",
                textTransform: "uppercase", letterSpacing: 0.6,
                marginBottom: 6, fontWeight: 500,
              }}>
                Beat
              </div>
              <select
                defaultValue={draft.beat ?? ""}
                onChange={(e) => scheduleSave({ beat: e.target.value || null })}
                disabled={isPublished}
                style={{
                  width: "100%", height: 38,
                  padding: "8px 10px",
                  background: "var(--ta-surface)",
                  border: "1px solid var(--ta-border)",
                  borderRadius: 6,
                  color: "var(--ta-text)", fontSize: 13,
                  outline: "none",
                }}
              >
                <option value="">— no beat —</option>
                {KNOWN_BEATS.map((b) => (
                  <option key={b} value={b}>{b}</option>
                ))}
              </select>
            </div>
          </div>
          <input
            className="ta-draft-editor-headline"
            placeholder="Headline"
            defaultValue={draft.headline ?? ""}
            onChange={(e) => scheduleSave({ headline: e.target.value })}
          />
          <input
            className="ta-draft-editor-deck"
            placeholder="Deck (subtitle)"
            defaultValue={draft.deck ?? ""}
            onChange={(e) => scheduleSave({ deck: e.target.value })}
          />
          <textarea
            ref={bodyRef}
            className="ta-draft-editor-body"
            placeholder="Body…"
            defaultValue={draft.body ?? ""}
            onChange={(e) => scheduleSave({ body: e.target.value })}
          />
        </>
      ) : (
        <>
          <h1 style={{
            fontFamily: "Georgia, serif", fontSize: 22, fontWeight: 500,
            lineHeight: 1.25, marginBottom: 8,
          }}>
            {draft.headline || <span style={{ color: "var(--ta-text-faint)", fontStyle: "italic" }}>Untitled draft</span>}
          </h1>
          {draft.deck && (
            <p style={{
              fontFamily: "Georgia, serif", fontStyle: "italic",
              color: "var(--ta-text-dim)", marginBottom: 12,
            }}>{draft.deck}</p>
          )}
          <div
            ref={readonlyBodyRef}
            style={{
              fontFamily: "Georgia, serif", fontSize: 16, lineHeight: 1.65,
              color: "var(--ta-text)", padding: "8px 0",
            }}
          >
            {renderBodyWithQuoteHighlights(draft.body, comments)}
          </div>
        </>
      )}

      <div className="ta-draft-authors">
        <div className="ta-draft-authors-label">Author + co-authors</div>
        <div className="ta-draft-authors-list">
          <a href={`#/profile/${draft.author.slug}`} className="ta-draft-author-chip ta-draft-author-chip-primary">
            <Avatar author={draft.author} />
            <span>{draft.author.name}</span>
          </a>
          {draft.coauthors.map((c) => (
            <span
              key={c.user_id}
              className="ta-draft-author-chip"
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <a
                href={`#/profile/${c.slug}`}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  color: "inherit", textDecoration: "none",
                }}
              >
                <Avatar author={c} />
                <span>{c.name}</span>
              </a>
              {canEdit && !isPublished && (
                <button
                  type="button"
                  onClick={() => removeCoauthor(c.user_id, c.name)}
                  title={`Remove ${c.name}`}
                  style={{
                    background: "transparent", border: "none",
                    color: "var(--ta-text-dim)", cursor: "pointer",
                    fontSize: 14, lineHeight: 1, padding: "0 2px",
                    marginLeft: 2,
                  }}
                >×</button>
              )}
            </span>
          ))}
        </div>
        {canEdit && !isPublished && (
          <div style={{ marginTop: 10, maxWidth: 360 }}>
            <UserSearch
              placeholder="Add co-author by name or @username…"
              excludeUserIds={[
                draft.author.id,
                ...draft.coauthors.map((c) => c.user_id),
              ]}
              onSelect={addCoauthor}
            />
          </div>
        )}
      </div>

      <div className="ta-draft-comments">
        <div className="ta-draft-comments-title">Comments ({comments.length})</div>
        {comments.length === 0 ? (
          <div style={{ padding: "14px 0", color: "var(--ta-text-faint)", fontSize: 13, fontStyle: "italic" }}>
            No comments yet. Be the first to leave one.
          </div>
        ) : (
          comments.map((c) => (
            <div key={c.id} className="ta-draft-comment">
              <div className="ta-draft-comment-head">
                <Avatar author={c.author} />
                <span className="ta-draft-comment-author">{c.author.name}</span>
                <span className="ta-draft-comment-time">{new Date(c.created_at).toLocaleString()}</span>
              </div>
              {c.quoted_text && (
                <div className="ta-draft-comment-quote">"{c.quoted_text}"</div>
              )}
              <div className="ta-draft-comment-text">{c.body}</div>
            </div>
          ))
        )}

        <div className="ta-draft-comment-form">
          <div style={{
            fontSize: 11, color: "var(--ta-text-faint)",
            textTransform: "uppercase", letterSpacing: 0.6,
            marginBottom: 6, fontWeight: 500,
          }}>
            Leave a comment
          </div>

          {pendingQuote && (
            <div className="ta-quote-hint">
              <span>
                <b>Attaching to:</b> "{
                  pendingQuote.length > 80
                    ? pendingQuote.slice(0, 77) + "…"
                    : pendingQuote
                }"
              </span>
              <button
                className="ta-quote-hint-clear"
                onClick={() => setPendingQuote(null)}
                title="Clear attached quote"
              >×</button>
            </div>
          )}

          <textarea
            value={commentBody}
            onChange={(e) => setCommentBody(e.target.value)}
            placeholder={
              pendingQuote
                ? "Comment on the highlighted text… use @username to ping someone."
                : "Add a note. Select text in the body to attach a quote, or use @username to ping someone."
            }
          />
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
            <button className="ta-btn ta-btn-primary" onClick={postComment}>
              Post comment
            </button>
            <span style={{ fontSize: 11, color: "var(--ta-text-faint)" }}>
              Visible to all team members
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Render the draft body, wrapping any text that matches an existing
 * comment's quoted_text in a highlighted span. Simple literal-match;
 * cheap and good enough for the typical 1-3 quotes per draft we see.
 *
 * Returns an array of React nodes (text + <span> elements). Preserves
 * paragraph breaks via splitting on \n\n.
 */
function renderBodyWithQuoteHighlights(body: string, comments: CommentDetail[]): React.ReactNode {
  const quotes = comments
    .map((c) => c.quoted_text)
    .filter((q): q is string => typeof q === "string" && q.length > 0)
    // Sort longest first so a longer quote doesn't get pre-empted by
    // a shorter substring of itself
    .sort((a, b) => b.length - a.length);

  const paragraphs = body.split(/\n\n+/);
  return paragraphs.map((p, i) => (
    <p key={i} style={{ marginBottom: 14 }}>
      {wrapQuotes(p, quotes)}
    </p>
  ));
}

function wrapQuotes(text: string, quotes: string[]): React.ReactNode {
  if (quotes.length === 0) return text;
  // Walk the text and split on the first matching quote. Recurse on
  // the leading + trailing slices so multiple quotes in one paragraph
  // each get wrapped.
  for (const q of quotes) {
    const idx = text.indexOf(q);
    if (idx >= 0) {
      const before = text.slice(0, idx);
      const after = text.slice(idx + q.length);
      return (
        <>
          {wrapQuotes(before, quotes)}
          <span className="ta-quoted-span" title="A comment is attached to this text">{q}</span>
          {wrapQuotes(after, quotes)}
        </>
      );
    }
  }
  return text;
}
