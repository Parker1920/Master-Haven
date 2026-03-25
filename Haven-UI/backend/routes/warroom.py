"""War Room endpoints - territorial conflicts, news, claims, peace treaties."""

import json
import logging
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, Cookie

from constants import HAVEN_UI_DIR
from db import get_db_connection
from image_processor import process_image
from services.auth_service import (
    get_session,
    hash_password,
    verify_password,
    _needs_rehash,
    _sessions as sessions,
    create_session,
)

logger = logging.getLogger('control.room')

router = APIRouter(tags=["warroom"])

# War media upload directory
war_media_dir = HAVEN_UI_DIR / 'public' / 'war-media'

# Media upload constraints
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# =============================================================================
# WAR ROOM HELPER FUNCTIONS
# =============================================================================


def get_war_room_partner_info(session: dict) -> dict:
    """Get partner info for War Room operations. Returns None if not enrolled."""
    if not session:
        return None

    user_type = session.get('user_type')
    partner_id = None

    if user_type == 'super_admin':
        return {'is_super_admin': True, 'partner_id': None}

    if user_type == 'partner':
        partner_id = session.get('partner_id')
    elif user_type == 'sub_admin':
        # Sub-admin's parent partner is stored as 'partner_id' in session
        partner_id = session.get('partner_id')

    if not partner_id:
        return None

    # Check if enrolled in War Room
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT wre.id, pa.display_name, pa.discord_tag, pa.region_color
            FROM war_room_enrollment wre
            JOIN partner_accounts pa ON wre.partner_id = pa.id
            WHERE wre.partner_id = ? AND wre.is_active = 1
        ''', (partner_id,))
        row = cursor.fetchone()
        if not row:
            return None

        return {
            'is_super_admin': False,
            'partner_id': partner_id,
            'enrollment_id': row[0],
            'display_name': row[1],
            'discord_tag': row[2],
            'region_color': row[3]
        }
    finally:
        conn.close()


async def send_war_notification(
    partner_id: int,
    notification_type: str,
    title: str,
    message: str,
    conflict_id: int = None
):
    """Create in-app notification and optionally send Discord webhook."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Create in-app notification
        cursor.execute('''
            INSERT INTO war_notifications (recipient_partner_id, notification_type, title, message, related_conflict_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (partner_id, notification_type, title, message, conflict_id))
        conn.commit()

        # Check for Discord webhook
        cursor.execute('''
            SELECT webhook_url FROM discord_webhooks
            WHERE partner_id = ? AND is_active = 1
        ''', (partner_id,))
        webhook_row = cursor.fetchone()

        if webhook_row and webhook_row[0]:
            webhook_url = webhook_row[0]
            # Send webhook using requests (fire and forget)
            import requests as req_lib
            embed = {
                "title": f"WAR ROOM: {title}",
                "description": message,
                "color": 15158332,  # Red
                "footer": {"text": "Haven War Room"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            try:
                req_lib.post(webhook_url, json={"embeds": [embed]}, timeout=5)
                cursor.execute('''
                    UPDATE discord_webhooks SET last_triggered_at = ? WHERE partner_id = ?
                ''', (datetime.now(timezone.utc).isoformat(), partner_id))
                conn.commit()
            except Exception as e:
                logger.warning(f"Failed to send War Room webhook to partner {partner_id}: {e}")
    finally:
        conn.close()


async def add_activity_feed_entry(
    event_type: str,
    headline: str,
    actor_partner_id: int = None,
    actor_name: str = None,
    target_partner_id: int = None,
    target_name: str = None,
    conflict_id: int = None,
    system_id: str = None,
    system_name: str = None,
    region_name: str = None,
    details: str = None,
    is_public: bool = True
):
    """Helper function to add an entry to the activity feed."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO war_activity_feed
            (event_type, headline, actor_partner_id, actor_name, target_partner_id, target_name,
             conflict_id, system_id, system_name, region_name, details, is_public)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (event_type, headline, actor_partner_id, actor_name, target_partner_id, target_name,
              conflict_id, system_id, system_name, region_name, details, 1 if is_public else 0))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


async def recalculate_war_statistics_internal(conn=None):
    """Internal function to recalculate war statistics (excludes practice conflicts)."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    cursor = conn.cursor()
    try:
        # Clear existing stats
        cursor.execute('DELETE FROM war_statistics')

        # Note: All queries exclude practice conflicts with (is_practice IS NULL OR is_practice = 0)

        # Longest Defense: defender_victory with max duration
        cursor.execute('''
            SELECT defender_partner_id, pa.display_name,
                   CAST((julianday(resolved_at) - julianday(declared_at)) * 24 AS INTEGER) as hours,
                   target_system_name, id
            FROM conflicts c
            JOIN partner_accounts pa ON c.defender_partner_id = pa.id
            WHERE resolution = 'defender_victory' AND resolved_at IS NOT NULL
              AND (c.is_practice IS NULL OR c.is_practice = 0)
            ORDER BY hours DESC LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            cursor.execute('''
                INSERT INTO war_statistics (stat_type, partner_id, partner_display_name, value, value_unit, details)
                VALUES ('longest_defense', ?, ?, ?, 'hours', ?)
            ''', (row[0], row[1], row[2], json.dumps({'system': row[3], 'conflict_id': row[4]})))

        # Fastest Invasion: attacker_victory with min duration
        cursor.execute('''
            SELECT attacker_partner_id, pa.display_name,
                   CAST((julianday(resolved_at) - julianday(declared_at)) * 24 AS INTEGER) as hours,
                   target_system_name, id
            FROM conflicts c
            JOIN partner_accounts pa ON c.attacker_partner_id = pa.id
            WHERE resolution = 'attacker_victory' AND resolved_at IS NOT NULL
              AND (c.is_practice IS NULL OR c.is_practice = 0)
            ORDER BY hours ASC LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            cursor.execute('''
                INSERT INTO war_statistics (stat_type, partner_id, partner_display_name, value, value_unit, details)
                VALUES ('fastest_invasion', ?, ?, ?, 'hours', ?)
            ''', (row[0], row[1], row[2], json.dumps({'system': row[3], 'conflict_id': row[4]})))

        # Largest Battle: conflict with most events
        cursor.execute('''
            SELECT c.id, c.target_system_name, c.attacker_partner_id, att.display_name,
                   c.defender_partner_id, def.display_name, COUNT(ce.id) as event_count
            FROM conflicts c
            JOIN partner_accounts att ON c.attacker_partner_id = att.id
            JOIN partner_accounts def ON c.defender_partner_id = def.id
            LEFT JOIN conflict_events ce ON c.id = ce.conflict_id
            WHERE (c.is_practice IS NULL OR c.is_practice = 0)
            GROUP BY c.id
            ORDER BY event_count DESC LIMIT 1
        ''')
        row = cursor.fetchone()
        if row and row[6] > 0:
            cursor.execute('''
                INSERT INTO war_statistics (stat_type, partner_id, partner_display_name, value, value_unit, details)
                VALUES ('largest_battle', NULL, NULL, ?, 'events', ?)
            ''', (row[6], json.dumps({
                'conflict_id': row[0], 'system': row[1],
                'attacker': row[3], 'defender': row[5]
            })))

        # Most Conquered: attacker with most victories
        cursor.execute('''
            SELECT attacker_partner_id, pa.display_name, COUNT(*) as wins
            FROM conflicts c
            JOIN partner_accounts pa ON c.attacker_partner_id = pa.id
            WHERE resolution = 'attacker_victory'
              AND (c.is_practice IS NULL OR c.is_practice = 0)
            GROUP BY attacker_partner_id
            ORDER BY wins DESC LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            cursor.execute('''
                INSERT INTO war_statistics (stat_type, partner_id, partner_display_name, value, value_unit, details)
                VALUES ('most_conquered', ?, ?, ?, 'systems', NULL)
            ''', (row[0], row[1], row[2]))

        conn.commit()
        logger.info("War Room: Statistics recalculated")
    finally:
        if close_conn:
            conn.close()


def create_auto_news(conn, event_type: str, headline: str, body: str, reference_id: int = None, reference_type: str = None, conflict_id: int = None):
    """Helper to create auto-generated news articles for war events."""
    cursor = conn.cursor()

    # Check if we already created news for this event
    if reference_id and reference_type:
        cursor.execute('''
            SELECT id FROM auto_news_events
            WHERE event_type = ? AND reference_id = ? AND reference_type = ?
        ''', (event_type, reference_id, reference_type))
        if cursor.fetchone():
            return None  # Already generated

    # Create the news article
    cursor.execute('''
        INSERT INTO war_news (headline, body, author_username, author_type, related_conflict_id, article_type)
        VALUES (?, ?, 'SYSTEM', 'auto', ?, 'breaking')
    ''', (headline, body, conflict_id))
    news_id = cursor.lastrowid

    # Record that we generated this
    cursor.execute('''
        INSERT INTO auto_news_events (event_type, reference_id, reference_type, news_id)
        VALUES (?, ?, ?, ?)
    ''', (event_type, reference_id, reference_type, news_id))

    # Also add to activity feed
    cursor.execute('''
        INSERT INTO war_activity_feed (event_type, headline, details, conflict_id, is_public)
        VALUES (?, ?, ?, ?, 1)
    ''', (event_type, headline, body, conflict_id))

    return news_id


# =============================================================================
# ENROLLMENT ENDPOINTS
# =============================================================================


@router.get('/api/warroom/enrollment')
async def get_war_room_enrollment(session: Optional[str] = Cookie(None)):
    """List all enrolled civs in War Room."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT wre.id, wre.partner_id, pa.display_name, pa.discord_tag, pa.region_color,
                   wre.enrolled_at, wre.enrolled_by, wre.is_active,
                   wre.home_region_x, wre.home_region_y, wre.home_region_z,
                   wre.home_region_name, wre.home_galaxy
            FROM war_room_enrollment wre
            JOIN partner_accounts pa ON wre.partner_id = pa.id
            WHERE wre.is_active = 1
            ORDER BY wre.enrolled_at DESC
        ''')
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'partner_id': r[1],
            'display_name': r[2],
            'discord_tag': r[3],
            'region_color': r[4],
            'enrolled_at': r[5],
            'enrolled_by': r[6],
            'is_active': r[7],
            'home_region_x': r[8],
            'home_region_y': r[9],
            'home_region_z': r[10],
            'home_region_name': r[11],
            'home_galaxy': r[12]
        } for r in rows]
    finally:
        conn.close()


@router.post('/api/warroom/enrollment')
async def enroll_in_war_room(request: Request, session: Optional[str] = Cookie(None)):
    """Enroll a partner in War Room (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()
    partner_id = data.get('partner_id')
    if not partner_id:
        raise HTTPException(status_code=400, detail="partner_id required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check partner exists and get current enabled_features + discord_tag
        cursor.execute('SELECT id, display_name, enabled_features, discord_tag FROM partner_accounts WHERE id = ?', (partner_id,))
        partner = cursor.fetchone()
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")

        discord_tag = partner[3]

        # Check if already enrolled (only check active enrollments)
        cursor.execute('SELECT id, is_active FROM war_room_enrollment WHERE partner_id = ?', (partner_id,))
        existing = cursor.fetchone()
        if existing:
            if existing[1] == 1:  # is_active = 1
                raise HTTPException(status_code=409, detail="Partner already enrolled")
            else:
                # Re-activate existing enrollment
                cursor.execute('''
                    UPDATE war_room_enrollment SET is_active = 1, enrolled_by = ?, enrolled_at = datetime('now')
                    WHERE partner_id = ?
                ''', (session_data.get('username'), partner_id))
        else:
            # Add new enrollment
            cursor.execute('''
                INSERT INTO war_room_enrollment (partner_id, enrolled_by)
                VALUES (?, ?)
            ''', (partner_id, session_data.get('username')))

        # Also add 'war_room' to partner's enabled_features so navbar shows the tab
        current_features = json.loads(partner[2] or '[]')
        if 'war_room' not in current_features:
            current_features.append('war_room')
            cursor.execute('''
                UPDATE partner_accounts SET enabled_features = ? WHERE id = ?
            ''', (json.dumps(current_features), partner_id))

        # Auto-claim all systems with this partner's discord_tag as initial territory
        systems_claimed = 0
        if discord_tag:
            cursor.execute('''
                SELECT id, name, region_x, region_y, region_z, galaxy, reality
                FROM systems
                WHERE discord_tag = ?
            ''', (discord_tag,))
            systems = cursor.fetchall()

            for system in systems:
                system_id, name, region_x, region_y, region_z, galaxy, reality = system
                # Check if already claimed
                cursor.execute('SELECT id FROM territorial_claims WHERE system_id = ?', (system_id,))
                if not cursor.fetchone():
                    cursor.execute('''
                        INSERT INTO territorial_claims (system_id, claimant_partner_id, region_x, region_y, region_z, galaxy, reality, claim_type, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'initial', 'Auto-claimed on enrollment')
                    ''', (system_id, partner_id, region_x, region_y, region_z, galaxy, reality))
                    systems_claimed += 1

            logger.info(f"War Room: Auto-claimed {systems_claimed} systems for {partner[1]} based on discord_tag '{discord_tag}'")

        conn.commit()

        logger.info(f"War Room: Enrolled {partner[1]} (ID: {partner_id})")
        return {
            'status': 'enrolled',
            'partner_id': partner_id,
            'display_name': partner[1],
            'systems_claimed': systems_claimed
        }
    finally:
        conn.close()


@router.delete('/api/warroom/enrollment/{partner_id}')
async def unenroll_from_war_room(partner_id: int, session: Optional[str] = Cookie(None)):
    """Unenroll a partner from War Room (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE war_room_enrollment SET is_active = 0 WHERE partner_id = ?
        ''', (partner_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Enrollment not found")

        # Also remove 'war_room' from partner's enabled_features
        cursor.execute('SELECT enabled_features FROM partner_accounts WHERE id = ?', (partner_id,))
        row = cursor.fetchone()
        if row:
            current_features = json.loads(row[0] or '[]')
            if 'war_room' in current_features:
                current_features.remove('war_room')
                cursor.execute('''
                    UPDATE partner_accounts SET enabled_features = ? WHERE id = ?
                ''', (json.dumps(current_features), partner_id))

        conn.commit()

        logger.info(f"War Room: Unenrolled partner ID {partner_id}")
        return {'status': 'unenrolled', 'partner_id': partner_id}
    finally:
        conn.close()


@router.get('/api/warroom/enrollment/status')
async def get_enrollment_status(session: Optional[str] = Cookie(None)):
    """Check if current user's civ is enrolled in War Room."""
    try:
        session_data = get_session(session)

        # Check if correspondent
        if session_data and session_data.get('user_type') == 'correspondent':
            return {
                'enrolled': False,
                'is_correspondent': True,
                'display_name': session_data.get('display_name', session_data.get('username'))
            }

        partner_info = get_war_room_partner_info(session_data)

        if partner_info and partner_info.get('is_super_admin'):
            return {'enrolled': True, 'is_super_admin': True}

        if not partner_info:
            return {'enrolled': False}

        return {
            'enrolled': True,
            'partner_id': partner_info['partner_id'],
            'display_name': partner_info['display_name'],
            'discord_tag': partner_info['discord_tag'],
            'region_color': partner_info['region_color']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_enrollment_status: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put('/api/warroom/enrollment/{partner_id}/home-region')
async def set_home_region(partner_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Set home region for an enrolled civilization (super admin or own civ)."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)

    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    # Allow super admin or the partner themselves
    is_super_admin = partner_info.get('is_super_admin')
    is_own_civ = partner_info.get('partner_id') == partner_id

    if not is_super_admin and not is_own_civ:
        raise HTTPException(status_code=403, detail="Can only set home region for your own civilization")

    data = await request.json()
    region_x = data.get('region_x')
    region_y = data.get('region_y')
    region_z = data.get('region_z')
    region_name = data.get('region_name')
    galaxy = data.get('galaxy', 'Euclid')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check enrollment exists
        cursor.execute('SELECT id FROM war_room_enrollment WHERE partner_id = ? AND is_active = 1', (partner_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Enrollment not found")

        cursor.execute('''
            UPDATE war_room_enrollment
            SET home_region_x = ?, home_region_y = ?, home_region_z = ?,
                home_region_name = ?, home_galaxy = ?
            WHERE partner_id = ?
        ''', (region_x, region_y, region_z, region_name, galaxy, partner_id))
        conn.commit()

        logger.info(f"War Room: Set home region for partner {partner_id}: ({region_x}, {region_y}, {region_z})")
        return {'status': 'updated', 'partner_id': partner_id}
    finally:
        conn.close()


@router.post('/api/warroom/enrollment/{partner_id}/sync-territory')
async def sync_territory(partner_id: int, session: Optional[str] = Cookie(None)):
    """Sync new unclaimed systems with this civ's discord_tag into territorial_claims. Super admin only."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get partner's discord_tag
        cursor.execute('''
            SELECT pa.discord_tag, pa.display_name
            FROM partner_accounts pa
            JOIN war_room_enrollment wre ON pa.id = wre.partner_id
            WHERE wre.partner_id = ? AND wre.is_active = 1
        ''', (partner_id,))
        partner = cursor.fetchone()
        if not partner:
            raise HTTPException(status_code=404, detail="Enrollment not found")

        discord_tag = partner[0]
        display_name = partner[1]

        if not discord_tag:
            return {'status': 'skipped', 'message': 'Partner has no discord_tag', 'systems_claimed': 0}

        # Find all systems with this discord_tag that aren't already claimed
        cursor.execute('''
            SELECT s.id, s.name, s.region_x, s.region_y, s.region_z, s.galaxy, s.reality
            FROM systems s
            WHERE s.discord_tag = ?
            AND s.id NOT IN (SELECT system_id FROM territorial_claims)
        ''', (discord_tag,))
        systems = cursor.fetchall()

        systems_claimed = 0
        for system in systems:
            system_id, name, region_x, region_y, region_z, galaxy, reality = system
            cursor.execute('''
                INSERT INTO territorial_claims (system_id, claimant_partner_id, region_x, region_y, region_z, galaxy, reality, claim_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'synced', 'Auto-synced from discord_tag')
            ''', (system_id, partner_id, region_x, region_y, region_z, galaxy, reality))
            systems_claimed += 1

        conn.commit()
        logger.info(f"War Room: Synced {systems_claimed} new systems for {display_name}")

        return {
            'status': 'synced',
            'partner_id': partner_id,
            'display_name': display_name,
            'systems_claimed': systems_claimed
        }
    finally:
        conn.close()


@router.post('/api/warroom/sync-all-territory')
async def sync_all_territory(session: Optional[str] = Cookie(None)):
    """Sync territory claims for ALL enrolled civilizations. Super admin only."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get all enrolled partners with their discord_tags
        cursor.execute('''
            SELECT pa.id, pa.discord_tag, pa.display_name
            FROM partner_accounts pa
            JOIN war_room_enrollment wre ON pa.id = wre.partner_id
            WHERE wre.is_active = 1 AND pa.discord_tag IS NOT NULL
        ''')
        partners = cursor.fetchall()

        total_systems = 0
        results = []

        for partner_id, discord_tag, display_name in partners:
            # Find systems with this discord_tag that aren't claimed
            cursor.execute('''
                SELECT s.id, s.name, s.region_x, s.region_y, s.region_z, s.galaxy, s.reality
                FROM systems s
                WHERE s.discord_tag = ?
                AND s.id NOT IN (SELECT system_id FROM territorial_claims)
            ''', (discord_tag,))
            systems = cursor.fetchall()

            partner_claimed = 0
            for system in systems:
                system_id, name, region_x, region_y, region_z, galaxy, reality = system
                cursor.execute('''
                    INSERT INTO territorial_claims (system_id, claimant_partner_id, region_x, region_y, region_z, galaxy, reality, claim_type, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'synced', 'Auto-synced from discord_tag')
                ''', (system_id, partner_id, region_x, region_y, region_z, galaxy, reality))
                partner_claimed += 1

            total_systems += partner_claimed
            if partner_claimed > 0:
                results.append({'display_name': display_name, 'systems_claimed': partner_claimed})

        conn.commit()
        logger.info(f"War Room: Bulk sync completed - {total_systems} total systems across {len(results)} civs")

        return {
            'status': 'synced',
            'total_systems_claimed': total_systems,
            'civs_updated': results
        }
    finally:
        conn.close()


@router.get('/api/warroom/region-search')
async def search_regions_for_warroom(search: str = '', limit: int = 20, session: Optional[str] = Cookie(None)):
    """Search for regions by name or coordinates. Searches both named regions and regions with systems."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not search or len(search) < 2:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        results = []
        search_lower = search.lower()

        # First, search named regions
        cursor.execute('''
            SELECT r.region_x, r.region_y, r.region_z, r.custom_name as name, r.galaxy,
                   (SELECT COUNT(*) FROM systems s
                    WHERE s.region_x = r.region_x AND s.region_y = r.region_y AND s.region_z = r.region_z) as system_count
            FROM regions r
            WHERE LOWER(r.custom_name) LIKE ?
            ORDER BY r.custom_name
            LIMIT ?
        ''', (f'%{search_lower}%', limit))

        for row in cursor.fetchall():
            results.append({
                'region_x': row[0],
                'region_y': row[1],
                'region_z': row[2],
                'name': row[3],
                'region_name': row[3],
                'galaxy': row[4] or 'Euclid',
                'system_count': row[5],
                'source': 'named'
            })

        # Also search for systems whose names match (to find regions by system name)
        if len(results) < limit:
            remaining = limit - len(results)
            cursor.execute('''
                SELECT DISTINCT s.region_x, s.region_y, s.region_z, s.galaxy,
                       r.custom_name as region_name,
                       (SELECT COUNT(*) FROM systems s2
                        WHERE s2.region_x = s.region_x AND s2.region_y = s.region_y AND s2.region_z = s.region_z) as system_count,
                       GROUP_CONCAT(s.name, ', ') as sample_systems
                FROM systems s
                LEFT JOIN regions r ON s.region_x = r.region_x AND s.region_y = r.region_y AND s.region_z = r.region_z
                WHERE LOWER(s.name) LIKE ?
                GROUP BY s.region_x, s.region_y, s.region_z
                LIMIT ?
            ''', (f'%{search_lower}%', remaining))

            seen_coords = {(r['region_x'], r['region_y'], r['region_z']) for r in results}
            for row in cursor.fetchall():
                coords = (row[0], row[1], row[2])
                if coords not in seen_coords:
                    results.append({
                        'region_x': row[0],
                        'region_y': row[1],
                        'region_z': row[2],
                        'name': row[4] or f"Region ({row[0]}, {row[1]}, {row[2]})",
                        'region_name': row[4],
                        'galaxy': row[3] or 'Euclid',
                        'system_count': row[5],
                        'sample_systems': row[6][:100] if row[6] else None,  # Truncate
                        'source': 'system_match'
                    })
                    seen_coords.add(coords)

        # Also try to parse as coordinates (e.g., "123, 456, 789" or "123 456 789")
        coord_match = re.match(r'[-]?\d+[,\s]+[-]?\d+[,\s]+[-]?\d+', search.strip())
        if coord_match and len(results) < limit:
            parts = re.split(r'[,\s]+', search.strip())
            if len(parts) >= 3:
                try:
                    rx, ry, rz = int(parts[0]), int(parts[1]), int(parts[2])
                    # Check if we already have this
                    if (rx, ry, rz) not in {(r['region_x'], r['region_y'], r['region_z']) for r in results}:
                        # Look up the region
                        cursor.execute('''
                            SELECT r.custom_name,
                                   (SELECT COUNT(*) FROM systems s
                                    WHERE s.region_x = ? AND s.region_y = ? AND s.region_z = ?) as system_count,
                                   (SELECT galaxy FROM systems WHERE region_x = ? AND region_y = ? AND region_z = ? LIMIT 1) as galaxy
                            FROM regions r
                            WHERE r.region_x = ? AND r.region_y = ? AND r.region_z = ?
                        ''', (rx, ry, rz, rx, ry, rz, rx, ry, rz))
                        row = cursor.fetchone()
                        results.insert(0, {  # Put coordinate match first
                            'region_x': rx,
                            'region_y': ry,
                            'region_z': rz,
                            'name': row[0] if row and row[0] else f"Region ({rx}, {ry}, {rz})",
                            'region_name': row[0] if row else None,
                            'galaxy': row[2] if row and row[2] else 'Euclid',
                            'system_count': row[1] if row else 0,
                            'source': 'coordinates'
                        })
                except ValueError:
                    pass

        return results[:limit]
    finally:
        conn.close()


@router.get('/api/warroom/home-regions')
async def get_home_regions(session: Optional[str] = Cookie(None)):
    """Get home regions for all enrolled civilizations."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT wre.partner_id, pa.display_name, pa.region_color,
                   wre.home_region_x, wre.home_region_y, wre.home_region_z,
                   wre.home_region_name, wre.home_galaxy
            FROM war_room_enrollment wre
            JOIN partner_accounts pa ON wre.partner_id = pa.id
            WHERE wre.is_active = 1 AND wre.home_region_x IS NOT NULL
        ''')
        rows = cursor.fetchall()

        return [{
            'partner_id': r[0],
            'display_name': r[1],
            'region_color': r[2],
            'region_x': r[3],
            'region_y': r[4],
            'region_z': r[5],
            'region_name': r[6],
            'galaxy': r[7]
        } for r in rows]
    finally:
        conn.close()


# =============================================================================
# TERRITORIAL CLAIMS ENDPOINTS
# =============================================================================


@router.get('/api/warroom/claims')
async def get_territorial_claims(partner_id: int = None, session: Optional[str] = Cookie(None)):
    """List all territorial claims, optionally filtered by partner."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = '''
            SELECT tc.id, tc.system_id, tc.claimant_partner_id, pa.display_name, pa.discord_tag,
                   pa.region_color, tc.claimed_at, tc.claim_type, tc.region_x, tc.region_y, tc.region_z,
                   tc.galaxy, tc.reality, tc.notes, s.name as system_name
            FROM territorial_claims tc
            JOIN partner_accounts pa ON tc.claimant_partner_id = pa.id
            LEFT JOIN systems s ON tc.system_id = s.id
        '''
        params = []
        if partner_id:
            query += ' WHERE tc.claimant_partner_id = ?'
            params.append(partner_id)
        query += ' ORDER BY tc.claimed_at DESC'

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'system_id': r[1],
            'claimant_partner_id': r[2],
            'claimant_display_name': r[3],
            'claimant_discord_tag': r[4],
            'claimant_color': r[5],
            'claimed_at': r[6],
            'claim_type': r[7],
            'region_x': r[8],
            'region_y': r[9],
            'region_z': r[10],
            'galaxy': r[11],
            'reality': r[12],
            'notes': r[13],
            'system_name': r[14]
        } for r in rows]
    finally:
        conn.close()


@router.post('/api/warroom/claims')
async def create_territorial_claim(request: Request, session: Optional[str] = Cookie(None)):
    """Claim a system for your civilization."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    system_id = data.get('system_id')
    if not system_id:
        raise HTTPException(status_code=400, detail="system_id required")

    # Super admin can claim for any partner
    partner_id = data.get('partner_id') if partner_info.get('is_super_admin') else partner_info['partner_id']
    if not partner_id:
        raise HTTPException(status_code=400, detail="partner_id required for super admin")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get system info
        cursor.execute('''
            SELECT id, name, region_x, region_y, region_z, galaxy, reality
            FROM systems WHERE id = ?
        ''', (system_id,))
        system = cursor.fetchone()
        if not system:
            raise HTTPException(status_code=404, detail="System not found")

        # Check if already claimed
        cursor.execute('SELECT id, claimant_partner_id FROM territorial_claims WHERE system_id = ?', (system_id,))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="System already claimed by another civilization")

        cursor.execute('''
            INSERT INTO territorial_claims (system_id, claimant_partner_id, region_x, region_y, region_z, galaxy, reality, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (system_id, partner_id, system[2], system[3], system[4], system[5], system[6], data.get('notes')))
        conn.commit()

        logger.info(f"War Room: Partner {partner_id} claimed system {system[1]} ({system_id})")
        return {'status': 'claimed', 'claim_id': cursor.lastrowid, 'system_name': system[1]}
    finally:
        conn.close()


@router.delete('/api/warroom/claims/{claim_id}')
async def release_territorial_claim(claim_id: int, session: Optional[str] = Cookie(None)):
    """Release a territorial claim."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check ownership
        cursor.execute('SELECT claimant_partner_id FROM territorial_claims WHERE id = ?', (claim_id,))
        claim = cursor.fetchone()
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        if not partner_info.get('is_super_admin') and claim[0] != partner_info['partner_id']:
            raise HTTPException(status_code=403, detail="Can only release your own claims")

        cursor.execute('DELETE FROM territorial_claims WHERE id = ?', (claim_id,))
        conn.commit()

        return {'status': 'released', 'claim_id': claim_id}
    finally:
        conn.close()


# =============================================================================
# CONFLICT MANAGEMENT ENDPOINTS
# =============================================================================


@router.get('/api/warroom/conflicts')
async def get_conflicts(status: str = None, partner_id: int = None, session: Optional[str] = Cookie(None)):
    """List conflicts with optional filters."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = '''
            SELECT c.id, c.target_system_id, c.target_system_name,
                   c.attacker_partner_id, att.display_name, att.region_color,
                   c.defender_partner_id, def.display_name, def.region_color,
                   c.declared_at, c.declared_by, c.acknowledged_at, c.resolved_at,
                   c.status, c.resolution, c.victor_partner_id, c.notes
            FROM conflicts c
            JOIN partner_accounts att ON c.attacker_partner_id = att.id
            JOIN partner_accounts def ON c.defender_partner_id = def.id
            WHERE 1=1
        '''
        params = []
        if status:
            query += ' AND c.status = ?'
            params.append(status)
        if partner_id:
            query += ' AND (c.attacker_partner_id = ? OR c.defender_partner_id = ?)'
            params.extend([partner_id, partner_id])
        query += ' ORDER BY c.declared_at DESC'

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'target_system_id': r[1],
            'target_system_name': r[2],
            'attacker': {'partner_id': r[3], 'display_name': r[4], 'color': r[5]},
            'defender': {'partner_id': r[6], 'display_name': r[7], 'color': r[8]},
            'declared_at': r[9],
            'declared_by': r[10],
            'acknowledged_at': r[11],
            'resolved_at': r[12],
            'status': r[13],
            'resolution': r[14],
            'victor_partner_id': r[15],
            'notes': r[16]
        } for r in rows]
    finally:
        conn.close()


@router.get('/api/warroom/conflicts/active')
async def get_active_conflicts(include_practice: bool = False, session: Optional[str] = Cookie(None)):
    """Get currently active conflicts for the live feed.

    Args:
        include_practice: If True, include practice conflicts (default: False)
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Filter out practice conflicts by default
        practice_filter = "" if include_practice else "AND (c.is_practice IS NULL OR c.is_practice = 0)"
        cursor.execute(f'''
            SELECT c.id, c.target_system_id, c.target_system_name,
                   att.display_name as attacker_name, att.region_color as attacker_color,
                   def.display_name as defender_name, def.region_color as defender_color,
                   c.declared_at, c.status, COALESCE(c.is_practice, 0) as is_practice
            FROM conflicts c
            JOIN partner_accounts att ON c.attacker_partner_id = att.id
            JOIN partner_accounts def ON c.defender_partner_id = def.id
            WHERE c.status IN ('pending', 'acknowledged', 'active')
            {practice_filter}
            ORDER BY c.declared_at DESC
        ''')
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'target_system_id': r[1],
            'target_system_name': r[2],
            'attacker_name': r[3],
            'attacker_color': r[4],
            'defender_name': r[5],
            'defender_color': r[6],
            'declared_at': r[7],
            'status': r[8],
            'is_practice': bool(r[9])
        } for r in rows]
    finally:
        conn.close()


@router.get('/api/warroom/conflicts/{conflict_id}')
async def get_conflict_detail(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Get conflict details including timeline."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict
        cursor.execute('''
            SELECT c.id, c.target_system_id, c.target_system_name,
                   c.attacker_partner_id, att.display_name, att.region_color,
                   c.defender_partner_id, def.display_name, def.region_color,
                   c.declared_at, c.declared_by, c.acknowledged_at, c.acknowledged_by,
                   c.resolved_at, c.resolved_by, c.status, c.resolution, c.victor_partner_id, c.notes,
                   COALESCE(c.is_practice, 0) as is_practice
            FROM conflicts c
            JOIN partner_accounts att ON c.attacker_partner_id = att.id
            JOIN partner_accounts def ON c.defender_partner_id = def.id
            WHERE c.id = ?
        ''', (conflict_id,))
        r = cursor.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Conflict not found")

        # Get timeline events
        cursor.execute('''
            SELECT id, event_type, event_at, actor_username, details
            FROM conflict_events
            WHERE conflict_id = ?
            ORDER BY event_at ASC
        ''', (conflict_id,))
        events = cursor.fetchall()

        return {
            'id': r[0],
            'target_system_id': r[1],
            'target_system_name': r[2],
            'attacker': {'partner_id': r[3], 'display_name': r[4], 'color': r[5]},
            'defender': {'partner_id': r[6], 'display_name': r[7], 'color': r[8]},
            'declared_at': r[9],
            'declared_by': r[10],
            'acknowledged_at': r[11],
            'acknowledged_by': r[12],
            'resolved_at': r[13],
            'resolved_by': r[14],
            'status': r[15],
            'resolution': r[16],
            'victor_partner_id': r[17],
            'notes': r[18],
            'is_practice': bool(r[19]),
            'timeline': [{
                'id': e[0],
                'event_type': e[1],
                'event_at': e[2],
                'actor': e[3],
                'details': e[4]
            } for e in events]
        }
    finally:
        conn.close()


@router.post('/api/warroom/conflicts')
async def declare_conflict(request: Request, session: Optional[str] = Cookie(None)):
    """Declare an attack on another civ's territory."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    target_system_id = data.get('target_system_id')
    if not target_system_id:
        raise HTTPException(status_code=400, detail="target_system_id required")

    attacker_id = data.get('attacker_partner_id') if partner_info.get('is_super_admin') else partner_info['partner_id']
    if not attacker_id:
        raise HTTPException(status_code=400, detail="attacker_partner_id required for super admin")

    # Practice mode - creates a conflict that doesn't affect real stats
    is_practice = data.get('is_practice', False)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Find the claim on this system
        cursor.execute('''
            SELECT tc.claimant_partner_id, pa.display_name, s.name
            FROM territorial_claims tc
            JOIN partner_accounts pa ON tc.claimant_partner_id = pa.id
            LEFT JOIN systems s ON tc.system_id = s.id
            WHERE tc.system_id = ?
        ''', (target_system_id,))
        claim = cursor.fetchone()
        if not claim:
            raise HTTPException(status_code=404, detail="System not claimed by any civilization")

        defender_id = claim[0]
        defender_name = claim[1]
        system_name = claim[2] or target_system_id

        if defender_id == attacker_id:
            raise HTTPException(status_code=400, detail="Cannot attack your own territory")

        # Check for existing active conflict on this system
        cursor.execute('''
            SELECT id FROM conflicts
            WHERE target_system_id = ? AND status IN ('pending', 'acknowledged', 'active')
        ''', (target_system_id,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Active conflict already exists for this system")

        # Create conflict
        username = session_data.get('username')
        cursor.execute('''
            INSERT INTO conflicts (target_system_id, target_system_name, attacker_partner_id, defender_partner_id, declared_by, is_practice)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (target_system_id, system_name, attacker_id, defender_id, username, 1 if is_practice else 0))
        conflict_id = cursor.lastrowid

        # Add declaration event
        event_details = f"{'[PRACTICE] ' if is_practice else ''}Attack declared on {system_name}"
        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, 'declared', ?, ?, ?)
        ''', (conflict_id, attacker_id, username, event_details))
        conn.commit()

        attacker_name = partner_info.get('display_name', 'Unknown')

        # Skip notifications and activity feed for practice conflicts
        if not is_practice:
            # Send notification to defender
            await send_war_notification(
                defender_id,
                'attack_declared',
                f"Attack Declaration: {system_name}",
                f"{attacker_name} has declared an attack on {system_name}! Respond to acknowledge the conflict.",
                conflict_id
            )

            # Add to public activity feed
            await add_activity_feed_entry(
                event_type='war_declared',
                headline=f"{attacker_name} declares war on {defender_name}",
                actor_partner_id=attacker_id,
                actor_name=attacker_name,
                target_partner_id=defender_id,
                target_name=defender_name,
                conflict_id=conflict_id,
                system_id=str(target_system_id),
                system_name=system_name,
                details=f"Attack declared on system {system_name}. Awaiting defender acknowledgement.",
                is_public=True
            )

        practice_label = " (PRACTICE)" if is_practice else ""
        logger.info(f"War Room: Conflict declared{practice_label} - {attacker_name} attacking {defender_name} at {system_name}")
        return {'status': 'declared', 'conflict_id': conflict_id, 'target_system': system_name, 'is_practice': is_practice}
    finally:
        conn.close()


@router.put('/api/warroom/conflicts/{conflict_id}/acknowledge')
async def acknowledge_conflict(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Defender acknowledges the conflict."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict
        cursor.execute('''
            SELECT defender_partner_id, attacker_partner_id, status, target_system_name
            FROM conflicts WHERE id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        defender_id, attacker_id, status, system_name = conflict

        # Check authorization
        if not partner_info.get('is_super_admin') and partner_info['partner_id'] != defender_id:
            raise HTTPException(status_code=403, detail="Only the defender can acknowledge")

        if status != 'pending':
            raise HTTPException(status_code=400, detail="Conflict already acknowledged or resolved")

        username = session_data.get('username')
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute('''
            UPDATE conflicts SET status = 'active', acknowledged_at = ?, acknowledged_by = ?
            WHERE id = ?
        ''', (now, username, conflict_id))

        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, 'acknowledged', ?, ?, ?)
        ''', (conflict_id, defender_id, username, "Defender acknowledged the conflict - battle is now active"))
        conn.commit()

        # Notify attacker
        await send_war_notification(
            attacker_id,
            'conflict_update',
            f"Conflict Acknowledged: {system_name}",
            f"The defender has acknowledged your attack on {system_name}. The battle is now active!",
            conflict_id
        )

        # Get defender and attacker names for activity feed
        cursor.execute('SELECT display_name FROM partner_accounts WHERE id = ?', (defender_id,))
        defender_row = cursor.fetchone()
        defender_name = defender_row[0] if defender_row else 'Unknown'

        cursor.execute('SELECT display_name FROM partner_accounts WHERE id = ?', (attacker_id,))
        attacker_row = cursor.fetchone()
        attacker_name = attacker_row[0] if attacker_row else 'Unknown'

        # Add to public activity feed
        await add_activity_feed_entry(
            event_type='conflict_acknowledged',
            headline=f"{defender_name} accepts {attacker_name}'s challenge",
            actor_partner_id=defender_id,
            actor_name=defender_name,
            target_partner_id=attacker_id,
            target_name=attacker_name,
            conflict_id=conflict_id,
            system_name=system_name,
            details=f"Battle for {system_name} is now active!",
            is_public=True
        )

        logger.info(f"War Room: Conflict {conflict_id} acknowledged")
        return {'status': 'acknowledged', 'conflict_id': conflict_id}
    finally:
        conn.close()


@router.put('/api/warroom/conflicts/{conflict_id}/resolve')
async def resolve_conflict(conflict_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Resolve a conflict with a victor."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    resolution = data.get('resolution')  # attacker_victory, defender_victory, stalemate
    if resolution not in ['attacker_victory', 'defender_victory', 'stalemate', 'cancelled']:
        raise HTTPException(status_code=400, detail="Invalid resolution")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT attacker_partner_id, defender_partner_id, status, target_system_id, target_system_name,
                   COALESCE(is_practice, 0) as is_practice
            FROM conflicts WHERE id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        attacker_id, defender_id, status, system_id, system_name, is_practice = conflict

        # Check authorization - only super admin or involved parties
        if not partner_info.get('is_super_admin'):
            if partner_info['partner_id'] not in [attacker_id, defender_id]:
                raise HTTPException(status_code=403, detail="Only involved parties can resolve")

        if status == 'resolved':
            raise HTTPException(status_code=400, detail="Conflict already resolved")

        victor_id = None
        if resolution == 'attacker_victory':
            victor_id = attacker_id
        elif resolution == 'defender_victory':
            victor_id = defender_id

        username = session_data.get('username')
        now = datetime.now(timezone.utc).isoformat()

        practice_label = "[PRACTICE] " if is_practice else ""
        cursor.execute('''
            UPDATE conflicts SET status = 'resolved', resolution = ?, victor_partner_id = ?,
                   resolved_at = ?, resolved_by = ?
            WHERE id = ?
        ''', (resolution, victor_id, now, username, conflict_id))

        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_username, details)
            VALUES (?, 'resolved', ?, ?)
        ''', (conflict_id, username, f"{practice_label}Conflict resolved: {resolution}"))

        # Transfer territory if attacker won (skip for practice conflicts)
        if resolution == 'attacker_victory' and not is_practice:
            cursor.execute('''
                UPDATE territorial_claims SET claimant_partner_id = ?, claimed_at = ?
                WHERE system_id = ?
            ''', (attacker_id, now, system_id))
            logger.info(f"War Room: Territory {system_name} transferred to attacker (partner {attacker_id})")

        conn.commit()

        # Recalculate statistics (practice conflicts are already excluded in the function)
        await recalculate_war_statistics_internal(conn)

        # Skip notifications and activity feed for practice conflicts
        if not is_practice:
            # Notify both parties
            for pid in [attacker_id, defender_id]:
                await send_war_notification(
                    pid,
                    'conflict_resolved',
                    f"Conflict Resolved: {system_name}",
                    f"The battle for {system_name} has ended. Resolution: {resolution.replace('_', ' ').title()}",
                    conflict_id
                )

            # Get names for activity feed
            cursor.execute('SELECT display_name FROM partner_accounts WHERE id = ?', (attacker_id,))
            attacker_row = cursor.fetchone()
            attacker_name = attacker_row[0] if attacker_row else 'Unknown'

            cursor.execute('SELECT display_name FROM partner_accounts WHERE id = ?', (defender_id,))
            defender_row = cursor.fetchone()
            defender_name = defender_row[0] if defender_row else 'Unknown'

            victor_name = None
            if victor_id == attacker_id:
                victor_name = attacker_name
            elif victor_id == defender_id:
                victor_name = defender_name

            # Add to public activity feed
            if resolution == 'attacker_victory':
                headline = f"{attacker_name} conquers {system_name} from {defender_name}"
                details = f"{attacker_name} has seized control of {system_name}. Territory transferred to the victor."
            elif resolution == 'defender_victory':
                headline = f"{defender_name} repels {attacker_name}'s invasion of {system_name}"
                details = f"{defender_name} has successfully defended {system_name} against {attacker_name}."
            elif resolution == 'stalemate':
                headline = f"Battle for {system_name} ends in stalemate"
                details = f"The conflict between {attacker_name} and {defender_name} over {system_name} has ended without a clear victor."
            else:
                headline = f"Conflict over {system_name} cancelled"
                details = f"The conflict between {attacker_name} and {defender_name} has been cancelled."

            await add_activity_feed_entry(
                event_type='conflict_resolved',
                headline=headline,
                actor_partner_id=victor_id,
                actor_name=victor_name,
                target_partner_id=defender_id if victor_id == attacker_id else attacker_id,
                target_name=defender_name if victor_id == attacker_id else attacker_name,
                conflict_id=conflict_id,
                system_id=str(system_id) if system_id else None,
                system_name=system_name,
                details=details,
                is_public=True
            )

        practice_log = " (PRACTICE)" if is_practice else ""
        logger.info(f"War Room: Conflict {conflict_id} resolved as {resolution}{practice_log}")
        return {'status': 'resolved', 'resolution': resolution, 'victor_partner_id': victor_id, 'is_practice': bool(is_practice)}
    finally:
        conn.close()


