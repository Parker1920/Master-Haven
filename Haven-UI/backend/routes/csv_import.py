"""CSV import, preview, and photo upload endpoints."""

import csv
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Cookie, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from constants import HAVEN_UI_DIR
from db import get_db_connection, add_activity_log
from glyph_decoder import decode_glyph_to_coords, galactic_coords_to_glyph
from image_processor import process_image
from services.auth_service import get_session
from services.completeness import update_completeness_score

logger = logging.getLogger('control.room')

router = APIRouter(tags=["csv_import"])

PHOTOS_DIR = HAVEN_UI_DIR / 'photos'


# ============================================================================
# Photo Upload
# ============================================================================

@router.post('/api/photos')
async def upload_photo(file: UploadFile = File(...)):
    """Upload a photo, auto-compressing to WebP with thumbnail generation. Public."""
    filename = file.filename or 'photo'
    raw_bytes = await file.read()

    # Process image: resize + compress to WebP + generate thumbnail
    try:
        result = process_image(raw_bytes, filename)
    except Exception as e:
        logger.warning(f"Image processing failed for {filename}, saving raw: {e}")
        # Fallback: save raw file if processing fails (e.g. corrupt image)
        dest = PHOTOS_DIR / filename
        if dest.exists():
            base, suffix = dest.stem, dest.suffix
            i = 1
            while (PHOTOS_DIR / f"{base}-{i}{suffix}").exists():
                i += 1
            dest = PHOTOS_DIR / f"{base}-{i}{suffix}"
        with dest.open('wb') as f:
            f.write(raw_bytes)
        path = str(dest.relative_to(HAVEN_UI_DIR))
        return JSONResponse({'path': path})

    # Avoid overwriting by renaming
    full_dest = PHOTOS_DIR / result['full_filename']
    thumb_dest = PHOTOS_DIR / result['thumb_filename']
    if full_dest.exists():
        stem = Path(filename).stem
        i = 1
        while (PHOTOS_DIR / f"{stem}-{i}.webp").exists():
            i += 1
        full_dest = PHOTOS_DIR / f"{stem}-{i}.webp"
        thumb_dest = PHOTOS_DIR / f"{stem}-{i}_thumb.webp"

    with full_dest.open('wb') as f:
        f.write(result['full_bytes'])
    with thumb_dest.open('wb') as f:
        f.write(result['thumb_bytes'])

    path = str(full_dest.relative_to(HAVEN_UI_DIR))
    return JSONResponse({
        'path': path,
        'filename': full_dest.name,
        'thumbnail': thumb_dest.name,
        'original_size': result['original_size'],
        'compressed_size': result['compressed_size'],
    })


# ============================================================================
# CSV Preview
# ============================================================================

