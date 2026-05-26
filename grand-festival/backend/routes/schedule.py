"""Read-only festival schedule, sourced live from a public Google Sheet.

The sheet is fetched server-side (no browser CORS), parsed into clean JSON, and
cached briefly so edits to the sheet surface on the site within the TTL without
anyone touching the website. The sheet stays the single source of truth and is
never edited from here.

Sheet layout (per column): Day | Hour GMT | Hour EST | Hour PST | Hour Brisbane
| Host | Event | Location(portal hex). Day labels like "Festival Day 1: ...".
"""

import csv
import io
import os
import re
import time
import urllib.request

from fastapi import APIRouter, HTTPException

router = APIRouter()

SHEET_ID = os.environ.get("GF_SCHEDULE_SHEET_ID", "1-WKKWGXsoT2iP3FSyNAQ10ah3N9BeE9Irs1Sq7Tu_ac")
GID = os.environ.get("GF_SCHEDULE_GID", "0")
CACHE_TTL = int(os.environ.get("GF_SCHEDULE_TTL", "300"))  # seconds

_cache: dict = {"at": 0.0, "data": None}

_TIME_RE = re.compile(r"(\d{1,2}:\d{2}):\d{2}\s*(AM|PM)", re.IGNORECASE)
_MAIN_RE = re.compile(r"Main System:\s*([0-9A-Fa-f]+)")


def _csv_url() -> str:
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID}"


def _fetch_csv() -> str:
    req = urllib.request.Request(_csv_url(), headers={"User-Agent": "GrandFestival/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed Google host
        return resp.read().decode("utf-8", errors="replace")


def _fmt_time(value: str) -> str:
    value = (value or "").strip()
    return _TIME_RE.sub(lambda m: f"{m.group(1)} {m.group(2).upper()}", value)


def _parse(text: str) -> dict:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return {"days": [], "main_system": None}

    main_system = None
    for cell in rows[0]:
        m = _MAIN_RE.search(cell or "")
        if m:
            main_system = m.group(1)
            break

    days: list[dict] = []
    current: dict | None = None
    for raw in rows[1:]:
        cells = [(c or "").strip() for c in (raw + [""] * 8)[:8]]
        day, gmt, est, pst, aus, host, event, location = cells

        if day:
            # A new festival day starts a fresh group. Other day-labels
            # ("No scheduled activity, ...") just close the current group.
            if day.lower().startswith("festival day"):
                current = {"label": day, "items": []}
                days.append(current)
            else:
                current = None

        if current is None or not (host or event):
            continue

        current["items"].append(
            {
                "gmt": _fmt_time(gmt),
                "est": _fmt_time(est),
                "pst": _fmt_time(pst),
                "aest": _fmt_time(aus),
                "host": host,
                "event": event,
                "location": location,
            }
        )

    # Drop any festival day that ended up with no scheduled items.
    days = [d for d in days if d["items"]]
    return {"days": days, "main_system": main_system}


@router.get("/schedule")
def get_schedule():
    now = time.time()
    if _cache["data"] is not None and (now - _cache["at"]) < CACHE_TTL:
        return {**_cache["data"], "fetched_at": _cache["at"], "cached": True}
    try:
        data = _parse(_fetch_csv())
        _cache.update(at=now, data=data)
        return {**data, "fetched_at": now, "cached": False}
    except Exception as exc:  # noqa: BLE001 - serve stale on any fetch/parse failure
        if _cache["data"] is not None:
            return {**_cache["data"], "fetched_at": _cache["at"], "cached": True, "stale": True}
        raise HTTPException(status_code=502, detail=f"Could not load the schedule: {exc}")
