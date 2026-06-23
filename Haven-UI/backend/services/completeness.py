"""
Data completeness scoring and grading for star systems.

Calculates a weighted score (0-100) across 6 categories, then maps to a letter grade.
Used by approval workflow, system detail, and browse endpoints.
"""

import logging

from constants import NO_LIFE_BIOMES, score_to_grade, get_discovery_type_slug

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


def _score_body_environment(body):
    """Environment completeness for ONE celestial body (planet OR moon).

    Both the planets and moons tables carry biome / weather / sentinel (and the
    *_text variants), so the same three-field check applies to a moon as to a
    planet. Returns (filled_count, total_fields, field_details).
    """
    fields = []
    filled = 0

    if _is_filled(body.get('biome')):
        filled += 1
        fields.append({'name': 'Biome', 'value': body.get('biome'), 'status': 'filled'})
    else:
        fields.append({'name': 'Biome', 'value': None, 'status': 'missing'})

    if _is_filled(body.get('weather')):
        filled += 1
        fields.append({'name': 'Weather', 'value': body.get('weather'), 'status': 'filled'})
    elif _is_filled(body.get('weather_text')):
        filled += 1
        fields.append({'name': 'Weather', 'value': body.get('weather_text'), 'status': 'filled'})
    else:
        fields.append({'name': 'Weather', 'value': None, 'status': 'missing'})

    if _is_filled(body.get('sentinel'), allow_none_sentinel=True):
        filled += 1
        fields.append({'name': 'Sentinels', 'value': body.get('sentinel'), 'status': 'filled'})
    elif _is_filled(body.get('sentinels_text')):
        filled += 1
        fields.append({'name': 'Sentinels', 'value': body.get('sentinels_text'), 'status': 'filled'})
    else:
        fields.append({'name': 'Sentinels', 'value': None, 'status': 'missing'})

    return filled, 3, fields


def _score_body_life(body):
    """Life completeness for ONE celestial body (planet OR moon).

    Dead-biome bodies legitimately have no fauna/flora, so those fields are
    skipped (not counted against the body) when the biome is in NO_LIFE_BIOMES.
    Returns (ratio, filled_count, applicable_count, field_details).
    """
    fields = []
    filled = 0
    applicable = 0
    biome_val = (body.get('biome') or '').strip()
    is_dead_biome = biome_val in NO_LIFE_BIOMES

    if _life_descriptor_filled(body.get('fauna'), body.get('fauna_text')):
        filled += 1
        applicable += 1
        fields.append({'name': 'Fauna', 'value': body.get('fauna') or body.get('fauna_text'), 'status': 'filled'})
    elif not is_dead_biome:
        applicable += 1
        fields.append({'name': 'Fauna', 'value': None, 'status': 'missing'})
    else:
        fields.append({'name': 'Fauna', 'value': None, 'status': 'skipped'})

    if _life_descriptor_filled(body.get('flora'), body.get('flora_text')):
        filled += 1
        applicable += 1
        fields.append({'name': 'Flora', 'value': body.get('flora') or body.get('flora_text'), 'status': 'filled'})
    elif not is_dead_biome:
        applicable += 1
        fields.append({'name': 'Flora', 'value': None, 'status': 'missing'})
    else:
        fields.append({'name': 'Flora', 'value': None, 'status': 'skipped'})

    materials_val = (body.get('materials') or '').strip()
    has_materials = bool(materials_val) and materials_val not in ('N/A', 'None')
    if has_materials:
        applicable += 1
        filled += 1
        display = materials_val[:50] + ('...' if len(materials_val) > 50 else '')
        fields.append({'name': 'Resources', 'value': display, 'status': 'filled'})
    else:
        res_filled = 0
        for f in ['common_resource', 'uncommon_resource', 'rare_resource']:
            if _is_filled(body.get(f)):
                res_filled += 1
        if res_filled > 0:
            applicable += 1
            filled += 1
            fields.append({'name': 'Resources', 'value': f'{res_filled}/3 types', 'status': 'filled'})
        else:
            applicable += 1
            fields.append({'name': 'Resources', 'value': None, 'status': 'missing'})

    ratio = filled / max(applicable, 1)
    return ratio, filled, applicable, fields


