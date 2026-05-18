/** Events index — historical events for the master timeline. */
import { useEffect, useState } from "react";
import { api, EventSummary } from "../api/client";

export function Events() {
  const [events, setEvents] = useState<EventSummary[] | null>(null);

  useEffect(() => {
    api<EventSummary[]>("/events", { query: { page_size: 200 } })
      .then(setEvents)
      .catch(() => setEvents([]));
  }, []);

  return (
    <>
      <div className="ta-civ-index-header">
        <h2 className="ta-civ-index-title">Events</h2>
        <p className="ta-civ-index-sub">
          {events === null
            ? "Loading…"
            : `${events.length} event${events.length === 1 ? "" : "s"} on record`}
        </p>
      </div>

      {events === null ? (
        <div className="ta-loading">Loading…</div>
      ) : events.length === 0 ? (
        <div className="ta-empty">No events on record yet.</div>
      ) : (
        <div className="ta-event-list">
          {events.map((e) => (
            <a key={e.slug} href={`#/event/${e.slug}`} className="ta-event-row">
              <div className="ta-event-year">{e.event_year ?? "—"}</div>
              <div className="ta-event-row-body">
                <div className="ta-event-title">{e.title}</div>
                {e.event_date && <div className="ta-event-date">{e.event_date}</div>}
              </div>
            </a>
          ))}
        </div>
      )}
    </>
  );
}
