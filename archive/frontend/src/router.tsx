/**
 * Hash-based router.
 *
 * URL contract:
 *   #/                     → Newsroom
 *   #/civs                 → Civilizations index
 *   #/civ/{slug}           → Civilization page
 *   #/inquisitions         → Inquisitions index
 *   #/inquisition/{id-or-slug} → Inquisition reader
 *   #/beats                → Beats index
 *   #/beat/{slug}          → Newsroom filtered by beat
 *   #/story/{id-or-slug}   → Story reader
 *   #/profile/{slug}       → Profile
 *   #/people               → People index
 *   #/person/{slug}        → Person page
 *   #/places               → Places index
 *   #/place/{slug}         → Place page
 *   #/events               → Events index
 *   #/event/{slug}         → Event page
 *   #/timeline             → Master timeline
 *   #/dashboard            → Dashboard
 *   #/drafts               → Drafts list
 *   #/draft/{id}           → Draft editor
 *   #/compose/{doctype}    → Compose new draft
 *   #/search               → Search results
 *   #/watchlist            → User's watchlist
 *   #/login                → Login
 *   #/admin                → Admin panel
 */

import { useEffect, useState } from "react";

export type Route =
  | { name: "home"; query?: string }
  | { name: "civs"; query?: string }
  | { name: "civ"; slug: string; query?: string }
  | { name: "inquisitions"; query?: string }
  | { name: "inquisition"; id: string; query?: string }
  | { name: "beats"; query?: string }
  | { name: "beat"; slug: string; query?: string }
  | { name: "story"; id: string; query?: string }
  | { name: "profile"; slug: string; query?: string }
  | { name: "people"; query?: string }
  | { name: "person"; slug: string; query?: string }
  | { name: "places"; query?: string }
  | { name: "place"; slug: string; query?: string }
  | { name: "events"; query?: string }
  | { name: "event"; slug: string; query?: string }
  | { name: "timeline"; query?: string }
  | { name: "dashboard"; query?: string }
  | { name: "drafts"; query?: string }
  | { name: "draft"; id: string; query?: string }
  | { name: "compose"; doctype: string; query?: string }
  | { name: "search"; query?: string }
  | { name: "watchlist"; query?: string }
  | { name: "login"; query?: string }
  | { name: "admin"; query?: string }
  | { name: "catalogue"; query?: string }
  | { name: "browse"; slug: string; query?: string }
  | { name: "article"; slug: string; query?: string }
  | { name: "newArticle"; query?: string }
  | { name: "notfound"; query?: string };

export function parseHash(): Route {
  // Preserve query string so callers can read e.g. ?q=foo on the search page.
  let hash = window.location.hash.replace(/^#/, "") || "/";
  let query: string | undefined;
  const qIdx = hash.indexOf("?");
  if (qIdx >= 0) {
    query = hash.slice(qIdx + 1);
    hash = hash.slice(0, qIdx);
  }
  const parts = hash.split("/").filter(Boolean);
  if (parts.length === 0) return { name: "home", query };
  switch (parts[0]) {
    case "civs": return { name: "civs", query };
    case "civ":
      return parts[1] ? { name: "civ", slug: parts[1], query } : { name: "notfound", query };
    case "inquisitions": return { name: "inquisitions", query };
    case "inquisition":
      return parts[1] ? { name: "inquisition", id: parts[1], query } : { name: "notfound", query };
    case "beats": return { name: "beats", query };
    case "beat":
      return parts[1] ? { name: "beat", slug: parts[1], query } : { name: "notfound", query };
    case "story":
      return parts[1] ? { name: "story", id: parts[1], query } : { name: "notfound", query };
    case "profile":
      return parts[1] ? { name: "profile", slug: parts[1], query } : { name: "notfound", query };
    case "people": return { name: "people", query };
    case "person":
      return parts[1] ? { name: "person", slug: parts[1], query } : { name: "notfound", query };
    case "places": return { name: "places", query };
    case "place":
      return parts[1] ? { name: "place", slug: parts[1], query } : { name: "notfound", query };
    case "events": return { name: "events", query };
    case "event":
      return parts[1] ? { name: "event", slug: parts[1], query } : { name: "notfound", query };
    case "timeline": return { name: "timeline", query };
    case "dashboard": return { name: "dashboard", query };
    case "drafts": return { name: "drafts", query };
    case "search": return { name: "search", query };
    case "watchlist": return { name: "watchlist", query };
    case "login": return { name: "login", query };
    case "admin": return { name: "admin", query };
    case "catalogue": return { name: "catalogue", query };
    case "browse":
      return parts[1] ? { name: "browse", slug: parts[1], query } : { name: "notfound", query };
    case "wiki":
      return parts[1] ? { name: "article", slug: parts[1], query } : { name: "notfound", query };
    case "new-article": return { name: "newArticle", query };
    case "draft":
      return parts[1] ? { name: "draft", id: parts[1], query } : { name: "notfound", query };
    case "compose":
      return parts[1] ? { name: "compose", doctype: parts[1], query } : { name: "notfound", query };
    default:
      return { name: "notfound", query };
  }
}

export function navigate(path: string) {
  // Always include leading slash. Strip leading # if caller already added it.
  const target = "#" + (path.startsWith("/") ? path : "/" + path.replace(/^#/, ""));
  if (window.location.hash === target) return;
  window.location.hash = target;
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(parseHash());
  useEffect(() => {
    const onChange = () => {
      setRoute(parseHash());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
