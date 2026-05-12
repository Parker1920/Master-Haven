"""Wizard v1 endpoints — records, check-existing.

Drafts are stored in the browser's localStorage per Parker's Phase 1 decision —
no server endpoint required. This module covers the two read-side helpers:

  GET  /api/wizard/records           — current Haven records keyed by type.metric
  GET  /api/wizard/check-existing    — combined dedup + pull-existing check
                                       at 12-glyphs-entered.

Records endpoint scans approved discoveries' type_metadata JSON for the top
value per (discovery_type, metric). For text-rank metrics (ship_class S>A>B>C,
deposit_richness Extraordinary>Rare>Common) we use a hard-coded rank table.
For numeric metrics (count, height, slots, etc.) we use MAX(). Frontend
iterates whatever keys exist; missing metrics simply degrade to no badge.
"""

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException

from db import get_db_connection, find_matching_system

logger = logging.getLogger('control.room')

router = APIRouter(tags=["wizard"])


# ---- Records definitions -----------------------------------------------
# Each entry: (discovery_type_key, metric_key, kind)
#   kind = 'numeric' (MAX), 'rank_class' (S>A>B>C), 'rank_rich' (Extraordinary>Rare>Common)
RECORD_DEFS = [
    ('starship', 'ship_class', 'rank_class'),
    ('starship', 'slots', 'numeric'),
    ('starship', 'manoeuvrability', 'numeric'),
    ('starship', 'damage', 'numeric'),
    ('starship', 'shield', 'numeric'),
    ('multitool', 'tool_class', 'rank_class'),
    ('multitool', 'damage', 'numeric'),
    ('multitool', 'mining', 'numeric'),
    ('multitool', 'scan', 'numeric'),
    ('mineral', 'deposit_richness', 'rank_rich'),
    ('fauna', 'height', 'numeric'),
    ('fauna', 'weight', 'numeric'),
]

# Discovery type emojis → human keys (mirrors src/data/discoveryTypes.js TYPE_INFO)
TYPE_EMOJI_TO_KEY = {
    '🦗': 'fauna',
    '🌿': 'flora',
    '💎': 'mineral',
    '🏛️': 'ancient',
    '📜': 'history',
    '🦴': 'bones',
    '👽': 'alien',
    '🚀': 'starship',
    '⚙️': 'multitool',
    '📖': 'lore',
    '🏠': 'base',
    '🆕': 'other',
}
TYPE_KEY_TO_EMOJI = {v: k for k, v in TYPE_EMOJI_TO_KEY.items()}

CLASS_RANK = {'S': 4, 'A': 3, 'B': 2, 'C': 1}
RICHNESS_RANK = {'Extraordinary': 3, 'Rare': 2, 'Common': 1}


def _parse_numeric(raw):
    """Pull the first number out of a possibly-decorated string ('11.8m', '48 slots', '+45%')."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    m = re.search(r'-?\d+(?:\.\d+)?', s)
    return float(m.group()) if m else None


@router.get('/api/wizard/records')
async def get_wizard_records():
    """Return current Haven records keyed as `{type}.{metric}` → {value, holder, system_name}.

    Example response:
        {
          "records": {
            "starship.ship_class": {"value": "S", "holder": "Stars",
                                    "system_name": "Vahnir-3", "discovery_id": 42},
            "fauna.height": {"value": 11.8, "raw": "11.8m", "holder": "Watcher", ...}
          }
        }
    Empty values are omitted; the frontend iterates and reads what's there.
    Cache the result client-side; backend is uncached but cheap on small DBs.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Pull all approved discoveries with type_metadata JSON. Filter out NULLs.
        cursor.execute("""
            SELECT id, discovery_type, type_metadata, discovered_by, system_id
            FROM discoveries
            WHERE type_metadata IS NOT NULL AND type_metadata != ''
        """)
        rows = cursor.fetchall()

        # Build a system_id → name map in one query
        sys_ids = list({r['system_id'] for r in rows if r['system_id']})
        sys_names = {}
        if sys_ids:
            placeholders = ','.join('?' * len(sys_ids))
            cursor.execute(f"SELECT id, name FROM systems WHERE id IN ({placeholders})", sys_ids)
            sys_names = {r['id']: r['name'] for r in cursor.fetchall()}

        records: dict = {}
        for row in rows:
            type_emoji = row['discovery_type']
            type_key = TYPE_EMOJI_TO_KEY.get(type_emoji)
            if not type_key:
                continue
            try:
                meta = json.loads(row['type_metadata']) or {}
            except (json.JSONDecodeError, TypeError):
                continue

            for (def_type, def_metric, kind) in RECORD_DEFS:
                if def_type != type_key:
                    continue
                raw_val = meta.get(def_metric)
                if raw_val is None or raw_val == '':
                    continue

                rec_key = f"{def_type}.{def_metric}"
                current = records.get(rec_key)

                if kind == 'numeric':
                    n = _parse_numeric(raw_val)
                    if n is None:
                        continue
                    if not current or n > current['_score']:
                        records[rec_key] = {
                            '_score': n,
                            'value': n,
                            'raw': str(raw_val),
                            'holder': row['discovered_by'] or 'Unknown',
                            'system_name': sys_names.get(row['system_id'], ''),
                            'system_id': row['system_id'],
                            'discovery_id': row['id'],
                        }
                elif kind == 'rank_class':
                    rank = CLASS_RANK.get(str(raw_val).strip().upper())
                    if not rank:
                        continue
                    if not current or rank > current['_score']:
                        records[rec_key] = {
                            '_score': rank,
                            'value': str(raw_val).strip().upper(),
                            'holder': row['discovered_by'] or 'Unknown',
                            'system_name': sys_names.get(row['system_id'], ''),
                            'system_id': row['system_id'],
                            'discovery_id': row['id'],
                        }
                elif kind == 'rank_rich':
                    rank = RICHNESS_RANK.get(str(raw_val).strip().title())
                    if not rank:
                        continue
                    if not current or rank > current['_score']:
                        records[rec_key] = {
                            '_score': rank,
                            'value': str(raw_val).strip().title(),
                            'holder': row['discovered_by'] or 'Unknown',
                            'system_name': sys_names.get(row['system_id'], ''),
                            'system_id': row['system_id'],
                            'discovery_id': row['id'],
                        }

        # Strip the internal sort score before returning
        for rec in records.values():
            rec.pop('_score', None)

        return {'records': records, 'count': len(records)}
    except Exception:
        logger.exception("Failed to compute wizard records")
        raise HTTPException(status_code=500, detail="Failed to compute records")
    finally:
        if conn:
            conn.close()


