"""
Smoke tests for the voyager URL slug system.

End-to-end verification that:
  1. The frontend slugifier (normalizeUsernameForUrl in identity.js) produces
     URL-safe hyphen slugs for any reasonable display name.
  2. The /api/public/voyager-fingerprint resolver normalizes those slugs back
     to space-separated DB names so the lookup hits the right row.
  3. The SQL norm expression in routes/analytics.py matches what the Python
     resolver produces (run live against in-memory SQLite).
  4. Slug → resolver → SQL form round-trips on every test username.
  5. Atlas URLs use percent-encoding (NOT hyphen slugging) — pinned so any
     change has to update this test.
  6. The OG/SSR layer renders human-friendly titles from raw URL slugs.

The frontend slugifier lives in JS, so we mirror its logic in Python here.
If the Python mirror and the JS impl ever drift, these tests will pass
while production breaks — keep them aligned. Same for the resolver-side
Python normalization in routes/analytics.py and the SQL expression below.

Run from repo root:
    py -m pytest Haven-UI/tests/test_voyager_slug.py -v
"""
import re
import sqlite3
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Python mirror of the JS slugifier in src/posters/_shared/identity.js.
# Must produce the same output as the JS impl for every input we care about.
# ---------------------------------------------------------------------------

def slugify_username(name):
    if not name:
        return ''
    clean = re.sub(r'#', '', str(name)).strip()
    if (
        len(clean) > 4
        and re.match(r'^\d{4}$', clean[-4:])
        and not re.match(r'^\d$', clean[-5])
    ):
        clean = clean[:-4]
    s = clean.lower()
    s = re.sub(r'\s+', '-', s)
    s = re.sub(r'[^a-z0-9-]', '', s)
    s = re.sub(r'-+', '-', s)
    s = re.sub(r'^-+|-+$', '', s)
    return s


# ---------------------------------------------------------------------------
# Python mirror of the resolver normalization in routes/analytics.py
# (public_voyager_fingerprint). Must match the live function exactly.
# ---------------------------------------------------------------------------

def resolver_normalize(slug):
    if slug is None:
        return None
    s = str(slug).strip()
    if not s:
        return None
    input_clean = s.replace('#', '').strip()
    if (
        len(input_clean) > 4
        and input_clean[-4:].isdigit()
        and (len(input_clean) == 4 or not input_clean[-5].isdigit())
    ):
        input_clean = input_clean[:-4]
    out = input_clean.lower().replace('-', ' ').strip()
    return out or None


# ---------------------------------------------------------------------------
# SQL norm expression — copy of the one built in routes/analytics.py.
# Simplified to read from a single `name` column instead of the COALESCE
# chain, since we're testing the normalization, not the column resolution.
# ---------------------------------------------------------------------------

SQL_NORM = """REPLACE(LOWER(TRIM(
    CASE
        WHEN LENGTH(TRIM(REPLACE(name, '#', ''))) > 4
            AND SUBSTR(TRIM(REPLACE(name, '#', '')), -4) GLOB '[0-9][0-9][0-9][0-9]'
            AND (LENGTH(TRIM(REPLACE(name, '#', ''))) = 4
                OR SUBSTR(TRIM(REPLACE(name, '#', '')), -5, 1) NOT GLOB '[0-9]')
        THEN SUBSTR(TRIM(REPLACE(name, '#', '')), 1, LENGTH(TRIM(REPLACE(name, '#', ''))) - 4)
        ELSE TRIM(REPLACE(name, '#', ''))
    END
)), '-', ' ')"""


@pytest.fixture
def memdb():
    conn = sqlite3.connect(':memory:')
    yield conn
    conn.close()


def sql_normalize(conn, name):
    cur = conn.execute(f'SELECT {SQL_NORM} FROM (SELECT ? AS name)', (name,))
    return cur.fetchone()[0]


# ===========================================================================
# 1. Frontend slug generation
# ===========================================================================

