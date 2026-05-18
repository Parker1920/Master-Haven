/**
 * Timeline — master horizontal-scrub layout.
 *
 * Phase 5b: full mockup parity.
 *
 * Layout model (mirrors the v0.9 mockup):
 *   - Outer canvas scrolls horizontally
 *   - Inner track is min YEAR_WIDTH * yearSpan + LABEL_W wide
 *   - Year ticks along the bottom axis, one per year in the range
 *   - Each civ gets a horizontal "lane" (row at fixed Y offset)
 *   - Civs without a year-aligned event still get a lane but with
 *     just the lane label
 *   - Civ founding / ending markers AND stories / inquisitions
 *     tagged with that civ render as cards on the lane
 *   - Events without a civ tag (rare in our data) go into an
 *     "Unaffiliated" catch-all lane
 *
 * Layout numbers tuned to keep cards readable on the Pi-served SPA
 * at typical phone widths (~360px viewport ⇒ horizontal scroll).
 */

import { useEffect, useMemo, useState } from "react";
import { api, CivilizationSummary, TimelineEntry } from "../api/client";
import { Loading } from "../components/Loading";

const LABEL_W = 100;       // px reserved for the lane-label gutter
const YEAR_WIDTH = 240;    // px per year
const LANE_HEIGHT = 72;    // px per civ lane
const LANE_START_Y = 24;   // px from top to first lane
const AXIS_BOTTOM = 30;    // px from bottom to the axis line
const CARD_WIDTH = 150;    // px per event card

interface CivLane {
  slug: string;
  name: string;
  color: string;          // primary brand color, used for the left border
}

const UNAFFILIATED_SLUG = "_unaffiliated";

