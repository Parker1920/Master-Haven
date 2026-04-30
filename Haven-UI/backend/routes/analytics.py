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


@router.get('/api/public/user-stats')
async def public_user_stats(username: str):
    """
    Public endpoint: contribution stats for a single user by username.
    Returns manual systems, extractor systems, discoveries, and last activity.
    Designed for Discord bot integration.
    """
    username = username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Normalize the input username (same logic as leaderboard)
        input_clean = username.replace('#', '').strip()
        # Strip trailing 4-digit Discord discriminator
        if (len(input_clean) > 4
                and input_clean[-4:].isdigit()
                and (len(input_clean) == 4 or not input_clean[-5].isdigit())):
            input_clean = input_clean[:-4]
        input_normalized = input_clean.lower().strip()

        if not input_normalized:
            raise HTTPException(status_code=400, detail="Invalid username")

        # Username normalization SQL (matches /api/public/contributors exactly)
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

        # Systems stats from pending_systems (approved only)
        cursor.execute(f'''
            SELECT
                MAX({raw_username}) as display_name,
                GROUP_CONCAT(DISTINCT COALESCE(NULLIF(discord_tag, ''), 'Personal')) as communities,
                COUNT(*) as total_systems,
                SUM(CASE WHEN COALESCE(source, 'manual') = 'manual' THEN 1 ELSE 0 END) as manual_count,
                SUM(CASE WHEN source = 'haven_extractor' THEN 1 ELSE 0 END) as extractor_count,
                MAX(submission_date) as last_system_activity
            FROM pending_systems
            WHERE status = 'approved' AND {normalized_username} = ?
        ''', (input_normalized,))
        sys_row = cursor.fetchone()

        total_systems = sys_row['total_systems'] if sys_row and sys_row['total_systems'] else 0

        # Discovery stats
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

        cursor.execute(f'''
            SELECT COUNT(*) as total_discoveries,
                   MAX(submission_timestamp) as last_discovery_activity
            FROM discoveries
            WHERE {disc_normalized} = ?
        ''', (input_normalized,))
        disc_row = cursor.fetchone()

        total_discoveries = disc_row['total_discoveries'] if disc_row and disc_row['total_discoveries'] else 0

        if total_systems == 0 and total_discoveries == 0:
            raise HTTPException(status_code=404, detail="No contributions found for that username")

        # Pick the best display name and most recent activity
        display_name = (sys_row['display_name'] if sys_row and sys_row['display_name'] else username)
        communities = (sys_row['communities'] if sys_row and sys_row['communities'] else None)
        last_system = sys_row['last_system_activity'] if sys_row else None
        last_disc = disc_row['last_discovery_activity'] if disc_row else None
        last_activity = max(filter(None, [last_system, last_disc]), default=None)

        return {
            'username': display_name,
            'communities': communities.split(',') if communities else [],
            'systems': {
                'total': total_systems,
                'manual': sys_row['manual_count'] or 0 if sys_row else 0,
                'extractor': sys_row['extractor_count'] or 0 if sys_row else 0,
            },
            'discoveries': total_discoveries,
            'last_activity': last_activity,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User stats lookup failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to look up user stats")
    finally:
        if conn:
            conn.close()


# ============================================================================
# Poster-driven aggregation endpoints
# Single-call data fetches sized for the Voyager Card and Galaxy Atlas posters.
# Composing multiple existing endpoints client-side worked but produced 4-6
# round-trips; a poster render needs everything in one shot.
# ============================================================================

@router.get('/api/public/voyager-fingerprint')
async def public_voyager_fingerprint(username: str):
    """One-shot fingerprint payload for the Voyager Card poster.

    Returns rank in primary community, total systems, galaxy reach, lifeform
    balance, top named regions, first-charted system, and completeness
    distribution — everything a single Voyager poster needs to render.

    Honors `user_profiles.poster_public`. If the matched profile has opted out
    we still return public-leaderboard counts but flag `poster_public: false`
    so the frontend can render a privacy placeholder instead of the full card.
    """
    username = username.strip()
    if not username:
        raise HTTPException(status_code=400, detail='username required')

    # Same normalization as /api/public/user-stats and the contributor leaderboard.
    # URL slugs use hyphens for spaces (so /voyager/hiroki-rinn resolves to
    # "Hiroki Rinn") — convert hyphens back to spaces before the DB lookup.
    input_clean = username.replace('#', '').strip()
    if (len(input_clean) > 4
            and input_clean[-4:].isdigit()
            and (len(input_clean) == 4 or not input_clean[-5].isdigit())):
        input_clean = input_clean[:-4]
    input_normalized = input_clean.lower().replace('-', ' ').strip()
    if not input_normalized:
        raise HTTPException(status_code=400, detail='Invalid username')

    raw_username = '''COALESCE(
        NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
        personal_discord_username,
        json_extract(system_data, '$.discovered_by'),
        'Unknown'
    )'''
    trimmed = f"TRIM(REPLACE({raw_username}, '#', ''))"
    # Outer REPLACE collapses hyphens to spaces so DB names containing hyphens
    # match slug input as well (rare, but keeps the two sides symmetric).
    norm = f"""REPLACE(LOWER(TRIM(
        CASE
            WHEN LENGTH({trimmed}) > 4
                AND SUBSTR({trimmed}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                AND (LENGTH({trimmed}) = 4
                    OR SUBSTR({trimmed}, -5, 1) NOT GLOB '[0-9]')
            THEN SUBSTR({trimmed}, 1, LENGTH({trimmed}) - 4)
            ELSE {trimmed}
        END
    )), '-', ' ')"""

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ----- Aggregate per-community submission counts (approved only) -----
        cursor.execute(f'''
            SELECT
                MAX({raw_username}) as display_name,
                COALESCE(NULLIF(discord_tag, ''), 'Personal') as community,
                COUNT(*) as systems,
                SUM(CASE WHEN COALESCE(source, 'manual') = 'manual' THEN 1 ELSE 0 END) as manual_count,
                SUM(CASE WHEN source = 'haven_extractor' THEN 1 ELSE 0 END) as extractor_count,
                MIN(submission_date) as first_submission,
                MAX(submission_date) as last_submission
            FROM pending_systems
            WHERE status = 'approved' AND {norm} = ?
            GROUP BY community
        ''', (input_normalized,))
        community_rows = [dict(r) for r in cursor.fetchall()]

        if not community_rows:
            raise HTTPException(status_code=404, detail='No contributions found for that username')

        display_name = next((r['display_name'] for r in community_rows if r['display_name']), username)
        total_systems = sum(r['systems'] for r in community_rows)
        total_manual = sum(r['manual_count'] or 0 for r in community_rows)
        total_extractor = sum(r['extractor_count'] or 0 for r in community_rows)
        first_submission = min((r['first_submission'] for r in community_rows if r['first_submission']), default=None)
        last_submission = max((r['last_submission'] for r in community_rows if r['last_submission']), default=None)

        # Pick primary community: most systems, ties broken by earliest activity.
        primary = max(community_rows, key=lambda r: (r['systems'], -1 if not r['first_submission'] else 0))

        # ----- Rank within primary community -----
        cursor.execute(f'''
            SELECT {norm} as nname, COUNT(*) as cnt
            FROM pending_systems
            WHERE status = 'approved'
              AND COALESCE(NULLIF(discord_tag, ''), 'Personal') = ?
            GROUP BY {norm}
            ORDER BY cnt DESC
        ''', (primary['community'],))
        primary_ranks = [(r['nname'], r['cnt']) for r in cursor.fetchall()]
        rank_in_primary = next((i + 1 for i, (n, _) in enumerate(primary_ranks) if n == input_normalized), None)
        community_total = sum(c for _, c in primary_ranks)
        primary_pct = round(primary['systems'] / community_total * 100, 1) if community_total else 0

        # ----- Global rank across all communities -----
        cursor.execute(f'''
            SELECT {norm} as nname, COUNT(*) as cnt
            FROM pending_systems
            WHERE status = 'approved'
            GROUP BY {norm}
            HAVING {norm} != 'unknown'
            ORDER BY cnt DESC
        ''')
        global_ranks = [(r['nname'], r['cnt']) for r in cursor.fetchall()]
        global_rank = next((i + 1 for i, (n, _) in enumerate(global_ranks) if n == input_normalized), None)
        community_count = len(community_rows)

        # ----- Galaxy reach (top 5 by system count + tail count) -----
        cursor.execute(f'''
            SELECT COALESCE(galaxy, 'Euclid') as galaxy, COUNT(*) as systems
            FROM pending_systems
            WHERE status = 'approved' AND {norm} = ?
            GROUP BY galaxy
            ORDER BY systems DESC
        ''', (input_normalized,))
        galaxy_rows = cursor.fetchall()
        galaxy_reach = [{'galaxy': r['galaxy'], 'systems': r['systems']} for r in galaxy_rows]

        # ----- Per-user identifier on the systems table -----
        # Most pending_systems rows for legacy CSV imports have NULL glyph_code/region_x,
        # so joining ps→systems via glyph yields nothing. Identify the user's systems
        # directly via discovered_by/personal_discord_username on the systems row,
        # using the same normalization. Counts here are independent of the leaderboard
        # (which is why we keep pending_systems as the canonical "systems contributed"
        # number) but they're correct for region/lifeform/completeness analysis.
        sys_raw = "COALESCE(NULLIF(NULLIF(s.discovered_by, 'Anonymous'), 'anonymous'), s.personal_discord_username, s.last_updated_by, 'Unknown')"
        sys_trimmed = f"TRIM(REPLACE({sys_raw}, '#', ''))"
        sys_norm = f"""LOWER(TRIM(
            CASE
                WHEN LENGTH({sys_trimmed}) > 4
                    AND SUBSTR({sys_trimmed}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({sys_trimmed}) = 4
                        OR SUBSTR({sys_trimmed}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({sys_trimmed}, 1, LENGTH({sys_trimmed}) - 4)
                ELSE {sys_trimmed}
            END
        ))"""

        # ----- Lifeform balance (from systems table directly) -----
        cursor.execute(f'''
            SELECT
                LOWER(COALESCE(s.dominant_lifeform, 'Unknown')) as lifeform,
                COUNT(*) as cnt
            FROM systems s
            WHERE {sys_norm} = ?
              AND s.dominant_lifeform IS NOT NULL
              AND s.dominant_lifeform NOT IN ('Unknown', 'None', '')
            GROUP BY LOWER(s.dominant_lifeform)
            ORDER BY cnt DESC
        ''', (input_normalized,))
        lifeform_rows = cursor.fetchall()
        inhabited_total = sum(r['cnt'] for r in lifeform_rows)
        lifeforms = []
        for r in lifeform_rows:
            pct = round(r['cnt'] / inhabited_total * 100, 1) if inhabited_total else 0
            lifeforms.append({'name': r['lifeform'].title(), 'systems': r['cnt'], 'pct': pct})

        # ----- Top named regions (from systems → regions JOIN) -----
        cursor.execute(f'''
            SELECT
                r.custom_name as region_name,
                COUNT(*) as systems
            FROM systems s
            JOIN regions r ON s.region_x = r.region_x
                AND s.region_y = r.region_y AND s.region_z = r.region_z
                AND COALESCE(s.reality, 'Normal') = COALESCE(r.reality, 'Normal')
                AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
            WHERE r.custom_name IS NOT NULL AND r.custom_name != ''
              AND {sys_norm} = ?
            GROUP BY s.region_x, s.region_y, s.region_z
            ORDER BY systems DESC
        ''', (input_normalized,))
        named_region_rows = cursor.fetchall()
        named_regions_count = len(named_region_rows)
        top_regions = [{'name': r['region_name'], 'systems': r['systems']} for r in named_region_rows[:3]]

        # ----- First-charted system (from systems table) -----
        cursor.execute(f'''
            SELECT
                COALESCE(s.name, 'Unknown') as name,
                r.custom_name as region,
                COALESCE(s.galaxy, 'Euclid') as galaxy,
                COALESCE(s.created_at, s.discovered_at) as charted_at
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x
                AND s.region_y = r.region_y AND s.region_z = r.region_z
                AND COALESCE(s.reality, 'Normal') = COALESCE(r.reality, 'Normal')
                AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
            WHERE {sys_norm} = ?
              AND COALESCE(s.created_at, s.discovered_at) IS NOT NULL
            ORDER BY COALESCE(s.created_at, s.discovered_at) ASC
            LIMIT 1
        ''', (input_normalized,))
        row = cursor.fetchone()
        first_charted = dict(row) if row else None

        # ----- Completeness grade distribution (from systems table) -----
        # Thresholds match score_to_grade() in constants.py: S>=85, A 65-84, B 40-64, C<40.
        cursor.execute(f'''
            SELECT
                AVG(COALESCE(s.is_complete, 0)) as avg_score,
                SUM(CASE WHEN s.is_complete >= 85 THEN 1 ELSE 0 END) as grade_s,
                SUM(CASE WHEN s.is_complete >= 65 AND s.is_complete < 85 THEN 1 ELSE 0 END) as grade_a,
                SUM(CASE WHEN s.is_complete >= 40 AND s.is_complete < 65 THEN 1 ELSE 0 END) as grade_b,
                SUM(CASE WHEN s.is_complete < 40 THEN 1 ELSE 0 END) as grade_c,
                COUNT(*) as total_scored
            FROM systems s
            WHERE {sys_norm} = ?
        ''', (input_normalized,))
        grades = dict(cursor.fetchone() or {})
        avg_score = round(grades.get('avg_score') or 0, 1)
        completeness_grade = score_to_grade(avg_score)

        # ----- Privacy flag from user_profiles -----
        cursor.execute('''
            SELECT poster_public FROM user_profiles
            WHERE username_normalized = ?
            LIMIT 1
        ''', (input_normalized,))
        prof = cursor.fetchone()
        poster_public = bool(prof['poster_public']) if prof and 'poster_public' in prof.keys() else True

        return {
            'username': display_name,
            'poster_public': poster_public,
            'first_submission': first_submission,
            'last_submission': last_submission,
            'primary_community': {
                'name': primary['community'],
                'systems': primary['systems'],
                'pct_of_community': primary_pct,
                'manual': primary['manual_count'] or 0,
                'extractor': primary['extractor_count'] or 0,
                'rank': rank_in_primary,
            },
            'totals': {
                'systems': total_systems,
                'manual': total_manual,
                'extractor': total_extractor,
                'communities': community_count,
                'global_rank': global_rank,
            },
            'galaxy_reach': galaxy_reach,
            'lifeforms': lifeforms,
            'inhabited_systems': inhabited_total,
            'named_regions': named_regions_count,
            'top_regions': top_regions,
            'first_charted': first_charted,
            'completeness': {
                'avg_score': avg_score,
                'grade': completeness_grade,
                'grade_s': grades.get('grade_s') or 0,
                'grade_a': grades.get('grade_a') or 0,
                'grade_b': grades.get('grade_b') or 0,
                'grade_c': grades.get('grade_c') or 0,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Voyager fingerprint lookup failed: {e}")
        raise HTTPException(status_code=500, detail='Failed to build voyager fingerprint')
    finally:
        if conn:
            conn.close()


@router.get('/api/public/galaxy-atlas')
async def public_galaxy_atlas(galaxy: str = 'Euclid', reality: str = 'Normal'):
    """One-shot atlas payload for the Galaxy Atlas poster.

    Returns total system/region/faction counts plus a region list with
    coordinates, name, system count, and the dominant `discord_tag` color
    bucket. Builds on the same aggregation logic as /api/map/regions-aggregated
    but adds named-region indexing and faction tallies needed by the poster.
    """
    galaxy = (galaxy or 'Euclid').strip()
    reality = (reality or 'Normal').strip()

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Per-region aggregation (named regions only get an index marker on
        # the poster, but unnamed regions still contribute the dot density).
        cursor.execute('''
            SELECT
                s.region_x,
                s.region_y,
                s.region_z,
                r.custom_name as region_name,
                COUNT(*) as system_count,
                AVG(s.x) as cx,
                AVG(s.y) as cy,
                AVG(s.z) as cz,
                GROUP_CONCAT(COALESCE(NULLIF(s.discord_tag, ''), 'Personal')) as tag_list
            FROM systems s
            LEFT JOIN regions r
              ON s.region_x = r.region_x
              AND s.region_y = r.region_y
              AND s.region_z = r.region_z
              AND COALESCE(s.reality, 'Normal') = COALESCE(r.reality, 'Normal')
              AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
            WHERE COALESCE(s.galaxy, 'Euclid') = ?
              AND COALESCE(s.reality, 'Normal') = ?
              AND s.region_x IS NOT NULL
              AND s.region_y IS NOT NULL
              AND s.region_z IS NOT NULL
            GROUP BY s.region_x, s.region_y, s.region_z
            ORDER BY system_count DESC
        ''', (galaxy, reality))

        rows = cursor.fetchall()
        regions = []
        faction_counts = {}        # lowercase tag -> system count (case-insensitive merge)
        faction_canon_case = {}    # lowercase tag -> first-seen canonical case (for display fallback)
        total_systems = 0

        for row in rows:
            entry = dict(row)
            raw_tags = [t for t in (entry.pop('tag_list') or '').split(',') if t]
            # Dedupe tags case-insensitively. 'Personal' and 'personal' merge.
            # Within a region: pick most-frequent capitalization as canonical.
            tag_freq = {}        # canonical-case-for-this-region -> count
            tag_canon_case = {}
            for t in raw_tags:
                lower = t.lower()
                canonical = tag_canon_case.setdefault(lower, t)
                tag_freq[canonical] = tag_freq.get(canonical, 0) + 1
                # Track the most-canonical case across the entire galaxy
                if lower not in faction_canon_case:
                    faction_canon_case[lower] = t
            dominant = max(tag_freq.items(), key=lambda kv: kv[1])[0] if tag_freq else 'Personal'
            entry['dominant_tag'] = dominant
            entry['tag_breakdown'] = tag_freq
            regions.append(entry)
            total_systems += entry['system_count']
            # Accumulate into faction_counts by LOWERCASE key so Personal/personal merge.
            for t, c in tag_freq.items():
                key = t.lower()
                faction_counts[key] = faction_counts.get(key, 0) + c

        # Lookup display names from discord_tag_colors (in super_admin_settings).
        display_name_map = _load_tag_display_names(cursor)

        # ----- Option C region picker -----
        # Faction-first with spatial deduplication. See poster-system-plan.md.
        named_pool = [r for r in regions if r['region_name']]
        picked = _pick_atlas_regions(named_pool, max_picks=9)
        for i, r in enumerate(picked, 1):
            r['index_number'] = i

        # faction_counts is now keyed by lowercase tag. Render with the canonical
        # case (first-seen capitalization) and resolve display_name via API → hardcoded fallback.
        factions = sorted(
            [{
                'tag': faction_canon_case.get(lk, lk),
                'systems': v,
                'display_name': display_name_map.get(lk) or _ATLAS_HARDCODED_DISPLAY_NAMES.get(lk) or faction_canon_case.get(lk, lk),
            } for lk, v in faction_counts.items()],
            key=lambda f: f['systems'],
            reverse=True,
        )

        return {
            'galaxy': galaxy,
            'reality': reality,
            'total_systems': total_systems,
            'total_regions': len(regions),
            'total_named_regions': len(named_pool),
            'total_factions': len(factions),
            'regions': regions,
            'named_regions': picked,
            'factions': factions,
        }
    except Exception as e:
        logger.exception(f"Galaxy atlas lookup failed: {e}")
        raise HTTPException(status_code=500, detail='Failed to build galaxy atlas')
    finally:
        if conn:
            conn.close()


# ============================================================================
# Galaxy atlas helpers — region picker + display-name lookup
# ============================================================================

# Hardcoded display-name fallbacks for tags that pre-date the discord_tag_colors API.
# Mirrors Haven-UI/src/posters/_shared/colors.js HARDCODED_DISPLAY_NAMES so the bot
# and any non-frontend consumer get the same display strings the UI shows.
_ATLAS_HARDCODED_DISPLAY_NAMES = {
    'ghub': 'Galactic Hub',
    'haven': 'Haven',
    'evrn': 'Everion Empire',
    'tgc': 'Tugarv Compendium',
    'acsd': 'Atlas-CSD',
    'shdw': 'Shadow Worlds',
    'tps': 'TPS',
    'tbh': 'Mourning Amity',
    'hg': 'Hilbert Group',
    'iea': 'IEA',
    'b.e.s': 'B.E.S',
    'bes': 'B.E.S',
    'arch': 'ARCH',
    'personal': 'Personal',
    'rss': 'RSS',
}


def _load_tag_display_names(cursor) -> dict:
    """Return {lowercase_tag: display_name} from super_admin_settings.discord_tag_colors.

    The settings JSON is the source of truth for tag → display name. Falls back
    to an empty dict if the setting doesn't exist; callers should default to
    the raw tag name.
    """
    try:
        cursor.execute(
            "SELECT setting_value FROM super_admin_settings WHERE setting_key = 'discord_tag_colors' LIMIT 1"
        )
        row = cursor.fetchone()
        if not row or not row['setting_value']:
            return {}
        import json as _json
        data = _json.loads(row['setting_value'])
        if not isinstance(data, dict):
            return {}
        out = {}
        for tag, info in data.items():
            if isinstance(info, dict) and info.get('name'):
                out[str(tag).lower()] = info['name']
        return out
    except Exception as e:
        logger.warning(f"_load_tag_display_names failed: {e}")
        return {}


def _pick_atlas_regions(named_pool: list, max_picks: int = 9) -> list:
    """Option C: faction-first with spatial deduplication.

    Algorithm:
      1. Group named regions by dominant_tag.
      2. For each tag, take its single biggest region (the civ's "flagship").
      3. Sort flagship list by system_count desc.
      4. Walk the sorted list. For each candidate, if it's too close to an
         already-picked marker, skip it and try the next-best region of a
         still-unrepresented civ.
      5. If <max_picks chosen after one pass, fill from the next-largest
         unpicked regions (any civ), still respecting the distance threshold.
      6. Return up to max_picks regions in the order they were picked.

    Distance threshold = 10% of the bounding-box diagonal of named regions.
    """
    if not named_pool:
        return []

    # Sort the pool once by size (largest first) to make picking deterministic
    pool_sorted = sorted(named_pool, key=lambda r: r['system_count'], reverse=True)

    # Compute spatial threshold from bounding box
    min_x = min(r['region_x'] for r in pool_sorted)
    max_x = max(r['region_x'] for r in pool_sorted)
    min_z = min(r['region_z'] for r in pool_sorted)
    max_z = max(r['region_z'] for r in pool_sorted)
    diag = ((max_x - min_x) ** 2 + (max_z - min_z) ** 2) ** 0.5
    threshold = max(diag * 0.1, 5.0)  # ~10% of diagonal, floor at 5 region units

    def too_close(candidate, picked_list):
        for p in picked_list:
            dx = candidate['region_x'] - p['region_x']
            dz = candidate['region_z'] - p['region_z']
            if (dx * dx + dz * dz) ** 0.5 < threshold:
                return True
        return False

    picked = []
    seen_tags = set()

    # Pass 1: faction-first — top region per civ, in size order
    # Build a dict: lowercase_tag -> [regions (sorted by size desc)]
    by_tag = {}
    for r in pool_sorted:
        tag = (r.get('dominant_tag') or 'Personal').lower()
        by_tag.setdefault(tag, []).append(r)

    # Sort civs by their flagship region's size (largest first)
    civ_flagships = sorted(
        [(tag, regions[0]) for tag, regions in by_tag.items()],
        key=lambda kv: kv[1]['system_count'],
        reverse=True,
    )

    for tag, flagship in civ_flagships:
        if len(picked) >= max_picks:
            break
        if too_close(flagship, picked):
            # Try the next-best region for this civ if any survives the threshold
            for alt in by_tag[tag][1:]:
                if not too_close(alt, picked):
                    picked.append(alt)
                    seen_tags.add(tag)
                    break
            continue
        picked.append(flagship)
        seen_tags.add(tag)

    # Pass 2: fill remaining slots from any region (regardless of civ rep)
    if len(picked) < max_picks:
        picked_ids = {(r['region_x'], r['region_y'], r['region_z']) for r in picked}
        for candidate in pool_sorted:
            if len(picked) >= max_picks:
                break
            cid = (candidate['region_x'], candidate['region_y'], candidate['region_z'])
            if cid in picked_ids:
                continue
            if too_close(candidate, picked):
                continue
            picked.append(candidate)
            picked_ids.add(cid)

    return picked
