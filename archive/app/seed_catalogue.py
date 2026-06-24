"""
Seed a small, FACTUAL catalogue (with facets) so the merged wiki + its
filters aren't empty for review.

NOT the old hallucinated demo seed (that lives in app/seed.py, opt-in
behind ARCHIVE_SEED=demo). The pages here are real, uncontroversial NMS
reference facts across the authored sections, each tagged with structured
facets so the Browse filter rail works. Plus two real community members as
dev users so the dev login can demonstrate create/edit.

Idempotent on slug. Run explicitly (NOT wired into entrypoint.sh, to keep
prod a true fresh start):

    python -m app.seed_catalogue
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from .db import session_scope

log = logging.getLogger("archive.seed_catalogue")


USERS: list[dict[str, Any]] = [
    {
        "discord_id": "seed-ekimo", "discord_username": "ekimo", "display_name": "Ekimo",
        "avatar_letter": "E", "avatar_color": "purple", "civ_slug": None,
        "base_role": "historian", "is_editor": 1, "is_admin": 1,
        "bio": "Founder of Voyager's Haven. Maintains the Haven atlas and this archive.",
    },
    {
        "discord_id": "seed-stars", "discord_username": "stars", "display_name": "Stars",
        "avatar_letter": "S", "avatar_color": "teal", "civ_slug": None,
        "base_role": "diplomat", "is_editor": 0, "is_admin": 0,
        "bio": "Cartographer. Contributes catalogue pages and field notes.",
    },
]


# Factual reference pages with structured facets (so filtering demos work).
ARTICLES: list[dict[str, Any]] = [
    # ---- lore ----
    {
        "namespace": "lore", "slug": "the-atlas", "title": "The Atlas",
        "subtitle": "The cosmic entity at the centre of the No Man's Sky narrative.",
        "body": "The **Atlas** is the enigmatic entity at the heart of No Man's Sky's central story. It "
                "presents itself to Travellers through red Atlas Interfaces scattered across the galaxies and is "
                "bound up with the nature of the simulation itself.\n\nThis page collects community-facing facts "
                "about the Atlas. In-game narrative text is the primary source; interpretation is flagged.",
        "infobox": [{"label": "Type", "value": "Cosmic entity"}, {"label": "Appears as", "value": "Atlas Interface (red)"}],
        "sources": [{"quality": "primary", "text": "In-game Atlas narrative text"}, {"quality": "community", "text": "Community lore analysis"}],
        "facets": {"topic": ["Atlas"], "canonicity": ["In-game canon"], "lifeform_scope": ["Mixed"], "source_type": ["Story-mission"], "arc_stage": ["Atlas Path"]},
    },
    {
        "namespace": "lore", "slug": "sentinels", "title": "Sentinels",
        "subtitle": "Autonomous drones that police planetary activity.",
        "body": "**Sentinels** are self-replicating machines that monitor and enforce order on most planets. "
                "Disturbing the environment raises a wanted level that escalates the response from drones to "
                "quadrupeds, walkers and starships. Sentinel activity varies by planet, from *Low* to *Aggressive*.",
        "infobox": [{"label": "Type", "value": "Autonomous drones"}, {"label": "Activity", "value": "Low → Aggressive"}],
        "sources": [{"quality": "primary", "text": "In-game Sentinel behaviour"}],
        "facets": {"topic": ["Sentinels"], "canonicity": ["In-game canon"], "lifeform_scope": ["Sentinel"], "source_type": ["NPC dialogue"]},
    },
    # ---- item ----
    {
        "namespace": "item", "slug": "activated-indium", "title": "Activated Indium",
        "subtitle": "A high-value stellar metal mined on blue-star worlds.",
        "body": "**Activated Indium** is a premium stellar metal found on planets orbiting blue stars. Its high "
                "per-unit value underpins many late-game mining operations and large automated extraction setups.",
        "infobox": [{"label": "Type", "value": "Stellar metal"}, {"label": "Found on", "value": "Blue-star planets"}, {"label": "Value", "value": "High"}],
        "sources": [{"quality": "secondary", "text": "Community resource pricing data"}],
        "facets": {"category": ["Element/Raw"], "element_division": ["Stellar"], "rarity": ["Rare"], "where_sourced": ["Mining", "Stellar"], "star_gating": ["Blue"]},
    },
    {
        "namespace": "item", "slug": "quicksilver", "title": "Quicksilver",
        "subtitle": "A special currency earned from community and Nexus missions.",
        "body": "**Quicksilver** is a premium currency separate from Units and Nanites. It is earned mainly "
                "through Nexus community missions and spent at the Quicksilver Synthesis Companion on cosmetics.",
        "infobox": [{"label": "Type", "value": "Premium currency"}, {"label": "Earned from", "value": "Nexus missions"}],
        "sources": [{"quality": "primary", "text": "In-game Nexus / Quicksilver Companion"}],
        "facets": {"category": ["Curiosity"], "rarity": ["Rare"], "where_sourced": ["NPC/Mission"]},
    },
    # ---- mechanic ----
    {
        "namespace": "mechanic", "slug": "portals", "title": "Portals",
        "subtitle": "Ancient gateways that enable instant travel via 16-glyph addresses.",
        "body": "**Portals** let a Traveller jump directly to any system whose address they know, encoded as 16 "
                "glyphs. The first glyph is the planet index; the rest encode the galactic coordinates. Portal "
                "addresses are the backbone of community cartography — Haven stores them for every logged system.",
        "infobox": [{"label": "Address length", "value": "16 glyphs"}, {"label": "Use", "value": "Instant system travel"}],
        "sources": [{"quality": "primary", "text": "In-game portal mechanics"}],
        "facets": {"category": ["Navigation"], "subsystem": ["Portals"], "activity": ["Exploring"], "introduced": ["Genesis (2016)"], "status": ["Current"]},
    },
    # ---- ship / tool reference overviews (no instance facets) ----
    {
        "namespace": "ship", "slug": "starship-classes", "title": "Starship Classes",
        "subtitle": "The C / B / A / S quality tiers and the main archetypes.",
        "body": "Every starship has a **class** — C, B, A or S in ascending quality — that bounds its stat ranges "
                "and supercharged-slot count. Ships also fall into archetypes (Fighter, Hauler, Explorer, Shuttle, "
                "Exotic, Solar, Sentinel Interceptor, Living Ship, and the built Corvette), each biased to a role.",
        "infobox": [{"label": "Classes", "value": "C · B · A · S"}],
        "sources": [{"quality": "secondary", "text": "Community ship documentation"}],
    },
    {
        "namespace": "tool", "slug": "multi-tool-classes", "title": "Multi-Tool Classes",
        "subtitle": "Tool quality tiers and the common archetypes.",
        "body": "**Multi-Tools** share the C / B / A / S class system and come in types including Pistol, Rifle, "
                "Experimental, Alien, Royal, Sentinel, Atlantid and the Voltaic Staff.",
        "infobox": [{"label": "Classes", "value": "C · B · A · S"}],
        "sources": [{"quality": "secondary", "text": "Community multi-tool documentation"}],
    },
    {
        "namespace": "creature", "slug": "fauna-overview", "title": "Fauna",
        "subtitle": "How creatures are catalogued across planets.",
        "body": "**Fauna** are the procedurally generated creatures inhabiting most planets, recorded by genus, "
                "temperament and diet. A planet's fauna count is complete once every species is discovered.",
        "infobox": [{"label": "Recorded by", "value": "Genus · temperament · diet"}],
        "sources": [{"quality": "primary", "text": "In-game discovery / analysis visor"}],
    },
    {
        "namespace": "guide", "slug": "logging-systems-in-haven", "title": "Logging systems the Haven way",
        "subtitle": "Conventions for consistent, searchable catalogue entries.",
        "body": "Consistent entries keep the archive searchable:\n\n- **Name the region first**, then the system.\n"
                "- **Tag the civilization** that holds the system.\n- **Always attach a source** — even \"I was "
                "there\" counts as community-attested.\n- Record the **portal glyphs**; they're the durable address.",
        "infobox": [{"label": "Difficulty", "value": "Beginner"}, {"label": "Time", "value": "~10 min"}],
        "sources": [{"quality": "community", "text": "Haven cartography conventions"}],
        "facets": {"topic_area": ["Getting Started", "Navigation"], "difficulty": ["Beginner"], "patch_relevance": ["Version-agnostic"], "format": ["Tips"]},
    },

    # ---- new-section reference pages (factual named things) ----
    {
        "namespace": "ship", "slug": "sentinel-interceptor", "title": "Sentinel Interceptor",
        "subtitle": "The Sentinel starship, recovered from crashed Interceptors on dissonant worlds.",
        "body": "The **Sentinel Interceptor** is a combat-focused starship of Sentinel make, added in the Interceptor "
                "update (2023). Interceptors are found by repairing crashed examples on **dissonant** (corrupted) "
                "planets, and are effectively always S-class.",
        "infobox": [{"label": "Make", "value": "Sentinel"}, {"label": "Found on", "value": "Dissonant planets"}],
        "sources": [{"quality": "primary", "text": "In-game Interceptor update"}],
        "facets": {"archetype": ["Sentinel Interceptor"], "class": ["S"], "bonus": ["Combat"], "procurement": ["Procedural"], "where_found": ["Dissonant planet", "Crashed ship"]},
    },
    {
        "namespace": "tool", "slug": "voltaic-staff", "title": "Voltaic Staff",
        "subtitle": "A two-handed multi-tool assembled from parts at an Autophage terminal.",
        "body": "The **Voltaic Staff** is a staff-form multi-tool added in the Echoes update (2023). Unlike other "
                "tools it is **built** from a Head, Core and Pole rather than rolled, crafted at an Autophage "
                "Synthesis terminal. It favours damage and scanning.",
        "infobox": [{"label": "Form", "value": "Staff (two-handed)"}, {"label": "Acquired", "value": "Built (Autophage)"}],
        "sources": [{"quality": "primary", "text": "In-game Echoes update"}],
        "facets": {"type": ["Voltaic Staff"], "class": ["S"], "bonus": ["Damage"], "handedness": ["Two-handed"], "where_found": ["Autophage terminal"]},
    },
    {
        "namespace": "flora", "slug": "star-bulb", "title": "Star Bulb",
        "subtitle": "The lush-biome flora resource.",
        "body": "**Star Bulb** is the signature harvestable plant of **Lush** biomes. Picking it requires no hazard "
                "protection and it's a common early farming staple, used in many crafting and cooking recipes.",
        "infobox": [{"label": "Biome", "value": "Lush"}, {"label": "Harvestable", "value": "Yes"}],
        "sources": [{"quality": "primary", "text": "In-game flora"}],
        "facets": {"biome": ["Lush"], "resource_yielded": ["Star Bulb"], "form": ["Flower"], "rarity": ["Common"], "harvestable": ["true"]},
    },
    {
        "namespace": "mineral", "slug": "indium", "title": "Indium",
        "subtitle": "The blue-star stellar metal.",
        "body": "**Indium** is the headline stellar metal of **blue** star systems, sitting at the top of the "
                "Copper → Cadmium → Emeril → Indium progression. It refines into Activated Indium and is mined from "
                "deposits and hotspots on blue-star worlds.",
        "infobox": [{"label": "Star", "value": "Blue"}, {"label": "Refines to", "value": "Activated Indium"}],
        "sources": [{"quality": "primary", "text": "In-game mineral system"}],
        "facets": {"resource": ["Indium"], "richness": ["A"], "deposit_type": ["Resource Deposit", "Deep-Level (Hotspot)"], "star_gating": ["Blue"]},
    },
    {
        "namespace": "exocraft", "slug": "nautilon", "title": "Nautilon",
        "subtitle": "The submersible exocraft for underwater exploration.",
        "body": "The **Nautilon** is a submarine exocraft built for deep-water exploration, added in the Abyss "
                "update. It lets Travellers descend safely, mine underwater resources and reach sunken points of "
                "interest.",
        "infobox": [{"label": "Type", "value": "Submarine"}, {"label": "Domain", "value": "Underwater"}],
        "sources": [{"quality": "primary", "text": "In-game Abyss update"}],
        "facets": {"type": ["Nautilon"], "terrain": ["Sea"], "use": ["Underwater", "Exploration"]},
    },
    {
        "namespace": "freighter", "slug": "sentinel-dreadnought", "title": "Sentinel Dreadnought freighter",
        "subtitle": "The angular Sentinel-style capital freighter design.",
        "body": "**Sentinel / Dreadnought** is one of the two broad freighter design families (the other being the "
                "Venator/Resurgent style). Capital freighters are the largest, with the most base-building room and "
                "fleet capacity, and are rescued during space battles or bought at stations.",
        "infobox": [{"label": "Design", "value": "Sentinel / Dreadnought"}, {"label": "Tier", "value": "Capital"}],
        "sources": [{"quality": "secondary", "text": "Community freighter documentation"}],
        "facets": {"design": ["Sentinel/Dreadnought"], "class": ["S"], "where_found": ["Space-battle rescue", "Derelict"]},
    },
    {
        "namespace": "creature", "slug": "diplo", "title": "Diplos (Rangifae)",
        "subtitle": "The large, docile long-necked herbivores of the Rangifae genus.",
        "body": "**Diplos** are among the most recognisable No Man's Sky creatures — large, gentle, long-necked "
                "herbivores of the **Rangifae** genus. They graze peacefully, pose no threat, and (being ground "
                "fauna) can be ridden once tamed.",
        "infobox": [{"label": "Genus", "value": "Rangifae"}, {"label": "Temperament", "value": "Docile / Prey"}],
        "sources": [{"quality": "community", "text": "Community field notes"}],
        "facets": {"genus": ["Rangifae"], "ecosystem": ["Ground"], "temperament": ["Prey"], "diet": ["Herbivore"], "rarity": ["Uncommon"], "rideable": ["true"]},
    },
    {
        "namespace": "event", "slug": "voyagers-expedition", "title": "Voyagers Expedition",
        "subtitle": "The community expedition that shipped alongside the Voyagers update.",
        "body": "**Voyagers** is one of Hello Games' official, time-limited Expeditions — a shared seed all players "
                "start together, completing milestones for unique rewards. It accompanied the Voyagers (6.0) update.",
        "infobox": [{"label": "Type", "value": "Official Expedition"}, {"label": "Host", "value": "Hello Games"}],
        "sources": [{"quality": "primary", "text": "Official Voyagers update notes"}],
        "facets": {"date": ["2025-09-01"], "type": ["Expedition"], "expedition": ["Voyagers"], "status": ["Past"], "scale": ["Universe-wide"]},
    },
]


def _seed_users(s) -> None:
    inserted = 0
    for u in USERS:
        if s.execute(text("SELECT 1 FROM archive_user WHERE discord_id = :d"), {"d": u["discord_id"]}).first():
            continue
        s.execute(
            text(
                "INSERT INTO archive_user (discord_id, discord_username, display_name, "
                "avatar_letter, avatar_color, civ_slug, base_role, is_editor, is_admin, bio) "
                "VALUES (:discord_id, :discord_username, :display_name, :avatar_letter, "
                ":avatar_color, :civ_slug, :base_role, :is_editor, :is_admin, :bio)"
            ),
            u,
        )
        inserted += 1
    log.info("seed_catalogue: archive_user — inserted %d, skipped %d", inserted, len(USERS) - inserted)


def _seed_articles(s) -> None:
    author = s.execute(text("SELECT id FROM archive_user WHERE discord_username = 'ekimo'")).first()
    author_id = author.id if author else None
    inserted = 0
    facet_rows = 0
    for a in ARTICLES:
        if s.execute(text("SELECT 1 FROM article WHERE slug = :s"), {"s": a["slug"]}).first():
            continue
        res = s.execute(
            text(
                "INSERT INTO article (namespace, slug, title, subtitle, body, "
                "infobox_json, sources_json, civ_slug, created_by) "
                "VALUES (:namespace, :slug, :title, :subtitle, :body, "
                ":infobox_json, :sources_json, :civ_slug, :created_by)"
            ),
            {
                "namespace": a["namespace"], "slug": a["slug"], "title": a["title"],
                "subtitle": a.get("subtitle"), "body": a.get("body", ""),
                "infobox_json": json.dumps(a.get("infobox", [])),
                "sources_json": json.dumps(a.get("sources", [])),
                "civ_slug": a.get("civ_slug"), "created_by": author_id,
            },
        )
        aid = res.lastrowid
        for key, vals in (a.get("facets") or {}).items():
            for v in vals:
                s.execute(
                    text("INSERT INTO article_facet (article_id, key, value) VALUES (:a, :k, :v)"),
                    {"a": aid, "k": key, "v": v},
                )
                facet_rows += 1
        inserted += 1
    log.info("seed_catalogue: article — inserted %d (skipped %d), facet rows %d",
             inserted, len(ARTICLES) - inserted, facet_rows)


def seed_catalogue() -> None:
    log.info("seed_catalogue: inserting factual anchor content")
    with session_scope() as s:
        _seed_users(s)
        _seed_articles(s)
    log.info("seed_catalogue complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    seed_catalogue()
