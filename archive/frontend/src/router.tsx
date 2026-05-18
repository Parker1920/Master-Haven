/**
 * Hash-based router.
 *
 * Matches the v0.9 mockup URL contract exactly:
 *   #/                     → Newsroom
 *   #/civs                 → Civilizations index
 *   #/civ/{slug}           → Civilization page
 *   #/inquisitions         → Inquisitions index
 *   #/inquisition/{id}     → Inquisition reader
 *   #/beat/{slug}          → Newsroom filtered by beat
 *   #/story/{id}           → Story reader
 *   #/profile/{slug}       → Profile
 *   #/timeline             → Master timeline
 *   #/dashboard            → Dashboard
 *   #/drafts               → Drafts list
 *   #/draft/{id}           → Draft editor
 *   #/compose/{doctype}    → Compose new draft
 */

import { useEffect, useState } from "react";

export type Route =
  | { name: "home" }
  | { name: "civs" }
  | { name: "civ"; slug: string }
  | { name: "inquisitions" }
  | { name: "inquisition"; id: string }
  | { name: "beat"; slug: string }
  | { name: "story"; id: string }
  | { name: "profile"; slug: string }
  | { name: "timeline" }
  | { name: "dashboard" }
  | { name: "drafts" }
  | { name: "draft"; id: string }
  | { name: "compose"; doctype: string }
  | { name: "login" }
  | { name: "notfound" };

export function parseHash(): Route {
  const hash = window.location.hash.replace(/^#/, "") || "/";
  const parts = hash.split("/").filter(Boolean);
  if (parts.length === 0) return { name: "home" };
  switch (parts[0]) {
    case "civs": return { name: "civs" };
    case "civ":
      return parts[1] ? { name: "civ", slug: parts[1] } : { name: "notfound" };
    case "inquisitions": return { name: "inquisitions" };
    case "inquisition":
      return parts[1] ? { name: "inquisition", id: parts[1] } : { name: "notfound" };
    case "beat":
      return parts[1] ? { name: "beat", slug: parts[1] } : { name: "notfound" };
    case "story":
      return parts[1] ? { name: "story", id: parts[1] } : { name: "notfound" };
    case "profile":
      return parts[1] ? { name: "profile", slug: parts[1] } : { name: "notfound" };
    case "timeline": return { name: "timeline" };
    case "dashboard": return { name: "dashboard" };
    case "drafts": return { name: "drafts" };
    case "login": return { name: "login" };
    case "draft":
      return parts[1] ? { name: "draft", id: parts[1] } : { name: "notfound" };
    case "compose":
      return parts[1] ? { name: "compose", doctype: parts[1] } : { name: "notfound" };
    default:
      return { name: "notfound" };
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
