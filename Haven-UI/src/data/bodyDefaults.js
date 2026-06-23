// Shared shell shapes for a new planet / moon. Single source of truth so a body
// created by the count-dropdown generator (Wizard) is byte-identical to one added
// manually via the "Add Moon" modal (PlanetEditor) — they must not drift, or the
// two creation paths produce differently-shaped records.

export const PLANET_DEFAULTS = {
  name: '', biome: '', weather: '', sentinel: 'None',
  fauna: 'N/A', flora: 'N/A', materials: '', base_location: '',
  base_latitude: '', base_longitude: '',
  photo: '', notes: '', moons: [],
  has_rings: 0, is_dissonant: 0, is_infested: 0,
  extreme_weather: 0, water_world: 0, vile_brood: 0,
  ancient_bones: 0, salvageable_scrap: 0, storm_crystals: 0, gravitino_balls: 0,
  is_gas_giant: 0, is_bubble: 0, is_floating_islands: 0, exotic_trophy: '',
  swarm_debris: 0, trash_debris: 0, high_sentinel_activity: 0, aggressive_sentinel_activity: 0,
  // Wonders Page Notes — free-form narrative from NMS Log Exploration Guide.
  // Backend migration 1.76.0 adds matching columns on planets + moons.
  estimated_age: '', core_element: '', lore_notes: '',
  root_structure: '', nutrient_source: '',
}

// Moons carry the same shared attributes as planets minus planet-only ones
// (a moon is never a gas giant). base_location / base_latitude / base_longitude
// exist on the moons table as of migration 1.97.0.
export const MOON_DEFAULTS = {
  name: '', biome: '', weather: '', sentinel: 'None',
  fauna: 'N/A', flora: 'N/A', materials: '', notes: '', photo: null,
  base_location: '', base_latitude: '', base_longitude: '',
  has_rings: 0, is_dissonant: 0, is_infested: 0,
  extreme_weather: 0, water_world: 0, vile_brood: 0, exotic_trophy: '',
  ancient_bones: 0, salvageable_scrap: 0, storm_crystals: 0, gravitino_balls: 0,
  is_bubble: 0, is_floating_islands: 0,
  swarm_debris: 0, trash_debris: 0, high_sentinel_activity: 0, aggressive_sentinel_activity: 0,
  estimated_age: '', core_element: '', lore_notes: '',
  root_structure: '', nutrient_source: '',
}