class TestSlugify:
    @pytest.mark.parametrize('raw,expected', [
        ('Hiroki Rinn',          'hiroki-rinn'),
        ('hiroki rinn',          'hiroki-rinn'),
        ('Hiroki  Rinn',         'hiroki-rinn'),
        ('  Hiroki Rinn  ',      'hiroki-rinn'),
        ('TurpitZz#9999',        'turpitzz'),
        ('X1234567',             'x1234567'),
        ('Ace#1234',             'ace'),
        ('ALLCAPS NAME',         'allcaps-name'),
        ('Player123',            'player123'),
        ('Turpitzz',             'turpitzz'),
        ('Some-Name Here',       'some-name-here'),
    ])
    def test_basic_cases(self, raw, expected):
        assert slugify_username(raw) == expected

    def test_apostrophe_stripped(self):
        # Non-alphanumeric chars (including ') are removed entirely.
        assert slugify_username("O'Brien") == 'obrien'

    def test_accented_chars_stripped(self):
        # Diacritics are dropped to keep slugs in the [a-z0-9-] charset.
        # Acceptable lossiness for URL safety; if a non-Latin user can't be
        # found, they can be looked up via the SPA search bar instead.
        assert slugify_username('José García') == 'jos-garca'

    def test_underscore_stripped_not_hyphenated(self):
        # Documents the choice: _ is treated as non-alphanumeric and stripped,
        # NOT converted to a hyphen. ('some_user' → 'someuser')
        assert slugify_username('some_user') == 'someuser'

    def test_special_chars_stripped(self):
        assert slugify_username('user@name!') == 'username'

    def test_repeated_hyphens_collapsed(self):
        assert slugify_username('A   B   C') == 'a-b-c'
        assert slugify_username('--leading-and-trailing--') == 'leading-and-trailing'

    @pytest.mark.parametrize('raw', [None, '', '   '])
    def test_empty_inputs(self, raw):
        assert slugify_username(raw) == ''

    def test_idempotent(self):
        # Running the slugifier on its own output must be a no-op.
        for name in ['Hiroki Rinn', 'TurpitZz#9999', 'Some-Name Here', 'ALLCAPS NAME']:
            once = slugify_username(name)
            twice = slugify_username(once)
            assert once == twice, f'slugify not idempotent for {name!r}: {once!r} → {twice!r}'


# ===========================================================================
# 2. Backend resolver normalization
# ===========================================================================

class TestResolverNormalize:
    @pytest.mark.parametrize('slug,expected', [
        ('hiroki-rinn',     'hiroki rinn'),
        ('turpitzz',        'turpitzz'),
        ('some-name-here',  'some name here'),
        ('Hiroki-Rinn',     'hiroki rinn'),    # case-insensitive
        ('hiroki rinn',     'hiroki rinn'),    # post-%20-decode form
        ('  hiroki-rinn  ', 'hiroki rinn'),    # incidental whitespace
        ('HIROKI-RINN',     'hiroki rinn'),
    ])
    def test_slug_to_db_form(self, slug, expected):
        assert resolver_normalize(slug) == expected

    def test_discord_discriminator_still_stripped(self):
        # If the URL slug somehow carries a 4-digit suffix (raw, not via #),
        # the resolver still strips it. Mirrors the JS slugifier path that
        # would have stripped TurpitZz#9999 → turpitzz before the URL.
        assert resolver_normalize('turpitzz9999') == 'turpitzz'

    def test_blank_input(self):
        assert resolver_normalize('') is None
        assert resolver_normalize('   ') is None
        assert resolver_normalize(None) is None


# ===========================================================================
# 3. SQL normalization expression — runs the actual SQL against in-memory
# SQLite. Pins behavior of the expression copied from routes/analytics.py.
# ===========================================================================

class TestSqlNormalization:
    @pytest.mark.parametrize('db_name,expected', [
        ('Hiroki Rinn',      'hiroki rinn'),
        ('TurpitZz#9999',    'turpitzz'),
        ('X1234567',         'x1234567'),
        ('Ace#1234',         'ace'),
        ('Some Name Here',   'some name here'),
        ('  Hiroki Rinn  ',  'hiroki rinn'),
        ('Player123',        'player123'),
    ])
    def test_sql_normalizes_db_name(self, memdb, db_name, expected):
        assert sql_normalize(memdb, db_name) == expected

    def test_sql_collapses_hyphens_to_spaces(self, memdb):
        # If a DB row has a hyphen in the display name (rare but possible),
        # SQL still folds it to a space so it matches resolver-normalized
        # slug input. Symmetry: same operation runs on both sides.
        assert sql_normalize(memdb, 'Some-Name') == 'some name'


# ===========================================================================
# 4. Round-trip — every display name should slugify, then resolve, then
# match the SQL-normalized form of the original. This is the actual
# behavior contract.
# ===========================================================================

ROUND_TRIP_NAMES = [
    'Hiroki Rinn',
    'hiroki rinn',
    'TurpitZz#9999',
    'Ace#1234',
    'Player123',
    'Some Name Here',
    'ALLCAPS NAME',
    'Turpitzz',
    'Some-Name Here',
]


