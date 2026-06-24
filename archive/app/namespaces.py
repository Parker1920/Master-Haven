"""
Catalogue namespace registry — backend source of truth.

The catalogue (the wiki half of the merged Archive) is organized into
namespaces. Three kinds:

- ARTICLE namespaces  → generic, writable through /api/v1/articles, backed
                        by the `article` table.
- SPECIAL namespaces  → have their own richer table + page. Only `civ`
                        (the `civilization` table) today.
- SYNCED namespaces   → sourced from the live Haven atlas (systems/planets),
                        never hand-authored here. Surfaced as catalogue
                        tiles but wired to live data in a later phase.

The frontend keeps its own copy of the display metadata (label, glyph,
accent, blurb) for rendering; this module is the authority on which
namespaces are writable and what the article table will accept.
"""

from __future__ import annotations

# Generic article namespaces — the writable wiki catalogue.
ARTICLE_NAMESPACES: tuple[str, ...] = (
    "traveler",
    "creature",
    "flora",
    "mineral",
    "ship",
    "freighter",
    "exocraft",
    "tool",
    "base",
    "event",
    "lore",
    "guide",
    "mechanic",
    "item",
)

# Namespaces backed by their own table (rich page), not `article`.
SPECIAL_NAMESPACES: tuple[str, ...] = ("civ",)

# Namespaces sourced from the live Haven atlas (deferred — not authored).
SYNCED_NAMESPACES: tuple[str, ...] = ("system", "planet")

# Ordered list used by the /namespaces endpoint so the portal can render
# every tile (with live counts) in a stable order.
ALL_NAMESPACES: tuple[str, ...] = (
    "civ",
    "traveler",
    "system",
    "planet",
    "creature",
    "flora",
    "mineral",
    "ship",
    "freighter",
    "exocraft",
    "tool",
    "base",
    "event",
    "lore",
    "guide",
    "mechanic",
    "item",
)


def namespace_kind(ns: str) -> str:
    if ns in ARTICLE_NAMESPACES:
        return "article"
    if ns in SPECIAL_NAMESPACES:
        return "special"
    if ns in SYNCED_NAMESPACES:
        return "synced"
    return "unknown"


def is_article_namespace(ns: str) -> bool:
    return ns in ARTICLE_NAMESPACES