export function Timeline() {
  const [entries, setEntries] = useState<TimelineEntry[] | null>(null);
  const [civs, setCivs] = useState<CivilizationSummary[] | null>(null);

  useEffect(() => {
    Promise.all([
      api<TimelineEntry[]>("/timeline"),
      api<CivilizationSummary[]>("/civilizations"),
    ])
      .then(([t, c]) => { setEntries(t); setCivs(c); })
      .catch(() => { setEntries([]); setCivs([]); });
  }, []);

  const { lanes, startYear, endYear, totalWidth } = useMemo(() => {
    if (!entries || !civs) {
      return { lanes: [] as CivLane[], startYear: 2017, endYear: 2026, totalWidth: 0 };
    }

    // Earliest + latest year across all entries (default to the range
    // the seed data covers if entries don't cover anything yet).
    const years = entries
      .map((e) => e.year ?? null)
      .filter((y): y is number => typeof y === "number");
    const minY = years.length ? Math.min(...years) : 2017;
    const maxY = years.length ? Math.max(...years) : 2026;
    // Pad a year on either side so end markers aren't right at the edge
    const startYear = Math.min(2017, minY) - 0;
    const endYear = Math.max(2026, maxY) + 0;
    const span = endYear - startYear + 1;
    const totalWidth = LABEL_W + span * YEAR_WIDTH;

    // Lane order: civ-tagged entries grouped by civ activity (newest
    // founded last so the lanes read roughly chronologically).
    const byCivSlug = new Set<string>();
    for (const e of entries) {
      if (e.civs.length > 0) e.civs.forEach((c) => byCivSlug.add(c));
    }
    const lanes: CivLane[] = civs
      .filter((c) => byCivSlug.has(c.slug))
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((c) => ({
        slug: c.slug,
        name: c.name,
        color: c.color_primary,
      }));
    // Always include the unaffiliated lane for events without a civ
    // (currently only the rare multi-civ briefs without explicit tags)
    const hasUnaffiliated = entries.some((e) => e.civs.length === 0);
    if (hasUnaffiliated) {
      lanes.push({ slug: UNAFFILIATED_SLUG, name: "(unaffiliated)", color: "#888" });
    }
    return { lanes, startYear, endYear, totalWidth };
  }, [entries, civs]);

  if (!entries || !civs) return <Loading label="Loading timeline…" />;
  if (entries.length === 0) {
    return (
      <div className="ta-empty">
        No timeline entries yet — stories and inquisitions will appear here as they're published.
      </div>
    );
  }

  const dateToX = (dateStr?: string | null, fallbackYear?: number | null): number => {
    // Returns absolute X (including the LABEL_W left gutter)
    let yearFraction = 0;
    if (dateStr) {
      const d = new Date(dateStr);
      if (!isNaN(d.getTime())) {
        yearFraction =
          (d.getFullYear() - startYear) +
          d.getMonth() / 12 +
          d.getDate() / 365;
      }
    }
    if (!yearFraction && fallbackYear !== undefined && fallbackYear !== null) {
      yearFraction = fallbackYear - startYear;
    }
    return LABEL_W + yearFraction * YEAR_WIDTH;
  };

  const laneIndexFor = (slug: string): number =>
    lanes.findIndex((l) => l.slug === slug);

  // Flatten entries into (lane, entry) pairs — an entry tagged with
  // multiple civs renders on each of those civ lanes.
  const placed: Array<{ lane: CivLane; entry: TimelineEntry; key: string }> = [];
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    const targetCivSlugs = e.civs.length > 0 ? e.civs : [UNAFFILIATED_SLUG];
    for (const civSlug of targetCivSlugs) {
      const li = laneIndexFor(civSlug);
      if (li < 0) continue;
      placed.push({
        lane: lanes[li],
        entry: e,
        key: `${e.kind}-${e.id ?? e.slug ?? "x"}-${civSlug}-${i}`,
      });
    }
  }

  const trackHeight = LANE_START_Y + lanes.length * LANE_HEIGHT + AXIS_BOTTOM + 30;

  return (
    <>
      <div className="ta-timeline-header">
        <h1 className="ta-timeline-title">Master timeline</h1>
        <p className="ta-timeline-sub">
          Every dated entry across the archive — stories, inquisitions, civ
          foundings + endings. Scroll horizontally; lanes group by civilization.
        </p>
      </div>

      <div className="ta-timeline-canvas">
        <div className="ta-timeline-track" style={{ width: totalWidth, height: trackHeight }}>
          {/* Lane labels — left-pinned via position:sticky inside the scroll */}
          <div className="ta-timeline-label-col" style={{ width: LABEL_W, height: trackHeight }}>
            {lanes.map((l, i) => (
              <div
                key={l.slug}
                className="ta-timeline-label"
                style={{
                  top: LANE_START_Y + i * LANE_HEIGHT,
                  borderLeftColor: l.color,
                }}
              >
                {l.name.replace(/^The /, "")}
              </div>
            ))}
          </div>

          {/* Lane background bands (alt rows) */}
          {lanes.map((_, i) => (
            <div
              key={`band-${i}`}
              className="ta-timeline-lane-band"
              style={{
                top: LANE_START_Y + i * LANE_HEIGHT,
                left: LABEL_W,
                width: totalWidth - LABEL_W,
                height: LANE_HEIGHT,
                background: i % 2 === 0 ? "rgba(255,255,255,0.015)" : "transparent",
              }}
            />
          ))}

          {/* Year axis line + ticks */}
          <div
            className="ta-timeline-axis"
            style={{
              left: LABEL_W,
              width: totalWidth - LABEL_W,
              bottom: AXIS_BOTTOM,
            }}
          />
          {Array.from({ length: endYear - startYear + 1 }, (_, i) => {
            const year = startYear + i;
            const x = LABEL_W + i * YEAR_WIDTH;
            return (
              <div key={year} className="ta-timeline-year" style={{ left: x, bottom: 0 }}>
                {year}
              </div>
            );
          })}

          {/* Event cards */}
          {placed.map(({ lane, entry, key }) => {
            const x = dateToX(entry.date, entry.year);
            const y = LANE_START_Y + laneIndexFor(lane.slug) * LANE_HEIGHT;
            const href = hrefFor(entry);
            const isMarker = entry.kind === "civ-founded" || entry.kind === "civ-ended";
            return (
              <a
                key={key}
                href={href}
                className={`ta-timeline-event${isMarker ? " ta-timeline-event-marker" : ""}`}
                style={{
                  left: x,
                  top: y,
                  width: CARD_WIDTH,
                  borderLeftColor: lane.color,
                }}
                title={entry.title}
              >
                <span
                  className="ta-timeline-event-kind"
                  style={{ background: lane.color }}
                >
                  {entry.kind.replace("civ-", "")}
                </span>
                <div className="ta-timeline-event-title">{entry.title}</div>
                <div className="ta-timeline-event-meta">{fmtDate(entry.date)}</div>
              </a>
            );
          })}
        </div>
      </div>

      <div className="ta-timeline-helper">
        ← scroll horizontally → · tap any card to open · lanes group events by civilization
      </div>
    </>
  );
}

function hrefFor(e: TimelineEntry): string {
  switch (e.kind) {
    case "story": return `#/story/${e.id}`;
    case "inquisition": return `#/inquisition/${e.id}`;
    case "civ-founded":
    case "civ-ended":
      return e.slug ? `#/civ/${e.slug}` : "#";
    default: return "#";
  }
}

function fmtDate(d: string): string {
  if (!d) return "";
  try {
    return new Date(d).toLocaleDateString("en-US", { month: "short", year: "numeric" });
  } catch { return d; }
}