@router.post('/api/csv_preview')
async def csv_preview(file: UploadFile = File(...), session: Optional[str] = Cookie(None)):
    """
    Parse a CSV file and return detected column mappings + preview data.
    Does NOT import anything - just returns the mapping for user confirmation.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    enabled_features = session_data.get('enabled_features', [])
    if not is_super and 'csv_import' not in enabled_features and 'CSV_IMPORT' not in enabled_features:
        raise HTTPException(status_code=403, detail='CSV import permission required')

    try:
        content = await file.read()
        if len(content) > 50 * 1024 * 1024:  # 50 MB limit
            raise HTTPException(status_code=400, detail='CSV file too large (max 50 MB)')
        text_content = content.decode('utf-8-sig')
        reader = csv.reader(io.StringIO(text_content))
        rows = list(reader)

        if len(rows) < 2:
            raise HTTPException(status_code=400, detail='CSV must have at least a header row and one data row')

        # --- Detect format: GHUB (row 0 = region, row 1 = headers) vs Dynamic (row 0 = headers) ---
        known_header_keywords = ['system', 'planet', 'portal', 'glyph', 'galaxy', 'coordinates', 'coord',
                                 'hub tag', 'star', 'economy', 'conflict', 'race', 'region', 'biome', 'resources']
        row0_lower = [c.lower().strip() for c in rows[0] if c.strip()]
        row0_matches = sum(1 for kw in known_header_keywords if any(kw in cell for cell in row0_lower))

        if row0_matches >= 2:
            header_row_idx = 0
            data_start_idx = 1
            region_name = None
        else:
            region_name = None
            for cell in rows[0]:
                if cell and cell.strip():
                    region_name = cell.strip()
                    break
            header_row_idx = 1
            data_start_idx = 2

        header = rows[header_row_idx]
        header_lower = [h.lower().strip() for h in header]

        # --- Build column mapping by scanning headers ---
        COLUMN_PATTERNS = {
            'system_name': ['system name', 'system', 'hub tag', 'new system name', 'new name'],
            'planet_name': ['planet name', 'planet'],
            'galaxy': ['galaxy'],
            'region': ['region'],
            'star_colour': ['star colour', 'star color', 'star type'],
            'star_class': ['star class', 'spectral class', 'stellar class', 'classification'],
            'economy_type': ['economy type', 'economy'],
            'conflict_level': ['conflict level', 'conflict'],
            'dominant_lifeform': ['race', 'lifeform', 'dominant lifeform'],
            'resources': ['resources', 'resource', 'materials'],
            'notes': ['notes', 'comments', 'special attributes', 'comments/special'],
            'nmsportals_link': ['nmsportals link', 'nmsportals'],
            'portal_code': ['portal code', 'glyph', 'glyph code', 'glyphs'],
            'coordinates': ['coordinates', 'coord', 'galactic coord'],
            'logged_by': ['logged by', 'uploaded by', 'contributor', 'discord'],
            'original_name': ['original system name', 'original name'],
            'reference_id': ['reference id', 'ref id', 'ref'],
        }

        column_mapping = []
        detected = {}
        for i, h in enumerate(header_lower):
            if not h:
                continue
            mapped = None
            for field, patterns in COLUMN_PATTERNS.items():
                for pattern in patterns:
                    if pattern in h:
                        mapped = field
                        break
                if mapped:
                    break
            column_mapping.append({
                'index': i,
                'csv_column': header[i].strip(),
                'mapped_to': mapped or 'ignored',
            })
            if mapped and mapped not in detected:
                detected[mapped] = i

        # Determine coordinate type
        coord_type = None
        if 'portal_code' in detected:
            coord_type = 'portal_glyph'
        elif 'coordinates' in detected:
            coord_type = 'galactic_coords'
        elif 'nmsportals_link' in detected:
            coord_type = 'nmsportals_link'

        # Preview first 5 data rows
        preview_rows = []
        for row in rows[data_start_idx:data_start_idx + 5]:
            preview = {}
            for cm in column_mapping:
                if cm['mapped_to'] != 'ignored' and cm['index'] < len(row):
                    preview[cm['mapped_to']] = row[cm['index']].strip()
            preview_rows.append(preview)

        return {
            'status': 'ok',
            'format': 'ghub' if header_row_idx == 1 else 'dynamic',
            'region_name': region_name,
            'header_row': header_row_idx,
            'data_start_row': data_start_idx,
            'total_data_rows': len(rows) - data_start_idx,
            'column_mapping': column_mapping,
            'detected_fields': list(detected.keys()),
            'coord_type': coord_type,
            'preview_rows': preview_rows,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV preview error: {e}")
        logger.exception("CSV preview failed")
        raise HTTPException(status_code=500, detail="Preview failed")


# ============================================================================
# CSV Import Helpers
# ============================================================================

# --- Galaxy name -> number lookup (loaded once) ---
_GALAXY_NAME_TO_NUMBER = None

def _get_galaxy_name_to_number():
    """Load galaxies.json and build a case-insensitive name->canonical name dict."""
    global _GALAXY_NAME_TO_NUMBER
    if _GALAXY_NAME_TO_NUMBER is not None:
        return _GALAXY_NAME_TO_NUMBER
    galaxies_path = Path(__file__).parent.parent / 'data' / 'galaxies.json'
    try:
        with open(galaxies_path, 'r') as f:
            data = json.load(f)
        _GALAXY_NAME_TO_NUMBER = {v.lower(): v for v in data.values()}
        for k, v in data.items():
            _GALAXY_NAME_TO_NUMBER[k] = v
    except Exception:
        _GALAXY_NAME_TO_NUMBER = {'euclid': 'Euclid'}
    return _GALAXY_NAME_TO_NUMBER


def _resolve_galaxy_name(raw_galaxy):
    """Resolve a galaxy name from CSV to the canonical name from galaxies.json."""
    if not raw_galaxy or not raw_galaxy.strip():
        return 'Euclid'
    lookup = _get_galaxy_name_to_number()
    canonical = lookup.get(raw_galaxy.strip().lower())
    if canonical:
        return canonical
    return raw_galaxy.strip()


# --- Note parsing helpers for CSV import ---
SPECIAL_FEATURE_KEYWORDS = {
    'dissonant system': 'is_dissonant',
    'dissonance detected': 'is_dissonant',
    'dissonance': 'is_dissonant',
    'vile brood': 'vile_brood',
    'vile brood detected': 'vile_brood',
    'ancient bones': 'ancient_bones',
    'salvageable scrap': 'salvageable_scrap',
    'storm crystals': 'storm_crystals',
    'gravitino balls': 'gravitino_balls',
    'gravitino ball': 'gravitino_balls',
    'ringed planet': 'has_rings',
    'ringed': 'has_rings',
    'infested': 'is_infested',
    'gas giant': 'is_gas_giant',
    'bubbles': None,
    'bioluminescent': None,
    'bioluminescence': None,
    'floating islands': None,
    'floating flora': None,
    'mountainous': None,
}


def _parse_notes_to_features(notes_str):
    """Parse a free-text notes/comments string into special feature flags and remaining notes."""
    if not notes_str:
        return {}, ''
    features = {}
    remaining = []
    parts = [p.strip() for p in notes_str.split(',')]
    for part in parts:
        part_lower = part.lower().strip()
        matched = False
        for keyword, field in SPECIAL_FEATURE_KEYWORDS.items():
            if keyword in part_lower:
                if field:
                    features[field] = 1
                matched = True
                break
        if not matched and part.strip():
            remaining.append(part.strip())
    return features, ', '.join(remaining)


def _extract_glyph_from_nmsportals_link(url):
    """Extract 12-char glyph code from an nmsportals.github.io URL."""
    if not url:
        return None
    url = url.strip()
    if '#' in url:
        glyph = url.split('#')[-1].strip()
        if len(glyph) == 12:
            try:
                int(glyph, 16)
                return glyph.upper()
            except ValueError:
                pass
    return None


def _normalize_conflict_level(raw):
    """Normalize conflict level values from CSV to our standard values."""
    if not raw:
        return None
    raw = raw.strip().strip("'").strip()
    mapping = {
        'low': 'Low', 'medium': 'Medium', 'high': 'High', 'none': 'None',
        'outlaw': 'Pirate', 'pirate': 'Pirate',
        '-data unavailable-': 'None', "'-data unavailable-": 'None',
    }
    return mapping.get(raw.lower(), raw)


def _normalize_economy_type(raw):
    """Normalize economy type values from CSV to our standard values."""
    if not raw:
        return None
    raw = raw.strip().strip("'").strip()
    mapping = {
        'trading': 'Trading', 'mining': 'Mining', 'manufacturing': 'Manufacturing',
        'technology': 'Technology', 'scientific': 'Scientific',
        'power generation': 'Power Generation', 'mass production': 'Mass Production',
        'advanced materials': 'Advanced Materials', 'pirate': 'Pirate',
        'none': 'None', 'abandoned': 'Abandoned',
        '-data unavailable-': 'None', "'-data unavailable-": 'None',
    }
    return mapping.get(raw.lower(), raw)


def _normalize_lifeform(raw):
    """Normalize dominant lifeform values from CSV."""
    if not raw:
        return None
    raw = raw.strip()
    mapping = {
        'gek': 'Gek', "vy'keen": "Vy'keen", 'vykeen': "Vy'keen",
        'korvax': 'Korvax', 'uncharted': None, 'none': None,
    }
    return mapping.get(raw.lower(), raw)


# ============================================================================
# CSV Import
# ============================================================================

@router.post('/api/import_csv')
async def import_csv(file: UploadFile = File(...), column_mapping: Optional[str] = Form(None), session: Optional[str] = Cookie(None)):
    """
    Dynamic CSV importer. Supports multiple CSV formats by auto-detecting column headers.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    enabled_features = session_data.get('enabled_features', [])
    if not is_super and 'csv_import' not in enabled_features and 'CSV_IMPORT' not in enabled_features:
        raise HTTPException(status_code=403, detail='CSV import permission required')

    partner_tag = session_data.get('discord_tag')

    try:
        content = await file.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail='CSV file too large (max 50 MB)')
        text_content = content.decode('utf-8-sig')
        reader = csv.reader(io.StringIO(text_content))
        rows = list(reader)

        if len(rows) < 2:
            raise HTTPException(status_code=400, detail='CSV must have at least a header row and one data row')

        # --- Parse optional column mapping override from frontend ---
        mapping_override = None
        if column_mapping:
            try:
                mapping_override = json.loads(column_mapping)
            except (json.JSONDecodeError, TypeError):
                pass

        # --- Detect format ---
        known_header_keywords = ['system', 'planet', 'portal', 'glyph', 'galaxy', 'coordinates', 'coord',
                                 'hub tag', 'star', 'economy', 'conflict', 'race', 'region', 'biome', 'resources']
        row0_lower = [c.lower().strip() for c in rows[0] if c.strip()]
        row0_matches = sum(1 for kw in known_header_keywords if any(kw in cell for cell in row0_lower))

        if row0_matches >= 2:
            header_row_idx = 0
            data_start_idx = 1
            region_name = None
        else:
            region_name = None
            for cell in rows[0]:
                if cell and cell.strip():
                    region_name = cell.strip()
                    break
            header_row_idx = 1
            data_start_idx = 2

        header = rows[header_row_idx]
        header_lower = [h.lower().strip() for h in header]

        # --- Build column index map ---
        COLUMN_PATTERNS = {
            'system_name': ['system name', 'system', 'hub tag', 'new system name', 'new name'],
            'planet_name': ['planet name', 'planet'],
            'galaxy': ['galaxy'],
            'region': ['region'],
            'star_colour': ['star colour', 'star color', 'star type'],
            'star_class': ['star class', 'spectral class', 'stellar class', 'classification'],
            'economy_type': ['economy type', 'economy'],
            'conflict_level': ['conflict level', 'conflict'],
            'dominant_lifeform': ['race', 'lifeform', 'dominant lifeform'],
            'resources': ['resources', 'resource', 'materials'],
            'notes': ['notes', 'comments', 'special attributes', 'comments/special'],
            'nmsportals_link': ['nmsportals link', 'nmsportals'],
            'portal_code': ['portal code', 'glyph', 'glyph code', 'glyphs'],
            'coordinates': ['coordinates', 'coord', 'galactic coord'],
            'logged_by': ['logged by', 'uploaded by', 'contributor', 'discord'],
            'original_name': ['original system name', 'original name'],
        }

        col_idx = {}
        if mapping_override:
            for item in mapping_override:
                if item.get('mapped_to') and item['mapped_to'] != 'ignored':
                    col_idx[item['mapped_to']] = item['index']
        else:
            for i, h in enumerate(header_lower):
                if not h:
                    continue
                for field, patterns in COLUMN_PATTERNS.items():
                    if field in col_idx:
                        continue
                    for pattern in patterns:
                        if pattern in h:
                            col_idx[field] = i
                            break
                    if field in col_idx:
                        break

        # --- Coordinate extraction helper ---
        def get_glyph_from_row(row):
            """Extract a 12-char glyph code from the row using available coordinate columns."""
            if 'portal_code' in col_idx and col_idx['portal_code'] < len(row):
                raw = row[col_idx['portal_code']].strip()
                if len(raw) == 12:
                    try:
                        int(raw, 16)
                        return raw.upper()
                    except ValueError:
                        pass
            if 'nmsportals_link' in col_idx and col_idx['nmsportals_link'] < len(row):
                glyph = _extract_glyph_from_nmsportals_link(row[col_idx['nmsportals_link']])
                if glyph:
                    return glyph
            if 'coordinates' in col_idx and col_idx['coordinates'] < len(row):
                coords = row[col_idx['coordinates']].strip()
                if ':' in coords:
                    try:
                        glyph_data = galactic_coords_to_glyph(coords)
                        return glyph_data['glyph'].upper()
                    except (ValueError, Exception):
                        pass
            return None

        def get_cell(row, field):
            idx = col_idx.get(field)
            if idx is not None and idx < len(row):
                val = row[idx].strip()
                return val if val else None
            return None

        # --- Process rows: group by system (same glyph minus planet index) ---
        # Import find_matching_system at call time to avoid circular imports
        from db import find_matching_system

        system_groups = {}
        imported_count = 0
        skipped_count = 0
        errors = []
        processed_rows = 0

        for row_idx, row in enumerate(rows[data_start_idx:], start=data_start_idx + 1):
            try:
                if not row or all(not c.strip() for c in row):
                    continue

                glyph_code = get_glyph_from_row(row)
                if not glyph_code:
                    errors.append(f"Row {row_idx}: Could not extract glyph/coordinates")
                    skipped_count += 1
                    continue

                planet_index = int(glyph_code[0], 16)
                system_glyph_key = '0' + glyph_code[1:]

                system_name = get_cell(row, 'system_name') or f"System_{system_glyph_key}"
                galaxy_raw = get_cell(row, 'galaxy')
                galaxy = _resolve_galaxy_name(galaxy_raw)
                star_colour = get_cell(row, 'star_colour')
                star_class = get_cell(row, 'star_class')
                economy_type = _normalize_economy_type(get_cell(row, 'economy_type'))
                conflict_level = _normalize_conflict_level(get_cell(row, 'conflict_level'))
                dominant_lifeform = _normalize_lifeform(get_cell(row, 'dominant_lifeform'))
                region_col = get_cell(row, 'region')
                logged_by = get_cell(row, 'logged_by')

                planet_name = get_cell(row, 'planet_name')
                resources_raw = get_cell(row, 'resources')
                notes_raw = get_cell(row, 'notes')

                features, remaining_notes = _parse_notes_to_features(notes_raw)
                resource_features, clean_resources_str = _parse_notes_to_features(resources_raw)
                features.update(resource_features)

                planet_data = None
                if planet_name:
                    planet_data = {
                        'name': planet_name,
                        'planet_index': planet_index,
                        'materials': clean_resources_str or None,
                        'notes': remaining_notes or None,
                        **{k: v for k, v in features.items()},
                    }

                if system_glyph_key not in system_groups:
                    system_groups[system_glyph_key] = {
                        'glyph_code': system_glyph_key,
                        'name': system_name,
                        'galaxy': galaxy,
                        'star_type': star_colour,
                        'stellar_classification': star_class,
                        'economy_type': economy_type,
                        'conflict_level': conflict_level,
                        'dominant_lifeform': dominant_lifeform,
                        'region_name': region_col,
                        'logged_by': logged_by,
                        'planets': [],
                    }
                if planet_data:
                    system_groups[system_glyph_key]['planets'].append(planet_data)

                processed_rows += 1

            except Exception as e:
                errors.append(f"Row {row_idx}: {str(e)}")
                skipped_count += 1

        # --- Insert grouped systems + planets ---
        import uuid
        conn = get_db_connection()
        cursor = conn.cursor()
        imported_region_coords = None

        for sys_glyph_key, sys_data in system_groups.items():
            try:
                glyph_code = sys_data['glyph_code']

                try:
                    decoded = decode_glyph_to_coords(glyph_code)
                except Exception as e:
                    errors.append(f"System '{sys_data['name']}': Invalid glyph {glyph_code} - {e}")
                    skipped_count += 1
                    continue

                x, y, z = decoded['x'], decoded['y'], decoded['z']
                star_x, star_y, star_z = decoded['star_x'], decoded['star_y'], decoded['star_z']
                region_x, region_y, region_z = decoded['region_x'], decoded['region_y'], decoded['region_z']
                solar_system = decoded['solar_system']

                galaxy = sys_data.get('galaxy') or 'Euclid'
                reality = 'Normal'

                # Canonical dedup: last-11 glyph chars + galaxy + reality
                existing = find_matching_system(cursor, glyph_code, galaxy, reality)
                if existing:
                    skipped_count += 1
                    continue

                sys_id = str(uuid.uuid4())
                discord_tag = partner_tag

                logged_by = sys_data.get('logged_by')
                desc_parts = []
                if logged_by:
                    desc_parts.append(f"Logged by: {logged_by}")
                description = '\n'.join(desc_parts) if desc_parts else None

                cursor.execute('''
                    INSERT INTO systems (id, name, galaxy, reality, x, y, z, star_x, star_y, star_z, description,
                        glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z, discord_tag,
                        star_type, stellar_classification, economy_type, conflict_level, dominant_lifeform,
                        discovered_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sys_id, sys_data['name'], galaxy, reality,
                    x, y, z, star_x, star_y, star_z, description,
                    glyph_code, 0, solar_system, region_x, region_y, region_z, discord_tag,
                    sys_data.get('star_type'), sys_data.get('stellar_classification'),
                    sys_data.get('economy_type'), sys_data.get('conflict_level'),
                    sys_data.get('dominant_lifeform'),
                    logged_by,
                ))

                for planet in sys_data.get('planets', []):
                    cursor.execute('''
                        INSERT INTO planets (system_id, name, x, y, z, climate, weather, sentinel, fauna, flora,
                            materials, notes, planet_index,
                            has_rings, is_dissonant, is_infested, vile_brood,
                            ancient_bones, salvageable_scrap, storm_crystals, gravitino_balls, is_gas_giant)
                        VALUES (?, ?, 0, 0, 0, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        sys_id, planet['name'],
                        planet.get('materials'), planet.get('notes'), planet.get('planet_index', 0),
                        1 if planet.get('has_rings') else 0,
                        1 if planet.get('is_dissonant') else 0,
                        1 if planet.get('is_infested') else 0,
                        1 if planet.get('vile_brood') else 0,
                        1 if planet.get('ancient_bones') else 0,
                        1 if planet.get('salvageable_scrap') else 0,
                        1 if planet.get('storm_crystals') else 0,
                        1 if planet.get('gravitino_balls') else 0,
                        1 if planet.get('is_gas_giant') else 0,
                    ))

                try:
                    update_completeness_score(conn, sys_id)
                except Exception:
                    pass

                imported_count += 1

                if imported_region_coords is None and region_x is not None:
                    imported_region_coords = {
                        'region_x': region_x, 'region_y': region_y, 'region_z': region_z,
                        'galaxy': galaxy, 'reality': reality,
                    }

                if sys_data.get('region_name') and region_x is not None:
                    try:
                        cursor.execute('''
                            INSERT INTO regions (region_x, region_y, region_z, custom_name, reality, galaxy, discord_tag)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(reality, galaxy, region_x, region_y, region_z)
                            DO NOTHING
                        ''', (region_x, region_y, region_z, sys_data['region_name'], reality, galaxy, discord_tag))
                    except Exception:
                        pass

            except Exception as e:
                errors.append(f"System '{sys_data.get('name', '?')}': {str(e)}")
                skipped_count += 1

        conn.commit()
        conn.close()

        if region_name and imported_count > 0 and imported_region_coords:
            conn = get_db_connection()
            cursor = conn.cursor()
            import_reality = imported_region_coords.get('reality', 'Normal')
            import_galaxy = imported_region_coords.get('galaxy', 'Euclid')
            cursor.execute('''
                INSERT INTO regions (region_x, region_y, region_z, custom_name, reality, galaxy)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(reality, galaxy, region_x, region_y, region_z)
                DO UPDATE SET custom_name = excluded.custom_name
            ''', (imported_region_coords['region_x'], imported_region_coords['region_y'],
                  imported_region_coords['region_z'], region_name, import_reality, import_galaxy))
            conn.commit()
            conn.close()

        add_activity_log(
            'csv_import',
            f"Imported {imported_count} systems ({processed_rows} rows) from CSV",
            details=f"File: {file.filename}, Systems: {imported_count}, Skipped: {skipped_count}, Errors: {len(errors)}, Region: {region_name}",
            user_name=session_data.get('username', 'unknown')
        )

        return {
            'status': 'ok',
            'imported': imported_count,
            'skipped': skipped_count,
            'errors': errors[:10] if errors else [],
            'total_errors': len(errors),
            'region_name': region_name,
            'systems_grouped': len(system_groups),
            'total_rows_processed': processed_rows,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV import error: {e}")
        logger.exception("CSV import failed")
        raise HTTPException(status_code=500, detail="Import failed")
