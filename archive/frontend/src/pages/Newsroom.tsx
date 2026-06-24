/**
 * Home — a hybrid "archive front page" that weaves the catalogue (wiki)
 * and the newsroom into one surface:
 *   - hero with live stats
 *   - left spine: the grouped catalogue navigator (always present)
 *   - blended feed: Featured · Recently catalogued · Newsroom · Inquisitions
 *
 * When rendered for a /beat/{slug} route it falls back to a focused
 * newsroom-beat list.
 */

import { useEffect, useState } from "react";
import {
  api,
  ArticleSummary,
  CivilizationSummary,
  InquisitionSummary,
  NamespaceCount,
  StorySummary,
} from "../api/client";
import { CataloguePortal } from "../components/CataloguePortal";
import { InquisitionCard } from "../components/InquisitionCard";
import { StoryCard } from "../components/StoryCard";
import { ArticleCard } from "../components/ArticleCard";
import { Loading } from "../components/Loading";
import { NS_BY_KEY } from "../data/namespaces";
import { useAuth } from "../hooks/useAuth";

interface Props { beat?: string; }

export function Newsroom({ beat }: Props) {
  const { user } = useAuth();
  const [stories, setStories] = useState<StorySummary[] | null>(null);
  const [inquisitions, setInquisitions] = useState<InquisitionSummary[] | null>(null);
  const [civs, setCivs] = useState<CivilizationSummary[] | null>(null);
  const [recent, setRecent] = useState<ArticleSummary[]>([]);
  const [catCount, setCatCount] = useState<number | null>(null);
  const canCompose = !!user && (user.base_role === "diplomat" || user.base_role === "historian" || user.is_admin);

  useEffect(() => {
    const ac = new AbortController();
    Promise.all([
      api<StorySummary[]>("/stories", { query: { beat }, signal: ac.signal }),
      api<InquisitionSummary[]>("/inquisitions", { signal: ac.signal }),
      api<CivilizationSummary[]>("/civilizations", { query: { page_size: 500 }, signal: ac.signal }),
      api<ArticleSummary[]>("/articles", { query: { page_size: 60 }, signal: ac.signal }),
      api<NamespaceCount[]>("/articles/namespaces", { signal: ac.signal }),
    ]).then(([s, i, c, a, ns]) => {
      setStories(s); setInquisitions(i); setCivs(c);
      const sorted = [...a].sort((x, y) => (y.updated_at ?? "").localeCompare(x.updated_at ?? ""));
      setRecent(sorted.slice(0, 6));
      setCatCount(ns.filter((r) => NS_BY_KEY[r.namespace]?.kind === "article").reduce((n, r) => n + r.count, 0));
    }).catch((err) => {
      if (err?.name === "AbortError") return;
      setStories([]); setInquisitions([]); setCivs([]);
    });
    return () => ac.abort();
  }, [beat]);

  // Focused beat view.
  if (beat) {
    return (
      <div className="ta-home-beat">
        <a href="#/" className="ta-back-link">← Home</a>
        <h2 className="ta-cat-head-title" style={{ marginTop: 10, textTransform: "capitalize" }}>{beat} · Newsroom</h2>
        {stories === null ? <Loading /> : stories.length === 0 ? (
          <div className="ta-empty">No stories on the {beat} beat yet.</div>
        ) : (
          <div className="ta-story-grid" style={{ marginTop: 16 }}>
            {stories.map((s) => <StoryCard key={s.id} story={s} />)}
          </div>
        )}
      </div>
    );
  }

  const all = stories ?? [];
  const features = all.filter((s) => s.doctype === "feature");
  const briefs = all.filter((s) => s.doctype === "brief");
  const hero = features[0] ?? briefs[0] ?? null;
  const otherStories = all.filter((s) => s.id !== hero?.id);
  const loading = stories === null;

  return (
    <>
      <div className="ta-home-hero">
        <h1 className="ta-home-hero-name">The Travelers Archive</h1>
        <div className="ta-home-hero-tag">No Man's Sky, catalogued &amp; chronicled by the people who found it</div>
        <div className="ta-home-stats">
          <HomeStat n={catCount} label="catalogue pages" />
          <HomeStat n={civs?.length} label="civilizations" />
          <HomeStat n={stories?.length} label="stories" />
          <HomeStat n={inquisitions?.length} label="inquisitions" />
        </div>
      </div>

      <div className="ta-home-grid">
        <div className="ta-home-spine">
          <div className="ta-home-spine-head">Browse the catalogue</div>
          <CataloguePortal variant="spine" />
          <a href="#/catalogue" className="ta-home-spine-all">All categories →</a>
        </div>

        <div className="ta-home-feed">
          {loading ? <Loading label="Loading the archive…" /> : (
            <>
              {hero ? (
                <FeedSection title="Featured">
                  <StoryCard story={hero} hero />
                </FeedSection>
              ) : recent[0] ? (
                <FeedSection title="Featured page">
                  <FeaturedArticle a={recent[0]} />
                </FeedSection>
              ) : null}

              {recent.length > 0 && (
                <FeedSection title="Recently catalogued" more={{ href: "#/catalogue", label: "Browse all" }}>
                  <div className="ta-cat-grid">
                    {recent.map((a) => <ArticleCard key={a.slug} a={a} />)}
                  </div>
                </FeedSection>
              )}

              {otherStories.length > 0 ? (
                <FeedSection title="From the Newsroom">
                  <div className="ta-story-grid">{otherStories.slice(0, 4).map((s) => <StoryCard key={s.id} story={s} />)}</div>
                </FeedSection>
              ) : (
                <FeedSection title="From the Newsroom">
                  <div className="ta-home-quiet">
                    The newsroom is quiet right now.
                    {canCompose && <> <a className="ta-cat-link" href="#/compose/brief">File a brief</a> or <a className="ta-cat-link" href="#/compose/feature">start a feature</a>.</>}
                  </div>
                </FeedSection>
              )}

              {inquisitions && inquisitions.length > 0 && (
                <FeedSection title="Active Inquisitions" more={{ href: "#/inquisitions", label: "All inquisitions" }}>
                  <div className="ta-inq-shelf">{inquisitions.map((i) => <InquisitionCard key={i.id} inq={i} />)}</div>
                </FeedSection>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}

function HomeStat({ n, label }: { n: number | null | undefined; label: string }) {
  return (
    <div className="ta-home-stat">
      <span className="ta-home-stat-n">{n == null ? "…" : n}</span>
      <span className="ta-home-stat-l">{label}</span>
    </div>
  );
}

function FeedSection({ title, more, children }: { title: string; more?: { href: string; label: string }; children: React.ReactNode }) {
  return (
    <section className="ta-home-section">
      <div className="ta-home-section-head">
        <h2 className="ta-home-section-title">{title}</h2>
        {more && <a className="ta-home-section-more" href={more.href}>{more.label} →</a>}
      </div>
      {children}
    </section>
  );
}

function FeaturedArticle({ a }: { a: ArticleSummary }) {
  const def = NS_BY_KEY[a.namespace];
  return (
    <a href={`#/wiki/${a.slug}`} className="ta-home-featured" style={{ "--cat-accent": def?.accent } as React.CSSProperties}>
      <div className="ta-home-featured-glyph">{def?.glyph ?? "✦"}</div>
      <div>
        <div className="ta-home-featured-ns">{def?.label ?? a.namespace}</div>
        <div className="ta-home-featured-title">{a.title}</div>
        {a.subtitle && <div className="ta-home-featured-sub">{a.subtitle}</div>}
      </div>
    </a>
  );
}
