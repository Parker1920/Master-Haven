"""Shared helpers for event participation (opt-in competitions).

An event is a time-boxed, community-scoped competition. A submission becomes
part of an event when the submitter picks it at upload time (mirrors the
`expedition_id` pattern). The chosen `event_id` is stored on the pending row
and carried to the live `systems` / `discoveries` row on approval, so the
leaderboard counts APPROVED rows only, grouped by event_id.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger('control.room')

# Which event_type values accept each kind of submission.
_KIND_TO_TYPES = {
    'submission': ('submissions', 'both'),
    'discovery': ('discoveries', 'both'),
}


def resolve_submission_event_id(cursor, raw_event_id, discord_tag, kind):
    """Validate a submitter-chosen event_id and return it as int, else None.

    Returns the event id only when the event exists, is active, its date window
    currently contains today (UTC, inclusive), it accepts this submission
    ``kind`` ('submission' | 'discovery'), and it belongs to the submission's
    community (``discord_tag``). Any failure returns None so a bad or expired
    pick simply doesn't enter the competition rather than failing the upload.
    """
    if raw_event_id in (None, '', 0, '0'):
        return None
    try:
        event_id = int(raw_event_id)
    except (TypeError, ValueError):
        return None

    cursor.execute(
        'SELECT discord_tag, start_date, end_date, is_active, event_type '
        'FROM events WHERE id = ?',
        (event_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    ev = dict(row)

    if not ev.get('is_active'):
        return None

    # Community scope: the submission's tag must match the event's community.
    if discord_tag and ev.get('discord_tag') and discord_tag != ev['discord_tag']:
        return None

    # Type compatibility (a 'discoveries' event rejects system submissions, etc).
    accepted = _KIND_TO_TYPES.get(kind, ())
    if (ev.get('event_type') or 'submissions') not in accepted:
        return None

    # Date window — inclusive, compared on the UTC calendar date. start_date /
    # end_date are stored as 'YYYY-MM-DD' (from the date picker); slice defensively
    # in case a full ISO timestamp ever lands there.
    today = datetime.now(timezone.utc).date().isoformat()
    start = (ev.get('start_date') or '')[:10]
    end = (ev.get('end_date') or '')[:10]
    if start and today < start:
        return None
    if end and today > end:
        return None

    return event_id
