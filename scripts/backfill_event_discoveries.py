#!/usr/bin/env python3
"""Retroactively credit already-approved discoveries to an event (Part B of the
events "global opt-in" fix, Master Haven 1.80.0 / Backend 1.77.0).

Background: before the global-opt-in fix, an event was community-locked at intake
(services/events.py dropped any event_id whose submission tag != the event's
hosting civ). So discoveries submitted under Personal / a different civ — or
submitted before the picker showed the event — were approved with
`discoveries.event_id = NULL` and never counted. The leaderboard counts
`WHERE event_id = ?`, so the fix is simply to stamp the correct event_id onto the
matching live rows.

This script is PREVIEW-BY-DEFAULT. It prints the event row and every candidate
discovery it would touch (id, name, submitter, tag, submitted, in-window?) and
changes NOTHING unless you pass --commit. On --commit it copies the DB to a
timestamped .bak first and runs the UPDATE in a single transaction.

Usage (run on the Pi, where the production DB lives):

  # 1) Preview — see exactly what would be credited:
  python3 backfill_event_discoveries.py \
      --db /home/pi8gb/docker/haven-data/haven_ui.db --event-id 7

  # 2) Restrict to rows whose submission_timestamp is inside the event window:
  #    (add --only-in-window)
  # 3) Or restrict to an explicit id list you read off the preview:
  #    (add --ids 68,69,70)
  # 4) Commit once the preview looks right:
  python3 backfill_event_discoveries.py \
      --db /home/pi8gb/docker/haven-data/haven_ui.db --event-id 7 --commit

By default candidates are: live `discoveries` rows with event_id IS NULL whose
`discord_tag` matches the event's hosting civ. The event's date window is shown
per-row as in_window=Y/N but is NOT a filter unless --only-in-window is given
(some rows were submitted before the window but approved during it).
"""

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone


def _norm(s):
    return (s or '')[:10]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--db', required=True, help='Path to haven_ui.db (Pi: /home/pi8gb/docker/haven-data/haven_ui.db)')
    ap.add_argument('--event-id', type=int, required=True, help='Target event id (from the Events page / events table)')
    ap.add_argument('--only-in-window', action='store_true',
                    help='Only credit rows whose submission_timestamp falls inside [start_date, end_date]')
    ap.add_argument('--ids', default='', help='Comma-separated discovery ids to restrict to (overrides tag matching)')
    ap.add_argument('--tag', default=None,
                    help="Override the discord_tag to match (default: the event's own hosting tag)")
    ap.add_argument('--username-like', default='',
                    help="Comma-separated submitter name fragments to ALSO match (OR'd with the tag) — "
                         "use this to catch members who uploaded as Personal / a different civ, "
                         "since their discord_tag won't be the hosting tag")
    ap.add_argument('--commit', action='store_true', help='Actually write the change (default: preview only)')
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    ev = cur.execute('SELECT * FROM events WHERE id = ?', (args.event_id,)).fetchone()
    if not ev:
        print(f'ERROR: no event with id {args.event_id}', file=sys.stderr)
        sys.exit(1)
    ev = dict(ev)
    start, end = _norm(ev.get('start_date')), _norm(ev.get('end_date'))
    match_tag = args.tag if args.tag is not None else ev.get('discord_tag')

    print('=' * 78)
    print(f"EVENT {ev['id']}: {ev['name']}")
    print(f"  hosting tag : {ev.get('discord_tag')}")
    print(f"  type        : {ev.get('event_type')}")
    print(f"  window      : {start} .. {end}")
    print(f"  is_active   : {ev.get('is_active')}")
    print(f"  match tag   : {match_tag}  (rows with this discord_tag are candidates)")
    print('=' * 78)

    if ev.get('event_type') not in ('discoveries', 'both'):
        print(f"WARNING: event_type is '{ev.get('event_type')}' — it does not score discoveries.")
        print("         The discovery leaderboard tab will ignore these rows. Continue only if intended.")

    explicit_ids = [int(x) for x in args.ids.split(',') if x.strip()] if args.ids.strip() else None

    if explicit_ids:
        qmarks = ','.join('?' * len(explicit_ids))
        rows = cur.execute(
            f'SELECT id, discovery_name, discovered_by, discord_tag, submission_timestamp, event_id, analysis_status '
            f'FROM discoveries WHERE id IN ({qmarks})', explicit_ids
        ).fetchall()
    else:
        name_frags = [f.strip() for f in args.username_like.split(',') if f.strip()]
        where = ['event_id IS NULL']
        params = []
        ors = ['discord_tag = ?']
        params.append(match_tag)
        for frag in name_frags:
            ors.append('discovered_by LIKE ?')
            params.append(f'%{frag}%')
        where.append('(' + ' OR '.join(ors) + ')')
        rows = cur.execute(
            'SELECT id, discovery_name, discovered_by, discord_tag, submission_timestamp, event_id, analysis_status '
            f'FROM discoveries WHERE {" AND ".join(where)} '
            'ORDER BY submission_timestamp', params
        ).fetchall()

    candidates = []
    print(f"{'id':>6}  {'in_win':6}  {'submitted':10}  {'submitter':22}  {'tag':14}  name")
    print('-' * 78)
    for r in rows:
        r = dict(r)
        ts = _norm(r.get('submission_timestamp'))
        in_win = (not start or ts >= start) and (not end or ts <= end)
        skip = ''
        if r.get('event_id') is not None:
            skip = '  [already event_id=%s — SKIP]' % r['event_id']
        elif args.only_in_window and not in_win:
            skip = '  [outside window — SKIP]'
        else:
            candidates.append(r['id'])
        print(f"{r['id']:>6}  {'Y' if in_win else 'N':6}  {ts:10}  "
              f"{(r.get('discovered_by') or '')[:22]:22}  {(r.get('discord_tag') or '')[:14]:14}  "
              f"{(r.get('discovery_name') or '')[:30]}{skip}")

    print('-' * 78)
    print(f"{len(candidates)} discovery row(s) would be credited to event {ev['id']} ({ev['name']}).")

    # Informational: any still-pending rows with the same tag (not stamped here).
    pend = cur.execute(
        'SELECT COUNT(*) AS c FROM pending_discoveries '
        'WHERE status = ? AND discord_tag = ? AND (event_id IS NULL OR event_id = 0)',
        ('pending', match_tag)
    ).fetchone()
    if pend and pend['c']:
        print(f"NOTE: {pend['c']} still-PENDING discovery row(s) share this tag. They are NOT touched here — "
              f"once the code fix is live, re-submitting or picking the event on approval covers those.")

    if not args.commit:
        print("\nPREVIEW ONLY — nothing written. Re-run with --commit to apply.")
        conn.close()
        return

    if not candidates:
        print("\nNothing to commit.")
        conn.close()
        return

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    backup = f"{args.db}.bak_event{ev['id']}_{stamp}"
    shutil.copy2(args.db, backup)
    print(f"\nBacked up DB → {backup}")

    qmarks = ','.join('?' * len(candidates))
    cur.execute(f'UPDATE discoveries SET event_id = ? WHERE id IN ({qmarks})',
                [ev['id'], *candidates])
    conn.commit()
    print(f"COMMITTED: {cur.rowcount} row(s) now event_id = {ev['id']}.")

    # Verify the leaderboard count now reflects them.
    n = cur.execute('SELECT COUNT(*) AS c FROM discoveries WHERE event_id = ?', (ev['id'],)).fetchone()['c']
    print(f"Event {ev['id']} now has {n} approved discovery row(s) total.")
    conn.close()


if __name__ == '__main__':
    main()
