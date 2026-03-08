# Comment Rewrite — Frontend Report
**Date:** 2026-03-08

## Files Completed
| File | Status | Approx comments added | Notes |
|------|--------|----------------------|-------|
| **Utilities & Data** | | | |
| api.js | Complete | ~15 | Docstrings for getPhotoUrl/getThumbnailUrl, section headers, fetch helper docs |
| usePersonalColor.js | Complete | ~5 | Context hook purpose, default color note |
| AuthContext.jsx | Complete | ~12 | Session flow, role hierarchy, feature flags note |
| InactivityContext.jsx | Complete | ~5 | Timer logic, visibility API usage |
| adjectiveColors.js | Complete | ~8 | Tier system explanation, color mapping rationale |
| galaxies.js | Already documented | 0 | Static data file with clear structure |
| adjectives.js | Already documented | 0 | Static data file |
| discoveryTypes.js | Already documented | 0 | Already had inline docs |
| tagColors.js | Complete | ~6 | API cache pattern, fallback chain |
| warRoomApi.js | Already documented | 0 | Already had endpoint docs |
| useWarRoom.js | Already documented | 0 | Already had hook docs |
| warRoomUtils.js | Already documented | 0 | Already had utility docs |
| constants.js | Already documented | 0 | Simple constant exports |
| **Components A-L** | | | |
| DiscordTagBadge.jsx | Complete | ~4 | Hardcoded fallback note, personal color branch |
| DiscoveryCard.jsx | Complete | ~6 | Card layout, thumbnail usage, type badge |
| DiscoveryDetailModal.jsx | Complete | ~8 | Modal sections, full-size photo loading |
| DiscoverySubmitModal.jsx | Complete | ~10 | Type-specific fields, stub system creation, TYPE_FIELDS sync note |
| FeaturedDiscoveries.jsx | Complete | ~5 | Carousel/grid layout, view tracking |
| TypeShowcase.jsx | Complete | ~4 | Type-filtered discovery grid |
| DateRangePicker.jsx | Complete | ~3 | Preset ranges, custom date handling |
| GalaxyGrid.jsx | Complete | ~8 | Grid/list toggle, grade distribution bar, filter integration |
| GradeBreakdownBar.jsx | Complete | ~3 | S/A/B/C color segments |
| LeaderboardTable.jsx | Complete | ~5 | Tag color API usage, rank formatting |
| LoadingSpinner.jsx | Already documented | 0 | Simple presentational component |
| **Components M-Z + App** | | | |
| MoonEditor.jsx | Complete | ~6 | Field groups, special features, photo upload |
| Navbar.jsx | Complete | ~5 | Desktop + mobile nav sections, role-based links |
| PlanetEditor.jsx | Complete | ~8 | Biome/weather/resource fields, special features, exotic trophy |
| RegionDetail.jsx | Complete | ~5 | System cards within region, thumbnail grid |
| SearchableSelect.jsx | Complete | ~3 | Filterable dropdown, keyboard nav |
| Sparkline.jsx | Complete | ~2 | Mini inline chart |
| StatCard.jsx | Already documented | 0 | Simple presentational component |
| SubmissionChart.jsx | Complete | ~3 | Recharts area chart wrapper |
| SystemCard.jsx | Complete | ~5 | Grade badge, star type dot, tag badge |
| SystemsList.jsx | Complete | ~6 | Infinite scroll, filter integration, tag color API |
| ThemeProvider.jsx | Complete | ~4 | CSS variable injection from /api/settings |
| App.jsx | Complete | ~8 | Lazy route definitions, guard components, provider nesting |
| main.jsx | Complete | ~2 | React root mount, provider wrapping |
| RequireAdmin.jsx | Complete | ~3 | Route guard pattern doc |
| RequireSuperAdmin.jsx | Complete | ~2 | Super admin only guard |
| RequireFeature.jsx | Complete | ~3 | Feature flag guard, frontend-only enforcement note |
| CommunityPieChart.jsx | Complete | ~3 | Recharts pie with custom tooltip |
| **Pages A-L** | | | |
| AdminDashboard.jsx | Complete | ~8 | Tab layout, stat cards, role-scoped sections |
| Analytics.jsx | Complete | ~10 | Manual/extractor tabs, source breakdown bar, COALESCE note |
| CommunityDetail.jsx | Complete | ~6 | Drill-down from CommunityStats, region expansion |
| CommunityStats.jsx | Complete | ~8 | Public page, overview cards, activity timeline |
| Dashboard.jsx | Complete | ~5 | Landing page, recent systems, quick stats |
| Discoveries.jsx | Complete | ~6 | Type routing, featured section, browse grid |
| Events.jsx | Complete | ~7 | Event CRUD, leaderboard tabs, discovery event types |
| GalaxyBrowser.jsx | Complete | ~5 | Galaxy selection, system count, grade summary |
| Login.jsx | Complete | ~4 | Auth form, role-based redirect |
| ManagePartners.jsx | Complete | ~6 | Partner CRUD, feature toggles, API key management |
| ManageSubAdmins.jsx | Complete | ~5 | Delegated permissions, feature checkboxes |
| ExtractorUsers.jsx | Complete | ~5 | Extractor user management, rate limits, suspension |
| PartnerAnalytics.jsx | Complete | ~6 | Source filter dropdown, partner-scoped stats |
| DataRestrictions.jsx | Complete | ~5 | Per-system visibility, field group redaction |
| **Pages M-Z** | | | |
| PendingApprovals.jsx | Complete | ~12 | Systems/discoveries tabs, review modal, knownTagColors TODO |
| RegionBrowser.jsx | Complete | ~5 | Named/unnamed regions, pending region names |
| Settings.jsx | Complete | ~4 | Theme colors, site config |
| SpaceStationBrowser.jsx | Complete | ~4 | Trade goods grid, economy info |
| SystemDetail.jsx | Complete | ~10 | Full system view, planet/moon cards, star color conditional |
| SystemForm.jsx | Complete | ~8 | Create/edit form, glyph input, planet/moon editors |
| WarRoom.jsx | Complete | ~8 | Conflict dashboard, territory claims, peace treaties |
| WarRoomEnrollment.jsx | Complete | ~5 | Civilization enrollment flow |
| WarRoomConflict.jsx | Complete | ~6 | Conflict detail, event timeline, media |
| WarRoomNews.jsx | Complete | ~5 | News articles, correspondent system |
| Wizard.jsx | Complete | ~10 | Multi-step system creation, NOTE: INTENTIONAL DESIGN for planet defaults |

