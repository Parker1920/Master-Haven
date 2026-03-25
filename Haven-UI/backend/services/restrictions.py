"""
Data restriction service for per-system visibility controls.

Partners can restrict their systems' data from public view: hide entire systems,
redact specific field groups, or control map visibility.
"""

import json
import logging
from typing import Optional

from constants import RESTRICTABLE_FIELDS
from db import get_db_connection

logger = logging.getLogger('control.room')


def get_restriction_for_system(system_id: int) -> Optional[dict]:
    """Get restriction settings for a system, or None if unrestricted."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, system_id, discord_tag, is_hidden_from_public, hidden_fields,
                   map_visibility, created_at, updated_at, created_by
            FROM data_restrictions WHERE system_id = ?
        ''', (system_id,))
        row = cursor.fetchone()
        if row:
            return {
                'id': row['id'],
                'system_id': row['system_id'],
                'discord_tag': row['discord_tag'],
                'is_hidden_from_public': bool(row['is_hidden_from_public']),
                'hidden_fields': json.loads(row['hidden_fields'] or '[]'),
                'map_visibility': row['map_visibility'] or 'normal',
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'created_by': row['created_by']
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get restriction for system {system_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_restrictions_batch(system_ids: list) -> dict:
    """Batch fetch restrictions for multiple systems in a single query."""
    if not system_ids:
        return {}
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(system_ids))
        cursor.execute(f'''
            SELECT id, system_id, discord_tag, is_hidden_from_public, hidden_fields,
                   map_visibility, created_at, updated_at, created_by
            FROM data_restrictions WHERE system_id IN ({placeholders})
        ''', system_ids)
        restrictions = {}
        for row in cursor.fetchall():
            restrictions[row['system_id']] = {
                'id': row['id'],
                'system_id': row['system_id'],
                'discord_tag': row['discord_tag'],
                'is_hidden_from_public': bool(row['is_hidden_from_public']),
                'hidden_fields': json.loads(row['hidden_fields'] or '[]'),
                'map_visibility': row['map_visibility'] or 'normal',
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'created_by': row['created_by']
            }
        return restrictions
    except Exception as e:
        logger.error(f"Failed to batch fetch restrictions: {e}")
        return {}
    finally:
        if conn:
            conn.close()


def get_restrictions_by_discord_tag(discord_tag: str) -> list:
    """Get all restrictions for a specific discord_tag."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT dr.*, s.name as system_name, s.galaxy
            FROM data_restrictions dr
            JOIN systems s ON dr.system_id = s.id
            WHERE dr.discord_tag = ?
            ORDER BY s.name
        ''', (discord_tag,))
        rows = cursor.fetchall()
        return [{
            'id': row['id'],
            'system_id': row['system_id'],
            'system_name': row['system_name'],
            'galaxy': row['galaxy'],
            'discord_tag': row['discord_tag'],
            'is_hidden_from_public': bool(row['is_hidden_from_public']),
            'hidden_fields': json.loads(row['hidden_fields'] or '[]'),
            'map_visibility': row['map_visibility'] or 'normal',
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'created_by': row['created_by']
        } for row in rows]
    except Exception as e:
        logger.error(f"Failed to get restrictions for tag {discord_tag}: {e}")
        return []
    finally:
        if conn:
            conn.close()


def can_bypass_restriction(session_data: Optional[dict], system_discord_tag: str) -> bool:
    """Check if current user can bypass restrictions for a system."""
    if not session_data:
        return False
    if session_data.get('user_type') == 'super_admin':
        return True
    if session_data.get('user_type') == 'partner':
        return session_data.get('discord_tag') == system_discord_tag
    return False


def apply_field_restrictions(system: dict, hidden_fields: list) -> dict:
    """Remove restricted fields from system data. Returns a modified copy."""
    if not hidden_fields:
        return system
    result = dict(system)
    for field_group in hidden_fields:
        if field_group in RESTRICTABLE_FIELDS:
            for field in RESTRICTABLE_FIELDS[field_group]:
                if field in result:
                    del result[field]
        if field_group == 'planets' and 'planets' in result:
            planet_count = len(result.get('planets', []))
            result['planets'] = []
            result['planet_count_only'] = planet_count
        if field_group == 'base_location' and 'planets' in result:
            for planet in result.get('planets', []):
                if 'base_location' in planet:
                    del planet['base_location']
    return result


def apply_data_restrictions(systems: list, session_data: Optional[dict], for_map: bool = False) -> list:
    """Filter systems based on data restrictions and viewer permissions.

    Uses batch query for all restrictions at once (1 query instead of N).
    """
    if not systems:
        return systems
    if session_data and session_data.get('user_type') == 'super_admin':
        return systems

    viewer_discord_tag = None
    if session_data and session_data.get('user_type') == 'partner':
        viewer_discord_tag = session_data.get('discord_tag')

    system_ids = [s.get('id') for s in systems if s.get('id')]
    restrictions_map = get_restrictions_batch(system_ids) if system_ids else {}

    result = []
    for system in systems:
        system_id = system.get('id')
        system_tag = system.get('discord_tag')

        if viewer_discord_tag and viewer_discord_tag == system_tag:
            result.append(system)
            continue

        restriction = restrictions_map.get(system_id) if system_id else None
        if not restriction:
            result.append(system)
            continue

        if restriction.get('is_hidden_from_public'):
            continue

        if for_map:
            map_vis = restriction.get('map_visibility', 'normal')
            if map_vis == 'hidden':
                continue
            elif map_vis == 'point_only':
                filtered_system = {
                    'id': system.get('id'),
                    'name': system.get('name'),
                    'x': system.get('x'),
                    'y': system.get('y'),
                    'z': system.get('z'),
                    'star_x': system.get('star_x'),
                    'star_y': system.get('star_y'),
                    'star_z': system.get('star_z'),
                    'galaxy': system.get('galaxy'),
                    'star_type': system.get('star_type'),
                    'map_visibility': 'point_only',
                    'planets': []
                }
                result.append(filtered_system)
                continue

        hidden_fields = restriction.get('hidden_fields', [])
        filtered_system = apply_field_restrictions(system, hidden_fields)
        result.append(filtered_system)

    return result
