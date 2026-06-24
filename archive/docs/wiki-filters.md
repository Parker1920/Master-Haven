# Haven Archive — Wiki Filters & Categories Spec

Status: **proposal for review** (2026-06-23). Investigation across every wiki section to define the
custom filters/categories each one gets. Two sources feed it:

1. **Atlas-synced sections** (Star Systems, Planets, Items/Resources) reuse Haven's **already-authoritative,
   curated vocabularies** — `adjectives.js`, `resource_catalog.py`, `constants.py`, `galaxies.js`. Per the
   project rule, these curated lists are the gold standard; we do **not** re-author them.
2. **Authored sections** (Ships, Multi-tools, Fauna, Flora, Civs, Bases…) use **current NMS taxonomy**
   (Voyagers / Worlds Part II era, 2025–26), sourced from the official NMS wiki.

---

## A. Recommended section set

The investigation strongly recommends **splitting some sections and adding a few** so each catalog's facets
actually fit its data (forcing fauna+flora+minerals into one "creature" table = ~80% null columns per row).

> **DECISIONS LOCKED (2026-06-23):** adopted the **Fauna → Fauna + Flora + Minerals** split and added
> **Freighters** + **Exocraft**. **Companions** and **Frigates** deferred. The four new namespaces
> (`flora`, `mineral`, `freighter`, `exocraft`) are now live in the registry (backend + frontend).
> Mineral richness uses the canonical **C/B/A/S** scale (D-2 resolved).

**Core (already in v1):** Civilizations · Travelers · Star Systems\* · Planets\* · Lore & Story · Guides ·
Game Mechanics · Items & Resources\* · Events · Bases & Builds · Starships · Multi-Tools · Fauna
( \* = atlas-synced / partly-synced )

**Recommended NEW / SPLIT sections:**

| New section | Why | Priority |
|---|---|---|
| **Flora** (split from Fauna) | You named it explicitly; disjoint attributes (form/root/nutrient vs genus/temperament). | High |
| **Minerals** (split from Fauna) | First-class in-game discovery; richness/deposit facets don't fit fauna. | High |
| **Companions** (split from Fauna) | Tamed-pet *instances* with trait %s + genes — different cardinality (1 species → many companions). | Medium |
| **Freighters** | Own class/design taxonomy (Sentinel/Dreadnought vs Venator/Resurgent), turrets, capital. | Medium |
| **Exocraft** | 6 named vehicles (Roamer/Nomad/Pilgrim/Colossus/Minotaur/Nautilon); no class system. | Low |
| **Frigates** | Fleet ships (Support/Exploration/Combat/Trade/Industrial); could be a sub-tab of Freighters. | Low |

Corvette (Voyagers 6.0) is a **"Built" type within Starships**, not its own section. Moons stay a **facet of
Planets** (`is_moon`), not a section.

---

## B. Shared cross-cutting enums (define once, reuse everywhere)

These recur across many sections — single-source them.

- **Galaxy** — Haven's 256-galaxy list (`galaxies.js`). Show the ~12 named + "Multi-galaxy" + "Other" expander.
- **Reality** — `Normal` · `Permadeath` (Haven).
- **Platform** — `PC (Steam)` · `PC (GOG)` · `PC (MS Store)` · `PlayStation` · `Xbox` · `Switch` · `Mac` · `Cross-platform`.
- **Game mode** — `Normal` · `Creative` · `Relaxed` · `Survival` · `Permadeath` · `Custom` (Haven).
- **Class** — `C` · `B` · `A` · `S` (+ `X`/Platinum = Haven's "fully charted" tier, systems only).
- **Star type** — `Yellow` · `Red` · `Green` · `Blue` · `Purple` (Haven curated).
- **Biome (canonical buckets)** — `Lush` · `Barren` · `Dead` · `Scorched` · `Frozen` · `Toxic` · `Irradiated`
  · `Marsh` · `Volcanic` · `Exotic` · `Mega Exotic` · `Gas Giant` · `Waterworld`. **NB:** distinct from
  Haven's 222 descriptive `biomeAdjectives` (those are flavor planet-descriptions; these ~13 are the
  filterable categories that Fauna/Flora/Minerals/Bases share).