class TestRoundTrip:
    @pytest.mark.parametrize('display_name', ROUND_TRIP_NAMES)
    def test_slug_resolves_to_sql_normalization(self, memdb, display_name):
        slug = slugify_username(display_name)
        if not slug:
            pytest.skip(f'no slug produced for {display_name!r}')
        resolver_input = resolver_normalize(slug)
        sql_db_value = sql_normalize(memdb, display_name)
        assert resolver_input == sql_db_value, (
            f'{display_name!r}: slug={slug!r} → resolver={resolver_input!r} '
            f'but SQL produced {sql_db_value!r}'
        )

    @pytest.mark.parametrize('variant', [
        'hiroki-rinn',
        'Hiroki-Rinn',
        'hiroki rinn',     # decoded %20 path
        '  hiroki-rinn  ', # accidental whitespace
        'HIROKI-RINN',     # screaming caps
    ])
    def test_url_variants_all_resolve(self, memdb, variant):
        # Every URL form a user might type for "Hiroki Rinn" must normalize
        # to the same DB-side value. This is the load-bearing property —
        # if it breaks, /voyager/hiroki-rinn 404s.
        sql_db_value = sql_normalize(memdb, 'Hiroki Rinn')
        assert resolver_normalize(variant) == sql_db_value

    def test_slug_matches_db_for_full_set(self, memdb):
        # Insert each name as a row, then look up by its slug → resolver
        # form using the SQL norm expression. Confirms the full pipeline:
        # JS slug → URL → Python resolver → SQL match.
        memdb.execute('CREATE TABLE u (name TEXT)')
        for name in ROUND_TRIP_NAMES:
            memdb.execute('INSERT INTO u (name) VALUES (?)', (name,))
        memdb.commit()

        for name in ROUND_TRIP_NAMES:
            slug = slugify_username(name)
            if not slug:
                continue
            normalized_input = resolver_normalize(slug)
            cur = memdb.execute(
                f'SELECT name FROM u WHERE {SQL_NORM} = ?',
                (normalized_input,),
            )
            rows = cur.fetchall()
            assert any(r[0] == name for r in rows), (
                f'lookup failed: name={name!r} slug={slug!r} '
                f'normalized_input={normalized_input!r} rows={rows!r}'
            )


# ===========================================================================
# 5. Atlas URLs — galaxy names use percent-encoding, NOT hyphen slugging.
# Pinned so any change to galaxy URL strategy has to update this test.
# ===========================================================================

class TestAtlasUrl:
    def test_single_word_galaxy(self):
        from routes.ssr import build_atlas_og
        og = build_atlas_og('Euclid')
        assert og['url'] == '/atlas/Euclid'
        assert 'Euclid' in og['title']

    def test_multi_word_galaxy_percent_encoded(self):
        from routes.ssr import build_atlas_og
        og = build_atlas_og('Hilbert Dimension')
        # Spaces become %20 (quote() with safe='' encodes them).
        # If galaxy URLs ever switch to hyphen slugs, this test fails first.
        assert og['url'] == '/atlas/Hilbert%20Dimension'
        assert 'Hilbert Dimension' in og['title']

    def test_eissentam(self):
        from routes.ssr import build_atlas_og
        og = build_atlas_og('Eissentam')
        assert og['url'] == '/atlas/Eissentam'
        assert og['image'] == '/api/posters/atlas/Eissentam.png'


# ===========================================================================
# 6. SSR / OG title rendering
# ===========================================================================

class TestVoyagerOg:
    def test_hyphen_slug_becomes_titlecase_display(self):
        from routes.ssr import build_voyager_og
        og = build_voyager_og('hiroki-rinn')
        assert og['title'] == "Hiroki Rinn — Voyager's Haven"
        assert "Hiroki Rinn" in og['description']

    def test_image_url_uses_raw_slug(self):
        from routes.ssr import build_voyager_og
        og = build_voyager_og('hiroki-rinn')
        # OG image URL stays on the slug — that's the cache key the poster
        # service renders against. Title-casing the image URL would 404.
        assert og['image'] == '/api/posters/voyager_og/hiroki-rinn.png'

    def test_canonical_url_uses_raw_slug(self):
        from routes.ssr import build_voyager_og
        og = build_voyager_og('hiroki-rinn')
        assert og['url'] == '/voyager/hiroki-rinn'

    def test_single_word_username(self):
        from routes.ssr import build_voyager_og
        og = build_voyager_og('turpitzz')
        assert og['title'] == "Turpitzz — Voyager's Haven"
        assert og['url'] == '/voyager/turpitzz'

    def test_multi_hyphen_slug(self):
        from routes.ssr import build_voyager_og
        og = build_voyager_og('some-name-here')
        assert og['title'] == "Some Name Here — Voyager's Haven"
        assert og['image'] == '/api/posters/voyager_og/some-name-here.png'

    def test_plain_ascii_url_not_double_encoded(self):
        from routes.ssr import build_voyager_og
        og = build_voyager_og('hiroki-rinn')
        # No % in URL — hyphens are unreserved per RFC 3986.
        assert '%' not in og['url']
