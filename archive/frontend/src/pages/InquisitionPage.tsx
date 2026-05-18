/** Long-form inquisition reader with gold-tinted header. */
import { useEffect, useState } from "react";
import { api, InquisitionDetail } from "../api/client";
import { Avatar } from "../components/Avatar";
import { Loading } from "../components/Loading";

export function InquisitionPage({ id }: { id: string }) {
  const [inq, setInq] = useState<InquisitionDetail | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setInq(null);
    setNotFound(false);
    api<InquisitionDetail>(`/inquisitions/${id}`)
      .then(setInq)
      .catch(() => setNotFound(true));
  }, [id]);

  if (notFound) return <div className="ta-empty">Inquisition not found.</div>;
  if (!inq) return <Loading label="Loading inquisition…" />;

  return (
    <>
      <div className="ta-inq-reader-header">
        <div className="ta-inq-reader-numeral">{inq.numeral}</div>
        <div className="ta-inq-reader-eyebrow">Inquisition</div>
        <div className="ta-inq-reader-rule" />
        <h1 className="ta-inq-reader-title">{inq.title}</h1>
        {inq.subtitle && (
          <div className="ta-inq-reader-subtitle">{inq.subtitle}</div>
        )}
        <div style={{ display: "flex", justifyContent: "center", gap: 12, flexWrap: "wrap", marginBottom: 14 }}>
          {inq.authors.map((a) => (
            <div key={a.id} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <a href={`#/profile/${a.slug}`}><Avatar author={a} size="md" /></a>
              <div style={{ fontSize: 11, color: "#fff", fontWeight: 500 }}>{a.name}</div>
            </div>
          ))}
        </div>
        <div style={{
          display: "inline-block",
          background: "rgba(250, 199, 117, 0.15)",
          color: "var(--ta-accent-gold)",
          padding: "4px 12px",
          borderRadius: 100,
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: 1,
          fontWeight: 500,
          border: "1px solid rgba(250,199,117,0.3)",
        }}>
          {inq.state.replace("_", " ")}
          {inq.progress < 100 ? ` · ${inq.progress}%` : ""}
        </div>
      </div>

      <div className="ta-story-reader">
        <a href="#/inquisitions" className="ta-back-link">← Back to inquisitions</a>
        <Prose body={inq.body} />

        {inq.civs.length > 0 && (
          <div style={{ marginTop: 32, padding: 16, background: "var(--ta-bg)", borderRadius: 10 }}>
            <div style={{
              fontSize: 10, textTransform: "uppercase", letterSpacing: 1,
              color: "var(--ta-text-faint)", fontWeight: 500, marginBottom: 10,
            }}>
              Civilizations covered
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {inq.civs.map((c) => (
                <a key={c} href={`#/civ/${c}`} style={{
                  color: "var(--ta-accent-blue)", fontSize: 13, fontWeight: 500,
                }}>{c} →</a>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

/** Tiny markdown-ish renderer: paragraphs, **bold**, > blockquotes. */
export function Prose({ body }: { body: string }) {
  const paragraphs = body.split(/\n\n+/);
  return (
    <div className="ta-prose">
      {paragraphs.map((p, i) => {
        if (p.startsWith("> ")) {
          return <blockquote key={i}>{renderInline(p.replace(/^>\s*/, ""))}</blockquote>;
        }
        return <p key={i}>{renderInline(p)}</p>;
      })}
    </div>
  );
}

function renderInline(text: string): React.ReactNode {
  // **bold** -> <strong>
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) {
      return <strong key={i}>{p.slice(2, -2)}</strong>;
    }
    return p;
  });
}
