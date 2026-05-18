/**
 * Compose — small "set up new draft" form.
 *
 * Lets the author tag civs + pick a beat at creation time, then POSTs
 * to /drafts and redirects to the editor. We collect this up front so
 * the draft hits the queue with its routing metadata already in place
 * rather than relying on the author to remember to set them later.
 */

import { useEffect, useState } from "react";
import { api, ApiError, DraftDetail } from "../api/client";
import { CivPicker } from "../components/CivPicker";
import { KNOWN_BEATS } from "../components/UserSearch";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { navigate } from "../router";

interface Props {
  doctype: string;
}

const TITLES: Record<string, string> = {
  brief: "New brief",
  feature: "New feature",
  inquisition: "Begin an inquisition",
};

const BLURBS: Record<string, string> = {
  brief: "A short news item. ~150 words, single beat, one or two civs.",
  feature: "A long-form piece. Multi-section, mentions several civs, often months in the making.",
  inquisition: "A historian-led investigation. Builds over weeks with sources and evolving findings.",
};

export function Compose({ doctype }: Props) {
  const { user, loading } = useAuth();
  const [civs, setCivs] = useState<string[]>([]);
  const [beat, setBeat] = useState<string>("");
  const [headline, setHeadline] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      setErr("login required to compose a draft");
      return;
    }
    if (doctype !== "brief" && doctype !== "feature" && doctype !== "inquisition") {
      setErr(`unknown doctype: ${doctype}`);
    }
  }, [doctype, user, loading]);

  if (loading) return <div className="ta-loading">Loading…</div>;

  if (err) {
    return (
      <div className="ta-empty">
        Couldn't start a {doctype}: {err}
        <div style={{ marginTop: 12 }}>
          <a href="#/drafts" className="ta-back-link">← back to drafts</a>
        </div>
      </div>
    );
  }

  const onCreate = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      const d = await api<DraftDetail>("/drafts", {
        method: "POST",
        body: {
          doctype,
          headline: headline.trim() || null,
          beat: beat || null,
          civs,
        },
      });
      showToast("Draft created");
      navigate(`/draft/${d.id}`);
    } catch (e) {
      const msg = e instanceof ApiError ? String(e.detail) : "create failed";
      setErr(msg);
      showToast(`Compose failed: ${msg}`);
      setSubmitting(false);
    }
  };

  return (
    <div className="ta-draft-page">
      <a href="#/drafts" className="ta-back-link">← Back to drafts</a>

      <h1 style={{
        fontFamily: "Georgia, serif", fontSize: 24, fontWeight: 500,
        marginBottom: 4,
      }}>
        {TITLES[doctype] ?? `New ${doctype}`}
      </h1>
      <p style={{
        fontSize: 13, color: "var(--ta-text-dim)",
        marginBottom: 18, lineHeight: 1.5,
      }}>
        {BLURBS[doctype] ?? ""}
      </p>

      <div style={{ marginBottom: 14 }}>
        <div style={{
          fontSize: 11, color: "var(--ta-text-faint)",
          textTransform: "uppercase", letterSpacing: 0.6,
          marginBottom: 6, fontWeight: 500,
        }}>
          Working headline (optional — you can fill this in later)
        </div>
        <input
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          placeholder="Headline"
          style={{
            width: "100%",
            padding: "10px 12px",
            background: "var(--ta-surface)",
            border: "1px solid var(--ta-border)",
            borderRadius: 6,
            color: "var(--ta-text)",
            fontFamily: "Georgia, serif",
            fontSize: 18,
            outline: "none",
          }}
        />
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1fr) 220px",
        gap: 12,
        marginBottom: 18,
      }}>
        <CivPicker
          label="Tagged civilizations"
          selected={civs}
          onChange={setCivs}
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
            value={beat}
            onChange={(e) => setBeat(e.target.value)}
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

      <div style={{ display: "flex", gap: 8 }}>
        <button
          className="ta-btn ta-btn-primary"
          onClick={onCreate}
          disabled={submitting}
        >
          {submitting ? "Creating…" : `Create ${doctype}`}
        </button>
        <a href="#/drafts" className="ta-btn">Cancel</a>
      </div>
    </div>
  );
}
