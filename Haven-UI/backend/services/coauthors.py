"""
System co-author persistence (Wizard v1).

Extracted from control_room_api.py to break the circular import that used to
exist: control_room_api imports routes.approvals, and approvals.approve_system
needed _persist_system_coauthors. Previously approvals.py did a lazy import
wrapped in try/except — if the import ever silently failed, every approval
would drop co-authors with only a warning line. With the helper here in
services/ both modules can import it eagerly at the top.

Per Parker's Phase 1 decision: co-author counts are tracked SEPARATELY from
primary submission counts. Each system_coauthors row contributes one
coauthored-systems credit per profile, never to the primary count.

Self-co-author prevention (H-C1) is enforced here: the primary submitter's
own normalized username is dropped from the coauthor set if present.
"""

from datetime import datetime, timezone

from services.auth_service import normalize_username_for_dedup

# M-C1: server-side cap on coauthors per system. The wizard's CoAuthorChipInput
# enforces a max of 10 client-side; this is the backend backstop so a scripted
# POST can't attach 1000 usernames. Excess entries past the cap are silently
# dropped (matches the chip input's behavior on its own cap).
MAX_COAUTHORS_PER_SYSTEM = 10


def persist_system_coauthors(cursor, system_id, coauthors, submitter_username=None,
                             submitter_profile_id=None):
    """Replace the system_coauthors rows for this system_id.

    coauthors is a list of strings (Discord usernames) or {username, profile_id?}
    objects. Normalized via the same Discord-discriminator-stripping rules used
    by analytics, deduped by normalized username, and stored with a best-effort
    profile_id lookup.

    Self-co-author prevention: if the primary submitter's normalized username
    or profile_id matches a co-author entry, that entry is silently dropped
    so the submitter can't double-dip the leaderboard.

    Returns the number of rows inserted.
    """
    # Always replace — frontend sends the canonical full list
    cursor.execute('DELETE FROM system_coauthors WHERE system_id = ?', (system_id,))

    if not coauthors:
        return 0

    submitter_norm = normalize_username_for_dedup(submitter_username) if submitter_username else None

    seen = set()
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    for entry in coauthors:
        if isinstance(entry, dict):
            username = (entry.get('username') or '').strip()
            profile_id = entry.get('profile_id')
        else:
            username = str(entry or '').strip()
            profile_id = None
        if not username:
            continue
        norm = normalize_username_for_dedup(username)
        if not norm or norm in seen:
            continue

        # H-C1: prevent self-co-author. If we know who the primary submitter
        # is (by normalized name OR profile_id), silently skip a coauthor
        # entry that matches them. Both checks because either side might be
        # unknown at write time (admin direct-write may not have a profile_id).
        if submitter_norm and norm == submitter_norm:
            continue
        if submitter_profile_id and profile_id == submitter_profile_id:
            continue

        seen.add(norm)

        # Best-effort profile lookup so analytics can join on profile_id.
        if not profile_id:
            cursor.execute(
                'SELECT id FROM user_profiles WHERE username_normalized = ? AND is_active = 1',
                (norm,),
            )
            row = cursor.fetchone()
            if row:
                profile_id = row[0]
                # Re-check: maybe the resolved profile_id IS the submitter.
                if submitter_profile_id and profile_id == submitter_profile_id:
                    continue

        cursor.execute("""
            INSERT OR REPLACE INTO system_coauthors
            (system_id, profile_id, username, username_normalized, credited_at)
            VALUES (?, ?, ?, ?, ?)
        """, (system_id, profile_id, username, norm, now))
        inserted += 1
        if inserted >= MAX_COAUTHORS_PER_SYSTEM:
            break
    return inserted
