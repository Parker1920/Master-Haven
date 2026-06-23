"""
Haven atlas sync.

Pulls live community figures from the main Haven control-room API
(GET /api/public/community-overview — public, no auth) and caches them
in the archive DB so civilization pages can render "Member systems /
Discoveries / Contributors — live from the atlas".

Design:
- HTTP pull, NOT a shared DB. The archive and Haven are separate stacks
  with separate SQLite files; the only contract is the public JSON API.
  On the Pi both containers sit on docker_default, so the internal name
  `http://haven:8005` resolves (set via HAVEN_API_BASE).
- Everything is a CACHE. `atlas_community_stat` / `atlas_summary` are
  fully rebuilt each run and safe to wipe. We never author here.
- Defensive: a sync failure (Haven down, network blip, bad JSON) logs a
  warning, records a failed `haven_sync_run`, and returns — it never
  raises into the scheduler or crashes the app.

Matching an archive civilization to a Haven community:
- Preferred: `civilization.haven_tag` holds the exact Haven discord_tag.
- Fallback: normalize (lowercase, alphanumerics only) the civ slug/name
  and match against a community's tag_norm or normalized display_name.
  Matching itself lives in the read path (routes); this module only
  populates the cache.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy import text

from ..config import get_settings
from ..db import session_scope

log = logging.getLogger("archive.haven_sync")

COMMUNITY_OVERVIEW_PATH = "/api/public/community-overview"


def normalize_tag(value: str | None) -> str:
    """Lowercase + strip to alphanumerics, for fuzzy tag/name matching.

    'The Aeon Concord' -> 'theaeonconcord', 'GHUB' -> 'ghub'. Shared with
    the read path so the cache and the lookup normalize identically.
    """
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record_failure(source: str, started: str, error: str) -> None:
    """Best-effort log row for a failed run. Swallows its own errors so a
    logging failure can never mask the original sync error."""
    try:
        with session_scope() as db:
            db.execute(
                text(
                    "INSERT INTO haven_sync_run "
                    "(source, started_at, finished_at, ok, communities_synced, error) "
                    "VALUES (:src, :st, :ft, 0, 0, :err)"
                ),
                {"src": source, "st": started, "ft": _now_iso(), "err": error[:500]},
            )
    except Exception:  # noqa: BLE001 — never let logging crash the caller
        log.exception("failed to record haven_sync_run failure row")


def lookup_atlas_stats(db, slug: str, name: str, haven_tag: str | None = None) -> dict:
    """Resolve one civ's live atlas figures from the cache.

    Match order: explicit haven_tag → normalized slug → normalized name →
    normalized display_name. Returns an AtlasCivStats-shaped dict; when no
    Haven community matches, returns {"matched": False}.

    `db` is an active SQLAlchemy session (request-scoped is fine — this is
    read-only).
    """
    def _to_dict(r) -> dict:
        return {
            "matched": True,
            "haven_tag": r.tag,
            "display_name": r.display_name,
            "total_systems": r.total_systems,
            "total_discoveries": r.total_discoveries,
            "unique_contributors": r.unique_contributors,
            "manual_systems": r.manual_systems,
            "extractor_systems": r.extractor_systems,
            "synced_at": r.synced_at,
        }

    candidates: list[str] = []
    for raw in (haven_tag, slug, name):
        norm = normalize_tag(raw)
        if norm and norm not in candidates:
            candidates.append(norm)
    if not candidates:
        return {"matched": False}

    # Fast path: indexed tag_norm match (covers exact tag and name==tag).
    for norm in candidates:
        row = db.execute(
            text("SELECT * FROM atlas_community_stat WHERE tag_norm = :n LIMIT 1"),
            {"n": norm},
        ).first()
        if row:
            return _to_dict(row)

    # Fuzzy path: a community whose display_name normalizes to a candidate
    # (e.g. archive 'Galactic Hub' ~ Haven display_name 'Galactic Hub').
    cand_set = set(candidates)
    rows = db.execute(
        text(
            "SELECT tag, tag_norm, display_name, total_systems, total_discoveries, "
            "unique_contributors, manual_systems, extractor_systems, synced_at "
            "FROM atlas_community_stat"
        )
    ).fetchall()
    for row in rows:
        if normalize_tag(row.display_name) in cand_set:
            return _to_dict(row)

    return {"matched": False}


def sync_haven_atlas(timeout: float = 20.0) -> dict:
    """Pull community-overview and refresh the local atlas cache.

    Returns a small summary dict ({ok, communities_synced, ...}) for the
    manual-trigger endpoint. Never raises.
    """
    settings = get_settings()
    base = (settings.haven_api_base or "").rstrip("/")
    if not base:
        log.warning("haven atlas sync skipped — HAVEN_API_BASE is empty")
        return {"ok": False, "error": "HAVEN_API_BASE not configured"}

    url = f"{base}{COMMUNITY_OVERVIEW_PATH}"
    started = _now_iso()

    # --- fetch -------------------------------------------------------
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001 — network/JSON failures are expected
        msg = f"{type(exc).__name__}: {exc}"
        log.warning("haven atlas sync failed (%s): %s", url, msg)
        _record_failure("community-overview", started, msg)
        return {"ok": False, "error": msg}

    communities = payload.get("communities") or []
    totals = payload.get("totals") or {}
    synced_at = _now_iso()

    # --- write cache -------------------------------------------------
    try:
        with session_scope() as db:
            count = 0
            seen_tags: list[str] = []
            for c in communities:
                tag = (c.get("discord_tag") or "").strip()
                if not tag:
                    continue
                seen_tags.append(tag)
                db.execute(
                    text(
                        """
                        INSERT INTO atlas_community_stat
                          (tag, tag_norm, display_name, total_systems,
                           total_discoveries, unique_contributors,
                           manual_systems, extractor_systems, synced_at)
                        VALUES
                          (:tag, :tag_norm, :dn, :ts, :td, :uc, :ms, :es, :sa)
                        ON CONFLICT(tag) DO UPDATE SET
                           tag_norm            = excluded.tag_norm,
                           display_name        = excluded.display_name,
                           total_systems       = excluded.total_systems,
                           total_discoveries   = excluded.total_discoveries,
                           unique_contributors = excluded.unique_contributors,
                           manual_systems      = excluded.manual_systems,
                           extractor_systems   = excluded.extractor_systems,
                           synced_at           = excluded.synced_at
                        """
                    ),
                    {
                        "tag": tag,
                        "tag_norm": normalize_tag(tag),
                        "dn": c.get("display_name") or tag,
                        "ts": int(c.get("total_systems") or 0),
                        "td": int(c.get("total_discoveries") or 0),
                        "uc": int(c.get("unique_contributors") or 0),
                        "ms": int(c.get("manual_systems") or 0),
                        "es": int(c.get("extractor_systems") or 0),
                        "sa": synced_at,
                    },
                )
                count += 1

            # Prune communities that vanished from the source (renamed /
            # merged) so the cache can't keep serving a stale civ. Delete by
            # "tag not seen this run" — deterministic regardless of clock
            # resolution. Guard against an empty payload wiping the cache.
            if seen_tags:
                placeholders = ",".join(f":t{i}" for i in range(len(seen_tags)))
                prune_params = {f"t{i}": seen_tags[i] for i in range(len(seen_tags))}
                db.execute(
                    text(
                        f"DELETE FROM atlas_community_stat "
                        f"WHERE tag NOT IN ({placeholders})"
                    ),
                    prune_params,
                )

            # Global totals (single row id=1).
            db.execute(
                text(
                    """
                    INSERT INTO atlas_summary
                      (id, total_systems, total_discoveries,
                       total_communities, total_contributors, synced_at)
                    VALUES (1, :ts, :td, :tc, :tcon, :sa)
                    ON CONFLICT(id) DO UPDATE SET
                       total_systems      = excluded.total_systems,
                       total_discoveries  = excluded.total_discoveries,
                       total_communities  = excluded.total_communities,
                       total_contributors = excluded.total_contributors,
                       synced_at          = excluded.synced_at
                    """
                ),
                {
                    "ts": int(totals.get("total_systems") or 0),
                    "td": int(totals.get("total_discoveries") or 0),
                    "tc": int(totals.get("total_communities") or len(communities)),
                    "tcon": int(totals.get("total_contributors") or 0),
                    "sa": synced_at,
                },
            )

            db.execute(
                text(
                    "INSERT INTO haven_sync_run "
                    "(source, started_at, finished_at, ok, communities_synced, error) "
                    "VALUES ('community-overview', :st, :ft, 1, :n, NULL)"
                ),
                {"st": started, "ft": _now_iso(), "n": count},
            )
    except Exception as exc:  # noqa: BLE001
        msg = f"{type(exc).__name__}: {exc}"
        log.exception("haven atlas sync write failed")
        _record_failure("community-overview", started, msg)
        return {"ok": False, "error": msg}

    log.info("haven atlas sync ok — %d communities cached", count)
    return {
        "ok": True,
        "communities_synced": count,
        "totals": {
            "total_systems": int(totals.get("total_systems") or 0),
            "total_discoveries": int(totals.get("total_discoveries") or 0),
            "total_communities": int(totals.get("total_communities") or len(communities)),
            "total_contributors": int(totals.get("total_contributors") or 0),
        },
        "synced_at": synced_at,
    }
