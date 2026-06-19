# Completeness Grading Investigation

**Date:** 2026-06-19
**Author:** Claude (read-only research — no source files changed)
**For:** Parker — review before any implementation
**Scope:** Why the score caps below 100%, how grading works, and what it takes to add an **S+** grade.

---

## TL;DR

1. **The backend can already reach 100%.** In the local dev DB, **1,060 systems are stored at exactly 100** — so the scoring math is *not* the wall. The categories sum cleanly to 100.

2. **The real ceiling for a normal submission is 97 (backend) / ~95 (wizard preview),** and it comes from **two specific things**:
   - The **`description`** field. It's worth 3.33 pts inside "System Extra." Every one of the 1,060 perfect systems has a description; **the maximum score for any system with a *blank* description is exactly 97.** Most extractor and many manual uploads never get a description, so they top out at 95–97.
   - The **wizard's live-preview hook** (`useCompletenessScore.js`) is a *separate, drifted reimplementation* of the backend formula. It invents a **"Planet Detail" category (10 pts) that requires `base_location`** (a player base) — which the backend has **no equivalent for** — and splits planet weights differently. A fully-scanned, base-less system maxes the **preview at ~95%**, even though the backend will store it higher. This is almost certainly the "96%" you see while building a system.

3. **`is_complete` stores the 0–100 *score*; the letter grade is never stored — it's derived on every read.** So S+ is mostly a *threshold + color* change. No schema migration is needed for the grade itself (a re-score backfill *is* needed if we change the scoring formula).

4. **S+ should mean "100% — every scored field filled."** To make that genuinely reachable from in-game data (not gated on a human-typed note), we should **drop `description` from scoring** (or stop letting it gate the top) **and reconcile the wizard hook to the backend formula.**