@router.delete('/api/warroom/conflicts/{conflict_id}')
async def cancel_conflict(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Cancel a pending conflict (attacker only)."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT c.attacker_partner_id, c.defender_partner_id, c.status, c.target_system_name,
                   pa1.display_name as attacker_name, pa2.display_name as defender_name
            FROM conflicts c
            LEFT JOIN partner_accounts pa1 ON c.attacker_partner_id = pa1.id
            LEFT JOIN partner_accounts pa2 ON c.defender_partner_id = pa2.id
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        attacker_id, defender_id, status, system_name, attacker_name, defender_name = conflict

        if not partner_info.get('is_super_admin') and partner_info['partner_id'] != attacker_id:
            raise HTTPException(status_code=403, detail="Only the attacker can cancel")

        if status != 'pending':
            raise HTTPException(status_code=400, detail="Can only cancel pending conflicts")

        cursor.execute('''
            UPDATE conflicts SET status = 'resolved', resolution = 'cancelled',
                   resolved_at = ?, resolved_by = ?
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), session_data.get('username'), conflict_id))
        conn.commit()

        # Add to public activity feed
        await add_activity_feed_entry(
            event_type='conflict_cancelled',
            headline=f"{attacker_name} withdraws attack on {system_name}",
            actor_partner_id=attacker_id,
            actor_name=attacker_name,
            target_partner_id=defender_id,
            target_name=defender_name,
            conflict_id=conflict_id,
            system_name=system_name,
            details=f"{attacker_name} has withdrawn their declaration of war against {defender_name} for {system_name}.",
            is_public=True
        )

        return {'status': 'cancelled', 'conflict_id': conflict_id}
    finally:
        conn.close()


@router.post('/api/warroom/conflicts/{conflict_id}/events')
async def add_conflict_event(conflict_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Add a timeline event to a conflict."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    event_type = data.get('event_type')
    details = data.get('details')

    if event_type not in ['skirmish', 'capture', 'defense', 'retreat', 'reinforcement', 'note']:
        raise HTTPException(status_code=400, detail="Invalid event_type")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict details for activity feed
        cursor.execute('''
            SELECT c.status, c.target_system_name, pa.display_name
            FROM conflicts c
            LEFT JOIN partner_accounts pa ON c.attacker_partner_id = pa.id OR c.defender_partner_id = pa.id
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")
        if conflict[0] == 'resolved':
            raise HTTPException(status_code=400, detail="Cannot add events to resolved conflict")

        system_name = conflict[1] or 'Unknown System'

        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (conflict_id, event_type, partner_info.get('partner_id'), session_data.get('username'), details))
        event_id = cursor.lastrowid
        conn.commit()

        # Add to activity feed for significant battle events (not notes)
        if event_type != 'note':
            actor_name = partner_info.get('display_name', session_data.get('username', 'Unknown'))

            # Create appropriate headline based on event type
            event_headlines = {
                'skirmish': f"Skirmish reported at {system_name}",
                'capture': f"{actor_name} captures position at {system_name}",
                'defense': f"{actor_name} defends position at {system_name}",
                'retreat': f"Forces retreat at {system_name}",
                'reinforcement': f"{actor_name} sends reinforcements to {system_name}"
            }
            headline = event_headlines.get(event_type, f"Battle update at {system_name}")

            await add_activity_feed_entry(
                event_type=f'battle_{event_type}',
                headline=headline,
                actor_partner_id=partner_info.get('partner_id'),
                actor_name=actor_name,
                conflict_id=conflict_id,
                system_name=system_name,
                details=details,
                is_public=True
            )

        return {'status': 'added', 'event_id': event_id}
    finally:
        conn.close()


@router.get('/api/warroom/conflicts/{conflict_id}/events')
async def get_conflict_events(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Get timeline events for a conflict."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verify conflict exists
        cursor.execute('SELECT id FROM conflicts WHERE id = ?', (conflict_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Conflict not found")

        cursor.execute('''
            SELECT id, event_type, actor_partner_id, actor_username, details, event_at
            FROM conflict_events
            WHERE conflict_id = ?
            ORDER BY event_at ASC
        ''', (conflict_id,))
        events = []
        for row in cursor.fetchall():
            events.append({
                'id': row[0],
                'event_type': row[1],
                'actor_partner_id': row[2],
                'actor_username': row[3],
                'details': row[4],
                'created_at': row[5]  # Frontend expects created_at
            })
        return events
    finally:
        conn.close()


# =============================================================================
# DEBRIEF ENDPOINTS
# =============================================================================


@router.get('/api/warroom/debrief')
async def get_debrief(session: Optional[str] = Cookie(None)):
    """Get current mission objectives."""
    try:
        session_data = get_session(session)
        if not session_data:
            raise HTTPException(status_code=401, detail="Not authenticated")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT objectives, updated_at, updated_by FROM current_debrief WHERE id = 1')
            row = cursor.fetchone()
            if not row:
                return {'objectives': [], 'updated_at': None, 'updated_by': None}

            objectives = json.loads(row[0]) if row[0] else []
            return {'objectives': objectives, 'updated_at': row[1], 'updated_by': row[2]}
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_debrief: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put('/api/warroom/debrief')
async def update_debrief(request: Request, session: Optional[str] = Cookie(None)):
    """Update mission objectives (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()
    objectives = data.get('objectives', [])

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE current_debrief SET objectives = ?, updated_at = ?, updated_by = ?
            WHERE id = 1
        ''', (json.dumps(objectives), datetime.now(timezone.utc).isoformat(), session_data.get('username')))
        conn.commit()

        return {'status': 'updated', 'objectives': objectives}
    finally:
        conn.close()


# =============================================================================
# WAR NEWS ENDPOINTS
# =============================================================================


@router.get('/api/warroom/news')
async def get_war_news(limit: int = 20, offset: int = 0, session: Optional[str] = Cookie(None)):
    """Get war news articles."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT wn.id, wn.headline, wn.body, wn.author_username, wn.author_type,
                   wn.related_conflict_id, wn.published_at, wn.is_pinned,
                   wn.article_type, wn.view_count, wn.reporting_org_id,
                   ro.name as reporting_org_name, wc.display_name as author_name
            FROM war_news wn
            LEFT JOIN reporting_organizations ro ON wn.reporting_org_id = ro.id
            LEFT JOIN war_correspondents wc ON wn.author_username = wc.username
            WHERE wn.is_active = 1
            ORDER BY wn.is_pinned DESC, wn.published_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'headline': r[1],
            'body': r[2],
            'author': r[3],
            'author_type': r[4],
            'conflict_id': r[5],
            'created_at': r[6],
            'is_pinned': r[7],
            'article_type': r[8] or 'breaking',
            'view_count': r[9] or 0,
            'reporting_org_id': r[10],
            'reporting_org_name': r[11],
            'author_name': r[12] or r[3]
        } for r in rows]
    finally:
        conn.close()


@router.get('/api/warroom/news/ticker')
async def get_news_ticker(session: Optional[str] = Cookie(None)):
    """Get latest 10 news items for the ticker."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, headline, published_at FROM war_news
            WHERE is_active = 1
            ORDER BY published_at DESC
            LIMIT 10
        ''')
        rows = cursor.fetchall()

        return [{'id': r[0], 'headline': r[1], 'published_at': r[2]} for r in rows]
    finally:
        conn.close()


@router.post('/api/warroom/news')
async def create_war_news(request: Request, session: Optional[str] = Cookie(None)):
    """Create a news article (super admin, correspondent, or enrolled partner)."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    username = session_data.get('username')
    is_super_admin = session_data.get('user_type') == 'super_admin'
    author_type = 'super_admin'
    author_display_name = username

    if is_super_admin:
        author_type = 'super_admin'
    else:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if they're a correspondent
        cursor.execute('SELECT id, display_name FROM war_correspondents WHERE username = ? AND is_active = 1', (username,))
        correspondent = cursor.fetchone()
        if correspondent:
            author_type = 'correspondent'
            author_display_name = correspondent[1] or username
            conn.close()
        else:
            # Check if they're an enrolled partner
            partner_info = get_war_room_partner_info(session_data)
            conn.close()
            if partner_info and not partner_info.get('is_super_admin'):
                author_type = 'partner'
                author_display_name = partner_info.get('display_name', username)
            else:
                raise HTTPException(status_code=403, detail="Must be super admin, war correspondent, or enrolled partner")

    data = await request.json()
    headline = data.get('headline')
    body = data.get('body')
    article_type = data.get('article_type', 'breaking')
    if not headline or not body:
        raise HTTPException(status_code=400, detail="headline and body required")

    # Validate article_type
    valid_types = ['breaking', 'report', 'analysis', 'editorial', 'announcement']
    if article_type not in valid_types:
        article_type = 'breaking'

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO war_news (headline, body, author_username, author_type, related_conflict_id, is_pinned, article_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (headline, body, author_display_name, author_type, data.get('conflict_id'), data.get('is_pinned', False), article_type))
        news_id = cursor.lastrowid
        conn.commit()

        # Add to activity feed
        await add_activity_feed_entry(
            event_type='news_published',
            headline=f"News: {headline}",
            actor_name=author_display_name,
            details=f"New {article_type} article published by {author_display_name}",
            is_public=True
        )

        logger.info(f"War Room: News created by {author_display_name} ({author_type}): {headline}")
        return {'status': 'created', 'news_id': news_id}
    finally:
        conn.close()


@router.delete('/api/warroom/news/{news_id}')
async def delete_war_news(news_id: int, session: Optional[str] = Cookie(None)):
    """Delete a news article (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE war_news SET is_active = 0 WHERE id = ?', (news_id,))
        conn.commit()
        return {'status': 'deleted', 'news_id': news_id}
    finally:
        conn.close()


# =============================================================================
# WAR CORRESPONDENTS ENDPOINTS
# =============================================================================


@router.get('/api/warroom/correspondents')
async def get_correspondents(session: Optional[str] = Cookie(None)):
    """List war correspondents (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, username, display_name, is_active, created_at, created_by
            FROM war_correspondents
            ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'username': r[1],
            'display_name': r[2],
            'is_active': bool(r[3]),
            'created_at': r[4],
            'created_by': r[5]
        } for r in rows]
    finally:
        conn.close()


@router.post('/api/warroom/correspondents')
async def create_correspondent(request: Request, session: Optional[str] = Cookie(None)):
    """Create a war correspondent (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()
    username = data.get('username')
    password = data.get('password')
    display_name = data.get('display_name')

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO war_correspondents (username, password_hash, display_name, created_by)
            VALUES (?, ?, ?, ?)
        ''', (username, hash_password(password), display_name, session_data.get('username')))
        conn.commit()

        logger.info(f"War Room: Correspondent created: {username}")
        return {'status': 'created', 'correspondent_id': cursor.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already exists")
    finally:
        conn.close()


@router.post('/api/warroom/correspondents/login')
async def correspondent_login(request: Request, response: Response):
    """Login as a war correspondent."""
    data = await request.json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, username, display_name, is_active, password_hash
            FROM war_correspondents
            WHERE username = ?
        ''', (username,))
        correspondent = cursor.fetchone()

        if not correspondent or not verify_password(password, correspondent['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Upgrade legacy SHA-256 hash to bcrypt on successful login
        if _needs_rehash(correspondent['password_hash']):
            cursor.execute('UPDATE war_correspondents SET password_hash = ? WHERE id = ?',
                           (hash_password(password), correspondent['id']))
            conn.commit()

        if not correspondent[3]:
            raise HTTPException(status_code=403, detail="Account is inactive")

        # Create session for correspondent
        session_id = secrets.token_hex(32)
        session_data = {
            'user_type': 'correspondent',
            'username': correspondent[1],
            'display_name': correspondent[2] or correspondent[1],
            'correspondent_id': correspondent[0]
        }
        sessions[session_id] = session_data

        response.set_cookie(
            key='session',
            value=session_id,
            httponly=True,
            secure=False,
            samesite='lax',
            max_age=86400 * 7
        )

        logger.info(f"War Room: Correspondent logged in: {username}")
        return {
            'status': 'success',
            'username': correspondent[1],
            'display_name': correspondent[2] or correspondent[1],
            'user_type': 'correspondent'
        }
    finally:
        conn.close()


# =============================================================================
# STATISTICS ENDPOINTS
# =============================================================================


@router.get('/api/warroom/statistics')
async def get_war_statistics(session: Optional[str] = Cookie(None)):
    """Get war statistics."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT stat_type, partner_id, partner_display_name, value, value_unit, details, calculated_at
            FROM war_statistics
        ''')
        rows = cursor.fetchall()

        stats = {}
        for r in rows:
            stats[r[0]] = {
                'partner_id': r[1],
                'holder': r[2],
                'value': r[3],
                'unit': r[4],
                'details': json.loads(r[5]) if r[5] else None,
                'calculated_at': r[6]
            }

        return stats
    finally:
        conn.close()


@router.get('/api/warroom/statistics/leaderboard')
async def get_war_leaderboard(session: Optional[str] = Cookie(None)):
    """Get per-civ rankings."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get all enrolled civs with their stats (excludes practice conflicts)
        cursor.execute('''
            SELECT pa.id, pa.display_name, pa.region_color,
                   (SELECT COUNT(*) FROM territorial_claims WHERE claimant_partner_id = pa.id) as systems_controlled,
                   (SELECT COUNT(*) FROM conflicts WHERE attacker_partner_id = pa.id AND resolution = 'attacker_victory' AND (is_practice IS NULL OR is_practice = 0)) as systems_conquered,
                   (SELECT COUNT(*) FROM conflicts WHERE defender_partner_id = pa.id AND resolution = 'attacker_victory' AND (is_practice IS NULL OR is_practice = 0)) as systems_lost,
                   (SELECT COUNT(*) FROM conflicts WHERE (attacker_partner_id = pa.id OR defender_partner_id = pa.id) AND status IN ('pending', 'acknowledged', 'active') AND (is_practice IS NULL OR is_practice = 0)) as active_conflicts
            FROM partner_accounts pa
            JOIN war_room_enrollment wre ON pa.id = wre.partner_id
            WHERE wre.is_active = 1
            ORDER BY systems_controlled DESC
        ''')
        rows = cursor.fetchall()

        return [{
            'partner_id': r[0],
            'display_name': r[1],
            'color': r[2],
            'systems_controlled': r[3],
            'systems_conquered': r[4],
            'systems_lost': r[5],
            'active_conflicts': r[6],
            'win_rate': round(r[4] / (r[4] + r[5]) * 100, 1) if (r[4] + r[5]) > 0 else 0
        } for r in rows]
    finally:
        conn.close()


@router.post('/api/warroom/statistics/recalculate')
async def recalculate_statistics(session: Optional[str] = Cookie(None)):
    """Force recalculation of statistics (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    await recalculate_war_statistics_internal()
    return {'status': 'recalculated'}


# =============================================================================
# NOTIFICATIONS ENDPOINTS
# =============================================================================


@router.get('/api/warroom/notifications')
async def get_notifications(session: Optional[str] = Cookie(None)):
    """Get user's War Room notifications."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        return []  # Super admins don't get individual notifications

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, notification_type, title, message, related_conflict_id, created_at, read_at
            FROM war_notifications
            WHERE recipient_partner_id = ? AND dismissed_at IS NULL
            ORDER BY created_at DESC
            LIMIT 50
        ''', (partner_info['partner_id'],))
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'type': r[1],
            'title': r[2],
            'message': r[3],
            'conflict_id': r[4],
            'created_at': r[5],
            'read': r[6] is not None
        } for r in rows]
    finally:
        conn.close()


