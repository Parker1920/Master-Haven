# Wizard v1 Rebuild — Phase 0 Integration Audit

**Status:** read-only investigation, no code changed.
**Scope:** rebuild of `/wizard` (system submission flow).
**Design contract:** `C:\Master-Haven\wizard-mockup-v1_1.html` (10,299 lines).
**Current production:** `Haven-UI/src/pages/Wizard.jsx` (1,250 lines).
**Working branch:** `claude/priceless-hugle-c16c8b` (worktree, clean).
**Mockup wins** in every conflict with existing UI — but the backend, components, and schema are reused wherever they cover the contract.

---

## TL;DR

- Mockup is **3 screens** (hero / mode-gate / wizard) with **two flows**: 4-step **Easy** and single-page **Advanced** with sticky sidebar + live preview panel. Current wizard is one long form with no stepper.
- Most backend already covers it: glyphs, namegen, region naming, planets, moons, station, profile lookup/claim, submit, save, approve. **Six v1.1 features need new backend or schema**: co-authors, expeditions, drafts, conflict resolution, submitter notes, system-level game version.
- Reusable React components cover ~70 % of the work: `GlyphPicker`, `PlanetEditor`/`MoonEditor`/`CelestialBodyEditor`, `SearchableSelect`, `Modal`, `Card`, `FormField`, `ProfileClaimModal`. Photo-upload + drag-drop pattern already exists in `DiscoverySubmitModal.jsx`.
- **Critical caveat:** the mockup file has corrupted curly quotes throughout the JS (`'…'` → `'…'`) and CSS variables (`var(--sans)` → `var(–sans)`). It will not run as-is. The markup and CSS layout are fine; treat the JS as pseudo-code.
- Recommended phase split: **Phase 1** = 1 schema migration + 4 new endpoints + 1 endpoint extension. **Phase 2** = new `Wizard.jsx` + 8 new components + 2 hooks + reuse of existing pieces. **Phase 3** = local browser walk-through.

---

## 1 · Current Wizard inventory

`Haven-UI/src/pages/Wizard.jsx` (1,250 lines) is a single React component using one giant `<form>`. No stepper, no sidebar, no live preview, no draft save, no co-authors, no edit-mode banner.

### Imports & dependencies

| File | Purpose | Used in mockup? |
|---|---|---|
| `components/Card` | Wrapper | yes |
| `components/Button` | All buttons | yes |
| `components/Modal` | Planet modal, personal-discord, profile-claim | yes (planet, profile, conflict) |
| `components/PlanetEditor` | Planet card + modal | yes (Advanced flow) |
| `components/GlyphPicker` | Visual + text glyph entry | yes |
| `components/SearchableSelect` | Galaxy dropdown | yes (heavily — 18+ instances per planet card) |
| `components/ProfileClaimModal` | First-submission claim flow | yes |
| `utils/AuthContext` | `isAdmin`, `isPartner`, `user` | yes |
| `utils/stationPlacement` (`generateStationPosition`) | Auto orbital position | yes (mockup line 5764) |
| `utils/economyTradeGoods` (`getTradeGoodsForEconomyAndTier`) | Trade-goods filter | yes (mockup line 7360) |
| `data/galaxies` (`GALAXIES`, `REALITIES`) | Galaxy/reality select options | yes |

### State the current Wizard manages

`system` (planets, station, glyphs, region, attributes), `editingPlanet` + modal flags, `discordTags`, `editExplanation`, `submitterDiscordUsername`, `personalDiscordUsername`, `personalDiscordModalOpen`, `pendingPersonalSelection`, `profileModalOpen`, `profileModalStatus`, `profileSuggestions`, `resolvedProfileId`, `pendingSubmitPayload`, `regionInfo`, `regionLoading`, `proposedRegionName`, `regionSubmitting`, `regionSubmitResult`, `showRegionRename`, `isSubmitting`, `originalTag`, `hasStation`.

### API calls the current Wizard makes