5. **Adding S+ touches ~20 files** because the grade→color mapping is duplicated in **three drifted palettes** plus the map HTML and posters. Full list in [§9](#9-every-file-that-must-change-for-s).

---

## 1. How scoring works today (backend — the authoritative path)

Source: [`Haven-UI/backend/services/completeness.py`](Haven-UI/backend/services/completeness.py) → `calculate_completeness_score()`.

It reads the `systems` row, its `planets`, and its `space_stations` row, scores **6 categories**, sums them, clamps to 100, and converts to a letter via `score_to_grade()`.

| # | Category | Max pts | Fields scored | Formula | Notes |
|---|----------|--------:|---------------|---------|-------|
| 1 | **System Core** | **35** | `star_type`, `economy_type`, `economy_level`, `conflict_level`, `dominant_lifeform` (5 fields) | `round(filled / 5 × 35)` | Abandoned systems (`economy_type` ∈ {None, Abandoned}) get auto-credit for economy/conflict. `dominant_lifeform = "None"` counts as filled. |
| 2 | **System Extra** | **10** | `glyph_code`, `stellar_classification`, **`description`** (3 fields) | `round(filled / 3 × 10)` | **`description` is the culprit field — see §3.** |
| 3 | **Planet Coverage** | **10** | has ≥1 planet | `10` if any planet else `0` | Binary. |
| 4 | **Planet Environment** | **25** | per planet: `biome`, `weather`(or `weather_text`), `sentinel`(or `sentinels_text`) | `round( avg_over_planets(min(env_filled/3, 1)) × 25 )` | Averaged across all planets. |
| 5 | **Planet Life** | **15** | per planet: `fauna`, `flora`, `resources` (`materials` or the 3 `*_resource` cols) | `round( avg_over_planets(life_filled / life_applicable) × 15 )` | **Biome-aware:** dead biomes (`NO_LIFE_BIOMES`) skip fauna/flora from the denominator; resources are always applicable. |
| 6 | **Space Station** | **5** | station present (+3), `trade_goods` recorded (+2) | up to `5` | Abandoned systems get the full 5 (no station expected). |
|   | **TOTAL** | **100** | | `min(sum, 100)` | Each category is **independently `round()`-ed, then summed.** |

`NO_LIFE_BIOMES` (constants.py): `Dead, Lifeless, Life-Incompatible, Airless, Low Atmosphere, Gas Giant, Empty`.

**The weights add up to exactly 100.** There is no missing or unreachable category at the backend level — a system with every field filled scores 100. (Verified: 1,060 systems do.)

---

## 2. Grade thresholds today

Source: [`Haven-UI/backend/constants.py:63`](Haven-UI/backend/constants.py) and `score_to_grade()`:

```python
GRADE_THRESHOLDS = {'S': (85, 100), 'A': (65, 84), 'B': (40, 64), 'C': (0, 39)}

def score_to_grade(score):
    if score >= 85: return 'S'
    elif score >= 65: return 'A'
    elif score >= 40: return 'B'
    return 'C'
```

| Grade | Score band | Color (official `gradeColors.js`) |
|-------|-----------|-----------------------------------|
| **S** | 85–100 | Gold `#ffd700` |
| **A** | 65–84 | Purple `#c084fc` |
| **B** | 40–64 | Blue `#60a5fa` |
| **C** | 0–39 | Green `#4ade80` |

---

## 3. The exact math: why you can't get past ~96%

### 3a. Backend ceiling = **97** without a description, **100** with one

The only category that can't be maxed by a "fully scanned" system is **System Extra (10 pts / 3 fields)**, because of **`description`** — a free-text human note. With description blank:

```
System Extra = round(2/3 × 10) = round(6.667) = 7      ← loses 3.33 pts
```

So the best a blank-description system can do is:

```
35 (Core) + 7 (Extra) + 10 (Coverage) + 25 (Env) + 15 (Life) + 5 (Station) = 97
```

**Database evidence (local dev DB, 13,641 systems — mechanism only, not production counts):**

| Query | Result |
|-------|--------|
| Systems stored at exactly `is_complete = 100` | **1,060** |
| …of those, how many have a non-blank `description` | **1,060 / 1,060 (100%)** |
| **Max `is_complete` among systems with a BLANK description** | **97** (6,187 such systems) |
| Max score by source | manual → 100 (1,057 perfect), haven_extractor → 100 (only 3 perfect), keeper_bot → 38 |

This is conclusive: **`description` is the single field standing between a complete system and 100.** The extractor essentially never writes a description (it only stashes the procgen name there for *renamed* systems — changelog 1.50.12), so virtually every extractor system caps at 97. The few perfect systems are manual uploads where someone typed a description (or edited it in on the SystemDetail page afterward).

**Where 95/96 come from:** 97 is the clean "everything but description" cap. The **per-planet averaging** in Env (25) and Life (15) then shaves a point or two whenever a multi-planet system has even one planet missing one field:

> Example: 5 planets, one missing a single env field → Env avg = (4×1.0 + 0.667)/5 = 0.933 → `round(0.933 × 25) = 23` → total **95**.

So a "fully uploaded except the description, with a hair of planet imperfection" system lands at exactly the **95–96** you're seeing.

### 3b. Wizard live-preview ceiling = **~95%** (a *different*, drifted formula)

Source: [`Haven-UI/src/hooks/useCompletenessScore.js`](Haven-UI/src/hooks/useCompletenessScore.js) — a **client-side approximation** the wizard uses for the live grade pill/progress bar ([`WizardProgressBar`](Haven-UI/src/components/wizard/WizardProgressBar.jsx), [`WizardPreviewPanel`](Haven-UI/src/components/wizard/WizardPreviewPanel.jsx), [`WizardAdvancedPreview`](Haven-UI/src/components/wizard/WizardAdvancedPreview.jsx)). It does **not** match the backend:

| Category | Backend | Wizard hook | Drift |
|----------|--------:|------------:|-------|
| System Core | 35 | 35 | same |
| System Extra | 10 | 10 | same (incl. `description`) |
| Planet Coverage | 10 | 10 | same |
| Planet **Environment** | **25** | **15** | ⚠️ different weight |
| Planet **Life** | 15 (fauna+flora+**resources**) | 15 (fauna+flora only) | ⚠️ resources moved out |
| Planet **Detail** | **— (does not exist)** | **10** (`materials` + **`base_location`**) | ⚠️ **phantom category** |
| Space Station | 5 (present+goods) | 5 (needs `name`+`race`) | ⚠️ stricter |

The killer is **Planet Detail (10 pts)**, which requires **`base_location`** on every planet — i.e. a player-built base. Almost no system has a base on every planet, so this category is effectively stuck at ~5/10. A perfectly-scanned, base-less, description-filled system scores in the **preview**:

```
35 + 10 + 10 + 15 + 15 + 5 (Detail: materials only) + 5 = 95
```

…and **92** if the description is also blank. The preview literally *cannot* reach 100 unless every planet has a documented base. **This is the number you watch while creating a system, and it's why it feels like "you can't get above 96%."** The backend, meanwhile, will store that same system at 95–97.

> **Two bugs, one symptom.** Even if we fix the backend `description` issue, the wizard preview will keep showing a lower, wrong number until the hook is reconciled to the backend formula.

---

## 4. How the score is stored & the grade derived

- **Column:** `systems.is_complete` — an **INTEGER 0–100 score** (originally a boolean; repurposed to a percentage in migration **v1.34.0/v1.35.0**, comment at [control_room_api.py:1168](Haven-UI/backend/control_room_api.py)).
- **The letter grade is NEVER stored.** It is computed on read every time, via `score_to_grade()` or an inline `>=85/65/40` ladder.
- **Where the score is (re)computed and written** — `update_completeness_score(cursor, system_id)` (writes `is_complete`):
  - `approve_system` → [routes/approvals.py:1970](Haven-UI/backend/routes/approvals.py)
  - batch approve → [routes/approvals.py:2964](Haven-UI/backend/routes/approvals.py)
  - admin direct save (`save_system`) → [control_room_api.py:2511, 3063](Haven-UI/backend/control_room_api.py)
  - CSV import → [routes/csv_import.py:676](Haven-UI/backend/routes/csv_import.py)
  - stub creation, etc.
- **Where the grade is derived on read:** `score_to_grade()` at completeness.py:240, systems.py:1727 & :2077, analytics.py:1966; inline ladders at systems.py:1375-1382 and across the frontend.

**Implication for S+:** because the grade is derived, adding S+ is *fundamentally a read-time threshold change plus colors* — **no migration to store a grade.** A migration is only needed if we change the **scoring formula** (to re-score the existing `is_complete` values), which prior formula changes already did (v1.35.0, v1.40.0 both re-scored every system).

---

## 5. The three drifted color palettes (cleanup opportunity)

The grade→color mapping is **not** single-sourced today. There are **three** different palettes live in the frontend:

| Source | S | A | B | C |
|--------|---|---|---|---|
| **Official** — `gradeColors.js`, `index.css`, `SystemThumb` poster, map HTML | Gold `#ffd700` | Purple `#c084fc` | Blue `#60a5fa` | Green `#4ade80` |
| `GRADE_STYLE` — [SystemDetail.jsx:50](Haven-UI/src/pages/SystemDetail.jsx), [SystemsList.jsx:37](Haven-UI/src/components/SystemsList.jsx), [ComparePanel.jsx:20](Haven-UI/src/components/ComparePanel.jsx) | amber var | **Emerald `#34d399`** | Blue `#60a5fa` | white-translucent |
| `GRADE_BG` — [StatTile.jsx:71](Haven-UI/src/components/shared/StatTile.jsx) | amber `#ffb44c` | Emerald `#34d399` | Blue | white-translucent |

So the same grade letter renders gold-on-purple in one place and amber-on-emerald in another. **Adding S+ is the natural moment to collapse these onto `gradeColors.js`.** Not strictly required, but recommended.

---

## 6. What "S+" should mean

> **S+ = 100% complete: every scored field is filled.** A "fully uploaded" system — full system core, full planet data on every body, station + trade goods (or legitimately abandoned).

For S+ to be *earnable and meaningful*, two things must be true:

1. **100 must be reachable from in-game data alone** — not gated on a human-typed `description`. Today a flawless extractor upload caps at 97 forever because it has no description. That makes S+ unreachable for the entire extractor path. → **Drop `description` from scoring (recommended) — see §8.**
2. **The wizard preview must agree with the backend** so a user can actually drive the bar to 100 and watch it land on S+. → **Reconcile `useCompletenessScore.js` — see §8.**

---

## 7. Proposed grade thresholds

S+ carves the perfect top off the existing S band. **Minimal disruption: only the ~1,060 already-perfect systems get promoted S→S+; A/B/C are untouched.**

| Grade | Proposed band | Meaning |
|-------|--------------|---------|
| **S+** | **`score == 100`** | Fully uploaded — every scored field filled |
| **S** | 85–99 | Excellent, near-complete |
| **A** | 65–84 | Good (unchanged) |
| **B** | 40–64 | Partial (unchanged) |
| **C** | 0–39 | Sparse (unchanged) |

```python
# proposed score_to_grade
if score >= 100: return 'S+'
elif score >= 85: return 'S'
elif score >= 65: return 'A'
elif score >= 40: return 'B'
return 'C'
```

**Alternative (if exact-100 feels brittle):** `S+ = 98–100`, `S = 85–97`. This tolerates a stray rounding point on big multi-planet systems. **My recommendation is exact `== 100`** *after* we drop `description` and reconcile the wizard — at that point a genuinely-complete system hits a clean 100, and "S+ = literally perfect" is the clearest story. Flagging the 98+ option only as a fallback if we'd rather not touch the formula.

---

## 8. Making 100% genuinely reachable (the fix behind complaint #1)

Two coordinated changes. Both are *recommendations* for Parker to approve — not yet implemented.

### Fix A — stop `description` from gating the top (backend formula)
**Option A1 (recommended):** Remove `description` from the **System Extra** category. System Extra becomes `glyph_code` + `stellar_classification` (10 pts, 5 each — both always present on a real upload). A fully-scanned system then reaches **100 from extractable data alone**, and S+ becomes reachable for *both* manual and extractor paths.
**Option A2:** Keep `description` but make it a non-scored bonus / move its weight elsewhere.
**Option A3 (not recommended):** Keep it and require the wizard to collect it — but the extractor can't write descriptions, so extractor systems could never be S+. Rejected for that reason.
> Either A1 or A2 requires a **re-score backfill migration** (loop all systems → `update_completeness_score`), exactly like v1.35.0/v1.40.0. No schema change.

### Fix B — reconcile the wizard preview to the backend
Rewrite [`useCompletenessScore.js`](Haven-UI/src/hooks/useCompletenessScore.js) to mirror `services/completeness.py` exactly: **6 categories, same weights** (Env **25** not 15, fold resources back into **Life**, **delete the phantom "Planet Detail"/`base_location` category**, match the station rule). After this, the live grade pill equals the stored score and the user can actually watch it reach 100 → S+.
> `base_location` can still be collected as useful data — it just shouldn't be a *completeness* requirement, since the backend never treated it as one.

---

## 9. Every file that must change for S+

Grade letters and colors are duplicated widely. Grouped by what each needs. (Inventory cross-checked by a dedicated search pass.)

### ⚠️ CSS naming gotcha
`.grade-s+` is **not a valid CSS selector** (`+` is the adjacent-sibling combinator). Any code that builds a class with `grade-${grade.toLowerCase()}` will emit the broken `grade-s+`. **S+ needs a sanitized class token** like `grade-splus` / `bar-splus`, and the components must map the grade string `"S+"` → `"splus"`. Object-key lookups like `GRADE_STYLE["S+"]` are fine; only CSS-class string-building needs the sanitizer.

### A. Threshold logic (score → grade) — add the `>= 100 → 'S+'` rung
| File | Location | What |
|------|----------|------|
| `backend/constants.py` | `score_to_grade()` + `GRADE_THRESHOLDS` | Add `S+` rung + dict entry |
| `backend/routes/systems.py` | inline ladder ~1375-1382 | Add `S+` branch |
| `src/hooks/useCompletenessScore.js` | ~147-150 | Add `S+` branch (also rewritten per Fix B) |
| `src/components/shared/StatTile.jsx` | `gradeFromScore()` ~78-84 | Add `S+` branch (shared by posters + wizard) |
| `src/posters/OGSystemCard.jsx` | `gradeFromScore()` ~78-84 | Duplicate of StatTile — add `S+` |
| `public/VH-System-View.html` | `getGradeStyle()` ~529 | `|| TIER_COLORS.C` fallback — S+ silently becomes C unless added |

### B. SQL grade-distribution buckets — add a 5th `grade_s_plus` (or fold S+ into S for aggregates)
| File | Location |
|------|----------|
| `backend/routes/systems.py` | galaxy summary `CASE WHEN` ~867-870 |
| `backend/routes/analytics.py` | community grade dist `CASE WHEN` ~1956-1959 |
| `backend/routes/regions.py` | `grade_s` counters at ~236 and ~462 (hard-coded `>= 85`) |

### C. Color maps — add an `S+` entry (these have **no fallback** → S+ renders unstyled if missed)
| File | Map | Current S+ behavior |
|------|-----|---------------------|
| `src/utils/gradeColors.js` | `TIER_COLORS` | returns `null` (safe-ish) — **add S+ here first; it's the intended single source** |
| `src/styles/index.css` | `.grade-s/.bar-s` rules ~320-328 | add `.grade-splus` / `.bar-splus` |
| `src/pages/SystemDetail.jsx` | `GRADE_STYLE` ~50 | `undefined` → unstyled |
| `src/components/SystemsList.jsx` | `GRADE_OVERLAY_STYLE` ~37 | `undefined` → unstyled |
| `src/components/ComparePanel.jsx` | `GRADE_STYLE` ~20 | `undefined` → unstyled |
| `src/components/shared/StatTile.jsx` | `GRADE_BG` ~71 | `undefined` → unstyled |
| `src/posters/SystemThumb.jsx` | `GRADE_BG` ~69 | `undefined` → unstyled |
| `public/VH-System-View.html` | inline `TIER_COLORS` ~523 | add S+ |
| `public/VH-Cartographer.html` | `#cf-grade` filter pills ~1218-1221 | add an `S+` filter chip |

### D. Fallback-to-C spots (S+ silently degrades to C until colors added)
`src/components/wizard/WizardProgressBar.jsx` (`|| TIER_COLORS.C`), `WizardPreviewPanel.jsx` (`TIER_COLORS[grade]`), `WizardAdvancedPreview.jsx` (`|| GRADE_BG.C`).

### E. Grade-distribution display (needs a 5th segment, or S+ counts within S)
`src/components/GalaxyGrid.jsx` (the `bar-s/a/b/c` stripe ~138-221), plus any region/community grade bars consuming `grade_s_plus`.

### F. Formula + re-score (only if doing Fix A/B)
`backend/services/completeness.py` (drop/!gate `description`), a new **re-score backfill migration** in `backend/migrations.py`, and `src/hooks/useCompletenessScore.js` (Fix B rewrite).

> **Rough count: ~20 files.** The duplication exists because the three palettes (§5) and the map HTML never got single-sourced. Collapsing them onto `gradeColors.js` during this work would shrink future grade changes to one file.

---

## 10. Proposed S+ color

Palette context: **S=Gold, A=Purple, B=Blue, C=Green** (a flat, NMS-inspired scale). S+ must sit visually **"above gold"** and not collide with B-blue or C-green.

| Option | Color | Hex | Rationale | Watch-outs |
|--------|-------|-----|-----------|------------|
| **1 — Diamond Cyan** *(recommended solid)* | bright cyan | `#22d3ee` (text `#06363d`) | Reads as a flawless gem one tier above gold; works everywhere a single color is needed (CSS text, map pills). | Sits between B-blue and C-green on the wheel — pick a **saturated** cyan so it's not muddy at pill size. |
| **2 — Iridescent / Holo** *(premium flourish)* | gradient gold→cyan→violet | e.g. `linear-gradient(100deg,#ffd700,#22d3ee,#c084fc)` | Most "beyond S" / NMS S-class shimmer; feels genuinely special. | Doesn't work for a plain `color:` text rule (needs `background-clip:text`); more CSS per location. Pair with a solid fallback (#22d3ee) for single-color contexts. |
| **3 — Platinum / White** *(safest)* | platinum | `#e5e7eb` (text `#1f2937`) | "Platinum above gold"; the **only light tier** → impossible to confuse with S/A/B/C. | Light text can read like un-graded default text in some contexts; best as a pill **background**. |

**My recommendation:** **Option 1 (Diamond Cyan `#22d3ee`)** as the canonical solid added to `TIER_COLORS`, with **Option 2 (iridescent)** used *only* for the badge/pill background where you want the "wow." That gives one reliable color for the 20 locations plus a special-cased shimmer on the hero pill. But the palette is yours — this is a pick-one decision for you.

---

## 11. Edge cases

| Case | Today's behavior | S+ implication |
|------|------------------|----------------|
| **Abandoned systems** (`economy_type` ∈ {None, Abandoned}) | Auto-credit for economy/conflict (Core) **and** full 5 pts for station. **Can already reach 100/S** if everything else (incl. description today) is filled. | Will correctly earn **S+** once `description` no longer gates 100. Good — an abandoned system *is* "fully documented" without a station. |
| **Stub systems** (`is_stub=1`, created to anchor a discovery) | Minimal data → low score → grade C. | Never S+; no special handling needed. (Optional: hide the grade pill for stubs in the UI — already badged "Stub.") |
| **Dead-biome planets** (`NO_LIFE_BIOMES`) | Fauna/flora dropped from the Life denominator; **resources still required.** A dead planet with resources scores full Life. | A system of all-dead planets **can** still hit 100/S+ — correct, since there's no life data to miss. |
| **`description` (free text)** | Worth 3.33 pts; blank caps the system at 97. | **Central decision (§8):** to make S+ reachable for extractor uploads, drop it from scoring (A1) or de-gate it (A2). |
| **`base_location` (wizard preview only)** | Drags the wizard's live grade down via the phantom "Planet Detail" category; **backend ignores it.** | Remove from the preview formula (Fix B). Keep collecting the data, just don't score it. |
| **Per-planet rounding** | Each category `round()`s independently; multi-planet systems lose a point when one planet is slightly short → 95/96. | If S+ is exact `==100`, a single short planet correctly blocks S+. This is the intended meaning ("every field filled"). |
| **Existing stored scores after a formula change** | `is_complete` is cached. | Fix A/B require a **re-score backfill migration** so old rows reflect the new formula (precedent: v1.35.0, v1.40.0). |
| **Grade-distribution aggregates** (galaxy/region/community bars) | 4 buckets S/A/B/C. | Add a 5th `grade_s_plus` bucket **or** count S+ within S for these rollups — pick one and apply consistently across the 3 SQL spots + GalaxyGrid. |

---

## 12. Open questions for Parker

1. **`description` in scoring** — drop it (A1, recommended) so a fully-*scanned* system = 100, or keep it as a bonus (A2)? This is the lever that unblocks 100%/S+ for extractor uploads.
2. **S+ threshold** — exact `== 100` (recommended, after the formula fix) or `>= 98` (rounding slack)?
3. **S+ color** — Diamond Cyan `#22d3ee` (recommended), iridescent gradient, or platinum `#e5e7eb`?
4. **Reconcile the wizard preview** to the backend formula in the same pass? (Strongly recommended — otherwise the live grade keeps showing a wrong, lower number.)
5. **Single-source the colors** — collapse the three drifted palettes (§5) onto `gradeColors.js` while we're in here?
6. **Distribution rollups** — give S+ its own bucket in the galaxy/region/community bars, or fold it into S for aggregates?

---

*Research complete. No source files were modified. Awaiting direction on §12 before any implementation.*