@router.get('/api/warroom/notifications/count')
async def get_notification_count(session: Optional[str] = Cookie(None)):
    """Get unread notification count."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        return {'count': 0}

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT COUNT(*) FROM war_notifications
            WHERE recipient_partner_id = ? AND read_at IS NULL AND dismissed_at IS NULL
        ''', (partner_info['partner_id'],))
        count = cursor.fetchone()[0]
        return {'count': count}
    finally:
        conn.close()


@router.put('/api/warroom/notifications/read-all')
async def mark_all_notifications_read(session: Optional[str] = Cookie(None)):
    """Mark all notifications as read."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        return {'status': 'ok'}

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE war_notifications SET read_at = ?
            WHERE recipient_partner_id = ? AND read_at IS NULL
        ''', (datetime.now(timezone.utc).isoformat(), partner_info['partner_id']))
        conn.commit()
        return {'status': 'ok', 'marked': cursor.rowcount}
    finally:
        conn.close()


# =============================================================================
# DISCORD WEBHOOKS ENDPOINTS
# =============================================================================


@router.get('/api/warroom/webhooks')
async def get_webhook(session: Optional[str] = Cookie(None)):
    """Get webhook for current partner."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        raise HTTPException(status_code=403, detail="Partner access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT webhook_url, is_active, last_triggered_at
            FROM discord_webhooks WHERE partner_id = ?
        ''', (partner_info['partner_id'],))
        row = cursor.fetchone()

        if not row:
            return {'configured': False}

        return {
            'configured': True,
            'webhook_url': row[0][:50] + '...' if row[0] else None,  # Partial for security
            'is_active': bool(row[1]),
            'last_triggered_at': row[2]
        }
    finally:
        conn.close()