| Method | Path | Lines |
|---|---|---|
| GET | `/api/discord_tags` | 79 |
| GET | `/api/systems/:id` (edit load) | 106 |
| GET | `/api/regions/:rx/:ry/:rz?reality=&galaxy=` | 127, 183 |
| GET | `/api/namegen?glyph=&galaxy=` | 134, 429 |
| POST | `/api/regions/:rx/:ry/:rz/submit` | 167 |
| POST | `/api/save_system` (admin direct) | 266 |
| POST | `/api/submit_system` (public → pending) | 290, 304, 323, 328, 350, 381 |
| POST | `/api/profiles/lookup` | 298 |
| POST | `/api/profiles/create` | 364 |

---

## 2 · Mockup inventory (v1.1 design contract)

### Top-level structure

| Region | Element | HTML lines | Purpose |
|---|---|---|---|
| Hero | `section.hero` | 4998–5003 | Always-visible title block |
| Mode gate | `section#mode-gate` | 5009–5046 | Two-card chooser: **First Charting** (Easy) vs **Full Logbook** (Advanced) |
| Wizard | `section#wizard-view` | 5052–6115 | Holds both flows (`.hidden` toggle) |
| Easy flow | `#easy-flow` | 5071–5326 | 4-step linear stepper: Portal → Community → Name & Star → Planets |
| Advanced flow | `#advanced-flow` | 5331–6000 | Sticky left sidebar with 7 anchor sections, content scrolls right; live grade tracker per section |
| Live preview | `aside#preview-panel` | 6005–6110 | "System disk" SVG + stat readouts; sticky right column |
| Floating chrome | top progress bar / mode toolbar / restore-draft banner / edit-mode banner / conflict modal / help panel | 6119–10298 | Outside the wizard container |

### Section inventory (Advanced flow — 7 anchor sections)

| ID | Section | New widgets vs current Wizard |
|---|---|---|
| `#adv-portal` | Portal Address | dup-system banner; auto-detect summary card; mandatory unnamed-region naming gating Submit |
| `#adv-attrs` | System Attributes | **NMS Game Version field** (5676), Spectral Class colored badge, auto-disable Tier/Conflict on None/Abandoned (already in current Wizard) |
| `#adv-planets` | Planets & Moons | **Generate Placeholders** button (5705); inline V9 cards with collapsible attribute panels; modal still available; Exotic Trophy searchable select (already in CelestialBodyEditor) |
| `#adv-station` | Space Station | Has Space Station toggle (already exists); auto orbital position display (already exists); economy+tier-filtered trade goods (already exists) |
| `#adv-discoveries` | Discoveries | **System-scoped discoveries inline** (current flow uses a separate modal); per-entry target selector planet/moon/space; 12-type chip grid; type-specific metadata fields; multi-photo + main-star + reorder; evidence URLs; per-entry Game Version; **★ Submit for record consideration** checkbox; auto-record-beat detection |
| `#adv-identity` | Identity | Discord community + submitter username (already exist); **Co-Authors chip input** (5849); **Expedition select / + Create new** (5860) |
| `#adv-submit` | Submit | Same-name soft warning; **clickable validation summary** (jumps to field); **submitter notes for reviewer**; final summary card; replaced by **post-submit success screen** (rank delta, streak, achievement, card preview, Submit Another) |

### v1.1 features (the additions over v1)

