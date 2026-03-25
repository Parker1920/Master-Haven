"""Analytics and public community stats endpoints."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException

from constants import normalize_discord_username, score_to_grade, GRADE_THRESHOLDS
from db import get_db_connection
from services.auth_service import get_session, is_super_admin

logger = logging.getLogger('control.room')

router = APIRouter()


# ============================================================================
# Analytics Endpoints (System Submissions)
# Partner-scoped: partners are auto-filtered to their community's data.
# Super admin sees all data, optionally filtered by discord_tag.
# All source filters treat NULL/legacy rows as 'manual' via COALESCE.
# ============================================================================

@router.get('/api/analytics/submission-leaderboard')
async def get_submission_leaderboard(
    discord_tag: Optional[str] = None,
    source: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = 50,
    session: Optional[str] = Cookie(None)
):
    """
    Get submission leaderboard showing tallies per person.
    Partners can only see their own community's leaderboard.
    Super admins can see all.

    Params:
    - discord_tag: Filter by community (partners automatically filtered)
    - source: Filter by submission source ('manual' or 'haven_extractor')
    - start_date, end_date: Date range (ISO format)
    - period: Preset periods (week, month, year, all)
    - limit: Max results (default 50)
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    # Partners can only see their own community
    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build date filter based on period or explicit dates
        date_filter = ''
        date_params = []

        if period == 'week':
            date_filter = " AND submission_date >= date('now', '-7 days')"
        elif period == 'month':
            date_filter = " AND submission_date >= date('now', '-30 days')"
        elif period == 'year':
            date_filter = " AND submission_date >= date('now', '-365 days')"
        elif start_date:
            date_filter = " AND submission_date >= ?"
            date_params.append(start_date)
            if end_date:
                date_filter += " AND submission_date <= ?"
                date_params.append(end_date + 'T23:59:59')

        # Build community filter
        tag_filter = ''
        tag_params = []
        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            tag_params = [discord_tag]

        # Build source filter (manual includes legacy NULL rows)
        source_filter = ''
        source_params = []
        if source:
            if source == 'manual':
                source_filter = " AND COALESCE(source, 'manual') = 'manual'"
            else:
                source_filter = ' AND source = ?'
                source_params = [source]

        # Query for leaderboard from pending_systems (includes both approved and rejected)
        # Extract username from multiple sources: submitted_by, personal_discord_username, or discovered_by from JSON
        # Skip 'Anonymous' and 'anonymous' values to find the actual username
        # Normalize usernames: remove #, strip trailing 4-digit Discord discriminators, lowercase
        # This consolidates "Obliterated", "Obliterated#4519", "obliterated4519" as the same person

        # Define the raw username extraction
        raw_username = '''COALESCE(
            NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
            personal_discord_username,
            json_extract(system_data, '$.discovered_by'),
            'Unknown'
        )'''

        # Define normalization: trim whitespace, remove #, strip trailing 4-digit discriminator, lowercase
        # This handles: "User#1234" -> "user", "User1234" -> "user", "User" -> "user", " User " -> "user"
        # Step 1: TRIM and REPLACE # with empty string
        trimmed_username = f'''TRIM(REPLACE({raw_username}, '#', ''))'''

        normalized_username = f'''LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_username}) > 4
                    AND SUBSTR({trimmed_username}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_username}) = 4
                        OR SUBSTR({trimmed_username}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_username}, 1, LENGTH({trimmed_username}) - 4)
                ELSE {trimmed_username}
            END
        ))'''

        # Use COALESCE to convert NULL/empty discord_tag to 'Personal' for grouping
        tag_display = "COALESCE(NULLIF(discord_tag, ''), 'Personal')"

        query = f'''
            SELECT
                MAX({raw_username}) as username,
                {normalized_username} as normalized_name,
                GROUP_CONCAT(DISTINCT {tag_display}) as discord_tags,
                COUNT(*) as total_submissions,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                MIN(submission_date) as first_submission,
                MAX(submission_date) as last_submission
            FROM pending_systems
            WHERE 1=1 {tag_filter} {date_filter} {source_filter}
            GROUP BY {normalized_username}
            HAVING {normalized_username} != 'unknown'
            ORDER BY total_submissions DESC
            LIMIT ?
        '''

        params = tag_params + date_params + source_params + [limit]
        cursor.execute(query, params)
        rows = cursor.fetchall()

        leaderboard = []
        for row in rows:
            entry = dict(row)
            total = entry['total_submissions']
            approved = entry['approved'] or 0
            entry['approval_rate'] = round((approved / total * 100), 1) if total > 0 else 0

            # For users with multiple sources (discord communities or personal), fetch breakdown
            tags = [t.strip() for t in (entry.get('discord_tags') or '').split(',') if t.strip()]
            if len(tags) > 1:
                # Use the normalized_name from the query for accurate matching
                norm_name = entry.get('normalized_name', '').lower()
                breakdown_query = f'''
                    SELECT
                        {tag_display} as discord_tag,
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                        SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
                    FROM pending_systems
                    WHERE {normalized_username} = ?
                      {date_filter} {source_filter}
                    GROUP BY {tag_display}
                    ORDER BY total DESC
                '''
                cursor.execute(breakdown_query, [norm_name] + date_params + source_params)
                breakdown_rows = cursor.fetchall()
                entry['tag_breakdown'] = [dict(b) for b in breakdown_rows]

            # Remove internal normalized_name from response
            entry.pop('normalized_name', None)
            leaderboard.append(entry)

        # Get totals
        totals_query = f'''
            SELECT
                COUNT(*) as total_submissions,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as total_approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as total_rejected
            FROM pending_systems
            WHERE 1=1 {tag_filter} {date_filter} {source_filter}
        '''
        cursor.execute(totals_query, tag_params + date_params + source_params)
        totals_row = cursor.fetchone()

        return {
            'leaderboard': leaderboard,
            'totals': {
                'total_submissions': totals_row['total_submissions'] or 0,
                'total_approved': totals_row['total_approved'] or 0,
                'total_rejected': totals_row['total_rejected'] or 0
            }
        }
    finally:
        if conn:
            conn.close()


