/**
 * NMS Economy Types and their associated Trade Commodities
 * Each economy type SELLS specific trade commodities at space stations
 *
 * Tiers determine availability based on system wealth:
 * - Tier 1: HIGH wealth only (base value ~50,000 units)
 * - Tier 2: HIGH wealth, sometimes MEDIUM
 * - Tier 3: MEDIUM and HIGH wealth
 * - Tier 4: MEDIUM and HIGH, sometimes LOW
 * - Tier 5: Always available (base value ~1,000 units)
 *
 * Reference: NMS Wiki - https://nomanssky.fandom.com/wiki/Tradeable
 */

// Trade commodities organized by economy type - what each economy SELLS
export const ECONOMY_TRADE_GOODS = {
  Trading: [
    { id: 'teleport_coordinators', name: 'Teleport Coordinators', tier: 1, description: 'High-end navigation devices' },
    { id: 'ion_sphere', name: 'Ion Sphere', tier: 2, description: 'Charged particle container' },
    { id: 'comet_droplets', name: 'Comet Droplets', tier: 3, description: 'Rare cosmic liquid' },
    { id: 'star_silk', name: 'Star Silk', tier: 4, description: 'Luxurious woven fabric' },
    { id: 'decrypted_user_data', name: 'Decrypted User Data', tier: 5, description: 'Encrypted information packages' },
  ],
  Scientific: [
    { id: 'neural_duct', name: 'Neural Duct', tier: 1, description: 'Bio-electronic conduit' },
    { id: 'organic_piping', name: 'Organic Piping', tier: 2, description: 'Biological tubing system' },
    { id: 'instability_injector', name: 'Instability Injector', tier: 3, description: 'Chaos-inducing device' },
    { id: 'neutron_microscope', name: 'Neutron Microscope', tier: 4, description: 'Subatomic imaging device' },
    { id: 'de_scented_pheromone_bottles', name: 'De-Scented Pheromone Bottles', tier: 5, description: 'Processed biological compounds' },
  ],
  'Advanced Materials': [
    { id: 'superconducting_fibre', name: 'Superconducting Fibre', tier: 1, description: 'Zero-resistance wire' },
    { id: 'five_dimensional_torus', name: 'Five Dimensional Torus', tier: 2, description: 'Exotic geometric construct' },
    { id: 'optical_solvent', name: 'Optical Solvent', tier: 3, description: 'Light-reactive chemical' },
    { id: 'self_repairing_heridium', name: 'Self-Repairing Heridium', tier: 4, description: 'Regenerating mineral' },
    { id: 'nanotube_crate', name: 'Nanotube Crate', tier: 5, description: 'Carbon nanotube container' },
  ],
  Mining: [
    { id: 're_latticed_arc_crystal', name: 'Re-Latticed Arc Crystal', tier: 1, description: 'Restructured crystal' },
    { id: 'polychromatic_zirconium', name: 'Polychromatic Zirconium', tier: 2, description: 'Precious mineral' },
    { id: 'bromide_salt', name: 'Bromide Salt', tier: 3, description: 'Chemical compound' },
    { id: 'unrefined_pyrite_grease', name: 'Unrefined Pyrite Grease', tier: 4, description: 'Industrial lubricant' },
    { id: 'dirt', name: 'Dirt', tier: 5, description: 'Industrial soil compound' },
  ],
  'Power Generation': [
    { id: 'fusion_core', name: 'Fusion Core', tier: 1, description: 'Compact power cell' },
    { id: 'experimental_power_fluid', name: 'Experimental Power Fluid', tier: 2, description: 'Research energy source' },
    { id: 'ohmic_gel', name: 'Ohmic Gel', tier: 3, description: 'Conductive material' },
    { id: 'industrial_grade_battery', name: 'Industrial-Grade Battery', tier: 4, description: 'Heavy-duty power cell' },
    { id: 'spark_canister', name: 'Spark Canister', tier: 5, description: 'Electrical storage unit' },
  ],
  Manufacturing: [
    { id: 'high_capacity_vector_compressor', name: 'High Capacity Vector Compressor', tier: 1, description: 'Advanced compression device' },
    { id: 'holographic_crankshaft', name: 'Holographic Crankshaft', tier: 2, description: 'Light-based mechanical part' },
    { id: 'six_pronged_mesh_decoupler', name: 'Six-Pronged Mesh Decoupler', tier: 3, description: 'Circuit separation device' },
    { id: 'non_stick_piston', name: 'Non-Stick Piston', tier: 4, description: 'Friction-free component' },
    { id: 'enormous_metal_cog', name: 'Enormous Metal Cog', tier: 5, description: 'Large mechanical gear' },
  ],
  Technology: [
    { id: 'quantum_accelerator', name: 'Quantum Accelerator', tier: 1, description: 'High-tech component' },
    { id: 'autonomous_positioning_unit', name: 'Autonomous Positioning Unit', tier: 2, description: 'Navigation component' },
    { id: 'ion_capacitor', name: 'Ion Capacitor', tier: 3, description: 'Energy storage device' },
    { id: 'welding_soap', name: 'Welding Soap', tier: 4, description: 'Metal bonding agent' },
    { id: 'decommissioned_circuit_board', name: 'Decommissioned Circuit Board', tier: 5, description: 'Salvaged electronics' },
  ],
  // Mass Production is often grouped with Manufacturing in game
  'Mass Production': [
    { id: 'high_capacity_vector_compressor', name: 'High Capacity Vector Compressor', tier: 1, description: 'Advanced compression device' },
    { id: 'holographic_crankshaft', name: 'Holographic Crankshaft', tier: 2, description: 'Light-based mechanical part' },
    { id: 'six_pronged_mesh_decoupler', name: 'Six-Pronged Mesh Decoupler', tier: 3, description: 'Circuit separation device' },
    { id: 'non_stick_piston', name: 'Non-Stick Piston', tier: 4, description: 'Friction-free component' },
    { id: 'enormous_metal_cog', name: 'Enormous Metal Cog', tier: 5, description: 'Large mechanical gear' },
  ],
  Pirate: [
    // Pirate systems have their own economy - they sell contraband items
    { id: 'contraband', name: 'Contraband', tier: 3, description: 'Illegal goods' },
    { id: 'stolen_goods', name: 'Stolen Goods', tier: 4, description: 'Pilfered merchandise' },
    { id: 'suspicious_package', name: 'Suspicious Package', tier: 5, description: 'Unknown contents' },
  ],
  None: [
    // Systems with no economy have no trade goods
  ],
  Abandoned: [
    // Abandoned systems have no trade goods
  ],
}