- **Rarity** — discoveries: `Common` · `Uncommon` · `Rare`. Minerals/items (Haven scale): `Common` · `Rare` · `Extraordinary`.
- **Update era** — `Genesis (2016)` · `NEXT (2018)` · `Beyond/Synthesis (2019–20)` · `Origins–Frontiers (2020–21)`
  · `Sentinel–Endurance (2021–22)` · `Fractal–Echoes (2023)` · `Worlds I–II (2024–25)` · `Voyagers/Modern (2025–26)`.
- **Civ tag** — dynamic from the `civilizations` table (cross-reference facet).

---

## C. Atlas-synced sections (reuse Haven's curated vocab verbatim)

### Star Systems
Reuse the exact dimensions the Systems-tab / Cartographer already filter on (`_build_advanced_filter_clauses`):

| Facet | Control | Values (source) |
|---|---|---|
| Star type | multi | Yellow/Red/Green/Blue/Purple (curated) |
| Economy type | single | Trading, Mining, Manufacturing, Technology, Scientific, Power Generation, Mass Production, Advanced Materials, Pirate, None, Abandoned (curated) |
| Economy tier | multi | T1/T2/T3/T4/None (curated) |
| Conflict level | multi | Low/Medium/High/Pirate/None (curated) |
| Dominant lifeform | single | Gek/Vy'keen/Korvax/None/Abandoned (curated) |
| Stellar classification | single | DB-distinct free-text (e.g. G2pf, M7) |
| Completeness grade | multi | C/B/A/S + **X** (X = `is_fully_charted` flag, not a score band) |
| Galaxy / Reality | single | curated |
| Has moons | boolean | — |
| Planet count | range | — |
| Resources present | multi | canonical 107-resource list (any planet/moon match) |
| Community (civ tag) | single | dynamic |
| No space station | boolean | system flag |

### Planets (+ Moons as a facet)
| Facet | Control | Values (source) |
|---|---|---|
| Biome | single | Haven `biomeAdjectives` (222 curated) — surface the ~13 buckets as the primary filter, full list as secondary |
| Weather | single | `weatherAdjectives` (~368 curated) |
| Sentinels | single | `sentinelAdjectives` (43 curated) |
| Flora / Fauna level | single | `floraAdjectives` (53) / `faunaAdjectives` (54) curated |
| Resources / materials | multi | canonical 107 list |
| Is moon | boolean | — |
| **Special-attribute flags (18 booleans)** | boolean each | `has_rings, is_dissonant, is_infested, extreme_weather, water_world, vile_brood, ancient_bones, salvageable_scrap, storm_crystals, gravitino_balls, is_bubble, is_floating_islands, swarm_debris, trash_debris, high_sentinel_activity, aggressive_sentinel_activity` (+ `is_gas_giant`, planet-only) |
| Exotic trophy | single | `exoticTrophyList` (11 curated) |
| Has base / base coords | boolean | — |

### Items & Resources  ⚠️ wire to `resource_catalog.py`, don't re-curate
| Facet | Control | Values |
|---|---|---|
| Canonical resource | single | `CANONICAL_RESOURCES` (107, grouped: Raw Materials, Special Harvestables, Cave & Underground, Hazardous Flora, Underwater, Exotic Glitch, Sentinel Drops, Misc) |
| Category | single | Element/Raw · Product · Component · Technology · Tradeable · Trade Commodity · Curiosity · Consumable · Crafted · Artifact |
| Element division | multi | Catalyst · Earth · Exotic · Flora · Fuel · Metal · Special · Stellar |
| Rarity / value tier | single | Common · Rare · Extraordinary (align with `gradeColors.js RICHNESS_COLORS`) |
| Where sourced | multi | Mining · Cave · Underwater · Asteroid · Flora · Fauna · Atmosphere · Storm-only · Refined · Trade Terminal · NPC/Mission · Derelict · Sentinel drop · Stellar |
| Star-type gating | multi | Yellow/Red/Green/Blue/Purple/N-A (stellar metals) |
| Class | single | C/B/A/S/X/N-A |

