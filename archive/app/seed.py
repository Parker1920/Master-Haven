"""
Seed the database with mock data extracted from the v0.9 mockup.

Runs idempotently — every INSERT is guarded by an existence check, so
calling this on every container boot is safe. The data here mirrors
the CIVS / PEOPLE / STORIES / INQUISITIONS JavaScript objects in
docs/v0.9-mockup.html so the live API can render the equivalent of
every mockup page.

Run as: `python -m app.seed`. The entrypoint.sh script runs this
after `alembic upgrade head`.

Edit-friendly notes:
- Add a new civ: append to CIVS list, run `python -m app.seed`.
- Same for people / stories / inquisitions.
- All cross-table joins are populated explicitly below.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from .db import session_scope

log = logging.getLogger("archive.seed")


# =====================================================================
# DATA
# =====================================================================

# Eight personas from the mockup. Discord IDs are synthetic ("seed-X")
# so they don't collide with real Discord IDs from the Phase 7 sync.
PEOPLE: list[dict[str, Any]] = [
    {
        "discord_id": "seed-ekimo",
        "discord_username": "ekimo",
        "display_name": "Ekimo",
        "avatar_letter": "E",
        "avatar_color": "purple",
        "civ_slug": "voyagers-haven",
        "bio": "Founder of Voyager's Haven. Built the Haven Control Room, the Keeper bot, and this archive.",
        "base_role": "historian",
        "is_editor": 1,
        "is_admin": 1,
    },
    {
        "discord_id": "seed-stars",
        "discord_username": "stars",
        "display_name": "Stars",
        "avatar_letter": "S",
        "avatar_color": "pink",
        "civ_slug": "voyagers-haven",
        "bio": "Lead cartographer at Voyager's Haven. Rebuilt the Keeper bot from scratch.",
        "base_role": "diplomat",
        "is_editor": 1,
        "is_admin": 0,
    },
    {
        "discord_id": "seed-watcher",
        "discord_username": "watcher",
        "display_name": "Watcher",
        "avatar_letter": "W",
        "avatar_color": "teal",
        "civ_slug": "voyagers-haven",
        "beat": "The Galactic Hub",
        "bio": "Diplomat embedded with the Galactic Hub. Covers Hub regional politics and the Quicksilver Wars.",
        "base_role": "diplomat",
        "is_editor": 0,
        "is_admin": 0,
    },
    {
        "discord_id": "seed-lucca",
        "discord_username": "lucca",
        "display_name": "Lucca",
        "avatar_letter": "L",
        "avatar_color": "amber",
        "civ_slug": "voyagers-haven",
        "beat": "Atlas Foundation",
        "bio": "Diplomat on the Atlas Foundation beat. Annual gathering coverage, lore tracking.",
        "base_role": "diplomat",
        "is_editor": 0,
        "is_admin": 0,
    },
    {
        "discord_id": "seed-jaina",
        "discord_username": "jaina",
        "display_name": "Jaina",
        "avatar_letter": "J",
        "avatar_color": "coral",
        "civ_slug": "voyagers-haven",
        "beat": "Multi-civ",
        "bio": "Cross-civ diplomatic desk. Trade corridors, treaties, multilateral relations.",
        "base_role": "diplomat",
        "is_editor": 0,
        "is_admin": 0,
    },
    {
        "discord_id": "seed-todd",
        "discord_username": "todd",
        "display_name": "Todd",
        "avatar_letter": "T",
        "avatar_color": "slate",
        "civ_slug": "voyagers-haven",
        "beat": "Conflicts",
        "bio": "Conflicts desk. Covers skirmishes, declared wars, and informal trader blocs.",
        "base_role": "diplomat",
        "is_editor": 0,
        "is_admin": 0,
    },
    {
        "discord_id": "seed-shadow",
        "discord_username": "shadow",
        "display_name": "Shadow",
        "avatar_letter": "Sh",
        "avatar_color": "green",
        "civ_slug": "voyagers-haven",
        "beat": "HAD.SH",
        "bio": "Diplomat on the HAD.SH beat. Federation projects, database integration.",
        "base_role": "diplomat",
        "is_editor": 0,
        "is_admin": 0,
    },
    {
        "discord_id": "seed-thekeeper",
        "discord_username": "thekeeper",
        "display_name": "TheKeeper",
        "avatar_letter": "K",
        "avatar_color": "coral",
        "civ_slug": "the-archivist",
        "bio": "Lead Historian. Authoring the multi-year Galactic Hub inquisition.",
        "base_role": "historian",
        "is_editor": 1,
        "is_admin": 0,
    },
]


# Nine civilizations from the mockup, plus 'the-archivist' as TheKeeper's
# home civ. Without that 10th civ, TheKeeper's civ_slug would dangle.
CIVS: list[dict[str, Any]] = [
    {
        "slug": "galactic-hub",
        "name": "The Galactic Hub",
        "status": "active",
        "galaxy": "Euclid",
        "founded": "c. 2017",
        "founded_year": 2017,
        "tagline": "16 regions · 4,000+ explorers",
        "description": "The largest civilization in Euclid. Founded c. 2017. Comprises 16 named regions across multiple galaxies.",
        "color_primary": "#042C53",
        "color_secondary": "#0F6E56",
    },
    {
        "slug": "voyagers-haven",
        "name": "Voyager's Haven",
        "status": "active",
        "galaxy": "Euclid",
        "founded": "2025",
        "founded_year": 2025,
        "tagline": "workshop community · ~50 members",
        "description": "A community focused on building public tools for the multiverse. Operates Haven Control Room, the Keeper bot, the Postal System, and is building an economy and an archive.",
        "color_primary": "#534AB7",
        "color_secondary": "#1D9E75",
    },
    {
        "slug": "eyfert-khannate",
        "name": "Eyfert Khannate",
        "status": "active",
        "galaxy": "Hilbert",
        "founded": "2021",
        "founded_year": 2021,
        "tagline": "~200 explorers",
        "description": "A long-established community in Hilbert. Known for its diplomatic rigor and structured trade agreements.",
        "color_primary": "#4A1B0C",
        "color_secondary": "#993C1D",
    },
    {
        "slug": "fas",
        "name": "Federation of Allied Stars",
        "status": "active",
        "galaxy": "Euclid",
        "founded": "2019",
        "founded_year": 2019,
        "tagline": "alliance of 12 communities",
        "description": "An alliance of 12 communities founded in 2019 around shared exploration standards.",
        "color_primary": "#1F2D3A",
        "color_secondary": "#042C53",
    },
    {
        "slug": "atlas-foundation",
        "name": "Atlas Foundation",
        "status": "active",
        "galaxy": "Multi-galaxy",
        "founded": "2018",
        "founded_year": 2018,
        "tagline": "roleplay collective · ~600 members",
        "description": "A multi-galaxy roleplay collective centered on Atlas mythology and lore. ~600 members across multiple regions.",
        "color_primary": "#5C1F4D",
        "color_secondary": "#993556",
    },
    {
        "slug": "hadsh",
        "name": "HAD.SH",
        "status": "active",
        "galaxy": "Euclid",
        "founded": "2020",
        "founded_year": 2020,
        "tagline": "cataloging community · ~80 members",
        "description": "A community focused on cataloging exploration data. Builds federated databases that integrate with the Travelers Collective.",
        "color_primary": "#173404",
        "color_secondary": "#639922",
    },
    {
        "slug": "lazarus",
        "name": "Lazarus Collective",
        "status": "active",
        "galaxy": "Eissentam",
        "founded": "2025",
        "founded_year": 2025,
        "tagline": "7 members · documentation focus",
        "description": "A small documentation-focused collective that formed in Eissentam. Modeled on the Haven Control Room.",
        "color_primary": "#633806",
        "color_secondary": "#C18C2D",
    },
    {
        "slug": "hub-cartographers",
        "name": "The Hub Cartographers",
        "status": "dormant",
        "galaxy": "Euclid",
        "founded": "2018",
        "founded_year": 2018,
        "ended": "2022",
        "ended_year": 2022,
        "tagline": "cartography splinter",
        "description": "A cartography-focused splinter group from the Galactic Hub, active 2018-2022.",
        "color_primary": "#888780",
        "color_secondary": "#a8b5c8",
    },
    {
        "slug": "old-travelers-guild",
        "name": "The Old Travelers Guild",
        "status": "archived",
        "galaxy": "Euclid",
        "founded": "2017",
        "founded_year": 2017,
        "ended": "2019",
        "ended_year": 2019,
        "tagline": "one of the earliest civs",
        "description": "One of the earliest documented NMS civilizations. Disbanded 2019. ~80 members at peak.",
        "color_primary": "#C18C2D",
        "color_secondary": "#FAC775",
    },
    {
        "slug": "the-archivist",
        "name": "The Archivist",
        "status": "active",
        "galaxy": "Multi-galaxy",
        "founded": "2026",
        "founded_year": 2026,
        "tagline": "historian collective",
        "description": "A small collective of historians who maintain the long-form inquisitions in this archive.",
        "color_primary": "#26215C",
        "color_secondary": "#FAC775",
    },
]


# Eight stories from the mockup STORIES dict (full body preserved so
# the story reader page has real content).
STORIES: list[dict[str, Any]] = [
    {
        "slug": "haven-keeper-postal",
        "doctype": "brief",
        "headline": "Big week for Haven: Keeper bot and Postal System launch",
        "deck": "The Haven shipped two community-facing tools this week: the Keeper bot deployed to Discord, and a postal system generating galaxy posters and player stat cards from URLs.",
        "body": "Voyager's Haven released two community tools within 48 hours of each other this week — the Keeper bot, a Discord integration for community management and historical retrieval, and the Postal System, a generator that creates custom galaxy posters and player stat cards from a URL passed through Discord, Twitter, or Messenger.\n\nBoth tools are free for any civilization to use. The Postal System, in particular, addresses a long-standing gap in NMS social tooling: the ability to share visual representations of a player's discoveries without manual screenshot work.\n\n\"This is what we mean when we say workshop community,\" said Stars, the Haven's lead cartographer. \"We build things, we publish them, other civs use them. That's the loop.\"\n\nThe Keeper bot, in particular, has been in development across multiple iterations. An earlier version went silent for several months before Stars rebuilt the entire codebase from scratch. The current version — which is what shipped this week — bears almost no relation to the original architecturally, even though the user-facing functionality has been preserved and expanded.",
        "beat": "projects",
        "civs": ["voyagers-haven"],
        "author_slug": "stars",
        "published_at": "2026-04-30T12:00:00",
    },
    {
        "slug": "hub-restructure",
        "doctype": "brief",
        "headline": "Hub announces 16-region restructure",
        "deck": "After six months of internal debate, Hub leadership confirmed the new structure today. Three regions merge; two new ones split off.",
        "body": "The Galactic Hub's leadership council confirmed a long-anticipated restructure at this morning's all-hands meeting in the Hub's primary capital system. Under the new arrangement, three older Euclid-galaxy regions will merge into a single new region, while two regions in Eissentam will split into two distinct regional councils.\n\nA sixth change formally recognizes a corridor that members have informally called \"the Western Reach\" for over a year.\n\n\"We've outgrown the old map,\" one regional coordinator said in remarks shared on the Hub's Discord. \"What we built six years ago worked when we had four hundred members. With four thousand, the regional boundaries no longer matched where people actually live and explore.\"\n\nThe Federation of Allied Stars confirmed it would update its diplomatic registry within the week. A Khannate spokesperson reached for comment said only that the Khannate \"looks forward to the new map.\"",
        "beat": "civupdates",
        "civs": ["galactic-hub"],
        "author_slug": "watcher",
        "published_at": "2026-04-30T17:13:00",
    },
    {
        "slug": "atlas-gathering",
        "doctype": "brief",
        "headline": "Atlas Foundation Gathering opens — 400+ travelers expected",
        "deck": "The annual gathering opened tonight near the Atlas Origin. Live coverage continues through the weekend.",
        "body": "The Atlas Foundation's annual gathering opened tonight at coordinates near the Atlas Origin, with attendance figures projected at over 400 travelers across the weekend.\n\nThe opening session featured the traditional Atlas readings, followed by smaller breakout sessions on lore developments and new initiatives within the Foundation. Live coverage from this writer will continue through the weekend.\n\nThis is the eighth annual gathering, and the largest in projected attendance since 2022.",
        "beat": "events",
        "civs": ["atlas-foundation"],
        "author_slug": "lucca",
        "published_at": "2026-04-30T15:00:00",
    },
    {
        "slug": "khannate-fas-trade",
        "doctype": "brief",
        "headline": "Khannate opens trade corridor with Federation of Allied Stars",
        "deck": "First formal trade agreement between the two communities. Limited to Quicksilver components for now.",
        "body": "The Eyfert Khannate and the Federation of Allied Stars announced their first formal trade agreement yesterday — a limited corridor focused on Quicksilver Companion components.\n\nThe agreement was finalized at the Khannate's eastern outpost during a three-day negotiation session attended by representatives from both communities. While the initial scope is narrow, both sides indicated the possibility of expansion if the corridor performs as expected.\n\n\"This is a starting point, not a finishing point,\" a Khannate spokesperson said.\n\nThe deal sidesteps the broader Quicksilver Wars, in which neither civ has formally taken a position.",
        "beat": "diplomacy",
        "civs": ["eyfert-khannate", "fas"],
        "author_slug": "jaina",
        "published_at": "2026-04-29T14:00:00",
    },
    {
        "slug": "quicksilver-skirmish-3",
        "doctype": "brief",
        "headline": "Third Quicksilver Wars skirmish reported in Hub border region",
        "deck": "No formal civ involvement claimed. Independent traders organizing into informal blocs.",
        "body": "A third skirmish in the ongoing Quicksilver Wars was reported this week in the Hub border region, marking an escalation in what has been a slow-burning conflict between independent trader blocs.\n\nNo formal civilizations have claimed involvement, and both the Galactic Hub and the Federation of Allied Stars have denied any direct participation. However, sources within the conflict suggest informal networks of traders are increasingly aligning along civ lines.\n\nThe Inquisition currently underway on the Quicksilver Wars (Inquisition XLVII) will document this latest incident as part of its broader investigation.",
        "beat": "conflicts",
        "civs": [],                        # 'multi-civ' label — no specific civ tagged
        "author_slug": "todd",
        "published_at": "2026-04-28T10:00:00",
    },
    {
        "slug": "hadsh-v3",
        "doctype": "brief",
        "headline": "HAD.SH releases v3 of their cataloging platform",
        "deck": "The new version adds Travelers Collective integration and federated database support.",
        "body": "HAD.SH has released v3 of its cataloging platform this week, adding integration with the Travelers Collective and federated database support — a key piece of the long-planned Phase B rollout.\n\nThe Phase B rollout, originally scheduled for earlier this year, will federate HAD.SH's exploration database with the Haven Control Room, allowing both communities to share verified discoveries while maintaining separate identities and ownership.\n\n\"This was the technical work that had to happen first,\" said a HAD.SH spokesperson. \"Now we can actually federate.\"",
        "beat": "civupdates",
        "civs": ["hadsh"],
        "author_slug": "shadow",
        "published_at": "2026-04-27T11:30:00",
    },
    {
        "slug": "haven-feature",
        "doctype": "feature",
        "headline": "Inside the Haven: how five tools became a workshop for the multiverse",
        "deck": "Seven months ago, Voyager's Haven didn't exist. Today the community runs Haven Control Room, an exploration database, the Keeper bot, the Postal System, and is building both an economy and an archive — all built in public, all free for any civ that wants them.",
        "body": "Seven months ago, Voyager's Haven didn't exist. Its founder, Ekimo, had been quietly building tools as a hobbyist — small utilities for managing exploration data — but there was no community. There was no Discord server. There was no website. There was just code, and an idea: that the multiverse needed shared infrastructure.\n\nToday, the Haven runs five public-facing tools, with a sixth (this very archive) and a seventh (an internal economy) in active development. Every tool is free. Every tool is open to any civilization that wants to use it. And every tool was built with the same conviction: that the work matters more than the credit.\n\n> \"We don't claim systems we haven't visited. We don't write histories we can't source. That's the whole charter, really.\"\n\nThat charter — written sometime around the founding of the community in late 2025 — has become a kind of organizing principle for the Haven's approach to building.",
        "beat": "projects",
        "civs": ["voyagers-haven"],
        "author_slug": "stars",
        "published_at": "2026-04-30T08:00:00",
        "read_minutes": 12,
    },
    {
        "slug": "keeper-retold",
        "doctype": "feature",
        "headline": "The Keeper, retold: from concept to Stars's rebuild",
        "deck": "The Keeper bot's first iteration was simple. It went silent for months. Then Stars took over and rebuilt it from the ground up.",
        "body": "The first iteration of the Keeper bot did three things: it greeted new members, it pinned messages, and it kept track of who had been promoted to which role.\n\nThat was the original scope. It worked, and for a while, it was enough. The Keeper bot ran in Voyager's Haven Discord without modification for several months, providing a thin layer of automation atop the community's growing membership.\n\nThen it broke.\n\nWhat exactly went wrong is, at this point, not entirely clear. The original codebase had been written quickly, and as the community grew, edge cases multiplied. The bot started missing message pinning. Role assignments occasionally failed silently. Eventually, the bot stopped responding to commands at all, and for a period of about three months, the Haven operated without it entirely.\n\nThis is the point at which Stars stepped in.",
        "beat": "projects",
        "civs": ["voyagers-haven"],
        "author_slug": "lucca",
        "published_at": "2026-04-26T14:00:00",
        "read_minutes": 8,
    },
    {
        "slug": "why-hub-waited",
        "doctype": "feature",
        "headline": "Why the Hub waited six months",
        "deck": "Inside the deliberation that led to today's region restructure announcement — interviews with three regional coordinators on what almost broke and what saved it.",
        "body": "The Hub did not announce its 16-region restructure on a whim. According to three regional coordinators interviewed for this piece, the deliberation began at the Hub's Spring Summit in October, and it nearly didn't conclude.\n\n\"There was a moment,\" said one coordinator, \"where we thought we were going to split the Hub itself.\"\n\nThe contention was not about whether the existing 14-region structure was working — it wasn't, and that had been clear to leadership for some time. The contention was about what to replace it with. Three competing proposals reached the floor at the Spring Summit, ranging from a relatively minor adjustment of the existing borders to a full re-architecture of the Hub's regional system.\n\nWhat ultimately won out was a compromise: three older Euclid regions would merge to address overlap problems, two Eissentam regions would split to address growth, and a corridor that had been informally called \"the Western Reach\" for over a year would be formally recognized.\n\nThis piece will be supplemented with additional reporting in the coming days as the new structure takes effect.",
        "beat": "civupdates",
        "civs": ["galactic-hub"],
        "author_slug": "watcher",
        "published_at": "2026-04-23T16:00:00",
        "read_minutes": 14,
    },
]


# Three inquisitions from the mockup.
INQUISITIONS: list[dict[str, Any]] = [
    {
        "slug": "inq-47",
        "numeral": "XLVII",
        "title": "The Quicksilver Wars",
        "subtitle": "2024-present",
        "deck": "A collaborative investigation into the c. 2024-2025 conflict over Quicksilver Companion shop monopolies.",
        "body": "**The question.** What were the precipitating events of the so-called Quicksilver Wars, and to what extent did formal civilizations participate versus independent traders?\n\n**Findings so far.** Initial trade disputes appear to have begun c. 2024 when at least three civilizations independently established Quicksilver-only trade routes. The conflict escalated when route exclusivity claims overlapped in the Hub region.\n\nThe participation of the Federation of Allied Stars remains disputed — primary sources from FAS leadership deny direct involvement, but secondary accounts from independent traders place FAS members at multiple confrontations.\n\n**Open questions.** Date of first organized confrontation (sources vary by 4 months); casualty figures (in-game terms; no canonical count); role of the Atlas Foundation as mediator vs. participant.\n\n**This inquisition is in progress.** Findings are tentative and may change as research continues.",
        "state": "in_progress",
        "progress": 65,
        "sources_count": 12,
        "started_at": "2026-03-08T00:00:00",
        "lead_author_slug": "stars",
        "author_slugs": ["stars", "watcher", "thekeeper", "lucca"],
        "civs": ["galactic-hub", "fas"],
    },
    {
        "slug": "inq-46",
        "numeral": "XLVI",
        "title": "The Galactic Hub: A Decade in the Making",
        "subtitle": "c. 2017-present",
        "deck": "A comprehensive history of the Galactic Hub from founding through present day. Expected to be the largest inquisition the Archive has yet undertaken.",
        "body": "**Scope.** This inquisition aims to document the full history of the Galactic Hub from its founding circa 2017 through the present day. At present, 14 pages have been completed, covering the founding period (2017-2018) and the early expansion (2018-2019).\n\n**Methodology.** Primary sources include interviews with founding members, archived Discord exports, contemporaneous Reddit threads, and Wayback Machine snapshots of the original Hub website (now defunct). Where possible, claims have been cross-referenced across multiple independent sources.\n\n**Coverage so far.** Founding (2017): the original gathering of explorers in Euclid. Early expansion (2018): the establishment of the regional system. The First Schism (2018): the departure of the Hub Cartographers.\n\n**Coverage planned.** The Pact era (2019-2021). The Membership Explosion (2021-2023). The Quicksilver Wars period (2024-present, in coordination with Inquisition XLVII). The recent restructure (2026).\n\n**Status.** Research is ongoing. Estimated completion is six months from this writing.",
        "state": "in_progress",
        "progress": 22,
        "sources_count": 47,
        "started_at": "2026-01-15T00:00:00",
        "lead_author_slug": "thekeeper",
        "author_slugs": ["thekeeper"],
        "civs": ["galactic-hub"],
    },
    {
        "slug": "inq-45",
        "numeral": "XLV",
        "title": "The Atlas Calls",
        "subtitle": "a community's relationship with its own mythology",
        "deck": "An examination of how the Atlas Foundation has navigated the relationship between in-game lore and community identity.",
        "body": "**Closed and published.** This inquisition was closed in March 2026 after eighteen sources were consolidated and reviewed.\n\n**Findings.** The Atlas Foundation occupies a singular position in the multiverse: it is the only major civilization whose identity is built primarily around in-game lore rather than cartographic territory or community function. This inquisition traces the development of that identity from the Foundation's establishment in 2018 through the present, with particular attention to the moments when in-game updates from Hello Games introduced new lore that the Foundation had to assimilate.\n\n**The result.** A community that takes its mythology seriously without conflating it with claims about reality — a balance that, as the inquisition documents, has been managed with remarkable care.",
        "state": "closed",
        "progress": 100,
        "sources_count": 18,
        "started_at": "2025-11-20T00:00:00",
        "closed_at": "2026-03-30T00:00:00",
        "lead_author_slug": "lucca",
        "author_slugs": ["lucca"],
        "civs": ["atlas-foundation"],
    },
]


# =====================================================================
# SEED RUNNER
# =====================================================================

def seed(force_demo: bool = False) -> None:
    """
    Run all idempotent demo inserts. Gated behind ARCHIVE_SEED=demo
    OR force_demo=True (so it doesn't accidentally re-seed the demo
    content that the v0.6 migration explicitly wiped).

    Use this for setting up a fresh dev environment with sample data:
        ARCHIVE_SEED=demo python -m app.seed
    Or pass --demo on the command line (see __main__ below).
    """
    import os
    if not force_demo and os.environ.get("ARCHIVE_SEED", "").lower() != "demo":
        log.info("seed: ARCHIVE_SEED!=demo — skipping demo content. "
                 "Set ARCHIVE_SEED=demo to insert the v0.9 mockup data.")
        return
    log.info("seed: inserting demo content (ARCHIVE_SEED=demo)")
    with session_scope() as s:
        _seed_people(s)
        _seed_civs(s)
        _seed_stories(s)
        _seed_inquisitions(s)
    log.info("seed complete")


def _seed_people(s) -> None:
    """Insert PEOPLE into archive_user. Match on discord_id (UNIQUE)."""
    inserted = 0
    for p in PEOPLE:
        row = s.execute(
            text("SELECT id FROM archive_user WHERE discord_id = :did"),
            {"did": p["discord_id"]},
        ).first()
        if row:
            continue
        s.execute(
            text("""
                INSERT INTO archive_user (
                    discord_id, discord_username, display_name,
                    avatar_letter, avatar_color, civ_slug, beat,
                    base_role, is_editor, is_admin, bio
                ) VALUES (
                    :discord_id, :discord_username, :display_name,
                    :avatar_letter, :avatar_color, :civ_slug, :beat,
                    :base_role, :is_editor, :is_admin, :bio
                )
            """),
            {**{"beat": None}, **p},   # 'beat' optional in source data
        )
        inserted += 1
    log.info("seed: archive_user — inserted %d, skipped %d", inserted, len(PEOPLE) - inserted)


def _seed_civs(s) -> None:
    """Insert CIVS. Match on slug (UNIQUE)."""
    inserted = 0
    for c in CIVS:
        row = s.execute(
            text("SELECT id FROM civilization WHERE slug = :slug"),
            {"slug": c["slug"]},
        ).first()
        if row:
            continue
        s.execute(
            text("""
                INSERT INTO civilization (
                    slug, name, status, galaxy, founded, founded_year,
                    ended, ended_year, tagline, description,
                    color_primary, color_secondary
                ) VALUES (
                    :slug, :name, :status, :galaxy, :founded, :founded_year,
                    :ended, :ended_year, :tagline, :description,
                    :color_primary, :color_secondary
                )
            """),
            {
                "ended": None,
                "ended_year": None,
                **c,
            },
        )
        inserted += 1
    log.info("seed: civilization — inserted %d, skipped %d", inserted, len(CIVS) - inserted)


def _seed_stories(s) -> None:
    """Insert STORIES. Match on slug (UNIQUE). Populate story_civilization join."""
    inserted = 0
    for st in STORIES:
        row = s.execute(
            text("SELECT id FROM story WHERE slug = :slug"),
            {"slug": st["slug"]},
        ).first()
        if row:
            continue
        # Resolve author by discord_username
        author = s.execute(
            text("SELECT id FROM archive_user WHERE discord_username = :u"),
            {"u": st["author_slug"]},
        ).first()
        if not author:
            log.warning("seed: story %s — author %s not found, skipping", st["slug"], st["author_slug"])
            continue
        result = s.execute(
            text("""
                INSERT INTO story (
                    slug, doctype, headline, deck, body, beat,
                    author_id, published_at, read_minutes
                ) VALUES (
                    :slug, :doctype, :headline, :deck, :body, :beat,
                    :author_id, :published_at, :read_minutes
                )
            """),
            {
                "slug": st["slug"],
                "doctype": st["doctype"],
                "headline": st["headline"],
                "deck": st.get("deck"),
                "body": st["body"],
                "beat": st.get("beat"),
                "author_id": author.id,
                "published_at": st["published_at"],
                "read_minutes": st.get("read_minutes"),
            },
        )
        story_id = result.lastrowid
        # Populate join
        for civ_slug in st.get("civs", []):
            s.execute(
                text("INSERT OR IGNORE INTO story_civilization (story_id, civ_slug) VALUES (:sid, :cs)"),
                {"sid": story_id, "cs": civ_slug},
            )
        inserted += 1
    log.info("seed: story — inserted %d, skipped %d", inserted, len(STORIES) - inserted)


def _seed_inquisitions(s) -> None:
    """Insert INQUISITIONS + author and civ joins. Match on numeral (UNIQUE)."""
    inserted = 0
    for inq in INQUISITIONS:
        row = s.execute(
            text("SELECT id FROM inquisition WHERE numeral = :n"),
            {"n": inq["numeral"]},
        ).first()
        if row:
            continue
        lead = s.execute(
            text("SELECT id FROM archive_user WHERE discord_username = :u"),
            {"u": inq["lead_author_slug"]},
        ).first()
        if not lead:
            log.warning("seed: inquisition %s — lead author %s not found", inq["slug"], inq["lead_author_slug"])
            continue
        result = s.execute(
            text("""
                INSERT INTO inquisition (
                    slug, numeral, title, subtitle, deck, body,
                    state, progress, sources_count,
                    started_at, closed_at, lead_author_id
                ) VALUES (
                    :slug, :numeral, :title, :subtitle, :deck, :body,
                    :state, :progress, :sources_count,
                    :started_at, :closed_at, :lead_author_id
                )
            """),
            {
                "slug": inq["slug"],
                "numeral": inq["numeral"],
                "title": inq["title"],
                "subtitle": inq.get("subtitle"),
                "deck": inq.get("deck"),
                "body": inq["body"],
                "state": inq["state"],
                "progress": inq["progress"],
                "sources_count": inq["sources_count"],
                "started_at": inq["started_at"],
                "closed_at": inq.get("closed_at"),
                "lead_author_id": lead.id,
            },
        )
        inq_id = result.lastrowid
        # Author join
        for author_slug in inq.get("author_slugs", []):
            author = s.execute(
                text("SELECT id FROM archive_user WHERE discord_username = :u"),
                {"u": author_slug},
            ).first()
            if author:
                s.execute(
                    text("INSERT OR IGNORE INTO inquisition_author (inquisition_id, user_id) VALUES (:i, :u)"),
                    {"i": inq_id, "u": author.id},
                )
        # Civ join
        for civ_slug in inq.get("civs", []):
            s.execute(
                text("INSERT OR IGNORE INTO inquisition_civilization (inquisition_id, civ_slug) VALUES (:i, :c)"),
                {"i": inq_id, "c": civ_slug},
            )
        inserted += 1
    log.info("seed: inquisition — inserted %d, skipped %d", inserted, len(INQUISITIONS) - inserted)


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # --demo flag forces seeding even if ARCHIVE_SEED env var is unset
    seed(force_demo="--demo" in sys.argv)
