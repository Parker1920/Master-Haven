// Planetary adjective autocomplete lists and resource catalogs for system/planet editors.
// Used by PlanetEditor, MoonEditor, CelestialBodyEditor, and PendingApprovals for dropdown options.
//
// SINGLE SOURCE OF TRUTH: the actual lists now live in ./optionCatalog.json, which is ALSO
// read by the backend (backend/option_catalog.py → GET /api/option-catalog) so the web
// wizard, the backend, and the Keeper Discord bot all use one identical set of options.
// This module just re-exports the adjective/resource arrays under their historical names so
// existing imports keep working. To add/change a value, edit optionCatalog.json.
//
// Adjective values match NMS in-game display strings. Arrays are sorted alphabetically
// (exotic_trophies is kept in its curated order).
import catalog from './optionCatalog.json'

export const biomeAdjectives = catalog.biomes
export const weatherAdjectives = catalog.weather
export const sentinelAdjectives = catalog.sentinel
export const floraAdjectives = catalog.flora
export const faunaAdjectives = catalog.fauna
export const resourcesList = catalog.resources
export const exoticTrophyList = catalog.exotic_trophies

/** Convert a string array to react-select option format: [{ value, label }]. */
export const toSelectOptions = (arr) => arr.map(value => ({ value, label: value }))
