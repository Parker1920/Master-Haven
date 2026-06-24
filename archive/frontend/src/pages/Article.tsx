/**
 * Article — the catalogue reader.
 *
 * Renders the title/subtitle/body (light markdown) with a tabbed
 * Overview / Sources infobox + source-quality badges, exactly like the
 * v0.3 design. Team members (diplomat+) get an inline edit form; admins
 * can delete.
 */

import { useEffect, useState } from "react";
import { api, apiRaw, ApiError, ArticleDetail, ArticlePatch, FacetDef, FacetSchema } from "../api/client";
import { NS_BY_KEY } from "../data/namespaces";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { navigate } from "../router";
import { Loading } from "../components/Loading";
import { ArticleForm, ArticleDraft } from "../components/ArticleForm";

export function Article({ slug }: { slug: string }) {
  const { user } = useAuth();
  const [art, setArt] = useState<ArticleDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState<"overview" | "sources">("overview");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [facetDefs, setFacetDefs] = useState<FacetDef[]>([]);

  const canEdit = !!user && (user.base_role !== "reader" || user.is_admin);

  useEffect(() => {
    setArt(null);
    setNotFound(false);
    setEditing(false);
    api<ArticleDetail>(`/articles/${slug}`)
      .then((a) => {
        setArt(a);
        setTab(a.infobox.length === 0 && a.sources.length > 0 ? "sources" : "overview");
      })
      .catch(() => setNotFound(true));
  }, [slug]);

  useEffect(() => {
    if (!art) return;
    let alive = true;
    api<FacetSchema>(`/articles/facets/${art.namespace}`)
      .then((s) => { if (alive) setFacetDefs(s.facets); })
      .catch(() => { /* facets optional for display */ });
    return () => { alive = false; };
  }, [art?.namespace]);

  if (notFound) {
    return (
      <div className="ta-empty">
        Article not found. <a className="ta-cat-link" href="#/catalogue">Back to the catalogue</a>
      </div>
    );
  }
  if (!art) return <Loading label="Loading…" />;

  const def = NS_BY_KEY[art.namespace];
  const accent = def?.accent ?? "#00C2B3";

  const facetRows = facetDefs
    .filter((fd) => (art.facets[fd.key] ?? []).length > 0)
    .map((fd) => ({
      label: fd.label,
      value: fd.control === "boolean" ? "Yes" : (art.facets[fd.key] ?? []).join(", "),
    }));
  // Freeform infobox shows only what the structured facets don't already cover.
  const facetLabelSet = new Set(facetRows.map((r) => r.label.toLowerCase()));
  const extraInfobox = art.infobox.filter((r) => !facetLabelSet.has(r.label.toLowerCase()));

  const save = async (d: ArticleDraft) => {
    setSaving(true);
    try {
      const patch: ArticlePatch = {
        namespace: d.namespace,
        title: d.title,
        subtitle: d.subtitle || null,
        civ_slug: d.civ_slug || null,
        body: d.body,
        infobox: d.infobox,
        sources: d.sources,
        facets: d.facets,
      };
      const updated = await api<ArticleDetail>(`/articles/${slug}`, { method: "PATCH", body: patch });
      setArt(updated);
      setEditing(false);
      showToast("Saved");
    } catch (e) {
      showToast(e instanceof ApiError ? String(e.detail) : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async () => {
    try {
      await apiRaw(`/articles/${slug}`, { method: "DELETE" });
      showToast(`${art.title} deleted`);
      navigate(def ? def.href.replace(/^#/, "") : "/catalogue");
    } catch (e) {
      showToast(e instanceof ApiError ? String(e.detail) : "Delete failed");
    }
  };

  if (editing) {
    return (
      <div className="ta-cat-form">
        <h2>Edit page</h2>
        <p className="lead">The slug and category stay fixed; everything else is editable.</p>
        <ArticleForm
          mode="edit"
          submitting={saving}
          initial={{
            namespace: art.namespace, slug: art.slug, title: art.title,
            subtitle: art.subtitle ?? "", civ_slug: art.civ_slug ?? "",
            body: art.body ?? "", infobox: art.infobox, sources: art.sources,
            facets: art.facets,
          }}
          onSubmit={save}
          onCancel={() => setEditing(false)}
        />
      </div>
    );
  }

  return (
    <div className="ta-cat-article-layout" style={{ "--cat-accent": accent } as React.CSSProperties}>
      <main>
        <div className="ta-cat-breadcrumb">
          <a className="ta-cat-link" href="#/catalogue">Catalogue</a> ›{" "}
          {def ? <a className="ta-cat-link" href={def.href}>{def.label}</a> : art.namespace}
        </div>
        <div className="ta-cat-eyebrow"><span className="dot" /> {def?.label ?? art.namespace}</div>
        <h1 className="ta-cat-title">{art.title}</h1>
        {art.subtitle && <div className="ta-cat-subtitle">{art.subtitle}</div>}
        <div className="ta-cat-meta">
          {art.editor && <span>By <a href={`#/profile/${art.editor.slug}`}><b>{art.editor.name}</b></a></span>}
          {art.civ_slug && <span>· <a href={`#/civ/${art.civ_slug}`}>{art.civ_slug}</a></span>}
          {canEdit && (
            <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
              <button className="ta-cat-mini-btn" onClick={() => setEditing(true)}>✎ Edit</button>
              {user?.is_admin && <button className="ta-cat-mini-btn" onClick={() => setConfirmDelete(true)}>Delete</button>}
            </span>
          )}
        </div>

        {art.body.trim() ? (
          <div className="ta-cat-body"><MarkdownLite text={art.body} /></div>
        ) : (
          <p style={{ color: "var(--ta-text-faint)", fontSize: 13 }}>
            No body yet.{canEdit && <> <span className="ta-cat-link" style={{ cursor: "pointer" }} onClick={() => setEditing(true)}>Write the first version →</span></>}
          </p>
        )}
      </main>

      <aside>
        <div className="ta-cat-infobox">
          <div className="ta-cat-infobox-head">
            <div className="ta-cat-infobox-glyph">{def?.glyph ?? "✦"}</div>
            <div className="ta-cat-infobox-name">{art.title}</div>
          </div>
          <div className="ta-cat-ib-tabs">
            <button className={`ta-cat-ib-tab${tab === "overview" ? " active" : ""}`} onClick={() => setTab("overview")}>Overview</button>
            <button className={`ta-cat-ib-tab${tab === "sources" ? " active" : ""}`} onClick={() => setTab("sources")}>Sources</button>
          </div>
          {tab === "overview" ? (
            <div className="ta-cat-ib-panel">
              {facetRows.length === 0 && extraInfobox.length === 0 ? (
                <div className="ta-cat-ib-empty">No overview facts yet.</div>
              ) : (
                <>
                  {facetRows.map((r, i) => (
                    <div className="ta-cat-ib-row" key={`f${i}`}>
                      <span className="ta-cat-ib-k">{r.label}</span>
                      <span className="ta-cat-ib-v">{r.value}</span>
                    </div>
                  ))}
                  {extraInfobox.map((r, i) => (
                    <div className="ta-cat-ib-row" key={`i${i}`}>
                      <span className="ta-cat-ib-k">{r.label}</span>
                      <span className="ta-cat-ib-v">{r.value}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          ) : (
            <div className="ta-cat-ib-panel">
              {art.sources.length === 0 ? (
                <div className="ta-cat-ib-empty">No sources cited yet.</div>
              ) : (
                art.sources.map((s, i) => (
                  <div className="ta-cat-src-row" key={i}>
                    <span className={`ta-cat-src ${s.quality}`} title={s.quality}>{badge(s.quality)}</span>
                    <span>{s.url ? <a className="ta-cat-link" href={s.url} target="_blank" rel="noreferrer">{s.text}</a> : s.text}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </aside>

      {confirmDelete && (
        <div className="ta-modal-backdrop" onClick={() => setConfirmDelete(false)}>
          <div className="ta-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420 }}>
            <h3 style={{ fontFamily: "var(--ta-font-display)", fontSize: 20, margin: "0 0 12px" }}>Delete {art.title}?</h3>
            <p style={{ fontSize: 13, color: "var(--ta-text-dim)", marginBottom: 16 }}>
              This soft-deletes the page. It disappears from the catalogue.
            </p>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button className="ta-btn" onClick={() => setConfirmDelete(false)} style={{ padding: "6px 14px" }}>Cancel</button>
              <button className="ta-btn" onClick={doDelete} style={{ padding: "6px 14px", borderColor: "var(--ta-accent-red)", color: "var(--ta-accent-red)" }}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function badge(q: string): string {
  return q === "primary" ? "P" : q === "secondary" ? "S" : q === "rotted" ? "!" : "C";
}

/* ------- minimal markdown renderer (paragraphs / ## / - / > / **bold** / links) ------- */
function MarkdownLite({ text }: { text: string }) {
  const blocks = text.replace(/\r\n/g, "\n").split(/\n{2,}/);
  return <>{blocks.map((b, i) => renderBlock(b.trim(), i))}</>;
}

function renderBlock(block: string, key: number): React.ReactNode {
  if (!block) return null;
  const lines = block.split("\n");
  if (lines.length > 0 && lines.every((l) => l.startsWith("- "))) {
    return <ul key={key}>{lines.map((l, i) => <li key={i}>{inline(l.slice(2))}</li>)}</ul>;
  }
  if (block.startsWith("> ")) return <blockquote key={key}>{inline(block.replace(/^> ?/gm, ""))}</blockquote>;
  if (block.startsWith("### ")) return <h3 key={key}>{inline(block.slice(4))}</h3>;
  if (block.startsWith("## ")) return <h2 key={key}>{inline(block.slice(3))}</h2>;
  if (block.startsWith("# ")) return <h2 key={key}>{inline(block.slice(2))}</h2>;
  return <p key={key}>{inline(block)}</p>;
}

function inline(s: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  s.split(/(\*\*[^*]+\*\*)/g).forEach((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) out.push(<strong key={`b${i}`}>{p.slice(2, -2)}</strong>);
    else out.push(...linkify(p, i));
  });
  return out;
}

function linkify(s: string, k: number): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const re = /\[([^\]]+)\]\(([^)]+)\)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let idx = 0;
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) out.push(s.slice(last, m.index));
    out.push(<a key={`l${k}-${idx++}`} href={m[2]} target="_blank" rel="noreferrer">{m[1]}</a>);
    last = m.index + m[0].length;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}