/**
 * Get trade goods for a specific economy type
 * @param {string} economyType - The economy type (Trading, Mining, etc.)
 * @returns {Array} Array of trade goods for that economy
 */
export function getTradeGoodsForEconomy(economyType) {
  return ECONOMY_TRADE_GOODS[economyType] || []
}

/**
 * Get trade goods filtered by economy tier (wealth level)
 * @param {string} economyType - The economy type
 * @param {string} economyLevel - The economy tier (T1=Low, T2=Medium, T3=High)
 * @returns {Array} Array of available trade goods for that wealth level
 */
export function getTradeGoodsForEconomyAndTier(economyType, economyLevel) {
  const allGoods = ECONOMY_TRADE_GOODS[economyType] || []

  // Filter based on wealth level
  // T1 (Low) = only tier 5, sometimes tier 4
  // T2 (Medium) = tiers 3, 4, 5
  // T3 (High) = all tiers 1-5
  // T4 (Pirate) = special pirate goods
  switch(economyLevel) {
    case 'T3': // High wealth - all tiers available
      return allGoods
    case 'T2': // Medium wealth - tiers 3, 4, 5
      return allGoods.filter(g => g.tier >= 3)
    case 'T1': // Low wealth - tiers 4, 5 (sometimes 4)
      return allGoods.filter(g => g.tier >= 4)
    case 'T4': // Pirate - return pirate goods
      return ECONOMY_TRADE_GOODS['Pirate'] || []
    default:
      return allGoods
  }
}

/**
 * Get a flat list of all trade goods
 * @returns {Array} All trade goods across all economies
 */
export function getAllTradeGoods() {
  return Object.values(ECONOMY_TRADE_GOODS).flat()
}

/**
 * Find a trade good by its ID
 * @param {string} id - The trade good ID
 * @returns {Object|null} The trade good object or null
 */
export function getTradeGoodById(id) {
  for (const goods of Object.values(ECONOMY_TRADE_GOODS)) {
    const found = goods.find(g => g.id === id)
    if (found) return found
  }
  return null
}

/**
 * Get trade good names from an array of IDs
 * @param {Array} ids - Array of trade good IDs
 * @returns {Array} Array of trade good names
 */
export function getTradeGoodNames(ids) {
  if (!ids || !Array.isArray(ids)) return []
  return ids.map(id => {
    const good = getTradeGoodById(id)
    return good ? good.name : id
  }).filter(Boolean)
}