# The five "Wonders Page Notes" fields (migration 1.76.0). A planet counts as
# having wonder information when ANY one of these is populated — root_structure
# and nutrient_source only apply to living/lush worlds, so requiring all five
# on every planet would make S+ unreachable.
WONDER_FIELDS = ('estimated_age', 'core_element', 'lore_notes', 'root_structure', 'nutrient_source')


def _has_base_coords(body) -> bool:
    """A planet/moon documents a base by carrying BOTH base lat & long."""
    return body.get('base_latitude') is not None and body.get('base_longitude') is not None


def _has_base_discovery(cursor, planet_ids, moon_ids) -> bool:
    """True if a base-type discovery is linked to any of these planets/moons.

    A base can be logged as a full discovery (type 'base', which carries its own
    lat/long) instead of via the planet/moon base lat/long fields — both paths
    count toward the X "documented base" requirement. type_slug is the canonical
    type column; fall back to deriving it from discovery_type for rows that
    predate type_slug.
    """
    conds, params = [], []
    if planet_ids:
        conds.append(f"planet_id IN ({','.join('?' * len(planet_ids))})")
        params.extend(planet_ids)
    if moon_ids:
        conds.append(f"moon_id IN ({','.join('?' * len(moon_ids))})")
        params.extend(moon_ids)
    if not conds:
        return False
    cursor.execute(
        f"SELECT type_slug, discovery_type FROM discoveries WHERE ({' OR '.join(conds)})",
        params,
    )
    for row in cursor.fetchall():
        row = dict(row)
        slug = row.get('type_slug') or get_discovery_type_slug(row.get('discovery_type') or '')
        if slug == 'base':
            return True
    return False


def check_splus_eligible(cursor, system_id) -> bool:
    """Run the X ("fully charted") checklist for a system.

    X is NOT a score band — it sits on top of the S grade. The caller must
    have already confirmed score >= 85 (constants.SPLUS_MIN_SCORE). A system is
    fully charted when ALL of these hold:

      1. The system has at least one planet.
      2. Every planet AND every moon has a discovery linked to it
         (discoveries.planet_id / discoveries.moon_id).
      3. At least ONE body (any planet OR moon) carries wonder information —
         at least one of the five Wonders Page fields (see WONDER_FIELDS) is
         populated. (Relaxed 2026-06-23 from "every planet".)
      4. At least one base is documented. A base counts when ANY body carries
         base lat/long, OR a base-type discovery is linked to a body, OR (legacy
         back-compat) a body has a non-empty free-text base_location.
      5. The space station is recorded — required only for systems that
         actually have one. Abandoned / uncharted systems (economy_type
         'None'/'Abandoned') and systems flagged no_space_station are exempt.

    Returns True only when every applicable item passes. The live `discoveries`
    table holds approved discoveries (pending ones live in pending_discoveries),
    so existence there is sufficient.
    """
    cursor.execute('SELECT economy_type, no_space_station FROM systems WHERE id = ?', (system_id,))
    srow = cursor.fetchone()
    if not srow:
        return False
    srow = dict(srow)
    # Station is exempt from the X checklist when the system is Abandoned OR has
    # been explicitly marked as having no space station (no_space_station flag).
    station_exempt = (
        srow.get('economy_type') in ('None', 'Abandoned')
        or bool(srow.get('no_space_station'))
    )

    base_cols = ('base_location', 'base_latitude', 'base_longitude')
    wonder_cols = ', '.join(WONDER_FIELDS)

    # planets: id + base + wonder fields
    cursor.execute(
        f"SELECT id, {', '.join(base_cols)}, {wonder_cols} FROM planets WHERE system_id = ?",
        (system_id,),
    )
    planets = [dict(r) for r in cursor.fetchall()]
    if not planets:
        return False
    planet_ids = [p['id'] for p in planets]
    ph = ','.join('?' * len(planet_ids))

    # moons: id + base + wonder fields (so they count toward wonder + base too)
    cursor.execute(
        f"SELECT id, {', '.join(base_cols)}, {wonder_cols} FROM moons WHERE planet_id IN ({ph})",
        planet_ids,
    )
    moons = [dict(r) for r in cursor.fetchall()]
    moon_ids = [m['id'] for m in moons]

    bodies = planets + moons

    # 3. wonder info on AT LEAST ONE body (planet or moon)
    if not any(any(_is_filled(b.get(f)) for f in WONDER_FIELDS) for b in bodies):
        return False

    # 4. at least one documented base — base lat/long on any body, or a legacy
    #    free-text base_location, or a base-type discovery.
    base_documented = any(_has_base_coords(b) or _is_filled(b.get('base_location')) for b in bodies)
    if not base_documented:
        base_documented = _has_base_discovery(cursor, planet_ids, moon_ids)
    if not base_documented:
        return False

    # 2a. a discovery linked to every planet (planet ids are globally unique,
    # so match on planet_id directly rather than relying on a stamped system_id)
    cursor.execute(
        f'SELECT DISTINCT planet_id FROM discoveries WHERE planet_id IN ({ph})',
        planet_ids,
    )
    discovered_planet_ids = {row[0] for row in cursor.fetchall()}
    if any(pid not in discovered_planet_ids for pid in planet_ids):
        return False

    # 2b. a discovery linked to every moon
    if moon_ids:
        mph = ','.join('?' * len(moon_ids))
        cursor.execute(
            f'SELECT DISTINCT moon_id FROM discoveries WHERE moon_id IN ({mph})',
            moon_ids,
        )
        discovered_moon_ids = {row[0] for row in cursor.fetchall()}
        if any(mid not in discovered_moon_ids for mid in moon_ids):
            return False

    # 5. recorded station (only required when the system should have one)
    if not station_exempt:
        cursor.execute('SELECT 1 FROM space_stations WHERE system_id = ? LIMIT 1', (system_id,))
        if not cursor.fetchone():
            return False

    return True


