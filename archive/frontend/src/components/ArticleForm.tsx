/**
 * ArticleForm — the no-markup create/edit form shared by ArticleNew
 * (create) and the Article page (inline edit).
 *
 * Holds its own draft state; calls onSubmit with a cleaned draft. The
 * parent owns the API call + navigation. In edit mode the namespace and
 * slug are locked (the slug is the page address).
 */

import { useEffect, useState } from "react";
import { api, ArticleSource, FacetDef, FacetSchema, InfoboxRow, SourceQuality } from "../api/client";
import { ARTICLE_NAMESPACES } from "../data/namespaces";
import { FacetControl } from "./FacetControl";

export interface ArticleDraft {
  namespace: string;
  slug: string;
  title: string;
  subtitle: string;
  civ_slug: string;
  body: string;
  infobox: InfoboxRow[];
  sources: ArticleSource[];
  facets: Record<string, string[]>;
}

export function emptyDraft(namespace = "lore"): ArticleDraft {
  return { namespace, slug: "", title: "", subtitle: "", civ_slug: "", body: "", infobox: [], sources: [], facets: {} };
}

function slugify(s: string): string {
  return s.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80);
}

const QUALITIES: SourceQuality[] = ["primary", "secondary", "community", "rotted"];

interface Props {
  mode: "create" | "edit";
  initial: ArticleDraft;
  submitting: boolean;
  onSubmit: (d: ArticleDraft) => void;
  onCancel?: () => void;
}

