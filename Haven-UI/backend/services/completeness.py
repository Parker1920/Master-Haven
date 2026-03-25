"""
Data completeness scoring and grading for star systems.

Calculates a weighted score (0-100) across 6 categories, then maps to a letter grade.
Used by approval workflow, system detail, and browse endpoints.
"""

import logging

from constants import NO_LIFE_BIOMES, score_to_grade

logger = logging.getLogger('control.room')


def _is_filled(val, allow_none_sentinel=False):
    """Check if a field value represents real data (not empty/default).

    NMS has legitimate values like 'None' for sentinels, 'Absent' for fauna/flora,
    and 0 for hazards on peaceful planets. These are REAL data, not missing data.
    """
    if val is None:
        return False
    s = str(val).strip()
    if not s:
        return False
    if s == 'N/A':
        return False
    if s == 'None' and not allow_none_sentinel:
        return False
    return True


def _life_descriptor_filled(val, val_text):
    """Check if a fauna/flora field has ANY value (including 'N/A', 'None', 'Absent').

    For fauna/flora, ANY non-empty string is real data. Only NULL/empty means not answered.
    """
    for v in [val, val_text]:
        if v is not None:
            s = str(v).strip()
            if s:
                return True
    return False


def calculate_completeness_score(cursor, system_id) -> dict:
    """Calculate a data completeness score (0-100) for a system.

    Returns a dict with: score, grade, breakdown (with per-category details).
    """
    cursor.execute('SELECT * FROM systems WHERE id = ?', (system_id,))
    system = cursor.fetchone()
    if not system:
        return {'score': 0, 'grade': 'C', 'breakdown': {}}
    system = dict(system)

    cursor.execute('SELECT * FROM planets WHERE system_id = ?', (system_id,))
    planets = [dict(row) for row in cursor.fetchall()]

    cursor.execute('SELECT * FROM space_stations WHERE system_id = ?', (system_id,))
    station = cursor.fetchone()
    station = dict(station) if station else None

    FIELD_LABELS = {
        'star_type': 'Star Type', 'economy_type': 'Economy Type', 'economy_level': 'Economy Tier',
        'conflict_level': 'Conflict Level', 'dominant_lifeform': 'Dominant Lifeform',
        'glyph_code': 'Glyph Code', 'stellar_classification': 'Stellar Class', 'description': 'Description',
        'biome': 'Biome', 'weather': 'Weather', 'sentinel': 'Sentinels',
        'fauna': 'Fauna', 'flora': 'Flora',
        'common_resource': 'Common Resource', 'uncommon_resource': 'Uncommon Resource', 'rare_resource': 'Rare Resource',
    }

    # --- System Core (35 pts) ---
    is_abandoned = system.get('economy_type') in ('None', 'Abandoned')
    sys_core_fields = ['star_type', 'economy_type', 'economy_level', 'conflict_level', 'dominant_lifeform']
    sys_core_filled = 0
    sys_core_details = []
    for f in sys_core_fields:
        val = system.get(f)
        if f in ('economy_type', 'economy_level', 'conflict_level') and is_abandoned:
            sys_core_filled += 1
            sys_core_details.append({'name': FIELD_LABELS[f], 'value': str(val) if val else 'N/A (Abandoned)', 'status': 'filled'})
        elif _is_filled(val):
            sys_core_filled += 1
            sys_core_details.append({'name': FIELD_LABELS[f], 'value': str(val), 'status': 'filled'})
        else:
            sys_core_details.append({'name': FIELD_LABELS[f], 'value': None, 'status': 'missing'})
    sys_core_score = round((sys_core_filled / len(sys_core_fields)) * 35)

    # --- System Extra (10 pts) ---
    sys_extra_fields = ['glyph_code', 'stellar_classification', 'description']
    sys_extra_details = []
    sys_extra_filled = 0
    for f in sys_extra_fields:
        val = system.get(f)
        if _is_filled(val):
            sys_extra_filled += 1
            display = str(val)[:40] + ('...' if val and len(str(val)) > 40 else '')
            sys_extra_details.append({'name': FIELD_LABELS[f], 'value': display, 'status': 'filled'})
        else:
            sys_extra_details.append({'name': FIELD_LABELS[f], 'value': None, 'status': 'missing'})
    sys_extra_score = round((sys_extra_filled / len(sys_extra_fields)) * 10)

    # --- Planet Coverage (10 pts) ---
    has_planets = len(planets) > 0
    planet_coverage_score = 10 if has_planets else 0

    # --- Planet Environment avg (25 pts) ---
    # --- Planet Life avg (15 pts) ---
    planet_env_score = 0
    planet_life_score = 0
    planet_env_details = []
    planet_life_details = []

    if planets:
        env_totals = []
        life_totals = []

        for p in planets:
            p_name = p.get('name', 'Unknown')
            p_env_fields = []
            p_life_fields = []

            # Environment scoring
            env_filled = 0
            if _is_filled(p.get('biome')):
                env_filled += 1
                p_env_fields.append({'name': 'Biome', 'value': p.get('biome'), 'status': 'filled'})
            else:
                p_env_fields.append({'name': 'Biome', 'value': None, 'status': 'missing'})

            weather_filled = _is_filled(p.get('weather'))
            weather_text_filled = _is_filled(p.get('weather_text'))
            if weather_filled:
                env_filled += 1
                p_env_fields.append({'name': 'Weather', 'value': p.get('weather'), 'status': 'filled'})
            elif weather_text_filled:
                env_filled += 1
                p_env_fields.append({'name': 'Weather', 'value': p.get('weather_text'), 'status': 'filled'})
            else:
                p_env_fields.append({'name': 'Weather', 'value': None, 'status': 'missing'})

            if _is_filled(p.get('sentinel'), allow_none_sentinel=True):
                env_filled += 1
                p_env_fields.append({'name': 'Sentinels', 'value': p.get('sentinel'), 'status': 'filled'})
            elif _is_filled(p.get('sentinels_text')):
                env_filled += 1
                p_env_fields.append({'name': 'Sentinels', 'value': p.get('sentinels_text'), 'status': 'filled'})
            else:
                p_env_fields.append({'name': 'Sentinels', 'value': None, 'status': 'missing'})

            env_total_fields = 3
            env_totals.append(min(env_filled / env_total_fields, 1.0))
            planet_env_details.append({'name': p_name, 'filled': env_filled, 'total': env_total_fields, 'fields': p_env_fields})

            # Life scoring
            life_filled = 0
            life_applicable = 0
            biome_val = (p.get('biome') or '').strip()
            is_dead_biome = biome_val in NO_LIFE_BIOMES

            if _life_descriptor_filled(p.get('fauna'), p.get('fauna_text')):
                life_filled += 1
                life_applicable += 1
                p_life_fields.append({'name': 'Fauna', 'value': p.get('fauna') or p.get('fauna_text'), 'status': 'filled'})
            elif not is_dead_biome:
                life_applicable += 1
                p_life_fields.append({'name': 'Fauna', 'value': None, 'status': 'missing'})
            else:
                p_life_fields.append({'name': 'Fauna', 'value': None, 'status': 'skipped'})

            if _life_descriptor_filled(p.get('flora'), p.get('flora_text')):
                life_filled += 1
                life_applicable += 1
                p_life_fields.append({'name': 'Flora', 'value': p.get('flora') or p.get('flora_text'), 'status': 'filled'})
            elif not is_dead_biome:
                life_applicable += 1
                p_life_fields.append({'name': 'Flora', 'value': None, 'status': 'missing'})
            else:
                p_life_fields.append({'name': 'Flora', 'value': None, 'status': 'skipped'})

            materials_val = (p.get('materials') or '').strip()
            has_materials = bool(materials_val) and materials_val not in ('N/A', 'None')
            if has_materials:
                life_applicable += 1
                life_filled += 1
                display = materials_val[:50] + ('...' if len(materials_val) > 50 else '')
                p_life_fields.append({'name': 'Resources', 'value': display, 'status': 'filled'})
            else:
                res_filled = 0
                res_total = 0
                for f in ['common_resource', 'uncommon_resource', 'rare_resource']:
                    res_total += 1
                    if _is_filled(p.get(f)):
                        res_filled += 1
                if res_filled > 0:
                    life_applicable += 1
                    life_filled += 1
                    p_life_fields.append({'name': 'Resources', 'value': f'{res_filled}/{res_total} types', 'status': 'filled'})
                else:
                    life_applicable += 1
                    p_life_fields.append({'name': 'Resources', 'value': None, 'status': 'missing'})

            life_totals.append(life_filled / max(life_applicable, 1))
            planet_life_details.append({'name': p_name, 'filled': life_filled, 'total': life_applicable, 'fields': p_life_fields})

        planet_env_score = round((sum(env_totals) / len(env_totals)) * 25)
        planet_life_score = round((sum(life_totals) / len(life_totals)) * 15)

    # --- Space Station (5 pts) ---
    station_score = 0
    station_details = []
    if is_abandoned:
        station_score = 5
        station_details.append({'name': 'Station', 'value': 'N/A (Abandoned)', 'status': 'filled'})
        station_details.append({'name': 'Trade Goods', 'value': 'N/A (Abandoned)', 'status': 'filled'})
    elif station:
        station_score += 3
        station_details.append({'name': 'Station', 'value': 'Present', 'status': 'filled'})
        trade_goods = station.get('trade_goods', '[]')
        if trade_goods and trade_goods != '[]':
            station_score += 2
            station_details.append({'name': 'Trade Goods', 'value': 'Recorded', 'status': 'filled'})
        else:
            station_details.append({'name': 'Trade Goods', 'value': None, 'status': 'missing'})
    else:
        station_details.append({'name': 'Station', 'value': None, 'status': 'missing'})
        station_details.append({'name': 'Trade Goods', 'value': None, 'status': 'missing'})

    # Total
    total = sys_core_score + sys_extra_score + planet_coverage_score + planet_env_score + planet_life_score + station_score
    total = min(total, 100)
    grade = score_to_grade(total)

    return {
        'score': total,
        'grade': grade,
        'breakdown': {
            'system_core': sys_core_score,
            'system_extra': sys_extra_score,
            'planet_coverage': planet_coverage_score,
            'planet_environment': planet_env_score,
            'planet_life': planet_life_score,
            'space_station': station_score,
            'planet_count': len(planets),
            'details': {
                'system_core': sys_core_details,
                'system_extra': sys_extra_details,
                'planet_coverage': [{'name': 'Has Planets', 'value': f'{len(planets)} planet(s)' if planets else None, 'status': 'filled' if planets else 'missing'}],
                'planet_environment': planet_env_details,
                'planet_life': planet_life_details,
                'space_station': station_details,
            }
        }
    }


def update_completeness_score(cursor, system_id) -> dict:
    """Calculate and store the completeness score for a system."""
    result = calculate_completeness_score(cursor, system_id)
    cursor.execute('UPDATE systems SET is_complete = ? WHERE id = ?', (result['score'], system_id))
    return result