---

## D. Authored sections (NMS taxonomy)

### Starships
| Facet | Control | Values |
|---|---|---|
| **Archetype** | single | Shuttle · Fighter · Hauler · Explorer · Exotic · Solar · Sentinel Interceptor · Living Ship · **Corvette (Built)** |
| **Class** | single | C · B · A · S |
| Type bonus | single | Damage / Hyperdrive / Shield+Inventory / Balanced / All-round / Pulse-drive / Combat |
| Procedural vs unique | single | Procedural · Unique (expedition/quicksilver) · Built (Corvette) |
| Where found | multi | Station/trade outpost · Crashed · Derelict · NPC gift · Expedition · Quicksilver · Dissonant planet (Interceptor) · Corvette Workshop |
| Sub-style (cosmetic) | multi | Royal · Squid/Ball · asymmetric · organic (community taxonomy) |
| Supercharged slots | single/range | 1(C)/2(B)/3(A)/4(S) |
| Slot ranges | range | general / tech |

**Primary filters:** Archetype · Class · Procedural/Unique/Built · Where found.

### Multi-Tools
| Facet | Control | Values |
|---|---|---|
| **Type** | single | Pistol · Rifle · Experimental · Alien · Royal · Sentinel · Atlantid · Voltaic Staff |
| **Class** | single | C · B · A · S |
| Type bonus | single | Mining · Damage · Scanning |
| Handedness | single | One-handed · Two-handed |
| Where found | multi | Cabinet · Minor Settlement · Station merchant · NPC gift · Monolith · Crashed ship · Sentinel Pillar (Royal) · Korvax monolith (Atlantid) · Autophage terminal (Voltaic Staff) · Expedition/Quicksilver |
| Special / built | multi | Royal · Sentinel · Atlantid · Voltaic Staff (Built) |
| Slots | range | base roll / max-by-class (C30/B40/A50/S60) |

**Primary filters:** Type · Class · Type bonus · Where found.

### Fauna
| Facet | Control | Values |
|---|---|---|
| **Genus** | multi | Ground: Bos, Felidae, Felihex, Osteofelidae, Procavya, Tetraceris, Reococcyx, Ungulatis, Hexungulatis, Anastomus, Mogara, Theroma, Rangifae, Tyranocae, Talpidae, Lok, Conokinis, Bosoptera, Floradae, Shaihuluda, Arthropodae · Flying: Agnelis, Cycromys, Rhopalocera, Oxyacta, Protocaeli · Aquatic: Ictaloris, Prionace, Chrysaora, Bosaquatica, Crustacea, Hippocampus, Mobula, Krakenidae, Procavaquatica · Robotic: Mechanoceris, Structurae, Spiralis, Prionterrae, Prototerrae · Exotic: Anomalous (show common names too — genus is internal since Origins 2020) |
| **Ecosystem** | multi | Ground · Flying · Underwater · Underground |
| **Temperament** | single | Predator · Player Predator · Prey · Passive (4 roles; ~20 visor words as flavor) |
| Diet | single | Herbivore · Carnivore · Omnivore · Pica (mineral-eater); aquatic Predatory/Non-predatory |
| **Rarity** | single | Common · Uncommon · Rare (megafauna & Anomalous always Rare) |
| Gender/sex | multi | Male, Female, Exotic, Indeterminate, Asymmetric, Non-uniform, Symmetric, Rational, Vectorised, Prime, Alpha, Radical, Asymptotic, Orthogonal, None (UK "Vectorised"; "Exotic" here = a gender, NOT rarity) |
| Height | range | Tiny <0.5 · Small 0.5–1.5 · Medium 1.5–3 · Large 3–5 · Mega >5 (m) |
| Activity | single | Always Active · Diurnal · Nocturnal · Mostly Diurnal · Mostly Nocturnal |
| Biome | multi | shared biome buckets |
| Rideable / Predator / Megafauna / Bone-yielder | boolean | — |