export function ArticleForm({ mode, initial, submitting, onSubmit, onCancel }: Props) {
  const [d, setD] = useState<ArticleDraft>(initial);
  const [slugTouched, setSlugTouched] = useState(mode === "edit");

  const set = <K extends keyof ArticleDraft>(k: K, v: ArticleDraft[K]) =>
    setD((p) => ({ ...p, [k]: v }));

  const onTitle = (v: string) =>
    setD((p) => ({ ...p, title: v, slug: mode === "create" && !slugTouched ? slugify(v) : p.slug }));

  const setIb = (i: number, key: "label" | "value", v: string) =>
    setD((p) => ({ ...p, infobox: p.infobox.map((r, idx) => (idx === i ? { ...r, [key]: v } : r)) }));
  const addIb = () => setD((p) => ({ ...p, infobox: [...p.infobox, { label: "", value: "" }] }));
  const delIb = (i: number) => setD((p) => ({ ...p, infobox: p.infobox.filter((_, idx) => idx !== i) }));

  const setSrc = (i: number, patch: Partial<ArticleSource>) =>
    setD((p) => ({ ...p, sources: p.sources.map((r, idx) => (idx === i ? { ...r, ...patch } : r)) }));
  const addSrc = () => setD((p) => ({ ...p, sources: [...p.sources, { quality: "community", text: "", url: "" }] }));
  const delSrc = (i: number) => setD((p) => ({ ...p, sources: p.sources.filter((_, idx) => idx !== i) }));

  // Facet schema for the current namespace (drives the structured filter fields).
  const [facetDefs, setFacetDefs] = useState<FacetDef[]>([]);
  useEffect(() => {
    let alive = true;
    api<FacetSchema>(`/articles/facets/${d.namespace}`)
      .then((s) => { if (alive) setFacetDefs(s.facets); })
      .catch(() => { if (alive) setFacetDefs([]); });
    return () => { alive = false; };
  }, [d.namespace]);

  const setFacet = (key: string, v: string[]) =>
    setD((p) => {
      const facets = { ...p.facets };
      if (v.length) facets[key] = v; else delete facets[key];
      return { ...p, facets };
    });

  const onNamespace = (v: string) => setD((p) => ({ ...p, namespace: v, facets: {} }));

  const valid = !!d.namespace && !!d.slug && d.title.trim().length > 0;

  const submit = () => {
    if (!valid || submitting) return;
    onSubmit({
      ...d,
      title: d.title.trim(),
      infobox: d.infobox.filter((r) => r.label.trim()),
      sources: d.sources.filter((r) => r.text.trim()),
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <FormField label="Category" required>
        <select
          className="ta-form-select" value={d.namespace} disabled={mode === "edit"}
          onChange={(e) => onNamespace(e.target.value)}
        >
          {ARTICLE_NAMESPACES.map((n) => <option key={n.ns} value={n.ns}>{n.label}</option>)}
        </select>
      </FormField>

      <FormField label="Title" required>
        <input className="ta-form-input" value={d.title} onChange={(e) => onTitle(e.target.value)}
               placeholder="e.g. Activated Indium" />
      </FormField>

      <FormField label="URL slug" required>
        <input
          className="ta-form-input" value={d.slug} disabled={mode === "edit"}
          onChange={(e) => { setSlugTouched(true); set("slug", slugify(e.target.value)); }}
          placeholder="activated-indium"
        />
        {mode === "edit" && (
          <div className="ta-cat-markup-note">The slug is the page address and can't change after creation.</div>
        )}
      </FormField>

      <FormField label="One-line summary">
        <input className="ta-form-input" value={d.subtitle} onChange={(e) => set("subtitle", e.target.value)}
               placeholder="Shows under the title and on cards" />
      </FormField>

      <FormField label="Linked civilization (optional slug)">
        <input className="ta-form-input" value={d.civ_slug} onChange={(e) => set("civ_slug", e.target.value)}
               placeholder="e.g. voyagers-haven" />
      </FormField>

      <FormField label="Body">
        <textarea
          className="ta-form-textarea" rows={10} value={d.body}
          onChange={(e) => set("body", e.target.value)}
          style={{ minHeight: 180, fontFamily: "var(--ta-font-read)" }}
          placeholder="Write in plain language. Blank line = new paragraph."
        />
        <div className="ta-cat-markup-note">
          Light markdown: <b>**bold**</b>, <b>## heading</b>, <b>- bullet</b>, <b>&gt; quote</b>. No wiki syntax to learn.
        </div>
      </FormField>

      {facetDefs.length > 0 && (
        <div>
          <div className="ta-form-label">Categories &amp; attributes (these power the filters)</div>
          <div className="ta-cat-form-facets">
            {facetDefs.map((def) => (
              <div className="ta-cat-form-facet" key={def.key}>
                {def.control !== "boolean" && <div className="ta-cat-form-facet-label">{def.label}</div>}
                <FacetControl def={def} value={d.facets[def.key] ?? []} onChange={(v) => setFacet(def.key, v)} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <div className="ta-form-label">Overview facts (infobox)</div>
        <div className="ta-cat-rows">
          {d.infobox.map((r, i) => (
            <div className="ta-cat-row-edit" key={i}>
              <input className="ta-form-input" placeholder="Label" value={r.label}
                     onChange={(e) => setIb(i, "label", e.target.value)} />
              <input className="ta-form-input" placeholder="Value" value={r.value}
                     onChange={(e) => setIb(i, "value", e.target.value)} />
              <button type="button" className="ta-cat-mini-btn" onClick={() => delIb(i)} aria-label="Remove">✕</button>
            </div>
          ))}
          <button type="button" className="ta-cat-add-row" onClick={addIb}>+ Add a fact</button>
        </div>
      </div>

      <div>
        <div className="ta-form-label">Sources</div>
        <div className="ta-cat-rows">
          {d.sources.map((r, i) => (
            <div className="ta-cat-row-edit src" key={i}>
              <select className="ta-form-select" value={r.quality}
                      onChange={(e) => setSrc(i, { quality: e.target.value as SourceQuality })}>
                {QUALITIES.map((q) => <option key={q} value={q}>{q}</option>)}
              </select>
              <input className="ta-form-input" placeholder="What it is" value={r.text}
                     onChange={(e) => setSrc(i, { text: e.target.value })} />
              <input className="ta-form-input" placeholder="URL (optional)" value={r.url ?? ""}
                     onChange={(e) => setSrc(i, { url: e.target.value })} />
              <button type="button" className="ta-cat-mini-btn" onClick={() => delSrc(i)} aria-label="Remove">✕</button>
            </div>
          ))}
          <button type="button" className="ta-cat-add-row" onClick={addSrc}>+ Add a source</button>
        </div>
        <div className="ta-cat-markup-note">Every page declares its sourcing — that's what keeps the Archive trustworthy.</div>
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        <button className="ta-btn ta-btn-primary" onClick={submit} disabled={!valid || submitting} style={{ padding: "8px 18px" }}>
          {submitting ? "Saving…" : mode === "create" ? "Create page" : "Save changes"}
        </button>
        {onCancel && (
          <button className="ta-btn" onClick={onCancel} disabled={submitting} style={{ padding: "8px 18px" }}>Cancel</button>
        )}
      </div>
    </div>
  );
}

function FormField({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <span className="ta-form-label">
        {label}{required && <span style={{ color: "var(--ta-accent-red)" }}> *</span>}
      </span>
      {children}
    </label>
  );
}