@router.put('/api/warroom/webhooks')
async def set_webhook(request: Request, session: Optional[str] = Cookie(None)):
    """Set or update webhook URL."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        raise HTTPException(status_code=403, detail="Partner access required")

    data = await request.json()
    webhook_url = data.get('webhook_url')
    is_active = data.get('is_active', True)

    if webhook_url and not webhook_url.startswith('https://discord.com/api/webhooks/'):
        raise HTTPException(status_code=400, detail="Invalid Discord webhook URL")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO discord_webhooks (partner_id, webhook_url, is_active)
            VALUES (?, ?, ?)
            ON CONFLICT(partner_id) DO UPDATE SET webhook_url = ?, is_active = ?
        ''', (partner_info['partner_id'], webhook_url, is_active, webhook_url, is_active))
        conn.commit()
        return {'status': 'updated'}
    finally:
        conn.close()


@router.delete('/api/warroom/webhooks')
async def delete_webhook(session: Optional[str] = Cookie(None)):
    """Remove webhook configuration."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        raise HTTPException(status_code=403, detail="Partner access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM discord_webhooks WHERE partner_id = ?', (partner_info['partner_id'],))
        conn.commit()
        return {'status': 'deleted'}
    finally:
        conn.close()


# =============================================================================
# MAP DATA ENDPOINT
# =============================================================================


