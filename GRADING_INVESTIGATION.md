# Completeness Grading — Current State

**Updated:** 2026-06-23 · Supersedes the 2026-06-19 investigation (which predated both the S+ tier *and* this X rework — it is no longer accurate).

The authoritative reference is the **root `CLAUDE.md`** ("Current Versions" rows for Master Haven 1.80.0 / Backend 1.79.0 / Haven-UI 1.70.0, and the changelog). This file is just a quick map.

## Score (0–100) — `services/completeness.py::calculate_completeness_score`

Six weighted categories, summed and clamped to 100:

| Category | Max | Fields |
|----------|----:|--------|
| System Core | 35 | star_type, economy_type, economy_level, conflict_level, dominant_lifeform |
| System Extra | 10 | glyph_code, stellar_classification (`description` dropped 2026-06-19) |
| Planet Coverage | 10 | ≥1 planet |
| Planet Environment | 25 | per planet: biome, weather, sentinel |
| Planet Life | 15 | per planet: fauna, flora, resources (biome-aware) |
| Space Station | 5 | station present (+3), trade goods (+2) — exempt when Abandoned or `no_space_station` |

Score → letter via `constants.score_to_grade`: **S** 85–100 · **A** 65–84 · **B** 40–64 · **C** 0–39.

## X — the "fully charted" tier (`check_splus_eligible`)

X is **not a score band** — it's a checklist on top of an S score (≥85), cached in `systems.is_fully_charted`, rendered as **X** in **Platinum `#E5E4E2`**. (Internally still named `splus`/`is_fully_charted`/`grade_splus` — only the displayed letter/color is "X".) A system is X when, in addition to scoring S:

1. ≥1 planet.
2. A discovery on **every** planet AND **every** moon.
3. Wonder notes on **at least one** planet or moon (any of the 5 `WONDER_FIELDS`).
4. A **documented base** — base lat/long on any planet/moon, **or** a `type_slug='base'` discovery, **or** legacy free-text `base_location`.
5. A recorded space station — unless Abandoned / `no_space_station`.

## Where it lives

- **Score/X logic:** `services/completeness.py` (single source of truth).
- **Thresholds + `GRADE_SPLUS='X'`:** `constants.py`.
- **Stored:** `systems.is_complete` (0–100) + `systems.is_fully_charted` (0/1). Letter is derived on read.
- **Recompute points:** approve_system + batch, save_system, csv_import, approve_discovery; re-score migrations (1.90/1.91/1.96/**1.97**).
- **Base coords:** `planets`/`moons` `base_latitude`/`base_longitude` (+ moon `base_location`), written by `db.set_base_fields`, collected via `LatLngInput` in `CelestialBodyEditor.jsx`.
- **Colors (single source):** `src/utils/gradeColors.js` → mirrored in `src/styles/index.css` (`.grade-*`/`.bar-*`) and the inline `TIER_COLORS` in `public/VH-System-View.html` / `public/VH-Cartographer.html`.
- **Wizard live mirror:** `src/hooks/useCompletenessScore.js`.
