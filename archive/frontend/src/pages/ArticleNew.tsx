/** ArticleNew — create a catalogue page (team role: diplomat+). */
import { useState } from "react";
import { api, ApiError, ArticleDetail } from "../api/client";
import { ArticleForm, ArticleDraft, emptyDraft } from "../components/ArticleForm";
import { ARTICLE_NAMESPACES, NS_BY_KEY } from "../data/namespaces";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { navigate } from "../router";

function queryNamespace(): string {
  const q = window.location.hash.split("?")[1] || "";
  const ns = new URLSearchParams(q).get("namespace") || "";
  return NS_BY_KEY[ns]?.kind === "article" ? ns : ARTICLE_NAMESPACES[0].ns;
}

export function ArticleNew() {
  const { user, loading } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [initial] = useState<ArticleDraft>(() => emptyDraft(queryNamespace()));

  if (loading) return <div className="ta-loading">Loading…</div>;

  const canCreate = !!user && (user.base_role !== "reader" || user.is_admin);
  if (!canCreate) {
    return (
      <div className="ta-empty">
        Creating a catalogue page needs a team role (diplomat or historian).
        {!user && <> <a className="ta-cat-link" href="#/login">Sign in</a>.</>}
        <div style={{ marginTop: 12 }}>
          <a className="ta-back-link" href="#/catalogue">← back to the catalogue</a>
        </div>
      </div>
    );
  }

  const create = async (d: ArticleDraft) => {
    setSubmitting(true);
    try {
      const created = await api<ArticleDetail>("/articles", {
        method: "POST",
        body: {
          namespace: d.namespace, slug: d.slug, title: d.title,
          subtitle: d.subtitle || null, civ_slug: d.civ_slug || null,
          body: d.body, infobox: d.infobox, sources: d.sources, facets: d.facets,
        },
      });
      showToast("Page created");
      navigate(`/wiki/${created.slug}`);
    } catch (e) {
      showToast(e instanceof ApiError ? String(e.detail) : "Create failed");
      setSubmitting(false);
    }
  };

  return (
    <div className="ta-cat-form">
      <a href="#/catalogue" className="ta-back-link">← Back to the catalogue</a>
      <h2 style={{ marginTop: 10 }}>Create a page</h2>
      <p className="lead">Pick a category, give it a title, and write in plain language. No wiki markup.</p>
      <ArticleForm mode="create" initial={initial} submitting={submitting} onSubmit={create} />
    </div>
  );
}