**Primary filters:** Genus · Ecosystem · Temperament · Rarity.

### Flora
| Facet | Control | Values |
|---|---|---|
| **Biome** | multi | shared buckets (Dead/Gas Giant yield no plant resource) |
| **Resource yielded** | multi | Carbon (default) · Star Bulb · Cactus Flesh · Solanium · Frost Crystal · Fungal Mould · Gamma Root · Faecium/Mordite · Kelp Sac · Marrow Bulb · + cultivated (NipNip, Fireberry, Frostwort…) |
| Form / category | multi | Ground cover · Shrub · Tree · Cactus · Coral · Fern · Flower · Mushroom · Seaweed · Spire · Weird/Exotic |
| **Hazardous** | boolean | Tentacle / Trap / Gas / Whirl / Underground-toxic types |
| Rarity | single | Common · Uncommon · Rare |
| Harvestable | boolean | (some need Haz-Mat Gauntlet) |

**Primary filters:** Biome · Resource yielded · Hazardous · Rarity.
*Note: Worlds Part II stripped species names from hazardous/rich plants — tolerate flora rows with no name.*

### Minerals
| Facet | Control | Values |
|---|---|---|
| **Resource yielded** | multi | star-metals (Copper/Cadmium/Emeril/Indium/Quartzite + Activated) · Cobalt · Mag. Ferrite · Salt · Silver · Sodium · biome minerals (Paraffinium/Pyrite/Phosphorus/Dioxite/Ammonia/Uranium/Rusted Metal/Mordite/Basalt/Cryst. Helium/Lithium/Gold) |
| **Richness** | single | Haven scale: Common · Rare · Extraordinary *(game-canonical is C/B/A/S — see decision D-2)* |
| Deposit type | multi | Resource Deposit · Deep-Level (Hotspot) · Buried Formation · Crystalline |
| Biome | multi | shared buckets |
| Star-type gating | multi | Yellow/Red/Green/Blue/Purple |

**Primary filters:** Resource · Richness · Biome · Deposit type.

### Companions
| Facet | Control | Values |
|---|---|---|
| Genus / anatomy | multi | (fauna genera) |
| Traits | range (0–100%) | Helpful↔Playful · Aggressive↔Gentle · Devoted↔Independent |
| Rideable / Pollinator / Predator | boolean | — |
| Size / color genes | range/multi | — |
| Mutation flags | boolean | Egg-sequenced · Overdosed (>100%) · Gene-split (150%) |
| Biome (origin) | multi | shared buckets |

**Primary filters:** Genus · Traits · Rideable.

### Civilizations
| Facet | Control | Values |
|---|---|---|
| **Type** | single | Hub Region · Federation · Empire · Alliance · Collective · Guild · Company · RP Nation · Order/Faith · Coalition · Independent |
| **Status** | single | Active · Dormant · Reforming · Merged · Archived/Defunct |
| Galaxy | multi | shared |
| Platform | multi | shared |
| Size band | single | Solo · Tiny (2–10) · Small (11–50) · Medium (51–200) · Large (201–1k) · Massive (1k+) |
| **Primary focus** | multi | Cartography · Documentation · PvP · Roleplay · Building · Trade · Lore · Casual · Photography · Racing · Diplomacy · Events |
| Founding era | single | shared update-era |
| Has claimed territory | boolean | — |
| Federation membership | multi | dynamic (links to civs) |

