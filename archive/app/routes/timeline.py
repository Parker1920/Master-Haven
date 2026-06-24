"""
Timeline — master mixed-stream timeline.

GET /api/v1/timeline   merged events + story dates + inquisition starts +
                       civ founded/ended markers

The mockup's master timeline page renders one row per civ-lane plus a
horizontal axis for each year. This endpoint hands the frontend the
full unsorted-by-civ stream; the frontend bins by year/lane on its end.

Future filter knobs (Phase 4+): ?year_from=, ?year_to=, ?civ=, ?kind=.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.schemas import Envelope, Meta, TimelineEntry

router = APIRouter(prefix="/api/v1/timeline", tags=["timeline"])


# Match a 4-digit year anywhere in the string. Handles free-form dates
# like "c. 2017", "~2020", "Early 2018", "Q1 2024", etc.
_YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")


def _year_of(date_str: str | None) -> int | None:
    """Best-effort year extraction.

    Order of attempts:
    1. ISO-format datetime parse (handles "2026-04-12T03:45...")
    2. Regex for any 4-digit year (handles "c. 2017", "Early 2018",
       "~2020", etc.)
    """
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).year
    except (ValueError, TypeError):
        pass
    match = _YEAR_RE.search(date_str)
    if match:
        try:
            year = int(match.group(1))
            # Sanity: timeline is a human-history one, accept 1800-2999.
            if 1800 <= year <= 2999:
                return year
        except (TypeError, ValueError):
            return None
    return None


@router.get("", response_model=Envelope[list[TimelineEntry]])
def list_timeline(
    db: Session = Depends(get_db),
    limit: int = Query(500, ge=1, le=2000),
):
    entries: list[TimelineEntry] = []

    # --- catalogue events (namespace='event' articles carrying a date facet) ---
    # The unified Events live in the catalogue; those tagged with a date
    # surface on the timeline and link to their wiki page.
    rows = db.execute(
        text(
            "SELECT a.slug, a.title, a.civ_slug, af.value AS date_val "
            "FROM article a "
            "JOIN article_facet af ON af.article_id = a.id AND af.key = 'date' "
            "WHERE a.namespace = 'event' AND a.deleted_at IS NULL"
        )
    ).fetchall()
    for r in rows:
        entries.append(TimelineEntry(
            kind="event",
            date=r.date_val or "",
            year=_year_of(r.date_val),
            title=r.title,
            slug=r.slug,
            civs=[r.civ_slug] if r.civ_slug else [],
        ))

    # --- story publication dates (batch-fetched civ tags) ---
    story_rows = db.execute(
        text(
            "SELECT s.id, s.slug, s.doctype, s.headline, s.published_at "
            "FROM story s "
            "WHERE s.deleted_at IS NULL"
        )
    ).fetchall()
    story_ids = [r.id for r in story_rows]
    story_civs_by_id: dict[int, list[str]] = defaultdict(list)
    if story_ids:
        placeholders = ",".join(str(int(i)) for i in story_ids)
        civ_rows = db.execute(
            text(
                f"SELECT story_id, civ_slug FROM story_civilization "
                f"WHERE story_id IN ({placeholders})"
            )
        ).fetchall()
        for r in civ_rows:
            story_civs_by_id[r.story_id].append(r.civ_slug)
    for r in story_rows:
        entries.append(TimelineEntry(
            kind="story",
            date=r.published_at,
            year=_year_of(r.published_at),
            title=r.headline,
            slug=r.slug,
            id=r.id,
            doctype=r.doctype,
            civs=story_civs_by_id.get(r.id, []),
        ))

    # --- inquisition start dates (batch-fetched civ tags) ---
    inq_rows = db.execute(
        text(
            "SELECT id, slug, numeral, title, started_at "
            "FROM inquisition WHERE deleted_at IS NULL"
        )
    ).fetchall()
    inq_ids = [r.id for r in inq_rows]
    inq_civs_by_id: dict[int, list[str]] = defaultdict(list)
    if inq_ids:
        placeholders = ",".join(str(int(i)) for i in inq_ids)
        civ_rows = db.execute(
            text(
                f"SELECT inquisition_id, civ_slug FROM inquisition_civilization "
                f"WHERE inquisition_id IN ({placeholders})"
            )
        ).fetchall()
        for r in civ_rows:
            inq_civs_by_id[r.inquisition_id].append(r.civ_slug)
    for r in inq_rows:
        entries.append(TimelineEntry(
            kind="inquisition",
            date=r.started_at,
            year=_year_of(r.started_at),
            title=f"Inquisition {r.numeral}: {r.title}",
            slug=r.slug,
            id=r.id,
            doctype="inquisition",
            civs=inq_civs_by_id.get(r.id, []),
        ))

    # --- civ founding + ending markers ---
    rows = db.execute(
        text(
            "SELECT slug, name, founded, founded_year, ended, ended_year "
            "FROM civilization WHERE deleted_at IS NULL"
        )
    ).fetchall()
    for r in rows:
        if r.founded_year:
            entries.append(TimelineEntry(
                kind="civ-founded",
                date=r.founded or str(r.founded_year),
                year=r.founded_year,
                title=f"{r.name} founded",
                slug=r.slug,
                civs=[r.slug],
            ))
        if r.ended_year:
            entries.append(TimelineEntry(
                kind="civ-ended",
                date=r.ended or str(r.ended_year),
                year=r.ended_year,
                title=f"{r.name} ended",
                slug=r.slug,
                civs=[r.slug],
            ))

    # Sort newest-first by date string (ISO dates sort correctly as strings)
    entries.sort(key=lambda e: e.date or "", reverse=True)
    entries = entries[:limit]

    return Envelope(
        data=entries,
        meta=Meta(total=len(entries)),
    )