def calculate_completeness_score(cursor, system_id) -> dict:
    """Calculate a data completeness score (0-100) for a system.

    Returns a dict with: score, grade, is_fully_charted, breakdown (with
    per-category details). `grade` is 'X' when the score clears S AND the
    fully-charted checklist passes (see check_splus_eligible).
    """
    cursor.execute('SELECT * FROM systems WHERE id = ?', (system_id,))
    system = cursor.fetchone()
    if not system:
        return {'score': 0, 'grade': 'C', 'breakdown': {}}
    system = dict(system)

    cursor.execute('SELECT * FROM planets WHERE system_id = ?', (system_id,))
    planets = [dict(row) for row in cursor.fetchall()]

    # Moons count as equal celestial bodies in the planet grade: each body
    # (planet OR moon) is weighted 1/(planets+moons) of the Planet Environment
    # and Planet Life categories. So a 5-planet + 1-moon system gives each body
    # ~16.7%, and a moon earns its share by carrying its own biome/weather/
    # sentinel + fauna/flora/resources. Built here as one ordered list so the
    # env/life averaging and the per-body detail breakdown stay in lockstep.
    bodies = []
    for p in planets:
        bodies.append({'body': p, 'label': p.get('name') or 'Unknown', 'is_moon': False})
        cursor.execute('SELECT * FROM moons WHERE planet_id = ?', (p.get('id'),))
        for mrow in cursor.fetchall():
            m = dict(mrow)
            bodies.append({
                'body': m,
                'label': f"🌙 {m.get('name') or 'Unknown'} (moon of {p.get('name') or 'Unknown'})",
                'is_moon': True,
            })

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
        # dominant_lifeform: "None" and "Abandoned" are BOTH legitimate
        # answers (a system with no race vs a system whose race left).
        # Both count as filled — pass allow_none_sentinel=True so the
        # "None" string isn't treated as missing data.
        elif f == 'dominant_lifeform' and _is_filled(val, allow_none_sentinel=True):
            sys_core_filled += 1
            sys_core_details.append({'name': FIELD_LABELS[f], 'value': str(val), 'status': 'filled'})
        # conflict_level: "None" is a legitimate answer — a peaceful system that
        # still has a station/economy can genuinely have no conflict. Count it as
        # filled on non-abandoned systems too; previously only the abandoned
        # branch let 'None' through, so picking "None" scored as missing data.
        elif f == 'conflict_level' and _is_filled(val, allow_none_sentinel=True):
            sys_core_filled += 1
            sys_core_details.append({'name': FIELD_LABELS[f], 'value': str(val), 'status': 'filled'})
        elif _is_filled(val):
            sys_core_filled += 1
            sys_core_details.append({'name': FIELD_LABELS[f], 'value': str(val), 'status': 'filled'})
        else:
            sys_core_details.append({'name': FIELD_LABELS[f], 'value': None, 'status': 'missing'})
    sys_core_score = round((sys_core_filled / len(sys_core_fields)) * 35)

    # --- System Extra (10 pts) ---
    # `description` was dropped from scoring (2026-06-19): it's free-text prose
    # (and is repurposed to stash the procgen name on renamed systems), so it
    # was never a meaningful completeness signal. The category stays worth 10
    # pts across the two remaining structural fields — 5 pts each.
    sys_extra_fields = ['glyph_code', 'stellar_classification']
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
    # Averaged across ALL bodies (planets AND moons) so each body weighs
    # 1/(planets+moons). Moons are scored with the exact same per-body helpers
    # as planets — a moon that's left blank drags the planet grade down just
    # like an undocumented planet would.
    planet_env_score = 0
    planet_life_score = 0
    planet_env_details = []
    planet_life_details = []

    if bodies:
        env_totals = []
        life_totals = []

        for b in bodies:
            body = b['body']
            label = b['label']

            env_filled, env_total_fields, p_env_fields = _score_body_environment(body)
            env_totals.append(min(env_filled / env_total_fields, 1.0))
            planet_env_details.append({'name': label, 'filled': env_filled, 'total': env_total_fields, 'fields': p_env_fields})

            life_ratio, life_filled, life_applicable, p_life_fields = _score_body_life(body)
            life_totals.append(life_ratio)
            planet_life_details.append({'name': label, 'filled': life_filled, 'total': life_applicable, 'fields': p_life_fields})

        planet_env_score = round((sum(env_totals) / len(env_totals)) * 25)
        planet_life_score = round((sum(life_totals) / len(life_totals)) * 15)

    # --- Space Station (5 pts) ---
    # A system explicitly flagged as having no station (no_space_station) gets
    # full credit just like an Abandoned-economy system — "no station" is a
    # complete answer, not missing data.
    no_station = bool(system.get('no_space_station'))
    station_score = 0
    station_details = []
    if is_abandoned or no_station:
        station_score = 5
        _slabel = 'N/A (Abandoned)' if is_abandoned else 'N/A (No Station)'
        station_details.append({'name': 'Station', 'value': _slabel, 'status': 'filled'})
        station_details.append({'name': 'Trade Goods', 'value': _slabel, 'status': 'filled'})
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

    # S+ is the "fully charted" tier on top of S — only worth checking once the
    # score itself clears the S baseline.
    is_fully_charted = total >= 85 and check_splus_eligible(cursor, system_id)
    grade = score_to_grade(total, is_fully_charted)

    return {
        'score': total,
        'grade': grade,
        'is_fully_charted': is_fully_charted,
        'breakdown': {
            'system_core': sys_core_score,
            'system_extra': sys_extra_score,
            'planet_coverage': planet_coverage_score,
            'planet_environment': planet_env_score,
            'planet_life': planet_life_score,
            'space_station': station_score,
            'planet_count': len(planets),
            'body_count': len(bodies),
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
    """Calculate and store the completeness score + fully-charted flag.

    Persists both the 0-100 score (is_complete) and the S+ checklist outcome
    (is_fully_charted, 0/1) so SQL grade ladders can surface S+ without re-running
    the checklist per row.
    """
    result = calculate_completeness_score(cursor, system_id)
    cursor.execute(
        'UPDATE systems SET is_complete = ?, is_fully_charted = ? WHERE id = ?',
        (result['score'], 1 if result.get('is_fully_charted') else 0, system_id),
    )
    return result