@router.get('/api/wizard/check-existing')
async def check_existing(
    glyph: str,
    galaxy: str = 'Euclid',
    reality: str = 'Normal',
):
    """One-shot lookup at 12-glyphs-entered.

    Returns: {exists: bool, system_id?, name?, summary?, edit_count?}
    summary is a compact subset for the "Pull existing data" prompt.
    Used by the wizard to populate the dup banner without two round-trips.
    """
    if not glyph or len(glyph) != 12:
        raise HTTPException(status_code=400, detail="glyph must be 12 hex characters")
    if not re.match(r'^[0-9A-Fa-f]{12}$', glyph):
        raise HTTPException(status_code=400, detail="glyph must be hexadecimal")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        existing = find_matching_system(cursor, glyph, galaxy, reality)
        if not existing:
            return {'exists': False}

        sys_id = existing[0]
        cursor.execute("""
            SELECT id, name, galaxy, reality, glyph_code,
                   star_type, economy_type, economy_level, conflict_level,
                   dominant_lifeform, stellar_classification, description,
                   region_x, region_y, region_z,
                   discovered_by, discord_tag, contributors, expedition_id,
                   game_version
            FROM systems WHERE id = ?
        """, (sys_id,))
        row = cursor.fetchone()
        if not row:
            return {'exists': False}

        sys_dict = dict(row)

        # Edit count from contributors JSON
        edit_count = 0
        try:
            contribs = json.loads(sys_dict.get('contributors') or '[]')
            edit_count = sum(1 for c in contribs if c.get('action') == 'edit')
        except (json.JSONDecodeError, TypeError):
            pass

        # Planet/moon counts for summary
        cursor.execute("SELECT COUNT(*) FROM planets WHERE system_id = ?", (sys_id,))
        planet_count = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM moons m
            JOIN planets p ON m.planet_id = p.id WHERE p.system_id = ?
        """, (sys_id,))
        moon_count = cursor.fetchone()[0]

        return {
            'exists': True,
            'system_id': sys_id,
            'name': sys_dict['name'],
            'edit_count': edit_count,
            'original_submitter': sys_dict.get('discovered_by'),
            'summary': {
                'name': sys_dict['name'],
                'galaxy': sys_dict.get('galaxy'),
                'reality': sys_dict.get('reality'),
                'star_type': sys_dict.get('star_type'),
                'economy_type': sys_dict.get('economy_type'),
                'economy_level': sys_dict.get('economy_level'),
                'conflict_level': sys_dict.get('conflict_level'),
                'dominant_lifeform': sys_dict.get('dominant_lifeform'),
                'stellar_classification': sys_dict.get('stellar_classification'),
                'description': sys_dict.get('description'),
                'planet_count': planet_count,
                'moon_count': moon_count,
                'expedition_id': sys_dict.get('expedition_id'),
                'game_version': sys_dict.get('game_version'),
            },
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("check-existing failed")
        raise HTTPException(status_code=500, detail="Lookup failed")
    finally:
        if conn:
            conn.close()