@router.get('/api/warroom/map-data')
async def get_war_map_data(session: Optional[str] = Cookie(None)):
    """Get aggregated data for the war map visualization."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get enrolled civs with home region data
        cursor.execute('''
            SELECT pa.id, pa.display_name, pa.discord_tag, pa.region_color,
                   wre.home_region_x, wre.home_region_y, wre.home_region_z,
                   wre.home_region_name, wre.home_galaxy
            FROM partner_accounts pa
            JOIN war_room_enrollment wre ON pa.id = wre.partner_id
            WHERE wre.is_active = 1
        ''')
        enrolled_civs = [{
            'partner_id': r[0],
            'display_name': r[1],
            'discord_tag': r[2],
            'color': r[3],
            'home_region': {
                'x': r[4],
                'y': r[5],
                'z': r[6],
                'name': r[7],
                'galaxy': r[8]
            } if r[4] is not None else None
        } for r in cursor.fetchall()]

        enrolled_ids = [c['partner_id'] for c in enrolled_civs]
        if not enrolled_ids:
            return {'regions': [], 'enrolled_civs': [], 'active_conflict_count': 0}

        # Get territorial claims grouped by region
        placeholders = ','.join('?' * len(enrolled_ids))
        cursor.execute(f'''
            SELECT tc.region_x, tc.region_y, tc.region_z, tc.galaxy, tc.reality,
                   tc.claimant_partner_id, pa.display_name, pa.region_color,
                   COUNT(*) as system_count
            FROM territorial_claims tc
            JOIN partner_accounts pa ON tc.claimant_partner_id = pa.id
            WHERE tc.claimant_partner_id IN ({placeholders})
            GROUP BY tc.region_x, tc.region_y, tc.region_z, tc.claimant_partner_id
            ORDER BY system_count DESC
        ''', enrolled_ids)

        regions = []
        for r in cursor.fetchall():
            region_key = f"{r[0]}:{r[1]}:{r[2]}"

            # Check for active conflicts in this region
            cursor.execute('''
                SELECT c.id, att.display_name, c.target_system_name
                FROM conflicts c
                JOIN territorial_claims tc ON c.target_system_id = tc.system_id
                JOIN partner_accounts att ON c.attacker_partner_id = att.id
                WHERE tc.region_x = ? AND tc.region_y = ? AND tc.region_z = ?
                  AND c.status IN ('pending', 'acknowledged', 'active')
            ''', (r[0], r[1], r[2]))
            active_conflicts = [{
                'conflict_id': ac[0],
                'attacker': ac[1],
                'target_system': ac[2]
            } for ac in cursor.fetchall()]

            regions.append({
                'region_x': r[0],
                'region_y': r[1],
                'region_z': r[2],
                'galaxy': r[3],
                'reality': r[4],
                'controlling_civ': {
                    'partner_id': r[5],
                    'display_name': r[6],
                    'color': r[7]
                },
                'system_count': r[8],
                'contested': len(active_conflicts) > 0,
                'active_conflicts': active_conflicts
            })

        # Get total active conflict count
        cursor.execute('''
            SELECT COUNT(*) FROM conflicts
            WHERE status IN ('pending', 'acknowledged', 'active')
        ''')
        active_conflict_count = cursor.fetchone()[0]

        # Build home_regions array for map visualization
        home_regions = []
        for civ in enrolled_civs:
            if civ['home_region'] and civ['home_region']['x'] is not None:
                hr = civ['home_region']
                home_regions.append({
                    'region_x': hr['x'],
                    'region_y': hr['y'],
                    'region_z': hr['z'],
                    'region_name': hr['name'],
                    'galaxy': hr['galaxy'],
                    'civ': {
                        'partner_id': civ['partner_id'],
                        'display_name': civ['display_name'],
                        'color': civ['color']
                    }
                })

        # Also mark regions that are home regions
        for region in regions:
            region['is_home_region'] = any(
                hr['region_x'] == region['region_x'] and
                hr['region_y'] == region['region_y'] and
                hr['region_z'] == region['region_z']
                for hr in home_regions
            )

        # Calculate region ownership based on systems.discord_tag (>50% rule)
        # Get all enrolled discord_tags
        enrolled_tags = {c['discord_tag']: c for c in enrolled_civs if c.get('discord_tag')}

        if enrolled_tags:
            # Query systems grouped by region and discord_tag
            tag_placeholders = ','.join('?' * len(enrolled_tags))
            cursor.execute(f'''
                SELECT region_x, region_y, region_z, galaxy, discord_tag, COUNT(*) as system_count
                FROM systems
                WHERE discord_tag IN ({tag_placeholders})
                  AND region_x IS NOT NULL
                GROUP BY region_x, region_y, region_z, discord_tag
            ''', list(enrolled_tags.keys()))

            # Build region ownership map: {region_key: {discord_tag: count, ...}}
            region_tag_counts = {}
            for row in cursor.fetchall():
                key = f"{row[0]}:{row[1]}:{row[2]}"
                if key not in region_tag_counts:
                    region_tag_counts[key] = {'galaxy': row[3], 'coords': (row[0], row[1], row[2]), 'tags': {}}
                region_tag_counts[key]['tags'][row[4]] = row[5]

            # Calculate ownership for each region (>50% = ownership)
            region_ownership = []
            for key, data in region_tag_counts.items():
                total_systems = sum(data['tags'].values())
                for tag, count in data['tags'].items():
                    percentage = (count / total_systems * 100) if total_systems > 0 else 0
                    if percentage > 50:
                        civ = enrolled_tags.get(tag)
                        if civ:
                            region_ownership.append({
                                'region_x': data['coords'][0],
                                'region_y': data['coords'][1],
                                'region_z': data['coords'][2],
                                'galaxy': data['galaxy'],
                                'owner': {
                                    'partner_id': civ['partner_id'],
                                    'display_name': civ['display_name'],
                                    'discord_tag': tag,
                                    'color': civ['color']
                                },
                                'system_count': count,
                                'total_in_region': total_systems,
                                'ownership_percentage': round(percentage, 1)
                            })
                        break  # Only one owner per region

            # Merge ownership data into existing regions and add new owned regions
            owned_region_keys = {f"{o['region_x']}:{o['region_y']}:{o['region_z']}": o for o in region_ownership}
            for region in regions:
                key = f"{region['region_x']}:{region['region_y']}:{region['region_z']}"
                if key in owned_region_keys:
                    ownership = owned_region_keys[key]
                    region['ownership'] = {
                        'owner': ownership['owner'],
                        'percentage': ownership['ownership_percentage'],
                        'system_count': ownership['system_count']
                    }
                else:
                    region['ownership'] = None

            # Add owned regions that don't have war claims
            existing_keys = {f"{r['region_x']}:{r['region_y']}:{r['region_z']}" for r in regions}
            for key, ownership in owned_region_keys.items():
                if key not in existing_keys:
                    regions.append({
                        'region_x': ownership['region_x'],
                        'region_y': ownership['region_y'],
                        'region_z': ownership['region_z'],
                        'galaxy': ownership['galaxy'],
                        'reality': 'Normal',
                        'controlling_civ': ownership['owner'],
                        'system_count': ownership['system_count'],
                        'contested': False,
                        'active_conflicts': [],
                        'is_home_region': any(
                            hr['region_x'] == ownership['region_x'] and
                            hr['region_y'] == ownership['region_y'] and
                            hr['region_z'] == ownership['region_z']
                            for hr in home_regions
                        ),
                        'ownership': {
                            'owner': ownership['owner'],
                            'percentage': ownership['ownership_percentage'],
                            'system_count': ownership['system_count']
                        }
                    })
        else:
            # No enrolled tags, no ownership data
            for region in regions:
                region['ownership'] = None

        return {
            'regions': regions,
            'enrolled_civs': enrolled_civs,
            'home_regions': home_regions,
            'active_conflict_count': active_conflict_count
        }
    finally:
        conn.close()


# =============================================================================
# ACTIVITY FEED ENDPOINTS
# =============================================================================


@router.get('/api/warroom/activity-feed')
async def get_activity_feed(limit: int = 50, offset: int = 0, session: Optional[str] = Cookie(None)):
    """Get the public activity feed."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, event_type, event_at, actor_partner_id, actor_name,
                   target_partner_id, target_name, conflict_id, system_id, system_name,
                   region_name, headline, details
            FROM war_activity_feed
            WHERE is_public = 1
            ORDER BY event_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        rows = cursor.fetchall()

        # Get total count
        cursor.execute('SELECT COUNT(*) FROM war_activity_feed WHERE is_public = 1')
        total = cursor.fetchone()[0]

        # Return array directly for simpler frontend consumption
        return [{
            'id': r[0],
            'event_type': r[1],
            'created_at': r[2],  # Frontend expects created_at
            'actor_partner_id': r[3],
            'actor_name': r[4],
            'target_partner_id': r[5],
            'target_name': r[6],
            'conflict_id': r[7],
            'system_id': r[8],
            'system_name': r[9],
            'region_name': r[10],
            'headline': r[11],
            'details': r[12]
        } for r in rows]
        # Note: pagination info available if needed via separate endpoint
    finally:
        conn.close()


# =============================================================================
# MULTI-PARTY CONFLICT ENDPOINTS
# =============================================================================