**Primary filters:** Type · Status · Primary focus · Galaxy.

### Bases & Builds
| Facet | Control | Values |
|---|---|---|
| **Build type / purpose** | multi | Home · Farm · Racetrack · Gallery/Museum · Settlement · Freighter Base · Capital · Puzzle · Art · Logic/Tech · Trading Post · Monument · Landing Hub · Roleplay · Underwater · Cave |
| **Planet biome** | multi | shared buckets + N/A (freighter/space) |
| Location type | single | Planet · Moon · Underwater · Cave · Freighter · Space |
| **Glyph available** | boolean | (can others teleport in) |
| Platform / Game mode / Galaxy | multi | shared |
| Size band | single | Micro · Small · Medium · Large · Massive · Limit-busting |
| Featured tech | multi | Power/Wiring · Logic · Auto-doors · Hydroponics · Teleporter · Landing Pads · Trade Terminal · Glitch-building · Terrain edits · Byte Beat · POI integration |

**Primary filters:** Build type · Biome · Glyph available · Platform.

### Travelers
| Facet | Control | Values |
|---|---|---|
| **Primary role** | single | Cartographer · Diplomat · Builder · Hunter · Trader · Lore-keeper · Historian · Leader · Photographer · Racer · Event Organizer · Tool-maker · Recruiter |
| Civilization(s) | multi | dynamic |
| **Status** | single | Active · Occasional · Retired · Memorial |
| Specialty | multi | (layered tags) |
| Title/rank | multi | Founder · Leader · Co-Leader · Officer · Sub-Admin · Diplomat · Veteran · Member · Honorary |
| Platform / Era | multi/single | shared |

**Primary filters:** Primary role · Civilization · Status · Specialty.

### Events
| Facet | Control | Values |
|---|---|---|
| **Type** | single | Expedition (official) · Festival · Community · War · Gathering · Census · Competition · Exhibition · Race · Charity · Anniversary |
| Official expedition | multi | Pioneers · Beachhead · Cartographers · Emergence · Exobiology · The Blighted · Leviathan · Polestar · Utopia · Singularity · Voyagers · Omega · Adrift · Liquidators · Aquarius · The Cursed · Titan · Relics · Corvette · Breach · Remnant · The Swarm (when Type=Expedition) |
| **Status** | single | Upcoming · Active · Past · Cancelled · Postponed |
| Host civ | multi | dynamic + Hello Games + Cross-community |
| Recurrence | single | One-off · Annual · Seasonal · Monthly · Weekly |
| Scale | single | Civ-internal · Inter-civ · Galaxy-wide · Universe-wide |

**Primary filters:** Type · Status · Host civ · Recurrence. *(Note: Haven already has an Events system with `event_id`; reconcile the wiki Events section with it rather than duplicating.)*

### Lore & Story
| Facet | Control | Values |
|---|---|---|
| **Topic** | multi | Races: Gek · Vy'keen · Korvax · Travellers · Sentinels · Autophage · First Spawn · Forgotten Colonies — Cosmic: Atlas · Telamon · -null- · The Anomaly · Boundary Failures — Arcs: Awakenings · Atlas Path · Artemis Arc · The Purge · Autophage questline — Characters: Artemis · Apollo · Nada · Polo — Concepts: Atlas Interfaces · Glyphs & Portals · Convergence |
| **Canonicity** | single | In-game canon · Dev intent/ARG · Community interpretation · Headcanon/fan-fiction · Disputed |
| Lifeform scope | multi | Gek · Vy'keen · Korvax · Traveller · Autophage · Sentinel · Mixed |
| Source type | multi | Story-mission · Lore stone/monolith · Plaque/Ruins · Korvax Encyclopedia · Boundary log · NPC dialogue · ARG · Community-authored |
| Story-arc stage | single | Pre-Awakening · Awakenings · Atlas Path · Artemis Path · The Purge · Post-game · Standalone |

