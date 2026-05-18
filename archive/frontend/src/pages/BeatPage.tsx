/**
 * Single-beat story listing.
 *
 * `/beats/{slug}` — distinct from the existing `/beat/{slug}` route
 * which uses the Newsroom-with-filter shape. This page is a clean,
 * scrollable list of every story in the beat, sorted newest-first.
 */

import { useEffect, useState } from "react";
import { api, ApiError, StorySummary } from "../api/client";
import { StoryCard } from "../components/StoryCard";

export function BeatPage({ slug }: { slug: string }) {
  const [stories, setStories] = useState<StorySummary[] | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setStories(null);
    setNotFound(false);
    api<StorySummary[]>(`/beats/${slug}/stories`)
      .then(setStories)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
        else setStories([]);
      });
  }, [slug]);

  if (notFound) return <div className="ta-empty">Beat "{slug}" not found.</div>;
  if (stories === null) return <div className="ta-loading">Loading beat…</div>;

  return (
    <>
      <div className="ta-civ-index-header">
        <a href="#/beats" className="ta-back-link">← All beats</a>
        <h2 className="ta-civ-index-title" style={{ textTransform: "capitalize" }}>{slug}</h2>
        <p className="ta-civ-index-sub">
          {stories.length} {stories.length === 1 ? "story" : "stories"} filed under {slug}
        </p>
      </div>
      {stories.length === 0 ? (
        <div className="ta-empty">No stories yet in this beat.</div>
      ) : (
        <div className="ta-story-grid">
          {stories.map((s) => <StoryCard key={s.id} story={s} />)}
        </div>
      )}
    </>
  );
}