@router.post('/api/warroom/conflicts/{conflict_id}/join')
async def join_conflict(conflict_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Join an existing conflict as an ally."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    side = data.get('side')  # 'attacker' or 'defender'
    if side not in ['attacker', 'defender']:
        raise HTTPException(status_code=400, detail="side must be 'attacker' or 'defender'")

    joining_partner_id = data.get('partner_id') if partner_info.get('is_super_admin') else partner_info['partner_id']

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict info
        cursor.execute('''
            SELECT c.status, c.target_system_name, c.attacker_partner_id, c.defender_partner_id,
                   att.display_name, def.display_name
            FROM conflicts c
            JOIN partner_accounts att ON c.attacker_partner_id = att.id
            JOIN partner_accounts def ON c.defender_partner_id = def.id
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        status, system_name, attacker_id, defender_id, attacker_name, defender_name = conflict

        if status == 'resolved':
            raise HTTPException(status_code=400, detail="Cannot join resolved conflict")

        # Check not already in conflict
        cursor.execute('SELECT id FROM conflict_parties WHERE conflict_id = ? AND partner_id = ?',
                       (conflict_id, joining_partner_id))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Already participating in this conflict")

        # Get joining partner name
        cursor.execute('SELECT display_name FROM partner_accounts WHERE id = ?', (joining_partner_id,))
        joining_name = cursor.fetchone()[0]

        # Add to conflict_parties (ensure primary parties are added if not exists)
        cursor.execute('''
            INSERT OR IGNORE INTO conflict_parties (conflict_id, partner_id, side, is_primary)
            VALUES (?, ?, 'attacker', 1)
        ''', (conflict_id, attacker_id))
        cursor.execute('''
            INSERT OR IGNORE INTO conflict_parties (conflict_id, partner_id, side, is_primary)
            VALUES (?, ?, 'defender', 1)
        ''', (conflict_id, defender_id))

        # Add joining party
        cursor.execute('''
            INSERT INTO conflict_parties (conflict_id, partner_id, side, joined_by, is_primary)
            VALUES (?, ?, ?, ?, 0)
        ''', (conflict_id, joining_partner_id, side, session_data.get('username')))

        # Add timeline event
        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, 'ally_joined', ?, ?, ?)
        ''', (conflict_id, joining_partner_id, session_data.get('username'),
              f"{joining_name} joined as {side} ally"))

        conn.commit()

        # Add to activity feed
        await add_activity_feed_entry(
            'ally_joined',
            f"{joining_name} joins the battle for {system_name} as {side}",
            actor_partner_id=joining_partner_id,
            actor_name=joining_name,
            conflict_id=conflict_id,
            system_name=system_name,
            details=f"Joined on the {'attacking' if side == 'attacker' else 'defending'} side"
        )

        logger.info(f"War Room: {joining_name} joined conflict {conflict_id} as {side}")
        return {'status': 'joined', 'conflict_id': conflict_id, 'side': side}
    finally:
        conn.close()


@router.get('/api/warroom/conflicts/{conflict_id}/parties')
async def get_conflict_parties(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Get all parties involved in a conflict."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT cp.partner_id, pa.display_name, pa.region_color, cp.side, cp.is_primary,
                   cp.joined_at, cp.resolution_agreed
            FROM conflict_parties cp
            JOIN partner_accounts pa ON cp.partner_id = pa.id
            WHERE cp.conflict_id = ?
            ORDER BY cp.is_primary DESC, cp.joined_at ASC
        ''', (conflict_id,))
        rows = cursor.fetchall()

        attackers = []
        defenders = []
        for r in rows:
            party = {
                'partner_id': r[0],
                'display_name': r[1],
                'color': r[2],
                'is_primary': bool(r[4]),
                'joined_at': r[5],
                'resolution_agreed': bool(r[6])
            }
            if r[3] == 'attacker':
                attackers.append(party)
            else:
                defenders.append(party)

        return {'attackers': attackers, 'defenders': defenders}
    finally:
        conn.close()


# =============================================================================
# MUTUAL AGREEMENT RESOLUTION ENDPOINTS
# =============================================================================


@router.put('/api/warroom/conflicts/{conflict_id}/propose-resolution')
async def propose_resolution(conflict_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Propose a resolution for the conflict. All parties must agree."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    resolution = data.get('resolution')  # attacker_victory, defender_victory, stalemate
    summary = data.get('summary', '')

    if resolution not in ['attacker_victory', 'defender_victory', 'stalemate']:
        raise HTTPException(status_code=400, detail="Invalid resolution")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict
        cursor.execute('''
            SELECT status, attacker_partner_id, defender_partner_id, target_system_name
            FROM conflicts WHERE id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        status, attacker_id, defender_id, system_name = conflict

        if status == 'resolved':
            raise HTTPException(status_code=400, detail="Conflict already resolved")

        # Check authorization - must be involved in conflict
        partner_id = partner_info.get('partner_id')
        is_involved = partner_id in [attacker_id, defender_id]
        if not is_involved:
            # Check if in conflict_parties
            cursor.execute('SELECT id FROM conflict_parties WHERE conflict_id = ? AND partner_id = ?',
                           (conflict_id, partner_id))
            is_involved = cursor.fetchone() is not None

        if not partner_info.get('is_super_admin') and not is_involved:
            raise HTTPException(status_code=403, detail="Must be involved in conflict")

        now = datetime.now(timezone.utc).isoformat()

        # Update conflict with proposed resolution
        cursor.execute('''
            UPDATE conflicts SET resolution = ?, resolution_summary = ?,
                   resolution_proposed_by = ?, resolution_proposed_at = ?
            WHERE id = ?
        ''', (resolution, summary, partner_id, now, conflict_id))

        # Ensure all parties exist in conflict_parties
        cursor.execute('''
            INSERT OR IGNORE INTO conflict_parties (conflict_id, partner_id, side, is_primary)
            VALUES (?, ?, 'attacker', 1)
        ''', (conflict_id, attacker_id))
        cursor.execute('''
            INSERT OR IGNORE INTO conflict_parties (conflict_id, partner_id, side, is_primary)
            VALUES (?, ?, 'defender', 1)
        ''', (conflict_id, defender_id))

        # Reset all agreements
        cursor.execute('UPDATE conflict_parties SET resolution_agreed = 0 WHERE conflict_id = ?', (conflict_id,))

        # Mark proposer as agreed
        cursor.execute('''
            UPDATE conflict_parties SET resolution_agreed = 1, resolution_agreed_at = ?
            WHERE conflict_id = ? AND partner_id = ?
        ''', (now, conflict_id, partner_id))

        # Add timeline event
        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, 'resolution_proposed', ?, ?, ?)
        ''', (conflict_id, partner_id, session_data.get('username'),
              f"Proposed resolution: {resolution.replace('_', ' ').title()}. {summary}"))

        conn.commit()

        # Notify all other parties
        cursor.execute('SELECT partner_id FROM conflict_parties WHERE conflict_id = ? AND partner_id != ?',
                       (conflict_id, partner_id))
        for (pid,) in cursor.fetchall():
            await send_war_notification(
                pid,
                'resolution_proposed',
                f"Resolution Proposed: {system_name}",
                f"A resolution has been proposed for the battle of {system_name}: {resolution.replace('_', ' ').title()}. Your agreement is needed.",
                conflict_id
            )

        logger.info(f"War Room: Resolution proposed for conflict {conflict_id}: {resolution}")
        return {'status': 'proposed', 'resolution': resolution, 'awaiting_agreement': True}
    finally:
        conn.close()


@router.put('/api/warroom/conflicts/{conflict_id}/agree-resolution')
async def agree_resolution(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Agree to the proposed resolution."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    partner_id = partner_info.get('partner_id')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict and proposed resolution
        cursor.execute('''
            SELECT c.status, c.resolution, c.resolution_summary, c.target_system_id, c.target_system_name,
                   c.attacker_partner_id, c.defender_partner_id
            FROM conflicts c
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        status, resolution, summary, system_id, system_name, attacker_id, defender_id = conflict

        if status == 'resolved':
            raise HTTPException(status_code=400, detail="Conflict already resolved")

        if not resolution:
            raise HTTPException(status_code=400, detail="No resolution has been proposed yet")

        # Check if party is involved
        cursor.execute('SELECT id FROM conflict_parties WHERE conflict_id = ? AND partner_id = ?',
                       (conflict_id, partner_id))
        if not cursor.fetchone() and not partner_info.get('is_super_admin'):
            raise HTTPException(status_code=403, detail="Must be involved in conflict")

        now = datetime.now(timezone.utc).isoformat()

        # Mark as agreed
        cursor.execute('''
            UPDATE conflict_parties SET resolution_agreed = 1, resolution_agreed_at = ?
            WHERE conflict_id = ? AND partner_id = ?
        ''', (now, conflict_id, partner_id))

        # Check if all primary parties have agreed
        cursor.execute('''
            SELECT COUNT(*) FROM conflict_parties
            WHERE conflict_id = ? AND is_primary = 1 AND resolution_agreed = 0
        ''', (conflict_id,))
        remaining = cursor.fetchone()[0]

        if remaining == 0:
            # All primary parties agreed - resolve the conflict!
            victor_id = None
            if resolution == 'attacker_victory':
                victor_id = attacker_id
            elif resolution == 'defender_victory':
                victor_id = defender_id

            cursor.execute('''
                UPDATE conflicts SET status = 'resolved', victor_partner_id = ?,
                       resolved_at = ?, resolved_by = 'mutual_agreement'
                WHERE id = ?
            ''', (victor_id, now, conflict_id))

            # Add timeline event
            cursor.execute('''
                INSERT INTO conflict_events (conflict_id, event_type, actor_username, details)
                VALUES (?, 'resolved', 'System', ?)
            ''', (conflict_id, f"Conflict resolved by mutual agreement: {resolution.replace('_', ' ').title()}"))

            # Transfer territory if attacker won
            if resolution == 'attacker_victory':
                cursor.execute('''
                    UPDATE territorial_claims SET claimant_partner_id = ?, claimed_at = ?
                    WHERE system_id = ?
                ''', (attacker_id, now, system_id))

            conn.commit()

            # Recalculate statistics
            await recalculate_war_statistics_internal(conn)

            # Add to activity feed
            await add_activity_feed_entry(
                'conflict_resolved',
                f"The Battle of {system_name} has ended: {resolution.replace('_', ' ').title()}!",
                conflict_id=conflict_id,
                system_name=system_name,
                details=summary
            )

            # Notify all parties
            cursor.execute('SELECT partner_id FROM conflict_parties WHERE conflict_id = ?', (conflict_id,))
            for (pid,) in cursor.fetchall():
                await send_war_notification(
                    pid,
                    'conflict_resolved',
                    f"Conflict Resolved: {system_name}",
                    f"The battle has ended by mutual agreement. Resolution: {resolution.replace('_', ' ').title()}",
                    conflict_id
                )

            logger.info(f"War Room: Conflict {conflict_id} resolved by mutual agreement: {resolution}")
            return {'status': 'resolved', 'resolution': resolution, 'victor_partner_id': victor_id}
        else:
            conn.commit()
            logger.info(f"War Room: Partner {partner_id} agreed to resolution for conflict {conflict_id}")
            return {'status': 'agreed', 'remaining_agreements_needed': remaining}
    finally:
        conn.close()


# =============================================================================
# MEDIA UPLOAD ENDPOINTS
# =============================================================================


@router.post('/api/warroom/media/upload')
async def upload_war_media(
    file: UploadFile,
    caption: str = None,
    conflict_id: int = None,
    session: Optional[str] = Cookie(None)
):
    """Upload a war image/screenshot."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Check user type - must be super admin, correspondent, or enrolled partner
    user_type = session_data.get('user_type')
    username = session_data.get('username')
    uploader_id = None

    if user_type == 'super_admin':
        pass
    elif user_type == 'correspondent':
        pass
    elif user_type in ['partner', 'sub_admin']:
        partner_info = get_war_room_partner_info(session_data)
        if not partner_info:
            raise HTTPException(status_code=403, detail="Must be enrolled in War Room")
        uploader_id = partner_info.get('partner_id')
    else:
        raise HTTPException(status_code=403, detail="Not authorized to upload media")

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Read file content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {MAX_FILE_SIZE // 1024 // 1024}MB")

    # Create upload directory if needed
    war_media_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    unique_id = secrets.token_hex(8)

    # Process image: resize + compress to WebP + generate thumbnail
    try:
        result = process_image(content, f"{unique_id}{ext}")
        new_filename = f"{unique_id}.webp"
        thumb_filename = f"{unique_id}_thumb.webp"

        with open(war_media_dir / new_filename, 'wb') as f:
            f.write(result['full_bytes'])
        with open(war_media_dir / thumb_filename, 'wb') as f:
            f.write(result['thumb_bytes'])

        saved_size = result['compressed_size']
        mime_type = 'image/webp'
    except Exception as e:
        logger.warning(f"War media image processing failed, saving raw: {e}")
        new_filename = f"{unique_id}{ext}"
        with open(war_media_dir / new_filename, 'wb') as f:
            f.write(content)
        thumb_filename = None
        saved_size = len(content)
        mime_types = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
            '.gif': 'image/gif', '.webp': 'image/webp'
        }
        mime_type = mime_types.get(ext, 'application/octet-stream')

    # Save to database
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO war_media
            (filename, original_filename, file_path, file_size, mime_type,
             uploaded_by_id, uploaded_by_username, uploaded_by_type, caption, related_conflict_id, thumbnail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (new_filename, file.filename, f'/war-media/{new_filename}', saved_size,
              mime_type, uploader_id, username, user_type, caption, conflict_id, thumb_filename))
        conn.commit()
        media_id = cursor.lastrowid

        response = {
            'status': 'uploaded',
            'media_id': media_id,
            'filename': new_filename,
            'url': f'/war-media/{new_filename}'
        }
        if thumb_filename:
            response['thumbnail_url'] = f'/war-media/{thumb_filename}'
        return response
    finally:
        conn.close()


@router.get('/api/warroom/media')
async def list_war_media(
    limit: int = 50,
    offset: int = 0,
    conflict_id: int = None,
    session: Optional[str] = Cookie(None)
):
    """List uploaded war media."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = '''
            SELECT id, filename, original_filename, file_path, file_size, mime_type,
                   uploaded_by_username, uploaded_by_type, uploaded_at, caption, related_conflict_id, thumbnail
            FROM war_media
            WHERE is_active = 1
        '''
        params = []
        if conflict_id:
            query += ' AND related_conflict_id = ?'
            params.append(conflict_id)
        query += ' ORDER BY uploaded_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'filename': r[1],
            'original_filename': r[2],
            'url': r[3],
            'file_size': r[4],
            'mime_type': r[5],
            'uploaded_by': r[6],
            'uploaded_by_type': r[7],
            'uploaded_at': r[8],
            'caption': r[9],
            'conflict_id': r[10],
            'thumbnail_url': f'/war-media/{r[11]}' if r[11] else None
        } for r in rows]
    finally:
        conn.close()


@router.get('/api/warroom/media/{media_id}')
async def get_war_media(media_id: int, session: Optional[str] = Cookie(None)):
    """Get single media item details."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, filename, original_filename, file_path, file_size, mime_type,
                   uploaded_by_username, uploaded_by_type, uploaded_at, caption, related_conflict_id, thumbnail
            FROM war_media WHERE id = ? AND is_active = 1
        ''', (media_id,))
        r = cursor.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Media not found")

        return {
            'id': r[0],
            'filename': r[1],
            'original_filename': r[2],
            'url': r[3],
            'file_size': r[4],
            'mime_type': r[5],
            'uploaded_by': r[6],
            'uploaded_by_type': r[7],
            'uploaded_at': r[8],
            'caption': r[9],
            'conflict_id': r[10],
            'thumbnail_url': f'/war-media/{r[11]}' if r[11] else None
        }
    finally:
        conn.close()


@router.delete('/api/warroom/media/{media_id}')
async def delete_war_media(media_id: int, session: Optional[str] = Cookie(None)):
    """Delete a media item (soft delete)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE war_media SET is_active = 0 WHERE id = ?', (media_id,))
        conn.commit()
        return {'status': 'deleted', 'media_id': media_id}
    finally:
        conn.close()


# =============================================================================
# REPORTING ORGANIZATIONS ENDPOINTS
# =============================================================================


@router.get('/api/warroom/reporting-orgs')
async def list_reporting_orgs(session: Optional[str] = Cookie(None)):
    """List reporting organizations."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT ro.id, ro.name, ro.description, ro.discord_server_id, ro.discord_server_name,
                   ro.logo_url, ro.is_active, ro.created_at,
                   (SELECT COUNT(*) FROM reporting_org_members WHERE org_id = ro.id AND is_active = 1) as member_count
            FROM reporting_organizations ro
            ORDER BY ro.name
        ''')
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'name': r[1],
            'description': r[2],
            'discord_server_id': r[3],
            'discord_server_name': r[4],
            'logo_url': r[5],
            'is_active': bool(r[6]),
            'created_at': r[7],
            'member_count': r[8]
        } for r in rows]
    finally:
        conn.close()


@router.post('/api/warroom/reporting-orgs')
async def create_reporting_org(request: Request, session: Optional[str] = Cookie(None)):
    """Create a reporting organization (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()
    name = data.get('name')
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO reporting_organizations (name, description, discord_server_id, discord_server_name, logo_url, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, data.get('description'), data.get('discord_server_id'),
              data.get('discord_server_name'), data.get('logo_url'), session_data.get('username')))
        conn.commit()

        logger.info(f"War Room: Reporting org created: {name}")
        return {'status': 'created', 'org_id': cursor.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Organization name already exists")
    finally:
        conn.close()


@router.put('/api/warroom/reporting-orgs/{org_id}')
async def update_reporting_org(org_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Update a reporting organization."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        updates = []
        params = []
        for field in ['name', 'description', 'discord_server_id', 'discord_server_name', 'logo_url', 'is_active']:
            if field in data:
                updates.append(f'{field} = ?')
                params.append(data[field])

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(org_id)
        cursor.execute(f'UPDATE reporting_organizations SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()

        return {'status': 'updated', 'org_id': org_id}
    finally:
        conn.close()


@router.delete('/api/warroom/reporting-orgs/{org_id}')
async def delete_reporting_org(org_id: int, session: Optional[str] = Cookie(None)):
    """Delete a reporting organization (soft delete)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE reporting_organizations SET is_active = 0 WHERE id = ?', (org_id,))
        conn.commit()
        return {'status': 'deleted', 'org_id': org_id}
    finally:
        conn.close()


@router.get('/api/warroom/reporting-orgs/{org_id}/members')
async def list_org_members(org_id: int, session: Optional[str] = Cookie(None)):
    """List members of a reporting organization."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, username, display_name, role, is_active, created_at, last_login_at
            FROM reporting_org_members
            WHERE org_id = ?
            ORDER BY created_at DESC
        ''', (org_id,))
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'username': r[1],
            'display_name': r[2],
            'role': r[3],
            'is_active': bool(r[4]),
            'created_at': r[5],
            'last_login_at': r[6]
        } for r in rows]
    finally:
        conn.close()