@router.get('/api/analytics/community-stats')
async def get_community_stats(
    source: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Get statistics per community/Discord tag.
    Super admin only - shows all communities.

    Params:
    - source: Filter by submission source ('manual' or 'haven_extractor')
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build date filter
        date_filter = ''
        date_params = []

        if period == 'week':
            date_filter = " AND submission_date >= date('now', '-7 days')"
        elif period == 'month':
            date_filter = " AND submission_date >= date('now', '-30 days')"
        elif period == 'year':
            date_filter = " AND submission_date >= date('now', '-365 days')"
        elif start_date:
            date_filter = " AND submission_date >= ?"
            date_params.append(start_date)
            if end_date:
                date_filter += " AND submission_date <= ?"
                date_params.append(end_date + 'T23:59:59')

        # Build source filter (manual includes legacy NULL rows)
        source_filter = ''
        source_params = []
        if source:
            if source == 'manual':
                source_filter = " AND COALESCE(source, 'manual') = 'manual'"
            else:
                source_filter = ' AND source = ?'
                source_params = [source]

        # Get community stats from pending_systems
        # Normalize usernames: trim whitespace, remove #, strip trailing 4-digit Discord discriminators, lowercase
        raw_username = '''COALESCE(
            NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
            personal_discord_username,
            json_extract(system_data, '$.discovered_by'),
            'Unknown'
        )'''

        trimmed_username = f'''TRIM(REPLACE({raw_username}, '#', ''))'''

        normalized_username = f'''LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_username}) > 4
                    AND SUBSTR({trimmed_username}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_username}) = 4
                        OR SUBSTR({trimmed_username}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_username}, 1, LENGTH({trimmed_username}) - 4)
                ELSE {trimmed_username}
            END
        ))'''

        query = f'''
            SELECT
                COALESCE(discord_tag, 'Untagged') as discord_tag,
                COUNT(*) as total_submissions,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as total_approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as total_rejected,
                COUNT(DISTINCT {normalized_username}) as unique_submitters
            FROM pending_systems
            WHERE 1=1 {date_filter} {source_filter}
            GROUP BY discord_tag
            ORDER BY total_submissions DESC
        '''

        cursor.execute(query, date_params + source_params)
        rows = cursor.fetchall()

        communities = []
        for row in rows:
            entry = dict(row)
            total = entry['total_submissions']
            approved = entry['total_approved'] or 0
            entry['approval_rate'] = round((approved / total * 100), 1) if total > 0 else 0

            # Get top submitter for this community (with full normalization)
            tag = row['discord_tag']
            if tag and tag != 'Untagged':
                cursor.execute(f'''
                    SELECT MAX({raw_username}) as username,
                           COUNT(*) as count
                    FROM pending_systems
                    WHERE discord_tag = ? {date_filter} {source_filter}
                    GROUP BY {normalized_username}
                    ORDER BY count DESC
                    LIMIT 1
                ''', [tag] + date_params + source_params)
            else:
                cursor.execute(f'''
                    SELECT MAX({raw_username}) as username,
                           COUNT(*) as count
                    FROM pending_systems
                    WHERE (discord_tag IS NULL OR discord_tag = '') {date_filter} {source_filter}
                    GROUP BY {normalized_username}
                    ORDER BY count DESC
                    LIMIT 1
                ''', date_params + source_params)

            top_row = cursor.fetchone()
            entry['top_submitter'] = top_row['username'] if top_row else None

            # Get total systems in the database for this community
            if tag and tag != 'Untagged':
                cursor.execute('SELECT COUNT(*) FROM systems WHERE discord_tag = ?', (tag,))
            else:
                cursor.execute("SELECT COUNT(*) FROM systems WHERE discord_tag IS NULL OR discord_tag = ''")
            entry['total_systems'] = cursor.fetchone()[0]

            communities.append(entry)

        return {'communities': communities}
    finally:
        if conn:
            conn.close()


@router.get('/api/analytics/submissions-timeline')
async def get_submissions_timeline(
    discord_tag: Optional[str] = None,
    source: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = 'day',
    session: Optional[str] = Cookie(None)
):
    """
    Get submissions over time for charting.
    Partners can only see their own community's timeline.

    Params:
    - discord_tag: Filter by community
    - source: Filter by submission source ('manual' or 'haven_extractor')
    - start_date, end_date: Date range
    - granularity: day, week, or month
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    # Partners can only see their own community
    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Default to last 30 days if no date range specified
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # Build date grouping based on granularity
        if granularity == 'week':
            date_format = "strftime('%Y-W%W', submission_date)"
        elif granularity == 'month':
            date_format = "strftime('%Y-%m', submission_date)"
        else:  # day
            date_format = "date(submission_date)"

        # Build filters
        tag_filter = ''
        params = [start_date, end_date + 'T23:59:59']

        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            params.append(discord_tag)

        # Build source filter (manual includes legacy NULL rows)
        source_filter = ''
        if source:
            if source == 'manual':
                source_filter = " AND COALESCE(source, 'manual') = 'manual'"
            else:
                source_filter = ' AND source = ?'
                params.append(source)

        query = f'''
            SELECT
                {date_format} as date,
                COUNT(*) as submissions,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
            FROM pending_systems
            WHERE submission_date >= ? AND submission_date <= ? {tag_filter} {source_filter}
            GROUP BY {date_format}
            ORDER BY date ASC
        '''

        cursor.execute(query, params)
        rows = cursor.fetchall()

        timeline = [dict(row) for row in rows]

        return {'timeline': timeline, 'granularity': granularity}
    finally:
        if conn:
            conn.close()


@router.get('/api/analytics/source-breakdown')
async def get_source_breakdown(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Get submission counts broken down by source type (manual vs haven_extractor).
    Used for the analytics overview bar showing proportional split.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build date filter
        date_filter = ''
        date_params = []
        if period == 'week':
            date_filter = " AND submission_date >= date('now', '-7 days')"
        elif period == 'month':
            date_filter = " AND submission_date >= date('now', '-30 days')"
        elif period == 'year':
            date_filter = " AND submission_date >= date('now', '-365 days')"
        elif start_date:
            date_filter = " AND submission_date >= ?"
            date_params.append(start_date)
            if end_date:
                date_filter += " AND submission_date <= ?"
                date_params.append(end_date + 'T23:59:59')

        tag_filter = ''
        tag_params = []
        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            tag_params = [discord_tag]

        # Group by source, treating NULL and companion_app as manual
        cursor.execute(f'''
            SELECT
                CASE
                    WHEN source = 'haven_extractor' THEN 'haven_extractor'
                    ELSE 'manual'
                END as source_type,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM pending_systems
            WHERE 1=1 {tag_filter} {date_filter}
            GROUP BY source_type
            ORDER BY total DESC
        ''', tag_params + date_params)
        rows = cursor.fetchall()

        breakdown = [dict(row) for row in rows]
        grand_total = sum(row['total'] for row in breakdown)

        return {'breakdown': breakdown, 'grand_total': grand_total}
    finally:
        if conn:
            conn.close()


@router.get('/api/analytics/extractor-summary')
async def get_extractor_summary(
    discord_tag: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Get Haven Extractor-specific statistics from the api_keys table.
    Returns registered user counts, active users, and submission totals.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Total registered extractor users
        cursor.execute("SELECT COUNT(*) FROM api_keys WHERE key_type = 'extractor'")
        registered_users = cursor.fetchone()[0]

        # Active in last 7 days
        cursor.execute('''
            SELECT COUNT(*) FROM api_keys
            WHERE key_type = 'extractor'
              AND last_submission_at >= datetime('now', '-7 days')
        ''')
        active_users_7d = cursor.fetchone()[0]

        # Total extractor submissions (with optional community filter)
        tag_filter = ''
        tag_params = []
        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            tag_params = [discord_tag]

        cursor.execute(f'''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM pending_systems
            WHERE source = 'haven_extractor' {tag_filter}
        ''', tag_params)
        ext_stats = dict(cursor.fetchone())

        avg_per_user = round(ext_stats['total'] / registered_users, 1) if registered_users > 0 else 0

        return {
            'registered_users': registered_users,
            'active_users_7d': active_users_7d,
            'total_submissions': ext_stats['total'],
            'approved': ext_stats['approved'] or 0,
            'rejected': ext_stats['rejected'] or 0,
            'pending': ext_stats['pending'] or 0,
            'avg_per_user': avg_per_user
        }
    finally:
        if conn:
            conn.close()


@router.get('/api/analytics/rejection-reasons')
async def get_rejection_reasons(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Get breakdown of rejection reasons.
    Super admin only.
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build filters
        filters = " AND action = 'rejected' AND notes IS NOT NULL AND notes != ''"
        params = []

        if discord_tag:
            filters += ' AND submission_discord_tag = ?'
            params.append(discord_tag)
        if start_date:
            filters += ' AND timestamp >= ?'
            params.append(start_date)
        if end_date:
            filters += ' AND timestamp <= ?'
            params.append(end_date + 'T23:59:59')

        query = f'''
            SELECT
                notes as reason,
                COUNT(*) as count
            FROM approval_audit_log
            WHERE 1=1 {filters}
            GROUP BY notes
            ORDER BY count DESC
            LIMIT 20
        '''

        cursor.execute(query, params)
        rows = cursor.fetchall()

        reasons = [dict(row) for row in rows]

        return {'reasons': reasons}
    finally:
        if conn:
            conn.close()


# ============================================================================
# Discovery Analytics Endpoints (Partner Analytics Dashboard)
# All discovery analytics auto-scope: partners see only their community,
# super admin sees all (optionally filtered by discord_tag).
# NOTE: discoveries table uses 'submission_timestamp' (not 'submission_date').
# ============================================================================

@router.get('/api/analytics/discovery-leaderboard')
async def get_discovery_leaderboard(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = 50,
    session: Optional[str] = Cookie(None)
):
    """
    Get discovery leaderboard showing top discoverers.
    Partners can only see their own community's leaderboard.
    Super admins can see all or filter by community.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    # Partners can only see their own community
    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build date filter
        date_filter = ''
        date_params = []

        if period == 'week':
            date_filter = " AND submission_timestamp >= date('now', '-7 days')"
        elif period == 'month':
            date_filter = " AND submission_timestamp >= date('now', '-30 days')"
        elif period == 'year':
            date_filter = " AND submission_timestamp >= date('now', '-365 days')"
        elif start_date:
            date_filter = " AND submission_timestamp >= ?"
            date_params.append(start_date)
            if end_date:
                date_filter += " AND submission_timestamp <= ?"
                date_params.append(end_date + 'T23:59:59')

        # Build community filter
        tag_filter = ''
        tag_params = []
        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            tag_params = [discord_tag]

        # Normalize discovered_by: trim, remove #, strip trailing 4-digit discriminator, lowercase
        raw_name = "COALESCE(NULLIF(NULLIF(discovered_by, 'Anonymous'), 'anonymous'), 'Unknown')"
        trimmed_name = f"TRIM(REPLACE({raw_name}, '#', ''))"
        normalized_name = f"""LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_name}) > 4
                    AND SUBSTR({trimmed_name}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_name}) = 4
                        OR SUBSTR({trimmed_name}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_name}, 1, LENGTH({trimmed_name}) - 4)
                ELSE {trimmed_name}
            END
        ))"""

        query = f'''
            SELECT
                MAX(discovered_by) as discoverer,
                {normalized_name} as normalized_name,
                COUNT(*) as total_discoveries,
                COUNT(DISTINCT type_slug) as unique_types,
                GROUP_CONCAT(DISTINCT type_slug) as type_slugs,
                MIN(submission_timestamp) as first_discovery,
                MAX(submission_timestamp) as last_discovery
            FROM discoveries
            WHERE 1=1 {tag_filter} {date_filter}
            GROUP BY {normalized_name}
            HAVING {normalized_name} != 'unknown'
            ORDER BY total_discoveries DESC
            LIMIT ?
        '''

        params = tag_params + date_params + [limit]
        cursor.execute(query, params)
        rows = cursor.fetchall()

        leaderboard = []
        for i, row in enumerate(rows, 1):
            entry = dict(row)
            entry['rank'] = i
            entry['type_slugs'] = [t.strip() for t in (entry.get('type_slugs') or '').split(',') if t.strip()]
            leaderboard.append(entry)

        # Get totals
        total_query = f'''
            SELECT COUNT(*) as total_discoveries,
                   COUNT(DISTINCT {normalized_name}) as total_discoverers
            FROM discoveries
            WHERE 1=1 {tag_filter} {date_filter}
        '''
        cursor.execute(total_query, tag_params + date_params)
        totals = dict(cursor.fetchone())

        return {
            'leaderboard': leaderboard,
            'totals': totals
        }
    finally:
        if conn:
            conn.close()


@router.get('/api/analytics/discovery-timeline')
async def get_discovery_timeline(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = 'day',
    session: Optional[str] = Cookie(None)
):
    """
    Get time-series of discovery submissions.
    Partners see their community only.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Default to last 30 days
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # Date grouping
        if granularity == 'week':
            date_format = "strftime('%Y-W%W', submission_timestamp)"
        elif granularity == 'month':
            date_format = "strftime('%Y-%m', submission_timestamp)"
        else:
            date_format = "date(submission_timestamp)"

        tag_filter = ''
        params = [start_date, end_date + 'T23:59:59']

        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            params.append(discord_tag)

        query = f'''
            SELECT
                {date_format} as date,
                COUNT(*) as discoveries,
                COUNT(DISTINCT type_slug) as unique_types,
                COUNT(DISTINCT LOWER(TRIM(discovered_by))) as unique_discoverers
            FROM discoveries
            WHERE submission_timestamp >= ? AND submission_timestamp <= ? {tag_filter}
            GROUP BY {date_format}
            ORDER BY date ASC
        '''

        cursor.execute(query, params)
        rows = cursor.fetchall()

        timeline = [dict(row) for row in rows]

        return {'timeline': timeline, 'granularity': granularity}
    finally:
        if conn:
            conn.close()


@router.get('/api/analytics/discovery-type-breakdown')
async def get_discovery_type_breakdown(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Get discovery counts grouped by type for a community.
    Partners see their community only.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build date filter
        date_filter = ''
        date_params = []

        if period == 'week':
            date_filter = " AND submission_timestamp >= date('now', '-7 days')"
        elif period == 'month':
            date_filter = " AND submission_timestamp >= date('now', '-30 days')"
        elif period == 'year':
            date_filter = " AND submission_timestamp >= date('now', '-365 days')"
        elif start_date:
            date_filter = " AND submission_timestamp >= ?"
            date_params.append(start_date)
            if end_date:
                date_filter += " AND submission_timestamp <= ?"
                date_params.append(end_date + 'T23:59:59')

        tag_filter = ''
        tag_params = []
        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            tag_params = [discord_tag]

        query = f'''
            SELECT
                COALESCE(type_slug, 'other') as type_slug,
                COALESCE(discovery_type, 'Other') as discovery_type,
                COUNT(*) as count
            FROM discoveries
            WHERE 1=1 {tag_filter} {date_filter}
            GROUP BY type_slug
            ORDER BY count DESC
        '''

        params = tag_params + date_params
        cursor.execute(query, params)
        rows = cursor.fetchall()

        breakdown = [dict(row) for row in rows]

        # Calculate percentages
        total = sum(item['count'] for item in breakdown)
        for item in breakdown:
            item['percentage'] = round((item['count'] / total * 100), 1) if total > 0 else 0

        return {'breakdown': breakdown, 'total': total}
    finally:
        if conn:
            conn.close()


@router.get('/api/analytics/partner-overview')
async def get_partner_overview(
    discord_tag: Optional[str] = None,
    source: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Combined overview endpoint for the partner analytics dashboard.
    Returns system submission totals, discovery totals, top submitters,
    top discoverers, and activity trends in a single call.

    Params:
    - source: Filter system submissions by source ('manual' or 'haven_extractor')
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build date filter for pending_systems
        sub_date_filter = ''
        sub_date_params = []
        disc_date_filter = ''
        disc_date_params = []

        if period == 'week':
            sub_date_filter = " AND submission_date >= date('now', '-7 days')"
            disc_date_filter = " AND submission_timestamp >= date('now', '-7 days')"
        elif period == 'month':
            sub_date_filter = " AND submission_date >= date('now', '-30 days')"
            disc_date_filter = " AND submission_timestamp >= date('now', '-30 days')"
        elif period == 'year':
            sub_date_filter = " AND submission_date >= date('now', '-365 days')"
            disc_date_filter = " AND submission_timestamp >= date('now', '-365 days')"
        elif start_date:
            sub_date_filter = " AND submission_date >= ?"
            sub_date_params.append(start_date)
            disc_date_filter = " AND submission_timestamp >= ?"
            disc_date_params.append(start_date)
            if end_date:
                sub_date_filter += " AND submission_date <= ?"
                sub_date_params.append(end_date + 'T23:59:59')
                disc_date_filter += " AND submission_timestamp <= ?"
                disc_date_params.append(end_date + 'T23:59:59')

        sub_tag_filter = ''
        sub_tag_params = []
        disc_tag_filter = ''
        disc_tag_params = []
        if discord_tag:
            sub_tag_filter = ' AND discord_tag = ?'
            sub_tag_params = [discord_tag]
            disc_tag_filter = ' AND discord_tag = ?'
            disc_tag_params = [discord_tag]

        # Build source filter for submission queries (manual includes legacy NULL rows)
        sub_source_filter = ''
        sub_source_params = []
        if source:
            if source == 'manual':
                sub_source_filter = " AND COALESCE(source, 'manual') = 'manual'"
            else:
                sub_source_filter = ' AND source = ?'
                sub_source_params = [source]

        # --- System submission stats ---
        cursor.execute(f'''
            SELECT
                COUNT(*) as total_submissions,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as total_approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as total_rejected,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as total_pending
            FROM pending_systems
            WHERE 1=1 {sub_tag_filter} {sub_date_filter} {sub_source_filter}
        ''', sub_tag_params + sub_date_params + sub_source_params)
        sub_stats = dict(cursor.fetchone())

        # Active submitters (unique normalized usernames)
        raw_username = '''COALESCE(
            NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
            personal_discord_username,
            json_extract(system_data, '$.discovered_by'),
            'Unknown'
        )'''
        trimmed_username = f"TRIM(REPLACE({raw_username}, '#', ''))"
        normalized_sub = f"""LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_username}) > 4
                    AND SUBSTR({trimmed_username}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_username}) = 4
                        OR SUBSTR({trimmed_username}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_username}, 1, LENGTH({trimmed_username}) - 4)
                ELSE {trimmed_username}
            END
        ))"""

        cursor.execute(f'''
            SELECT COUNT(DISTINCT {normalized_sub}) as active_submitters
            FROM pending_systems
            WHERE 1=1 {sub_tag_filter} {sub_date_filter} {sub_source_filter}
              AND {normalized_sub} != 'unknown'
        ''', sub_tag_params + sub_date_params + sub_source_params)
        active_submitters = cursor.fetchone()['active_submitters']

        # --- Discovery stats ---
        cursor.execute(f'''
            SELECT
                COUNT(*) as total_discoveries,
                COUNT(DISTINCT LOWER(TRIM(discovered_by))) as active_discoverers,
                COUNT(DISTINCT type_slug) as unique_types
            FROM discoveries
            WHERE 1=1 {disc_tag_filter} {disc_date_filter}
        ''', disc_tag_params + disc_date_params)
        disc_stats = dict(cursor.fetchone())

        # --- Top 5 submitters ---
        cursor.execute(f'''
            SELECT
                MAX({raw_username}) as username,
                {normalized_sub} as normalized_name,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved
            FROM pending_systems
            WHERE 1=1 {sub_tag_filter} {sub_date_filter} {sub_source_filter}
            GROUP BY {normalized_sub}
            HAVING {normalized_sub} != 'unknown'
            ORDER BY total DESC
            LIMIT 5
        ''', sub_tag_params + sub_date_params + sub_source_params)
        top_submitters = [dict(row) for row in cursor.fetchall()]

        # --- Top 5 discoverers ---
        raw_disc = "COALESCE(NULLIF(NULLIF(discovered_by, 'Anonymous'), 'anonymous'), 'Unknown')"
        trimmed_disc = f"TRIM(REPLACE({raw_disc}, '#', ''))"
        normalized_disc = f"""LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_disc}) > 4
                    AND SUBSTR({trimmed_disc}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_disc}) = 4
                        OR SUBSTR({trimmed_disc}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_disc}, 1, LENGTH({trimmed_disc}) - 4)
                ELSE {trimmed_disc}
            END
        ))"""

        cursor.execute(f'''
            SELECT
                MAX(discovered_by) as discoverer,
                {normalized_disc} as normalized_name,
                COUNT(*) as total,
                COUNT(DISTINCT type_slug) as unique_types
            FROM discoveries
            WHERE 1=1 {disc_tag_filter} {disc_date_filter}
            GROUP BY {normalized_disc}
            HAVING {normalized_disc} != 'unknown'
            ORDER BY total DESC
            LIMIT 5
        ''', disc_tag_params + disc_date_params)
        top_discoverers = [dict(row) for row in cursor.fetchall()]

        # --- Activity trend (last 7 days of submissions + discoveries) ---
        cursor.execute(f'''
            SELECT
                date(submission_date) as date,
                COUNT(*) as submissions
            FROM pending_systems
            WHERE submission_date >= date('now', '-7 days')
              {sub_tag_filter} {sub_source_filter}
            GROUP BY date(submission_date)
            ORDER BY date ASC
        ''', sub_tag_params + sub_source_params)
        sub_trend = {row['date']: row['submissions'] for row in cursor.fetchall()}

        cursor.execute(f'''
            SELECT
                date(submission_timestamp) as date,
                COUNT(*) as discoveries
            FROM discoveries
            WHERE submission_timestamp >= date('now', '-7 days')
              {disc_tag_filter}
            GROUP BY date(submission_timestamp)
            ORDER BY date ASC
        ''', disc_tag_params)
        disc_trend = {row['date']: row['discoveries'] for row in cursor.fetchall()}

        # Merge trends
        all_dates = sorted(set(list(sub_trend.keys()) + list(disc_trend.keys())))
        activity_trend = [
            {
                'date': d,
                'submissions': sub_trend.get(d, 0),
                'discoveries': disc_trend.get(d, 0)
            }
            for d in all_dates
        ]

        return {
            'submissions': {
                'total': sub_stats.get('total_submissions', 0),
                'approved': sub_stats.get('total_approved', 0),
                'rejected': sub_stats.get('total_rejected', 0),
                'pending': sub_stats.get('total_pending', 0),
                'active_submitters': active_submitters
            },
            'discoveries': {
                'total': disc_stats.get('total_discoveries', 0),
                'active_discoverers': disc_stats.get('active_discoverers', 0),
                'unique_types': disc_stats.get('unique_types', 0)
            },
            'top_submitters': top_submitters,
            'top_discoverers': top_discoverers,
            'activity_trend': activity_trend
        }
    finally:
        if conn:
            conn.close()


# ============================================================================
# Public Community Stats Endpoints (no auth required)
# These endpoints are public and power the Community Stats page.
# ============================================================================

@router.get('/api/public/community-overview')
async def public_community_overview():
    """
    Public endpoint: per-community stats (systems, discoveries, contributors, upload method split).
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Systems per community
        cursor.execute('''
            SELECT COALESCE(NULLIF(discord_tag, ''), 'Personal') as tag,
                   COUNT(*) as total_systems,
                   COUNT(DISTINCT COALESCE(NULLIF(discovered_by, ''), personal_discord_username)) as unique_contributors
            FROM systems
            GROUP BY tag
            ORDER BY total_systems DESC
        ''')
        sys_rows = {r['tag']: dict(r) for r in cursor.fetchall()}

        # Discoveries per community
        cursor.execute('''
            SELECT COALESCE(NULLIF(discord_tag, ''), 'Personal') as tag,
                   COUNT(*) as total_discoveries
            FROM discoveries
            GROUP BY tag
        ''')
        disc_rows = {r['tag']: dict(r) for r in cursor.fetchall()}

        # Upload method split per community (from pending_systems approved only)
        cursor.execute('''
            SELECT COALESCE(NULLIF(discord_tag, ''), 'Personal') as tag,
                   SUM(CASE WHEN COALESCE(source, 'manual') = 'manual' THEN 1 ELSE 0 END) as manual_systems,
                   SUM(CASE WHEN source = 'haven_extractor' THEN 1 ELSE 0 END) as extractor_systems
            FROM pending_systems
            WHERE status = 'approved'
            GROUP BY tag
        ''')
        source_rows = {r['tag']: dict(r) for r in cursor.fetchall()}

        # Community display names from partner_accounts
        cursor.execute("SELECT discord_tag, display_name FROM partner_accounts WHERE discord_tag IS NOT NULL")
        display_names = {r['discord_tag']: r['display_name'] for r in cursor.fetchall()}

        # Merge all data
        all_tags = set(sys_rows.keys()) | set(disc_rows.keys())
        communities = []
        for tag in sorted(all_tags, key=lambda t: sys_rows.get(t, {}).get('total_systems', 0), reverse=True):
            communities.append({
                'discord_tag': tag,
                'display_name': display_names.get(tag, tag),
                'total_systems': sys_rows.get(tag, {}).get('total_systems', 0),
                'total_discoveries': disc_rows.get(tag, {}).get('total_discoveries', 0),
                'unique_contributors': sys_rows.get(tag, {}).get('unique_contributors', 0),
                'manual_systems': source_rows.get(tag, {}).get('manual_systems', 0),
                'extractor_systems': source_rows.get(tag, {}).get('extractor_systems', 0),
            })

        # Grand totals
        total_systems = sum(c['total_systems'] for c in communities)
        total_discoveries = sum(c['total_discoveries'] for c in communities)

        cursor.execute("SELECT COUNT(DISTINCT COALESCE(NULLIF(discovered_by, ''), personal_discord_username)) FROM systems")
        total_contributors = cursor.fetchone()[0] or 0

        return {
            'communities': communities,
            'totals': {
                'total_systems': total_systems,
                'total_discoveries': total_discoveries,
                'total_communities': len(communities),
                'total_contributors': total_contributors,
            }
        }
    finally:
        if conn:
            conn.close()