**Primary filters:** Topic · Canonicity · Lifeform scope · Source type. *("Purgers" is not canonical — use "The Purge".)*

### Guides
| Facet | Control | Values |
|---|---|---|
| **Topic area** | multi | Exploration · Economy · Combat · Base-building · Multi-tool · Starship · Farming · Fishing · Settlements · Expeditions · Freighters · Photography · Crafting · Navigation · Companions · Living Ships · Modding · Multiplayer · Getting Started |
| **Difficulty** | single | Beginner · Intermediate · Advanced · Expert/Min-max · Reference |
| **Patch relevance** | single | Current · Recent · Legacy (pre-Worlds) · Outdated · Version-agnostic |
| Game mode | multi | shared |
| Format | single | Walkthrough · Reference · Tips · Video · Checklist · Tutorial · Tier list |

**Primary filters:** Topic area · Difficulty · Patch relevance · Game mode.

### Game Mechanics
| Facet | Control | Values |
|---|---|---|
| **Category** | single | Economy · Combat · Crafting · Exploration · Base-building · Multiplayer · Technology · Progression · Survival · Navigation · Inventory · Reputation · Customization · Automation |
| Subsystem | multi | Exosuit · Multi-tool · Starship · Freighter · Exocraft · Companion · Settlement · Base · Refiner · Trade · Nexus/Anomaly · Portals · Sentinels · Weather |
| Player activity | multi | Mining · Scanning · Fighting · Trading · Building · Farming · Fishing · Cooking · Refining · Piloting · Diplomacy · Exploring |
| Introduced in | single | shared update-era |
| Status | single | Current · Reworked · Deprecated · Legacy |

**Primary filters:** Category · Subsystem · Player activity · Introduced in.

---

## E. Corrections & cautions (from the research)

- **D-1 Genus is internal-only** since Origins (2020). Players see common names ("Cats", "Diplos"). A genus
  filter should display common names with genus as the key.
- **D-2 Mineral richness scale — RESOLVED:** use the game-canonical **C/B/A/S class** scale for the Minerals
  section (Parker, 2026-06-23). This diverges from Haven's discovery `deposit_richness`
  (Common/Rare/Extraordinary) — the wiki Minerals section uses C/B/A/S; the discovery-tab mineral type keeps
  its existing scale unless we later unify them.
- **"Exotic"** is a biome AND a fauna gender — never a rarity tier.
- Gender stored UK spelling **Vectorised**.
- Flora post-Worlds-II can have **no species name** (hazardous/rich plants) — model must allow it.
- **Items & Resources** must consume `resource_catalog.py` (aliases, `NON_MATERIAL_TOKENS`, element divisions),
  not a parallel hand-list.
- **Events** already exists in Haven (`event_id` on submissions) — reconcile, don't duplicate.

---

## F. Data-model implication (for the build phase)

Filters need **structured facets**, but today an `article` only has free-form `infobox_json`. Proposed approach:

1. A **per-namespace facet schema** (this doc, encoded as config): each section declares its facets
   (key, label, control type single/multi/range/boolean, value source: enum | shared-enum | atlas-field | dynamic).
2. Store an article's facet values in a structured, indexable place — either typed columns per namespace or a
   normalized `article_facet(article_id, key, value)` table (one row per value; supports multi-select + indexed
   filtering). The `article_facet` approach scales to all sections without per-section migrations.
3. The create/edit form renders facet controls from the schema (dropdowns/checkboxes/ranges) instead of the
   generic infobox rows; Browse renders a filter rail from the same schema and queries `article_facet`.
4. Atlas-synced sections (System/Planet/Item) filter against the **live Haven data** (later phase), reusing
   Haven's `_build_advanced_filter_clauses` rather than `article_facet`.

Shared enums (galaxy, platform, game-mode, class, star-type, biome, rarity, era) live in one module imported by
every section's schema.