| Feature | Mockup ref | Implementation summary |
|---|---|---|
| **Top progress bar** | `v11UpdateProgress` 9443 | Thin fill bar above content; width = total/max from grade breakdown |
| **Sticky mode toolbar** | 6134, `v11SetFlow` 9492 | Basic/Advanced flow toggle, Required-only checkbox, Edit-mode checkbox, Help button, autosave indicator |
| **Required-only mode** | `body.required-only` ~3751 | CSS hides every `.v11-optional` block |
| **Edit mode** | `#v11-edit-banner` 6160 | Banner: "Editing X · originally by Y · N prior edits · changed fields highlighted" |
| **Diff highlighting** | `.changed` CSS | Amber border/background on edited inputs |
| **Conflict resolution modal** | `#v11-conflict-modal` 10243, `v11ShowConflictModal` 9610 | Per-conflicting-field two-card chooser: "Yours" vs "Existing in Haven (game v6.18)" |
| **Co-authors** | 5852, `v11AddCoauthor` 9738 | Chip input. "Each co-author gets full credit (not partial)" |
| **Expeditions** | 5864, `v11ChangeExpedition` 9769 | Select existing or "+ Create new"; "📍 Active expedition" pill links to `/expedition/{id}`; follow-on submissions auto-tag |
| **Auto-save (drafts)** | `v11AutoSave` 9794 | 1-s debounce + 10-s interval; comment says "would write to localStorage" — **mockup doesn't actually persist**; serialize: glyphs / galaxy / reality / systemFields / planets / discoveries / station / coauthors / expedition / submitterNotes / savedAt |
| **Restore-draft banner** | `#v11-restore-banner` 6150 | "📝 You have a draft from 2 hours ago — restore it?" Restore / Dismiss |
| **Help panel (slide-in)** | `.v11-help-panel` 10263 | Static FAQ on Spectral Class, Wealth Tier, Conflict Level, Planet Attributes, Exotic Trophy, ★ records, region naming |
| **Inline field validation** | `v11AttachInlineValidation` 9858 | Per-field blur/change → `.v11-error` + appended `.v11-field-error` |
| **Validation summary** | `#validation-summary`, `computeValidation` 9320 | Up to 5 issues; **clickable** — jumps & focuses target field |
| **Same-name soft warning** | `v11CheckSameName` 9937 | Non-blocking banner if proposed name matches existing |
| **Existing-system pull** | `v11CheckExistingSystem` 9540 | "⚡ This system is already in Haven" → "Pull existing data" populates form |
| **Region context counter** | 5540 | "You're the 14th submission in this region" |
| **Grade guidance panel** | `v11RenderGradeGuidance` 9681 | Top-4 deltas: "+15 Add Spectral Class" |
| **Why-this-grade tooltip** | `v11AttachGradeTooltip` 9716 | Hover grade letter → per-category score + "S needs 85+" |
| **Wonder/record auto-detect** | `v11CheckRecordBeatLive` 9654 | When a numeric discovery field beats the current Haven record, auto-checks "submit for record" |
| **Inline Haven-record hint** | `v11RenderRecordHint` 9674 | "Current Haven record: 11.8 m on Tessen Prime" |
| **Submitter notes for reviewer** | `#v11-submitter-notes` 5910 | Admin-only review context |
| **Post-submit success screen** | `#v11-post-submit-view` 5956 | Rank delta (#47 → #44), streak count, conditional achievement chip, card preview, Submit Another / View Leaderboard |
| **Submit Another** | `v11SubmitAnother` 10070 | Resets glyphs/system/planets/discoveries/station; **preserves identity** (community, username, expedition, reality, galaxy); returns to portal |
| **Section status icons** | `v11UpdateSectionStatusIcons` 9467 | `○` empty / `◐` partial / `✓` complete on sidebar |
| **beforeunload guard** | 9845 | Browser prompt on dirty state |
| **Keyboard shortcuts** | 9968 | Esc closes modals; Cmd/Ctrl+S saves planet modal; Cmd/Ctrl+Enter submits |
| **Photo upload chrome** | `v11AttachPhotoUploadEvents` 9994 | Drag-over class, paste-to-upload, draggable tile reorder, ★ "set as main" |
| **Profile pre-fill** | `v11PrefillFromProfile` 10101 | reality, galaxy, discord_tag, submitter username, **last game version** from a mocked `profile.lastGameVersion` |

---

## 3 · Reusable Haven components

### Already covers the mockup as-is or with trivial wrap

| Component | Path | Mockup use |
|---|---|---|
| `GlyphPicker` | `src/components/GlyphPicker.jsx` | Whole Portal section. Visual & text modes; calls `/api/validate_glyph` + `/api/decode_glyph`; emits `onDecoded` with x/y/z/region/planet/SS. Already handles phantom/core warnings. |
| `PlanetEditor` + `MoonEditor` | thin wrappers around `CelestialBodyEditor` | Planet/moon cards. Already supports the **full v1.1 attribute set** (has_rings, is_dissonant, is_infested, extreme_weather, water_world, vile_brood, is_bubble, is_floating_islands, is_gas_giant, exotic_trophy). |
| `CelestialBodyEditor` | `src/components/CelestialBodyEditor.jsx` | Already integrates `SearchableSelect` for biome/weather/sentinel/flora/fauna/materials/exotic-trophy. Modal-based attribute panel matches mockup pattern. |
| `SearchableSelect` | `src/components/SearchableSelect.jsx` | Replaces every "react-select-in-production" placeholder. Single + multi support. Dark theme matches. |
| `Modal` | `src/components/Modal.jsx` | Planet modal, conflict modal, profile claim, personal discord, help panel (mockup uses `.v11-help-panel` slide-in but a Modal subclass works fine). |
| `Card` / `Button` / `FormField` / `Toast` | `src/components/*` | All small primitives. |
| `ProfileClaimModal` | `src/components/ProfileClaimModal.jsx` | First-submission `suggestions`/`not_found`/`created` flow already wired. |
| `RealitySelector` | `src/components/RealitySelector.jsx` | Optional — currently used elsewhere (`Systems`); Wizard mockup uses a plain select. |
| `DiscoverySubmitModal` | `src/components/DiscoverySubmitModal.jsx` | **Strong reference** for the inline Discoveries section: stub-system creation, photo upload + drag/drop, location_type planet/moon/space, type-specific metadata, evidence URLs. Should be **refactored into reusable subcomponents** for the wizard's inline discovery list rather than duplicated. |

### Hooks & utilities

| Path | Use |
|---|---|
| `src/hooks/useDebounce.js` | Auto-save debounce + system search debounce |
| `src/hooks/useDateFormat.js` | "Auto-saved 14:02:31", restore-draft "from 2 hours ago" |
| `src/utils/stationPlacement.js` (`generateStationPosition`) | Already used by current Wizard; matches mockup's auto orbital position |
| `src/utils/economyTradeGoods.js` (`getTradeGoodsForEconomyAndTier`) | Already covers mockup line 7360 |
| `src/utils/api.js` | All endpoint helpers; missing: `getDraft`, `saveDraft`, `getExpeditions`, `createExpedition`, `getRecords` (Phase 1 will add) |
| `src/data/galaxies.js` | `GALAXIES` (256 entries) + `REALITIES` |
| `src/data/adjectives.js` | biome/weather/sentinel/flora/fauna/resources/exotic options for SearchableSelect |
| `src/data/discoveryTypes.js` (`TYPE_INFO`) | 12 discovery types with emoji + label — matches mockup `DISCOVERY_TYPES` (line 6930) |
| `src/styles/index.css` | Tokens already in use: `--app-primary` (teal), `--app-accent-2` (violet), `--app-accent-amber`, `--app-card`, `--app-bg`, `--app-accent-3` |

### Components to build new

| Name | Purpose |
|---|---|
| `WizardModeGate.jsx` | Easy vs Advanced two-card chooser |
| `WizardSidebar.jsx` | Sticky left nav with section status icons + grade tracker |
| `WizardPreviewPanel.jsx` | Sticky right "system disk" SVG + live stats |
| `WizardProgressBar.jsx` | Top fill bar driven by completeness score |
| `WizardModeToolbar.jsx` | Flow / Required-only / Edit-mode / Help / autosave indicator |
| `EditModeBanner.jsx` | "Editing X · originally by Y · N prior edits" |
| `ConflictResolutionModal.jsx` | Per-field two-card chooser |
| `CoAuthorChipInput.jsx` | Chip-style multi-add |
| `ExpeditionPicker.jsx` | Select existing or `+ Create new` |
| `RestoreDraftBanner.jsx` | Banner with Restore / Dismiss |
| `HelpPanel.jsx` | Slide-in drawer with FAQ |
| `ValidationSummary.jsx` | Clickable list (jumps & focuses field) |
| `WizardDiscoveryList.jsx` | Inline (extract from `DiscoverySubmitModal`) |
| `SuccessScreen.jsx` | Post-submit rank/streak/achievement + Submit Another |

### Hooks to build new

| Name | Purpose |
|---|---|
| `useWizardDraft` | Debounced localStorage persistence + restore on load |
| `useCompletenessScore` | Live grade computation; mirrors backend `services/completeness.py` |
| `useFormDirty` | Drives `beforeunload` and Submit-Another reset preservation list |

---

## 4 · Backend contract (existing + needed)

### Endpoints that already cover the mockup

| Endpoint | File:line | Mockup use |
|---|---|---|
| `GET /api/glyph_images` | `routes/systems.py:623` | GlyphPicker icon mapping |
| `POST /api/validate_glyph` | `routes/systems.py:633` | GlyphPicker validation |
| `POST /api/decode_glyph` | `routes/systems.py:574` | GlyphPicker decode |
| `GET /api/check_duplicate` | `routes/systems.py:661` | Existing-system detection at 12-glyphs-entered |
| `GET /api/namegen?glyph=&galaxy=` | `routes/systems.py:1307` | Procedural system + region names |
| `GET /api/galaxies` | `routes/systems.py:327` | Galaxy dropdown (256 entries) |
| `GET /api/discord_tags` | `control_room_api.py` | Community dropdown |
| `GET /api/regions/{rx}/{ry}/{rz}?reality=&galaxy=` | `routes/regions.py:395` | Region info card |
| `POST /api/regions/{rx}/{ry}/{rz}/submit` | `routes/regions.py:982` | Mandatory unnamed-region naming |
| `GET /api/systems/:id` | `routes/systems.py` (`getSystemDetail`) | Edit-mode load |
| `GET /api/systems/search?q=&page=` | `routes/systems.py:1053` | (Used by DiscoverySubmitModal — wizard's inline discoveries reuse) |
| `POST /api/systems/stub` | (currently lives in `control_room_api.py`) | Inline stub creation in DiscoverySubmitModal — reusable for wizard |
| `POST /api/save_system` | `control_room_api.py:2338` | Admin direct save (partners with `system_create`) |
| `POST /api/submit_system` | `routes/approvals.py:97` | Public → pending |
| `POST /api/submit_discovery` | `routes/discoveries.py:641` | Public discovery submission (will be looped per inline discovery) |
| `POST /api/profiles/lookup` | `routes/profiles.py:40` | First-submitter fuzzy match |
| `POST /api/profiles/create` | `routes/profiles.py:98` | First-submitter create |
| `POST /api/profiles/use` | `routes/profiles.py:171` | Claim suggested profile |
| `GET /api/profiles/me` | `routes/profiles.py:334` | Profile pre-fill (defaultCivTag, defaultReality, defaultGalaxy) |
| `POST /api/photos` | `control_room_api.py` | Multi-photo upload (already drag/drop in DiscoverySubmitModal) |
| `GET /api/realities/summary` | `routes/systems.py:343` | (optional, current Wizard uses static REALITIES) |

### Endpoints needed (new in Phase 1)

| Endpoint | Purpose | Notes |
|---|---|---|
| `GET /api/wizard/draft` | Read latest draft for the logged-in profile (or by anonymous browser ID) | Profile-keyed for logged-in users; cookie-keyed for anon. **localStorage fallback** is acceptable as-is — server endpoint optional but is the only way to roam between devices |
| `POST /api/wizard/draft` | Upsert draft (debounced from frontend) | Body = full wizard snapshot. Use `services/dispatch.fire_and_forget` for the SQLite write — don't block the user's keystrokes. |
| `DELETE /api/wizard/draft` | Discard draft (after successful submit, or "Dismiss") | |
| `GET /api/expeditions?status=active` | List expeditions for `ExpeditionPicker` | Per-profile or per-community filter |
| `POST /api/expeditions` | Create new expedition | name, start_date, owner_profile_id |
| `GET /api/wizard/records` | Current Haven records keyed by metric | For `v11CheckRecordBeatLive`; e.g. `{ "starship.slots": {value: 48, holder: "Stars", system_name: "Vahnir-3"} }`. Backed by MAX queries; cache 5 min |
| `POST /api/wizard/check-existing` | Pull existing system data for `v11PullExistingData` | Already covered by `GET /api/check_duplicate` + `GET /api/systems/:id`; **wrapper endpoint** for one round-trip is nice-to-have |

### Endpoints needed to be **extended** (not new)

| Endpoint | Change | Why |
|---|---|---|
| `POST /api/submit_system` | Accept `coauthors[]`, `expedition_id`, `submitter_notes`, `game_version`, `conflict_resolution` (per-field "mine"/"theirs" map) | All currently silently dropped |
| `POST /api/save_system` | Same payload extensions as above | Admin/partner direct path |
| `POST /api/approve_system/{id}` | Persist `coauthors`, `expedition_id`, `submitter_notes` from pending row → systems / system_metadata | |
| `GET /api/systems/:id` | Return `coauthors[]`, `expedition_id`, `expedition_name`, `game_version`, `edit_count`, `original_submitter`, `prior_edits[]` | Edit-mode banner + diff baseline |
| `GET /api/wizard/records` | Provide records list | (above) |
| Pending-system list | Optional: include `submitter_notes` flag for reviewer UI | |

---

## 5 · Data model gaps

### Already in schema (reuse, no migration)

- All planet attributes the mockup references — `has_rings`, `is_dissonant`, `is_infested`, `extreme_weather`, `water_world`, `vile_brood`, `is_bubble`, `is_floating_islands`, `is_gas_giant`, `ancient_bones`, `salvageable_scrap`, `storm_crystals`, `gravitino_balls`, `exotic_trophy` (migrations v1.40.0, v1.50.0, v1.62.0).
- Moon attributes (subset): same as planets minus `is_gas_giant` and the four valuable resources.
- `systems.is_phantom`, `is_in_core`, `classification` — already populated by glyph decoder (initial schema).
- `systems.game_mode` — column exists (migration v1.52.0) but is **per-system difficulty**, distinct from the mockup's NMS engine version (e.g. "6.18", "Worlds Part 2").
- `systems.contributors` (JSON) — already used for edit history (migration v1.29.0). Edit count + prior submitter can be derived from this.
- `pending_edit_requests` table — partner-edits-untagged-system flow.
- `approval_audit_log` — full action history per submission, including `source` and `action`.
- User profiles + tier system (migrations v1.55.0–v1.58.0). `default_civ_tag`, `default_reality`, `default_galaxy` already exposed via `GET /api/profiles/me`.

### Missing (Phase 1 schema work)

| Need | Recommended schema | Notes |
|---|---|---|
| **System NMS engine version** | `ALTER TABLE systems ADD COLUMN game_version TEXT;` and same for `pending_systems` | Mockup line 5682. Distinct from `game_mode`. Optional — backfill blank. |
| **Submitter notes for reviewer** | `ALTER TABLE pending_systems ADD COLUMN submitter_notes TEXT;` | Mockup line 5910. Pending-only; not copied to `systems` on approve. |
| **Co-authors** | New table `system_coauthors (system_id, profile_id, username_normalized, credited_at)` with composite PK; mirror in `pending_systems_coauthors` for pending state | Plus serialized `coauthors[]` on `pending_systems.system_data` JSON for round-trip simplicity. Each co-author gets full leaderboard credit (mockup statement) — read-side query updates needed in `analytics.py`. |
| **Expeditions** | New table `expeditions (id, name, slug, owner_profile_id, status, started_at, ended_at, created_at)` | Plus `expedition_id INTEGER REFERENCES expeditions(id)` on `systems` and `pending_systems`. |
| **Drafts (server-side)** | New table `wizard_drafts (profile_id PK or session_token PK, data TEXT, updated_at)` — at most one row per key | localStorage on the client is the primary; this is the device-roaming fallback. **Optional in Phase 1**; can ship behind a flag. |
| **Conflict-resolution choice** | No schema. Submit payload carries a `field_choices: {"planets[0].biome": "mine"}` map; the backend just applies it. | |
| **Records snapshot (optional)** | Not strictly a schema — derived. If hot, can add `wonder_records (metric, value, system_id, holder_profile_id, updated_at)` cached table. | Phase 1 punt: serve via live MAX query. |

### Single migration plan (Phase 1)

Recommend **one** migration `1.75.0` that does:
1. `ALTER TABLE systems ADD COLUMN game_version TEXT;`
2. `ALTER TABLE pending_systems ADD COLUMN game_version TEXT;`
3. `ALTER TABLE pending_systems ADD COLUMN submitter_notes TEXT;`
4. `ALTER TABLE systems ADD COLUMN expedition_id INTEGER;`
5. `ALTER TABLE pending_systems ADD COLUMN expedition_id INTEGER;`
6. `CREATE TABLE expeditions (...)` with composite `(owner_profile_id, status)` index.
7. `CREATE TABLE system_coauthors (...)` with `(system_id, profile_id)` PK + `idx_coauthors_profile`.
8. `CREATE TABLE wizard_drafts (...)` — only if shipping server drafts in Phase 1.

All `IF NOT EXISTS` / column-presence-guarded. Idempotent.

---

## 6 · Risk assessment

### High risk (Parker decision needed)

1. **Drafts: localStorage vs server-side.** localStorage is faster, no backend, no privacy concerns. Server-side roams between devices but couples the wizard to login. Mockup punts ("would write to localStorage"). **Recommend localStorage in Phase 1**; add server endpoint in a follow-up if there's demand.
2. **Co-authors leaderboard semantics.** "Each co-author gets full credit (not partial)" affects `analytics.py` queries — a 3-coauthor system counts as 3 submissions for ranking. Needs to be a deliberate product decision because it can be gamed.
3. **Conflict resolution timing.** Should the conflict modal block at Submit (mockup) or be inline as you fill the form? Mockup blocks at Submit. Backend has to know the existing system's per-field values to compare — easy with `GET /api/systems/:id` but means a second round-trip. Acceptable.
4. **Expeditions ownership.** Per-profile or per-community? Public list or private? Recommend per-profile, listed only for the owner + active community members.
5. **Records / wonder system.** The mockup auto-flags record-beating discoveries. Real implementation needs a `MAX()` query per metric per submit, plus a UI to confirm — and a curated metric list. Could be punted to a follow-up. **Recommend punt**: Phase 1 stubs the endpoint as `[]` so the UI degrades silently.
6. **NMS game version field.** Optional or required? Recommend optional. Default to user's `lastGameVersion` from profile if set, else blank.

### Medium risk

- **Mockup file is corrupted.** Curly quotes everywhere in JS, dash-character variables in CSS. Markup and CSS layout are the design contract; the JS is pseudo-code. Don't copy/paste.
- **The mockup's V9/V10/V11 hook-chain pattern** (every feature monkey-patches the previous function) doesn't translate to React. Each feature is its own component or hook in the rebuild.
- **Live grade computation** runs on every keystroke. The current backend has `services/completeness.py`. We can either call the backend on a debounce or port the scoring logic to a frontend hook. Frontend hook is cheaper.
- **Validation summary "click to focus"** requires scrolling Advanced sections that are hidden via `.section-active` (only one visible at a time). The summary entry must show the right section first, then focus.
- **Mockup has a `body.required-only` mode** that hides every `.v11-optional` block. Cleaner to render conditionally in React than to mirror the CSS visibility hack.
- **Submit Another preservation list.** Documented at mockup line 10070: keep `discord_tag`, `submitter_username`, `expedition`, `reality`, `galaxy`. Reset everything else. Worth wiring as a single helper.

### Low risk

- Photo upload chrome (drag-drop, paste, reorder, ★main): pattern already in `DiscoverySubmitModal`.
- IntersectionObserver for FAB: standard.
- Beforeunload guard: 5 lines of `useEffect`.
- Keyboard shortcuts: standard `useEffect` with key listener.

### What might break in production

- Region-name auto-submission is required for unnamed regions in the current Wizard. Mockup keeps this. **No regression risk** if we keep the gate.
- Auto-tagging of partner submissions (`save_system` lines 2434-2442) — mockup has no UI for this; the partner's tag is enforced server-side regardless. **No regression risk**.
- The `_lastProceduralName` trick (lines 141-145, current Wizard) prevents overwriting a user-edited name when glyphs change. The mockup doesn't carry this state — needs to be re-implemented in the rebuild.

---

## 7 · Phase plan

### Phase 1 — Backend (one PR, one migration)

| Step | Files |
|---|---|
| 1.1 Migration `1.75.0` (schema only) | `Haven-UI/backend/migrations.py` |
| 1.2 New `routes/wizard.py` with `/draft` GET/POST/DELETE, `/records` GET, `/check-existing` GET | new file; wire in `routes/__init__.py` |
| 1.3 New `routes/expeditions.py` with `/expeditions` GET + POST, `/expeditions/{id}` GET | new file |
| 1.4 Extend `routes/approvals.py:97` (`submit_system`) to accept `coauthors[]`, `expedition_id`, `submitter_notes`, `game_version`, `conflict_resolution` | edit |
| 1.5 Extend `control_room_api.py:2338` (`save_system`) to accept the same payload extensions | edit |
| 1.6 Extend `routes/approvals.py:754` (`approve_system`) to copy new fields from pending → live + insert `system_coauthors` rows | edit |
| 1.7 Extend `routes/systems.py:GET /api/systems/:id` to join `expeditions`, `system_coauthors`, expose `edit_count` from `contributors` JSON | edit |
| 1.8 Extend `routes/analytics.py` leaderboards to credit each co-author once per system | edit; **decision flag** to gate (see risks 2) |
| 1.9 New `services/dispatch` calls for non-blocking draft writes in `wizard.py` | follow existing pattern |
| 1.10 `src/utils/api.js` helpers: `getDraft`, `saveDraft`, `deleteDraft`, `getExpeditions`, `createExpedition`, `getRecords`, `checkExisting` | edit |
| 1.11 `routes/auth.py:GET /api/status` version bump to `1.56.0`; root version → `1.60.0` | edit |
| 1.12 Backend tests for new endpoints | `tests/api/test_wizard_*.py` new |

Verification: hit each new endpoint with `curl`, confirm migration runs clean on the local stale DB and on a fresh one.

### Phase 2 — Frontend rebuild

| Step | Files |
|---|---|
| 2.1 Refactor `DiscoverySubmitModal.jsx` to extract `DiscoveryInlineList`, `PhotoUploader`, `LocationTypePicker` so the wizard can reuse them | edit + 3 new |
| 2.2 New layout components | `WizardModeGate`, `WizardSidebar`, `WizardPreviewPanel`, `WizardProgressBar`, `WizardModeToolbar`, `EditModeBanner`, `RestoreDraftBanner`, `HelpPanel`, `ConflictResolutionModal`, `CoAuthorChipInput`, `ExpeditionPicker`, `ValidationSummary`, `WizardDiscoveryList`, `SuccessScreen` |
| 2.3 New hooks | `useWizardDraft`, `useCompletenessScore`, `useFormDirty` |
| 2.4 Replace `pages/Wizard.jsx` | full rewrite around the new components |
| 2.5 Wire route on `App.jsx` | unchanged path `/wizard` |
| 2.6 Update `tests/e2e/wizard-glyph.spec.ts` and `tests/e2e/wizard-enter.spec.ts` to match the new DOM | edit |
| 2.7 Bump `Haven-UI/package.json` version | edit |
| 2.8 Update `CLAUDE.md` Current Versions table + new changelog entry | edit |

### Phase 3 — Local dev verification

| Step | What |
|---|---|
| 3.1 Start backend: `python Haven-UI/backend/control_room_api.py` (port 8005) | Confirm migration log line, no exceptions |
| 3.2 Start frontend: `cd Haven-UI && npm run dev` (port 5173) | Confirm Vite starts |
| 3.3 Walk through Easy flow | new system, glyphs, community, name, planets, submit |
| 3.4 Walk through Advanced flow | every section, draft auto-save indicator, restore-draft, validation summary click-to-focus, conflict modal triggered, post-submit success screen |
| 3.5 Edit-mode walk-through | `?edit=<id>` on a known system, verify diff highlights, conflict modal |
| 3.6 Mobile walk-through (Chrome DevTools 375 px) | sticky bars don't overlap, FAB toggles, sidebar collapses |
| 3.7 Take screenshots | save under `audit/work/wizard-v1-screens/` for review |
| 3.8 Stage diff for Parker | no commits yet |

---

## 8 · Open questions for Parker

1. Drafts: **localStorage only**, or also server endpoint?
2. Co-authors: **full credit each** (mockup line 5852) — confirm this is the intended product decision? Affects leaderboard ranking.
3. Wonder/records auto-detect: **ship in Phase 1** or **stub for follow-up**?
4. Easy flow vs Advanced: should the Easy flow (4-step) be a complete alternative, or does it always escalate to Advanced before submit? Mockup keeps both as standalone end-to-end paths.
5. Expedition visibility: **per-profile only**, or **per-community visible**?
6. Edit history: surface up to N prior edits in the banner, or just the count?
7. Help-panel content: copy-edit own pass, or use the mockup text as-is (lines 10263–10298)?
8. Do we want the rebuild to live behind a feature flag (`/wizard?v=2`) for gradual rollout, or replace the existing route outright?

---

**STOP.** No code changes made. Awaiting Phase 0 sign-off.
