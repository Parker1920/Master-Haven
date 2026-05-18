/** Story reader. */
import { useEffect, useState } from "react";
import { api, StoryDetail } from "../api/client";
import { Avatar } from "../components/Avatar";
import { Loading } from "../components/Loading";
import { BeatTag, CivTag, DocTypeTag } from "../components/Tag";
import { Prose } from "./InquisitionPage";

export function Story({ id }: { id: string }) {
  const [story, setStory] = useState<StoryDetail | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setStory(null);
    setNotFound(false);
    api<StoryDetail>(`/stories/${id}`)
      .then(setStory)
      .catch(() => setNotFound(true));
  }, [id]);

  if (notFound) return <div className="ta-empty">Story not found.</div>;
  if (!story) return <Loading label="Loading story…" />;

  const niceDate = new Date(story.published_at).toLocaleDateString("en-US", { dateStyle: "long" });

  return (
    <div className="ta-story-reader">
      <a href="#/" className="ta-back-link">← Back to newsroom</a>
      <div className="ta-story-tags">
        <DocTypeTag doctype={story.doctype} />
        {story.beat && <BeatTag beat={story.beat} />}
        {story.civs.map((c) => <CivTag key={c} slug={c} />)}
      </div>
      <h1>{story.headline}</h1>
      {story.deck && <p className="ta-story-reader-deck">{story.deck}</p>}
      <div className="ta-story-reader-byline">
        <a href={`#/profile/${story.author.slug}`}><Avatar author={story.author} size="md" /></a>
        <div className="ta-story-reader-byline-info">
          <div className="ta-story-reader-byline-name">
            <a href={`#/profile/${story.author.slug}`}>{story.author.name}</a>
          </div>
          <div className="ta-story-reader-byline-meta">
            {story.author.role ?? "diplomat"} · published {niceDate}
            {story.read_minutes ? ` · ${story.read_minutes} min read` : ""}
          </div>
        </div>
      </div>
      <Prose body={story.body} />

      {story.civs.length > 0 && (
        <div style={{
          marginTop: 32, padding: 16,
          background: "var(--ta-bg)", borderRadius: 10,
        }}>
          <div style={{
            fontSize: 10, textTransform: "uppercase", letterSpacing: 1,
            color: "var(--ta-text-faint)", fontWeight: 500, marginBottom: 10,
          }}>Mentioned civilizations</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {story.civs.map((c) => (
              <a key={c} href={`#/civ/${c}`} style={{
                color: "var(--ta-accent-blue)", fontSize: 13, fontWeight: 500,
              }}>{c} →</a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