## Notable Design Decisions Documented

### # NOTE: INTENTIONAL DESIGN comments added:

1. **Wizard planet defaults** (Wizard.jsx)
   - Default planet object initializes all special feature fields to 0/empty for consistent DB inserts

2. **PendingApprovals knownTagColors** (PendingApprovals.jsx)
   - TODO: Wire to /api/discord_tag_colors instead of hardcoded color map

3. **RequireFeature frontend-only enforcement** (RequireFeature.jsx)
   - Feature flags (BACKUP_RESTORE, SYSTEM_CREATE, etc.) are UI hints only — backend does not enforce them

4. **TYPE_FIELDS sync requirement** (DiscoverySubmitModal.jsx)
   - TYPE_FIELDS must stay in sync with discoveryTypes.js TYPE_INFO definitions

5. **ThemeProvider CSS variable pattern** (ThemeProvider.jsx)
   - API-driven theme with multiple key format fallbacks for backward compatibility

6. **App.jsx lazy loading** (App.jsx)
   - All pages except Dashboard are lazy-loaded for bundle splitting

## Files Already Well-Documented
- galaxies.js, adjectives.js, discoveryTypes.js, constants.js
- warRoomApi.js, useWarRoom.js, warRoomUtils.js
- LoadingSpinner.jsx, StatCard.jsx

## Verified
- All files compile: Yes (`npm run build` passed for all 5 agent groups)
- Errors: None