@router.get('/api/public/contributors')
async def public_contributors(community: Optional[str] = None, limit: int = 50):
    """
    Public endpoint: ranked contributor list with upload method per member.
    Only shows approved system counts and discovery counts (no rejection data).
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        tag_filter = ''
        tag_params = []
        if community:
            tag_filter = ' AND discord_tag = ?'
            tag_params = [community]

        # Username normalization (same pattern as admin leaderboard)
        raw_username = '''COALESCE(
            NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
            personal_discord_username,
            json_extract(system_data, '$.discovered_by'),
            'Unknown'
        )'''
        trimmed_username = f"TRIM(REPLACE({raw_username}, '#', ''))"
        normalized_username = f"""LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_username}) > 4
                    AND SUBSTR({trimmed_username}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_username}) = 4
                        OR SUBSTR({trimmed_username}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_username}, 1, LENGTH({trimmed_username}) - 4)
                ELSE {trimmed_username}
            END
        ))"""

        tag_display = "COALESCE(NULLIF(discord_tag, ''), 'Personal')"

        # Approved systems per contributor with source breakdown
        query = f'''
            SELECT
                MAX({raw_username}) as username,
                {normalized_username} as normalized_name,
                GROUP_CONCAT(DISTINCT {tag_display}) as discord_tags,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as total_systems,
                SUM(CASE WHEN status = 'approved' AND COALESCE(source, 'manual') = 'manual' THEN 1 ELSE 0 END) as manual_count,
                SUM(CASE WHEN status = 'approved' AND source = 'haven_extractor' THEN 1 ELSE 0 END) as extractor_count,
                MAX(submission_date) as last_activity
            FROM pending_systems
            WHERE status = 'approved' {tag_filter}
            GROUP BY {normalized_username}
            HAVING {normalized_username} != 'unknown' AND total_systems > 0
            ORDER BY total_systems DESC
            LIMIT ?
        '''
        cursor.execute(query, tag_params + [limit])
        sys_rows = cursor.fetchall()

        # Build contributor dict keyed by normalized name
        contributors = {}
        for row in sys_rows:
            entry = dict(row)
            norm = entry.pop('normalized_name')
            contributors[norm] = entry
            contributors[norm]['total_discoveries'] = 0

        # Discovery counts per contributor
        disc_raw = "COALESCE(NULLIF(NULLIF(discovered_by, 'Anonymous'), 'anonymous'), 'Unknown')"
        disc_trimmed = f"TRIM(REPLACE({disc_raw}, '#', ''))"
        disc_normalized = f"""LOWER(TRIM(
            CASE
                WHEN LENGTH({disc_trimmed}) > 4
                    AND SUBSTR({disc_trimmed}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({disc_trimmed}) = 4
                        OR SUBSTR({disc_trimmed}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({disc_trimmed}, 1, LENGTH({disc_trimmed}) - 4)
                ELSE {disc_trimmed}
            END
        ))"""

        disc_tag_filter = ''
        disc_tag_params = []
        if community:
            disc_tag_filter = ' AND discord_tag = ?'
            disc_tag_params = [community]

        disc_query = f'''
            SELECT {disc_normalized} as normalized_name, COUNT(*) as total_discoveries
            FROM discoveries
            WHERE 1=1 {disc_tag_filter}
            GROUP BY {disc_normalized}
        '''
        cursor.execute(disc_query, disc_tag_params)
        for row in cursor.fetchall():
            norm = row['normalized_name']
            if norm in contributors:
                contributors[norm]['total_discoveries'] = row['total_discoveries']

        # Build ranked list
        ranked = sorted(contributors.values(), key=lambda c: c['total_systems'], reverse=True)
        for i, entry in enumerate(ranked, 1):
            entry['rank'] = i

        # Total unique contributors
        count_query = f'''
            SELECT COUNT(DISTINCT {normalized_username}) as cnt
            FROM pending_systems
            WHERE status = 'approved' {tag_filter}
              AND {normalized_username} != 'unknown'
        '''
        cursor.execute(count_query, tag_params)
        total = cursor.fetchone()['cnt'] or 0

        return {
            'contributors': ranked,
            'total_contributors': total,
        }
    finally:
        if conn:
            conn.close()


@router.get('/api/public/activity-timeline')
async def public_activity_timeline(granularity: str = 'week', months: int = 6):
    """
    Public endpoint: combined systems + discoveries timeline.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Date format based on granularity
        if granularity == 'day':
            date_fmt = '%Y-%m-%d'
        elif granularity == 'month':
            date_fmt = '%Y-%m'
        else:
            date_fmt = '%Y-W%W'
            granularity = 'week'

        date_cutoff = f"date('now', '-{months} months')"

        # Manual systems timeline (source column is on pending_systems, not systems)
        manual_query = f'''
            SELECT strftime('{date_fmt}', submission_date) as date,
                   COUNT(*) as count
            FROM pending_systems
            WHERE submission_date >= {date_cutoff}
              AND status = 'approved'
              AND COALESCE(source, 'manual') = 'manual'
            GROUP BY date
            ORDER BY date
        '''
        cursor.execute(manual_query)
        manual_data = {r['date']: r['count'] for r in cursor.fetchall()}

        # Extractor systems timeline
        extractor_query = f'''
            SELECT strftime('{date_fmt}', submission_date) as date,
                   COUNT(*) as count
            FROM pending_systems
            WHERE submission_date >= {date_cutoff}
              AND status = 'approved'
              AND source = 'haven_extractor'
            GROUP BY date
            ORDER BY date
        '''
        cursor.execute(extractor_query)
        extractor_data = {r['date']: r['count'] for r in cursor.fetchall()}

        # Discoveries timeline
        disc_query = f'''
            SELECT strftime('{date_fmt}', submission_timestamp) as date,
                   COUNT(*) as discoveries
            FROM discoveries
            WHERE submission_timestamp >= {date_cutoff}
            GROUP BY date
            ORDER BY date
        '''
        cursor.execute(disc_query)
        disc_data = {r['date']: r['discoveries'] for r in cursor.fetchall()}

        # Merge into combined timeline
        all_dates = sorted(set(manual_data.keys()) | set(extractor_data.keys()) | set(disc_data.keys()))
        timeline = []
        for date in all_dates:
            if date:  # skip NULL dates
                timeline.append({
                    'date': date,
                    'manual': manual_data.get(date, 0),
                    'extractor': extractor_data.get(date, 0),
                    'discoveries': disc_data.get(date, 0),
                })

        return {'timeline': timeline, 'granularity': granularity}
    finally:
        if conn:
            conn.close()


@router.get('/api/public/discovery-breakdown')
async def public_discovery_breakdown():
    """
    Public endpoint: discovery counts grouped by type (all communities combined).
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                COALESCE(type_slug, 'other') as type_slug,
                COALESCE(discovery_type, 'Other') as discovery_type,
                COUNT(*) as count
            FROM discoveries
            GROUP BY type_slug
            ORDER BY count DESC
        ''')
        rows = cursor.fetchall()
        breakdown = [dict(row) for row in rows]

        total = sum(item['count'] for item in breakdown)
        for item in breakdown:
            item['percentage'] = round((item['count'] / total * 100), 1) if total > 0 else 0

        return {'breakdown': breakdown, 'total': total}
    finally:
        if conn:
            conn.close()


@router.get('/api/public/community-regions')
async def public_community_regions(community: str):
    """
    Public endpoint: regions for a specific community with lightweight system lists.
    Returns region name/coordinates, system count, and system id+name+star_type+grade.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all systems for this community with region info
        cursor.execute('''
            SELECT s.id, s.name, s.star_type, s.is_complete,
                   s.region_x, s.region_y, s.region_z,
                   r.custom_name as region_name
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x
                AND s.region_y = r.region_y AND s.region_z = r.region_z
            WHERE s.discord_tag = ?
            ORDER BY r.custom_name IS NULL, r.custom_name, s.name
        ''', [community])
        rows = cursor.fetchall()

        # Group by region
        regions_map = {}
        for row in rows:
            key = (row['region_x'], row['region_y'], row['region_z'])
            if key not in regions_map:
                custom = row['region_name']
                regions_map[key] = {
                    'region_x': row['region_x'],
                    'region_y': row['region_y'],
                    'region_z': row['region_z'],
                    'custom_name': custom,
                    'display_name': custom if custom else f"Region ({row['region_x']}, {row['region_y']}, {row['region_z']})",
                    'system_count': 0,
                    'systems': [],
                }
            # NOTE: is_complete stores score 0-100 (repurposed from boolean)
            score = row['is_complete'] or 0
            if score >= 85:
                grade = 'S'
            elif score >= 65:
                grade = 'A'
            elif score >= 40:
                grade = 'B'
            else:
                grade = 'C'
            regions_map[key]['systems'].append({
                'id': row['id'],
                'name': row['name'],
                'star_type': row['star_type'] or 'Unknown',
                'completeness_grade': grade,
            })
            regions_map[key]['system_count'] += 1

        # Sort: named regions first by count desc, then unnamed by count desc
        regions = sorted(
            regions_map.values(),
            key=lambda r: (r['custom_name'] is None, -r['system_count'])
        )

        return {'regions': regions, 'total_regions': len(regions)}
    finally:
        if conn:
            conn.close()