@router.post('/api/warroom/reporting-orgs/{org_id}/members')
async def add_org_member(org_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Add a member to a reporting organization."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verify org exists
        cursor.execute('SELECT id FROM reporting_organizations WHERE id = ? AND is_active = 1', (org_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Organization not found")

        cursor.execute('''
            INSERT INTO reporting_org_members (org_id, username, password_hash, display_name, role, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (org_id, username, hash_password(password), data.get('display_name'), data.get('role', 'reporter'),
              session_data.get('username')))
        conn.commit()

        logger.info(f"War Room: Member {username} added to org {org_id}")
        return {'status': 'created', 'member_id': cursor.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already exists in this organization")
    finally:
        conn.close()


@router.post('/api/warroom/reporting-orgs/login')
async def reporting_org_login(request: Request, response: Response):
    """Login as a reporting organization member."""
    data = await request.json()
    username = data.get('username')
    password = data.get('password')
    org_id = data.get('org_id')

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = '''
            SELECT rom.id, rom.org_id, rom.username, rom.display_name, rom.role, rom.is_active,
                   ro.name as org_name, ro.is_active as org_active, rom.password_hash
            FROM reporting_org_members rom
            JOIN reporting_organizations ro ON rom.org_id = ro.id
            WHERE rom.username = ?
        '''
        params = [username]
        if org_id:
            query += ' AND rom.org_id = ?'
            params.append(org_id)

        cursor.execute(query, params)
        member = cursor.fetchone()

        if not member or not verify_password(password, member['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Upgrade legacy SHA-256 hash to bcrypt on successful login
        if _needs_rehash(member['password_hash']):
            cursor.execute('UPDATE reporting_org_members SET password_hash = ? WHERE id = ?',
                           (hash_password(password), member['id']))

        if not member[5]:
            raise HTTPException(status_code=403, detail="Account is inactive")
        if not member[7]:
            raise HTTPException(status_code=403, detail="Organization is inactive")

        # Update last login
        cursor.execute('UPDATE reporting_org_members SET last_login_at = ? WHERE id = ?',
                       (datetime.now(timezone.utc).isoformat(), member[0]))
        conn.commit()

        # Create session
        session_id = secrets.token_hex(32)
        session_data = {
            'user_type': 'reporter',
            'username': member[2],
            'display_name': member[3] or member[2],
            'member_id': member[0],
            'org_id': member[1],
            'org_name': member[6],
            'role': member[4]
        }
        sessions[session_id] = session_data

        response.set_cookie(
            key='session',
            value=session_id,
            httponly=True,
            secure=False,
            samesite='lax',
            max_age=86400 * 7
        )

        logger.info(f"War Room: Reporter {username} logged in (org: {member[6]})")
        return {
            'status': 'success',
            'username': member[2],
            'display_name': member[3] or member[2],
            'org_name': member[6],
            'role': member[4],
            'user_type': 'reporter'
        }
    finally:
        conn.close()


# =============================================================================
# ENHANCED NEWS ENDPOINTS
# =============================================================================


@router.get('/api/warroom/news/{news_id}')
async def get_news_article(news_id: int, session: Optional[str] = Cookie(None)):
    """Get a single news article with full details."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT wn.id, wn.headline, wn.body, wn.author_username, wn.author_type,
                   wn.related_conflict_id, wn.published_at, wn.is_pinned, wn.article_type,
                   wn.featured_image_id, wn.reporting_org_id, wn.view_count,
                   ro.name as org_name,
                   wm.file_path as featured_image_url
            FROM war_news wn
            LEFT JOIN reporting_organizations ro ON wn.reporting_org_id = ro.id
            LEFT JOIN war_media wm ON wn.featured_image_id = wm.id
            WHERE wn.id = ? AND wn.is_active = 1
        ''', (news_id,))
        r = cursor.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Article not found")

        # Increment view count
        cursor.execute('UPDATE war_news SET view_count = view_count + 1 WHERE id = ?', (news_id,))
        conn.commit()

        # Get attached media
        cursor.execute('''
            SELECT id, filename, file_path, caption, thumbnail FROM war_media
            WHERE related_news_id = ? AND is_active = 1
        ''', (news_id,))
        media = cursor.fetchall()

        return {
            'id': r[0],
            'headline': r[1],
            'body': r[2],
            'author': r[3],
            'author_type': r[4],
            'conflict_id': r[5],
            'published_at': r[6],
            'is_pinned': bool(r[7]),
            'article_type': r[8],
            'featured_image_id': r[9],
            'reporting_org_id': r[10],
            'view_count': r[11] + 1,
            'org_name': r[12],
            'featured_image_url': r[13],
            'media': [{
                'id': m[0],
                'filename': m[1],
                'url': m[2],
                'caption': m[3],
                'thumbnail_url': f'/war-media/{m[4]}' if m[4] else None
            } for m in media]
        }
    finally:
        conn.close()


@router.put('/api/warroom/news/{news_id}')
async def update_news_article(news_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Update a news article."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Check if super admin, correspondent, or reporter who owns the article
    user_type = session_data.get('user_type')
    username = session_data.get('username')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get article
        cursor.execute('SELECT author_username, author_type FROM war_news WHERE id = ? AND is_active = 1', (news_id,))
        article = cursor.fetchone()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        # Authorization
        if user_type != 'super_admin':
            if article[0] != username:
                raise HTTPException(status_code=403, detail="Can only edit your own articles")

        data = await request.json()
        updates = []
        params = []

        for field in ['headline', 'body', 'article_type', 'is_pinned', 'featured_image_id', 'related_conflict_id']:
            if field in data:
                updates.append(f'{field} = ?')
                params.append(data[field])

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(news_id)
        cursor.execute(f'UPDATE war_news SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()

        return {'status': 'updated', 'news_id': news_id}
    finally:
        conn.close()


# =============================================================================
# WAR ROOM V3 - TERRITORY INTEGRATION
# =============================================================================


@router.get('/api/warroom/territory/by-tag')
async def get_territory_by_discord_tag(discord_tag: str = None, session: Optional[str] = Cookie(None)):
    """Get all systems owned by a discord_tag (partner territory)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get partner info for this discord_tag
        cursor.execute('''
            SELECT p.id, p.display_name, p.region_color, p.discord_tag
            FROM partner_accounts p
            WHERE p.discord_tag = ? AND p.is_active = 1
        ''', (discord_tag,))
        partner = cursor.fetchone()

        if not partner:
            return {'partner': None, 'systems': [], 'regions': {}}

        partner_id, display_name, color, tag = partner

        # Get all systems with this discord_tag
        cursor.execute('''
            SELECT id, name, galaxy, region_name, glyphs, region_x, region_y, region_z, reality
            FROM systems
            WHERE discord_tag = ?
            ORDER BY name
        ''', (discord_tag,))
        systems = cursor.fetchall()

        # Group by region and calculate ownership
        regions = {}
        for s in systems:
            region_key = f"{s[5]}_{s[6]}_{s[7]}_{s[2]}"  # x_y_z_galaxy
            if region_key not in regions:
                regions[region_key] = {
                    'region_x': s[5],
                    'region_y': s[6],
                    'region_z': s[7],
                    'galaxy': s[2],
                    'region_name': s[3],
                    'system_count': 0,
                    'systems': []
                }
            regions[region_key]['system_count'] += 1
            regions[region_key]['systems'].append({
                'id': s[0],
                'name': s[1],
                'glyphs': s[4],
                'reality': s[8]
            })

        return {
            'partner': {
                'id': partner_id,
                'display_name': display_name,
                'color': color,
                'discord_tag': tag
            },
            'systems': [{
                'id': s[0],
                'name': s[1],
                'galaxy': s[2],
                'region_name': s[3],
                'glyphs': s[4],
                'region_x': s[5],
                'region_y': s[6],
                'region_z': s[7],
                'reality': s[8]
            } for s in systems],
            'regions': regions,
            'total_systems': len(systems),
            'total_regions': len(regions)
        }
    finally:
        conn.close()


@router.get('/api/warroom/territory/search')
async def search_territory_systems(
    q: str = '',
    discord_tag: str = None,
    galaxy: str = None,
    limit: int = 50,
    session: Optional[str] = Cookie(None)
):
    """Search systems by name, filtering by discord_tag (for territory selection)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = '''
            SELECT s.id, s.name, s.galaxy, r.custom_name as region_name, s.glyph_code,
                   s.region_x, s.region_y, s.region_z, s.discord_tag, s.reality,
                   p.display_name as owner_name, p.region_color as owner_color
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x AND s.region_y = r.region_y
                AND s.region_z = r.region_z AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
            LEFT JOIN partner_accounts p ON s.discord_tag = p.discord_tag AND p.is_active = 1
            WHERE 1=1
        '''
        params = []

        if q:
            query += ' AND (s.name LIKE ? OR r.custom_name LIKE ?)'
            params.extend([f'%{q}%', f'%{q}%'])

        if discord_tag:
            query += ' AND s.discord_tag = ?'
            params.append(discord_tag)

        if galaxy:
            query += ' AND s.galaxy = ?'
            params.append(galaxy)

        query += ' ORDER BY s.name LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        results = cursor.fetchall()

        return [{
            'id': r[0],
            'name': r[1],
            'galaxy': r[2],
            'region_name': r[3],
            'glyphs': r[4],
            'region_x': r[5],
            'region_y': r[6],
            'region_z': r[7],
            'discord_tag': r[8],
            'reality': r[9],
            'owner_name': r[10],
            'owner_color': r[11],
            'is_partner_owned': r[10] is not None
        } for r in results]
    finally:
        conn.close()


@router.get('/api/warroom/territory/regions')
async def get_territory_regions(
    discord_tag: str = None,
    galaxy: str = 'Euclid',
    session: Optional[str] = Cookie(None)
):
    """Get regions with system counts, optionally filtered by discord_tag."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get regions from systems table, grouped by coordinates
        query = '''
            SELECT
                s.region_x, s.region_y, s.region_z, s.galaxy,
                r.custom_name as region_name,
                s.discord_tag,
                COUNT(*) as system_count,
                p.display_name as owner_name,
                p.region_color as owner_color,
                p.id as partner_id
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x AND s.region_y = r.region_y
                AND s.region_z = r.region_z AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
            LEFT JOIN partner_accounts p ON s.discord_tag = p.discord_tag AND p.is_active = 1
            WHERE s.galaxy = ?
        '''
        params = [galaxy]

        if discord_tag:
            query += ' AND s.discord_tag = ?'
            params.append(discord_tag)

        query += '''
            GROUP BY s.region_x, s.region_y, s.region_z, s.galaxy, s.discord_tag
            ORDER BY system_count DESC
        '''

        cursor.execute(query, params)
        results = cursor.fetchall()

        # Calculate region ownership (>50% = controls region)
        region_data = {}
        for r in results:
            key = f"{r[0]}_{r[1]}_{r[2]}_{r[3]}"
            if key not in region_data:
                region_data[key] = {
                    'region_x': r[0],
                    'region_y': r[1],
                    'region_z': r[2],
                    'galaxy': r[3],
                    'region_name': r[4],
                    'total_systems': 0,
                    'owners': {}
                }

            region_data[key]['total_systems'] += r[6]
            tag = r[5] or 'unclaimed'
            if tag not in region_data[key]['owners']:
                region_data[key]['owners'][tag] = {
                    'count': 0,
                    'name': r[7],
                    'color': r[8],
                    'partner_id': r[9]
                }
            region_data[key]['owners'][tag]['count'] += r[6]

        # Determine controlling faction for each region
        regions = []
        for key, data in region_data.items():
            controlling = None
            for tag, owner_info in data['owners'].items():
                if owner_info['count'] > data['total_systems'] / 2:
                    controlling = {
                        'discord_tag': tag,
                        'name': owner_info['name'],
                        'color': owner_info['color'],
                        'partner_id': owner_info['partner_id'],
                        'system_count': owner_info['count'],
                        'percentage': round(owner_info['count'] / data['total_systems'] * 100, 1)
                    }
                    break

            regions.append({
                'region_x': data['region_x'],
                'region_y': data['region_y'],
                'region_z': data['region_z'],
                'galaxy': data['galaxy'],
                'region_name': data['region_name'],
                'total_systems': data['total_systems'],
                'controlling_faction': controlling,
                'owners': data['owners']
            })

        return regions
    finally:
        conn.close()


@router.get('/api/warroom/territory/region-ownership')
async def get_region_ownership_summary(galaxy: str = 'Euclid', session: Optional[str] = Cookie(None)):
    """Get summary of which factions control which regions (>50% ownership)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get all systems grouped by region and discord_tag
        cursor.execute('''
            SELECT
                s.region_x, s.region_y, s.region_z, s.galaxy,
                MAX(r.custom_name) as region_name,
                s.discord_tag,
                COUNT(*) as system_count,
                p.display_name,
                p.region_color,
                p.id as partner_id
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x AND s.region_y = r.region_y
                AND s.region_z = r.region_z AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
            LEFT JOIN partner_accounts p ON s.discord_tag = p.discord_tag AND p.is_active = 1
            WHERE s.galaxy = ?
            GROUP BY s.region_x, s.region_y, s.region_z, s.galaxy, s.discord_tag
        ''', (galaxy,))

        results = cursor.fetchall()

        # Process into regions
        regions = {}
        for r in results:
            key = f"{r[0]}_{r[1]}_{r[2]}"
            if key not in regions:
                regions[key] = {
                    'region_x': r[0],
                    'region_y': r[1],
                    'region_z': r[2],
                    'galaxy': r[3],
                    'region_name': r[4],
                    'total': 0,
                    'by_owner': {}
                }
            regions[key]['total'] += r[6]
            tag = r[5] or 'unclaimed'
            regions[key]['by_owner'][tag] = {
                'count': r[6],
                'name': r[7],
                'color': r[8],
                'partner_id': r[9]
            }

        # Determine controllers
        controlled_regions = []
        for key, data in regions.items():
            for tag, info in data['by_owner'].items():
                if info['count'] > data['total'] / 2 and tag != 'unclaimed':
                    controlled_regions.append({
                        **{k: data[k] for k in ['region_x', 'region_y', 'region_z', 'galaxy', 'region_name', 'total']},
                        'controller': {
                            'discord_tag': tag,
                            'name': info['name'],
                            'color': info['color'],
                            'partner_id': info['partner_id'],
                            'systems': info['count'],
                            'percentage': round(info['count'] / data['total'] * 100, 1)
                        }
                    })
                    break

        return {
            'galaxy': galaxy,
            'controlled_regions': controlled_regions,
            'total_regions_with_control': len(controlled_regions)
        }
    finally:
        conn.close()


# =============================================================================
# PEACE TREATY ENDPOINTS
# =============================================================================


@router.post('/api/warroom/conflicts/{conflict_id}/propose-peace')
async def propose_peace_treaty(conflict_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Propose a peace treaty with demands/offers."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    partner_id = session_data.get('partner_id')
    username = session_data.get('username')
    user_type = session_data.get('user_type')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict details
        cursor.execute('''
            SELECT c.attacker_partner_id, c.defender_partner_id, c.status,
                   c.attacker_counter_count, c.defender_counter_count,
                   c.negotiation_status,
                   a.display_name as attacker_name,
                   d.display_name as defender_name
            FROM conflicts c
            JOIN partner_accounts a ON c.attacker_partner_id = a.id
            JOIN partner_accounts d ON c.defender_partner_id = d.id
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()

        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        attacker_id, defender_id, status, att_counters, def_counters, neg_status, attacker_name, defender_name = conflict

        if status == 'resolved':
            raise HTTPException(status_code=400, detail="Conflict already resolved")

        # Check if user is party to the conflict
        is_attacker = partner_id == attacker_id
        is_defender = partner_id == defender_id
        is_super = user_type == 'super_admin'

        if not (is_attacker or is_defender or is_super):
            raise HTTPException(status_code=403, detail="Not a party to this conflict")

        data = await request.json()
        items = data.get('items', [])  # List of {type: system/region, direction: give/receive, system_id/region coords, to/from partner}
        message = data.get('message', '')
        is_counter = data.get('is_counter', False)

        # Check counter limits (2 per side)
        if is_counter:
            if is_attacker and att_counters >= 2:
                raise HTTPException(status_code=400, detail="Maximum counter-offers reached (2). You must accept, reject, or continue fighting.")
            if is_defender and def_counters >= 2:
                raise HTTPException(status_code=400, detail="Maximum counter-offers reached (2). You must accept, reject, or continue fighting.")

        # Validate items - ensure HQ systems are not included
        for item in items:
            if item.get('type') == 'system' and item.get('system_id'):
                # Check if this is an HQ system
                cursor.execute('''
                    SELECT e.partner_id, e.home_region_x, e.home_region_y, e.home_region_z,
                           e.is_hq_protected, s.region_x, s.region_y, s.region_z
                    FROM war_room_enrollment e
                    JOIN systems s ON s.id = ?
                    WHERE e.is_hq_protected = 1
                      AND e.home_region_x = s.region_x
                      AND e.home_region_y = s.region_y
                      AND e.home_region_z = s.region_z
                ''', (item['system_id'],))
                hq_check = cursor.fetchone()
                if hq_check:
                    raise HTTPException(status_code=400, detail="Cannot include HQ/Home region systems in peace demands")

        # Determine recipient
        recipient_id = defender_id if is_attacker else attacker_id

        # Mark any pending proposals as superseded
        cursor.execute('''
            UPDATE peace_proposals SET status = 'superseded', responded_at = datetime('now')
            WHERE conflict_id = ? AND status = 'pending'
        ''', (conflict_id,))

        # Create the proposal
        cursor.execute('''
            INSERT INTO peace_proposals (conflict_id, proposer_partner_id, recipient_partner_id,
                                        proposal_type, counter_number, message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (conflict_id, partner_id, recipient_id,
              'counter' if is_counter else 'initial',
              (att_counters if is_attacker else def_counters) + (1 if is_counter else 0),
              message))
        proposal_id = cursor.lastrowid

        # Add proposal items
        for item in items:
            cursor.execute('''
                INSERT INTO proposal_items (proposal_id, item_type, direction, system_id, system_name,
                                           region_x, region_y, region_z, region_name, galaxy,
                                           from_partner_id, to_partner_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                proposal_id,
                item.get('type', 'system'),
                item.get('direction', 'give'),
                item.get('system_id'),
                item.get('system_name'),
                item.get('region_x'),
                item.get('region_y'),
                item.get('region_z'),
                item.get('region_name'),
                item.get('galaxy', 'Euclid'),
                item.get('from_partner_id', partner_id),
                item.get('to_partner_id', recipient_id)
            ))

        # Update conflict negotiation status
        cursor.execute('''
            UPDATE conflicts SET
                negotiation_status = 'pending',
                negotiation_started_at = COALESCE(negotiation_started_at, datetime('now'))
        ''', ())
        cursor.execute('UPDATE conflicts SET negotiation_status = ? WHERE id = ?', ('pending', conflict_id))

        # Increment counter count if this is a counter-offer
        if is_counter:
            if is_attacker:
                cursor.execute('UPDATE conflicts SET attacker_counter_count = attacker_counter_count + 1 WHERE id = ?', (conflict_id,))
            else:
                cursor.execute('UPDATE conflicts SET defender_counter_count = defender_counter_count + 1 WHERE id = ?', (conflict_id,))

        # Create notification for recipient
        cursor.execute('''
            INSERT INTO war_notifications (recipient_partner_id, notification_type, title, message, related_conflict_id)
            VALUES (?, 'peace_proposal', ?, ?, ?)
        ''', (recipient_id, 'Peace Treaty Proposed', f'A peace proposal has been sent for the conflict. Review the terms.', conflict_id))

        # Auto-news: Negotiations started
        proposer_name = attacker_name if is_attacker else defender_name
        create_auto_news(
            conn,
            'negotiations_started' if not is_counter else 'counter_offer',
            f"Peace Negotiations {'Continue' if is_counter else 'Begin'}: {attacker_name} vs {defender_name}",
            f"{proposer_name} has {'sent a counter-offer' if is_counter else 'proposed peace terms'} in the ongoing conflict.",
            reference_id=proposal_id,
            reference_type='peace_proposal',
            conflict_id=conflict_id
        )

        # Add conflict event
        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (conflict_id, 'peace_proposed', partner_id, username,
              f"{'Counter-offer' if is_counter else 'Peace proposal'} submitted with {len(items)} items"))

        conn.commit()
        return {'status': 'proposed', 'proposal_id': proposal_id}
    finally:
        conn.close()


@router.get('/api/warroom/conflicts/{conflict_id}/peace-proposals')
async def get_peace_proposals(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Get all peace proposals for a conflict."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get proposals
        cursor.execute('''
            SELECT pp.id, pp.proposer_partner_id, pp.recipient_partner_id, pp.proposal_type,
                   pp.counter_number, pp.status, pp.proposed_at, pp.responded_at, pp.message,
                   prop.display_name as proposer_name, prop.region_color as proposer_color,
                   rec.display_name as recipient_name, rec.region_color as recipient_color
            FROM peace_proposals pp
            JOIN partner_accounts prop ON pp.proposer_partner_id = prop.id
            JOIN partner_accounts rec ON pp.recipient_partner_id = rec.id
            WHERE pp.conflict_id = ?
            ORDER BY pp.proposed_at DESC
        ''', (conflict_id,))
        proposals = cursor.fetchall()

        result = []
        for p in proposals:
            # Get items for this proposal
            cursor.execute('''
                SELECT id, item_type, direction, system_id, system_name,
                       region_x, region_y, region_z, region_name, galaxy,
                       from_partner_id, to_partner_id
                FROM proposal_items WHERE proposal_id = ?
            ''', (p[0],))
            items = cursor.fetchall()

            result.append({
                'id': p[0],
                'proposer_partner_id': p[1],
                'recipient_partner_id': p[2],
                'proposal_type': p[3],
                'counter_number': p[4],
                'status': p[5],
                'proposed_at': p[6],
                'responded_at': p[7],
                'message': p[8],
                'proposer_name': p[9],
                'proposer_color': p[10],
                'recipient_name': p[11],
                'recipient_color': p[12],
                'items': [{
                    'id': i[0],
                    'item_type': i[1],
                    'direction': i[2],
                    'system_id': i[3],
                    'system_name': i[4],
                    'region_x': i[5],
                    'region_y': i[6],
                    'region_z': i[7],
                    'region_name': i[8],
                    'galaxy': i[9],
                    'from_partner_id': i[10],
                    'to_partner_id': i[11]
                } for i in items]
            })

        return result
    finally:
        conn.close()


@router.put('/api/warroom/peace-proposals/{proposal_id}/accept')
async def accept_peace_proposal(proposal_id: int, session: Optional[str] = Cookie(None)):
    """Accept a peace proposal, ending the conflict and transferring territory."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    partner_id = session_data.get('partner_id')
    username = session_data.get('username')
    user_type = session_data.get('user_type')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get proposal details
        cursor.execute('''
            SELECT pp.id, pp.conflict_id, pp.proposer_partner_id, pp.recipient_partner_id, pp.status,
                   c.attacker_partner_id, c.defender_partner_id, c.declared_at,
                   a.display_name as attacker_name, a.discord_tag as attacker_tag,
                   d.display_name as defender_name, d.discord_tag as defender_tag
            FROM peace_proposals pp
            JOIN conflicts c ON pp.conflict_id = c.id
            JOIN partner_accounts a ON c.attacker_partner_id = a.id
            JOIN partner_accounts d ON c.defender_partner_id = d.id
            WHERE pp.id = ?
        ''', (proposal_id,))
        proposal = cursor.fetchone()

        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        if proposal[4] != 'pending':
            raise HTTPException(status_code=400, detail="Proposal is not pending")

        # Check authorization - only recipient can accept
        if partner_id != proposal[3] and user_type != 'super_admin':
            raise HTTPException(status_code=403, detail="Only the recipient can accept this proposal")

        conflict_id = proposal[1]
        attacker_id = proposal[5]
        defender_id = proposal[6]
        declared_at = proposal[7]
        attacker_name = proposal[8]
        attacker_tag = proposal[9]
        defender_name = proposal[10]
        defender_tag = proposal[11]

        # Get items to transfer
        cursor.execute('SELECT * FROM proposal_items WHERE proposal_id = ?', (proposal_id,))
        items = cursor.fetchall()

        # Execute territory transfers
        systems_transferred = 0
        for item in items:
            item_type = item[2]
            direction = item[3]
            system_id = item[4]
            from_partner = item[11]
            to_partner = item[12]

            if item_type == 'system' and system_id:
                # Get the receiving partner's discord_tag
                cursor.execute('SELECT discord_tag FROM partner_accounts WHERE id = ?', (to_partner,))
                to_tag_row = cursor.fetchone()
                if to_tag_row:
                    new_tag = to_tag_row[0]

                    # Update systems.discord_tag
                    cursor.execute('UPDATE systems SET discord_tag = ? WHERE id = ?', (new_tag, system_id))

                    # Update or create territorial_claims
                    cursor.execute('DELETE FROM territorial_claims WHERE system_id = ?', (system_id,))
                    cursor.execute('''
                        INSERT INTO territorial_claims (system_id, claimant_partner_id, claim_type, notes)
                        VALUES (?, ?, 'conquered', 'Transferred via peace treaty')
                    ''', (system_id, to_partner))

                    systems_transferred += 1

            elif item_type == 'region':
                # Transfer all systems in the region
                region_x = item[5]
                region_y = item[6]
                region_z = item[7]
                galaxy = item[10]

                cursor.execute('SELECT discord_tag FROM partner_accounts WHERE id = ?', (to_partner,))
                to_tag_row = cursor.fetchone()
                if to_tag_row:
                    new_tag = to_tag_row[0]

                    # Get from_partner's discord_tag to only transfer their systems
                    cursor.execute('SELECT discord_tag FROM partner_accounts WHERE id = ?', (from_partner,))
                    from_tag_row = cursor.fetchone()
                    if from_tag_row:
                        from_tag = from_tag_row[0]

                        # Update all systems in region from the giving partner
                        cursor.execute('''
                            UPDATE systems SET discord_tag = ?
                            WHERE region_x = ? AND region_y = ? AND region_z = ?
                              AND galaxy = ? AND discord_tag = ?
                        ''', (new_tag, region_x, region_y, region_z, galaxy, from_tag))
                        systems_transferred += cursor.rowcount

        # Mark proposal as accepted
        cursor.execute('''
            UPDATE peace_proposals SET status = 'accepted', responded_at = datetime('now'), response_by = ?
            WHERE id = ?
        ''', (username, proposal_id))

        # Resolve the conflict
        cursor.execute('''
            UPDATE conflicts SET
                status = 'resolved',
                resolution = 'peace_treaty',
                resolved_at = datetime('now'),
                resolved_by = ?,
                negotiation_status = 'accepted',
                resolution_summary = ?
            WHERE id = ?
        ''', (username, f"Peace treaty accepted. {systems_transferred} systems transferred.", conflict_id))

        # Add conflict event
        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, 'peace_accepted', ?, ?, ?)
        ''', (conflict_id, partner_id, username, f"Peace treaty accepted. {systems_transferred} systems transferred."))

        # Calculate war duration
        from datetime import datetime as dt
        try:
            start = dt.fromisoformat(declared_at.replace('Z', '+00:00'))
            end = dt.now()
            duration = end - start
            duration_str = f"{duration.days} days" if duration.days > 0 else f"{duration.seconds // 3600} hours"
        except:
            duration_str = "unknown duration"

        # Auto-news: Peace concluded
        create_auto_news(
            conn,
            'peace_concluded',
            f"WAR ENDS: {attacker_name} and {defender_name} Sign Peace Treaty",
            f"After {duration_str} of conflict, peace has been achieved. {systems_transferred} systems changed hands as part of the agreement.",
            reference_id=conflict_id,
            reference_type='conflict',
            conflict_id=conflict_id
        )

        # Notify both parties
        cursor.execute('''
            INSERT INTO war_notifications (recipient_partner_id, notification_type, title, message, related_conflict_id)
            VALUES (?, 'peace_accepted', 'Peace Treaty Accepted', 'The peace treaty has been accepted. The war has ended.', ?)
        ''', (proposal[2], conflict_id))  # Notify proposer

        conn.commit()

        return {
            'status': 'accepted',
            'conflict_resolved': True,
            'systems_transferred': systems_transferred,
            'duration': duration_str
        }
    finally:
        conn.close()


@router.put('/api/warroom/peace-proposals/{proposal_id}/reject')
async def reject_peace_proposal(proposal_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Reject a peace proposal. Can optionally walk away (continue fighting) or send counter-offer."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    partner_id = session_data.get('partner_id')
    username = session_data.get('username')
    user_type = session_data.get('user_type')

    data = await request.json()
    walk_away = data.get('walk_away', False)  # If true, negotiations fail and war continues

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get proposal
        cursor.execute('''
            SELECT pp.id, pp.conflict_id, pp.proposer_partner_id, pp.recipient_partner_id, pp.status,
                   c.attacker_partner_id, c.defender_partner_id,
                   a.display_name as attacker_name,
                   d.display_name as defender_name
            FROM peace_proposals pp
            JOIN conflicts c ON pp.conflict_id = c.id
            JOIN partner_accounts a ON c.attacker_partner_id = a.id
            JOIN partner_accounts d ON c.defender_partner_id = d.id
            WHERE pp.id = ?
        ''', (proposal_id,))
        proposal = cursor.fetchone()

        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        if proposal[4] != 'pending':
            raise HTTPException(status_code=400, detail="Proposal is not pending")

        if partner_id != proposal[3] and user_type != 'super_admin':
            raise HTTPException(status_code=403, detail="Only the recipient can reject this proposal")

        conflict_id = proposal[1]
        attacker_name = proposal[7]
        defender_name = proposal[8]

        # Mark proposal as rejected
        cursor.execute('''
            UPDATE peace_proposals SET status = 'rejected', responded_at = datetime('now'), response_by = ?
            WHERE id = ?
        ''', (username, proposal_id))

        if walk_away:
            # Negotiations failed - war continues
            cursor.execute('''
                UPDATE conflicts SET negotiation_status = 'failed'
                WHERE id = ?
            ''', (conflict_id,))

            # Add conflict event
            cursor.execute('''
                INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
                VALUES (?, 'negotiations_failed', ?, ?, 'Peace talks have collapsed. The war continues.')
            ''', (conflict_id, partner_id, username))

            # Auto-news: Negotiations failed
            create_auto_news(
                conn,
                'negotiations_failed',
                f"PEACE TALKS COLLAPSE: {attacker_name} vs {defender_name} War Continues",
                f"Negotiations have broken down between the warring factions. Hostilities will continue.",
                reference_id=conflict_id,
                reference_type='conflict_negotiations',
                conflict_id=conflict_id
            )

            # Notify proposer
            cursor.execute('''
                INSERT INTO war_notifications (recipient_partner_id, notification_type, title, message, related_conflict_id)
                VALUES (?, 'negotiations_failed', 'Peace Talks Failed', 'Your peace proposal was rejected. The war continues.', ?)
            ''', (proposal[2], conflict_id))
        else:
            # Just rejected - waiting for counter-offer
            cursor.execute('''
                UPDATE conflicts SET negotiation_status = 'counter_expected'
                WHERE id = ?
            ''', (conflict_id,))

            # Add conflict event
            cursor.execute('''
                INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
                VALUES (?, 'proposal_rejected', ?, ?, 'Peace proposal rejected. Counter-offer may follow.')
            ''', (conflict_id, partner_id, username))

        conn.commit()

        return {
            'status': 'rejected',
            'walk_away': walk_away,
            'war_continues': walk_away
        }
    finally:
        conn.close()


@router.get('/api/warroom/conflicts/{conflict_id}/negotiation-status')
async def get_negotiation_status(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Get current negotiation status for a conflict."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT c.negotiation_status, c.attacker_counter_count, c.defender_counter_count,
                   c.negotiation_started_at, c.status,
                   a.display_name as attacker_name,
                   d.display_name as defender_name
            FROM conflicts c
            JOIN partner_accounts a ON c.attacker_partner_id = a.id
            JOIN partner_accounts d ON c.defender_partner_id = d.id
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()

        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        # Get pending proposal if any
        cursor.execute('''
            SELECT pp.id, pp.proposer_partner_id, pp.recipient_partner_id, pp.proposal_type,
                   pp.counter_number, pp.proposed_at, pp.message,
                   prop.display_name as proposer_name
            FROM peace_proposals pp
            JOIN partner_accounts prop ON pp.proposer_partner_id = prop.id
            WHERE pp.conflict_id = ? AND pp.status = 'pending'
            ORDER BY pp.proposed_at DESC LIMIT 1
        ''', (conflict_id,))
        pending = cursor.fetchone()

        return {
            'negotiation_status': conflict[0],
            'attacker_counter_count': conflict[1],
            'defender_counter_count': conflict[2],
            'attacker_counters_remaining': 2 - conflict[1],
            'defender_counters_remaining': 2 - conflict[2],
            'negotiation_started_at': conflict[3],
            'conflict_status': conflict[4],
            'attacker_name': conflict[5],
            'defender_name': conflict[6],
            'pending_proposal': {
                'id': pending[0],
                'proposer_partner_id': pending[1],
                'recipient_partner_id': pending[2],
                'proposal_type': pending[3],
                'counter_number': pending[4],
                'proposed_at': pending[5],
                'message': pending[6],
                'proposer_name': pending[7]
            } if pending else None
        }
    finally:
        conn.close()
