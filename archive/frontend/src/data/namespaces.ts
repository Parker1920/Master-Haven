/**
 * Catalogue namespace registry (frontend display metadata).
 *
 * Mirrors app/namespaces.py on the backend. The backend is the authority
 * on which namespaces are writable; this file holds the label / glyph /
 * accent / blurb used to render the portal, browse, and article views.
 *
 * kind:
 *   article  → generic, writable through /api/v1/articles
 *   special  → its own richer table/page (civ → Civilizations)
 *   synced   → sourced from the live Haven atlas (system/planet), surfaced
 *              as a tile but not authored here yet
 */

export type NamespaceKind = "article" | "special" | "synced";

export interface NamespaceDef {
  ns: string;
  label: string;
  singular: string;
  glyph: string;
  accent: string;
  blurb: string;
  kind: NamespaceKind;
  href: string;
}

export const NAMESPACES: NamespaceDef[] = [
  { ns: "civ", label: "Civilizations", singular: "Civilization", glyph: "⬡", accent: "#A78BFA",
    blurb: "Federations, empires, and traveler nations — with full histories.", kind: "special", href: "#/civs" },
  { ns: "traveler", label: "Travelers", singular: "Traveler", glyph: "✦", accent: "#5EE7DF",
    blurb: "The explorers, diplomats, and historians themselves.", kind: "article", href: "#/browse/traveler" },
  { ns: "system", label: "Star Systems", singular: "System", glyph: "★", accent: "#ffb547",
    blurb: "Catalogued systems across the galaxies — synced from the Haven atlas.", kind: "synced", href: "#/browse/system" },
  { ns: "planet", label: "Planets", singular: "Planet", glyph: "◉", accent: "#34d399",
    blurb: "Worlds, biomes, weather, and resources — synced from the atlas.", kind: "synced", href: "#/browse/planet" },
  { ns: "creature", label: "Fauna", singular: "Creature", glyph: "❂", accent: "#7dd3fc",
    blurb: "Documented creatures and their behaviors.", kind: "article", href: "#/browse/creature" },
  { ns: "flora", label: "Flora", singular: "Plant", glyph: "✿", accent: "#4ade80",
    blurb: "Plants, their biomes, and the resources they yield.", kind: "article", href: "#/browse/flora" },
  { ns: "mineral", label: "Minerals", singular: "Mineral", glyph: "◇", accent: "#c084fc",
    blurb: "Deposits, richness, and the resources they hold.", kind: "article", href: "#/browse/mineral" },
  { ns: "ship", label: "Starships", singular: "Starship", glyph: "➤", accent: "#60a5fa",
    blurb: "Notable ships, classes, and where to find them.", kind: "article", href: "#/browse/ship" },
  { ns: "freighter", label: "Freighters", singular: "Freighter", glyph: "▰", accent: "#93c5fd",
    blurb: "Capital ships, fleet designs, and frigate fleets.", kind: "article", href: "#/browse/freighter" },
  { ns: "exocraft", label: "Exocraft", singular: "Exocraft", glyph: "◎", accent: "#fb923c",
    blurb: "Roamer, Nomad, Pilgrim, Colossus, Minotaur, Nautilon.", kind: "article", href: "#/browse/exocraft" },
  { ns: "tool", label: "Multi-Tools", singular: "Multi-Tool", glyph: "⚙", accent: "#c084fc",
    blurb: "Tool finds, archetypes, and stats.", kind: "article", href: "#/browse/tool" },
  { ns: "base", label: "Bases & Builds", singular: "Base", glyph: "⌂", accent: "#fbbf24",
    blurb: "Player bases, megabuilds, and blueprints.", kind: "article", href: "#/browse/base" },
  { ns: "event", label: "Events", singular: "Event", glyph: "◆", accent: "#fb7185",
    blurb: "Expeditions, festivals, and community milestones.", kind: "article", href: "#/browse/event" },
  { ns: "lore", label: "Lore & Story", singular: "Lore page", glyph: "✶", accent: "#a78bfa",
    blurb: "Atlas, Sentinels, Travellers — the deep story.", kind: "article", href: "#/browse/lore" },
  { ns: "guide", label: "Guides", singular: "Guide", glyph: "❖", accent: "#2dd4bf",
    blurb: "How-to articles written by the community.", kind: "article", href: "#/browse/guide" },
  { ns: "mechanic", label: "Game Mechanics", singular: "Mechanic", glyph: "⚛", accent: "#818cf8",
    blurb: "Crafting, combat, economy, and systems.", kind: "article", href: "#/browse/mechanic" },
  { ns: "item", label: "Items & Resources", singular: "Item", glyph: "◈", accent: "#facc15",
    blurb: "Elements, products, tech, and tradeables.", kind: "article", href: "#/browse/item" },
];

export const NS_BY_KEY: Record<string, NamespaceDef> = Object.fromEntries(
  NAMESPACES.map((n) => [n.ns, n]),
);

export const ARTICLE_NAMESPACES: NamespaceDef[] = NAMESPACES.filter((n) => n.kind === "article");

/** Clusters for the portal + home spine, in display order. */
export interface NamespaceGroup {
  label: string;
  keys: string[];
}

export const NAMESPACE_GROUPS: NamespaceGroup[] = [
  { label: "Places", keys: ["system", "planet"] },
  { label: "Life & Geology", keys: ["creature", "flora", "mineral"] },
  { label: "Ships & Gear", keys: ["ship", "freighter", "exocraft", "tool"] },
  { label: "Community", keys: ["civ", "traveler", "base", "event"] },
  { label: "Knowledge", keys: ["lore", "guide", "mechanic", "item"] },
];
