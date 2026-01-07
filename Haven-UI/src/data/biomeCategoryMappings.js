// Biome Category Mappings - Maps all NMS biome adjectives to their parent categories
// Based on No Man's Sky Wiki data and game files

// The 17 parent biome categories (matching extractor BIOME_TYPES)
export const BIOME_CATEGORIES = [
  'Lush',
  'Toxic',
  'Scorched',
  'Radioactive',
  'Frozen',
  'Barren',
  'Dead',
  'Exotic',
  'Marsh',
  'Volcanic',
  'Waterworld',
  'Gas Giant',
  'Infested',
  'Mega Exotic',
  'Chromatic Red',
  'Chromatic Green',
  'Chromatic Blue'
];

// Comprehensive mapping of all biome adjectives to parent categories
// Sources: NMS Wiki, game files (NMS_UPDATE3_ENGLISH.MBIN)
export const BIOME_ADJECTIVE_MAP = {
  // ============================================
  // LUSH BIOME (Earth-like, paradise worlds)
  // ============================================
  'Lush': 'Lush',
  'Paradise': 'Lush',
  'Temperate': 'Lush',
  'Tropical': 'Lush',
  'Verdant': 'Lush',
  'Viridescent': 'Lush',
  'Humid': 'Lush',
  'Overgrown': 'Lush',
  'Flourishing': 'Lush',
  'Grassy': 'Lush',
  'Bountiful': 'Lush',
  'Rainy': 'Lush',

  // ============================================
  // FROZEN BIOME (Ice/snow worlds)
  // ============================================
  'Frozen': 'Frozen',
  'Icy': 'Frozen',
  'Arctic': 'Frozen',
  'Glacial': 'Frozen',
  'Icebound': 'Frozen',
  'Frostbound': 'Frozen',
  'Freezing': 'Frozen',
  'Sub-Zero': 'Frozen',
  'Sub-zero': 'Frozen',
  'Hiemal': 'Frozen',
  'Hyperborean': 'Frozen',

  // ============================================
  // TOXIC BIOME (Poisonous worlds)
  // ============================================
  'Toxic': 'Toxic',
  'Poisonous': 'Toxic',
  'Noxious': 'Toxic',
  'Corrosive': 'Toxic',
  'Acidic': 'Toxic',
  'Caustic': 'Toxic',
  'Acrid': 'Toxic',
  'Blighted': 'Toxic',
  'Miasmatic': 'Toxic',
  'Rotting': 'Toxic',

  // ============================================
  // SCORCHED BIOME (Hot/desert worlds)
  // ============================================
  'Scorched': 'Scorched',
  'Hot': 'Scorched',
  'Fiery': 'Scorched',
  'Boiling': 'Scorched',
  'Torrid': 'Scorched',
  'Incandescent': 'Scorched',
  'Scalding': 'Scorched',
  'Charred': 'Scorched',
  'Arid': 'Scorched',
  'High Temperature': 'Scorched',

  // ============================================
  // RADIOACTIVE/IRRADIATED BIOME
  // ============================================
  'Radioactive': 'Radioactive',
  'Irradiated': 'Radioactive',
  'Nuclear': 'Radioactive',
  'Isotopic': 'Radioactive',
  'Contaminated': 'Radioactive',
  'Decaying Nuclear': 'Radioactive',
  'Gamma Intensive': 'Radioactive',
  'Gamma-Intensive': 'Radioactive',
  'High Radio Source': 'Radioactive',
  'Supercritical': 'Radioactive',
  'High Energy': 'Radioactive',

  // ============================================
  // BARREN BIOME (Desert/rocky worlds)
  // ============================================
  'Barren': 'Barren',
  'Desert': 'Barren',
  'Rocky': 'Barren',
  'Bleak': 'Barren',
  'Parched': 'Barren',
  'Dusty': 'Barren',
  'Desolate': 'Barren',
  'Wind-Swept': 'Barren',
  'Wind-swept': 'Barren',
  'Abandoned': 'Barren',

  // ============================================
  // DEAD BIOME (Lifeless worlds)
  // ============================================
  'Dead': 'Dead',
  'Empty': 'Dead',
  'Lifeless': 'Dead',
  'Forsaken': 'Dead',
  'Life-Incompatible': 'Dead',
  'Low Atmosphere': 'Dead',
  'Airless': 'Dead',
  'Terraforming Catastrophe': 'Dead',

  // ============================================
  // MARSH/SWAMP BIOME
  // ============================================
  'Marsh': 'Marsh',
  'Marshy': 'Marsh',
  'Swamp': 'Marsh',
  'Boggy': 'Marsh',
  'Foggy': 'Marsh',
  'Misty': 'Marsh',
  'Hazy': 'Marsh',
  'Murky': 'Marsh',
  'Damp': 'Marsh',
  'Quagmire': 'Marsh',
  'Reeking': 'Marsh',
  'Vapour': 'Marsh',
  'Cloudy': 'Marsh',
  'Endless Morass': 'Marsh',

  // ============================================
  // VOLCANIC/LAVA BIOME
  // ============================================
  'Volcanic': 'Volcanic',
  'Lava': 'Volcanic',
  'Magma': 'Volcanic',
  'Erupting': 'Volcanic',
  'Molten': 'Volcanic',
  'Ashen': 'Volcanic',
  'Ash-shrouded': 'Volcanic',
  'Ash-Shrouded': 'Volcanic',
  'Tectonic': 'Volcanic',
  'Basalt': 'Volcanic',
  'Flame-Ruptured': 'Volcanic',
  'Unstable': 'Volcanic',
  'Violent': 'Volcanic',
  'Imminent Core Detonation': 'Volcanic',
  'Obsidian Bead': 'Volcanic',

  // ============================================
  // EXOTIC BIOME (Weird/anomaly worlds)
  // ============================================
  'Exotic': 'Exotic',
  'Weird': 'Exotic',
  // Beam/Aurora subtype
  'Fissured': 'Exotic',
  'Of Light': 'Exotic',
  'Breached': 'Exotic',
  // Bone Spire subtype
  'Rattling': 'Exotic',
  'Spined': 'Exotic',
  'Skeletal': 'Exotic',
  // Bubble subtype
  'Bubbling': 'Exotic',
  'Frothing': 'Exotic',
  'Foaming': 'Exotic',
  // Contour/Cable subtype
  'Contoured': 'Exotic',
  'Cabled': 'Exotic',
  'Webbed': 'Exotic',
  // Fract Cube/Nanophage subtype
  'Mechanical': 'Exotic',
  'Metallic': 'Exotic',
  'Metallurgic': 'Exotic',
  // Hexagon subtype
  'Hexagonal': 'Exotic',
  'Plated': 'Exotic',
  'Scaly': 'Exotic',
  // Hydro Garden/Sporal subtype
  'Fungal': 'Exotic',
  'Sporal': 'Exotic',
  'Capped': 'Exotic',
  // Irri Shells subtype
  'Finned': 'Exotic',
  'Bladed': 'Exotic',
  'Shell-Strewn': 'Exotic',
  // M Structure/Mollusc subtype
  'Ossified': 'Exotic',
  'Petrified': 'Exotic',
  'Calcified': 'Exotic',
  // Shards/Glass subtype
  'Columned': 'Exotic',
  'Sharded': 'Exotic',
  'Pillared': 'Exotic',
  // Wire Cell subtype
  'Shattered': 'Exotic',
  'Fractured': 'Exotic',
  'Fragmented': 'Exotic',
  // Glitch subtypes
  'Planetary Anomaly': 'Exotic',
  'Malfunctioning': 'Exotic',
  '[REDACTED]': 'Exotic',
  'Glassy': 'Exotic',
  'Thirsty': 'Exotic',
  'Doomed': 'Exotic',
  'Erased': 'Exotic',
  'Temporary': 'Exotic',
  'Corrupted': 'Exotic',

  // ============================================
  // MEGA EXOTIC / CHROMATIC BIOMES
  // ============================================
  // Red Chromatic
  'Crimson': 'Chromatic Red',
  'Lost Red': 'Chromatic Red',
  'Vermillion Globe': 'Chromatic Red',
  'Scarlet': 'Chromatic Red',
  'Blood': 'Chromatic Red',
  'Wine Dark': 'Chromatic Red',

  // Green Chromatic
  'Lost Green': 'Chromatic Green',
  'Vile Anomaly': 'Chromatic Green',
  'Toxic Anomaly': 'Chromatic Green',
  'Doomed Jade': 'Chromatic Green',
  'Haunted Emeril': 'Chromatic Green',
  'Deathly Green Anomaly': 'Chromatic Green',

  // Blue Chromatic
  'Lost Blue': 'Chromatic Blue',
  'Harsh Blue Globe': 'Chromatic Blue',
  'Frozen Anomaly': 'Chromatic Blue',
  'Azure': 'Chromatic Blue',
  'Cerulean': 'Chromatic Blue',
  'Ultramarine': 'Chromatic Blue',

  // Shared Mega Exotic
  'Chromatic Fog': 'Mega Exotic',
  'Stellar Corruption': 'Mega Exotic',
  'Stellar Corruption Detected': 'Mega Exotic',

  // ============================================
  // INFESTED BIOME (Overlay biome)
  // ============================================
  'Infested': 'Infested',
  'The Nest': 'Infested',
  'Xeno-Colony': 'Infested',
  'Worm-Ridden': 'Infested',
  'Worm-ridden': 'Infested',
  'Infested Paradise': 'Infested',
  // Infested variants by base biome
  'Boiling Doom': 'Infested',
  'Fiery Dreadworld': 'Infested',
  'Icy Abhorrence': 'Infested',
  'Frozen Hell': 'Infested',
  'Caustic Nightmare': 'Infested',
  'Toxic Horror': 'Infested',
  'Radioactive Abomination': 'Infested',
  'Mutated': 'Infested',
  'Mutating Relic': 'Infested',
  'Terrorsphere': 'Infested',
  'Infected Dustbowl': 'Infested',
  'Tainted': 'Infested',

  // ============================================
  // WATERWORLD BIOME (Purple star systems only)
  // ============================================
  'Waterworld': 'Waterworld',
  'Drowning': 'Waterworld',
  'Endless': 'Waterworld',

  // ============================================
  // GAS GIANT BIOME (Worlds Part 2 update)
  // ============================================
  'Gas Giant': 'Gas Giant',

  // ============================================
  // RELIC/RUINED VARIANTS (map to base types)
  // ============================================
  'Ruined': 'Dead',
  'Ruined Dustbowl': 'Barren',
  'Bleached Ruin': 'Dead',
  'Scorched Relic': 'Scorched',
  'Overgrown Relic': 'Lush',
  'Abandoned Crucible': 'Scorched',
  'Abandoned Paradise': 'Lush',
  'Claimed By Decay': 'Dead',
  'Lost To Fire': 'Scorched',
};

// Colors for each biome category (Tailwind classes)
export const BIOME_COLORS = {
  'Lush': 'bg-green-500',
  'Frozen': 'bg-cyan-400',
  'Toxic': 'bg-lime-500',
  'Scorched': 'bg-orange-500',
  'Radioactive': 'bg-yellow-400',
  'Barren': 'bg-amber-600',
  'Dead': 'bg-gray-500',
  'Marsh': 'bg-teal-500',
  'Volcanic': 'bg-red-600',
  'Exotic': 'bg-purple-500',
  'Mega Exotic': 'bg-pink-500',
  'Chromatic Red': 'bg-red-500',
  'Chromatic Green': 'bg-emerald-500',
  'Chromatic Blue': 'bg-blue-500',
  'Infested': 'bg-rose-700',
  'Waterworld': 'bg-sky-500',
  'Gas Giant': 'bg-indigo-400',
  'Unknown': 'bg-gray-600'
};

/**
 * Get the parent biome category for a given biome adjective
 * @param {string} biomeAdjective - The biome descriptor (e.g., "Paradise", "Icy", "Toxic")
 * @returns {string} - The parent category (e.g., "Lush", "Frozen", "Toxic")
 */
export function getBiomeCategory(biomeAdjective) {
  if (!biomeAdjective) return 'Unknown';

  // Direct lookup
  if (BIOME_ADJECTIVE_MAP[biomeAdjective]) {
    return BIOME_ADJECTIVE_MAP[biomeAdjective];
  }

  // Case-insensitive lookup
  const normalized = biomeAdjective.trim();
  for (const [adjective, category] of Object.entries(BIOME_ADJECTIVE_MAP)) {
    if (adjective.toLowerCase() === normalized.toLowerCase()) {
      return category;
    }
  }

  // Check if it's already a category name
  if (BIOME_CATEGORIES.includes(normalized)) {
    return normalized;
  }

  // Handle "Unknown(X)" format from extractor
  if (normalized.startsWith('Unknown')) {
    return 'Unknown';
  }

  return 'Unknown';
}

/**
 * Get the color class for a biome category
 * @param {string} category - The biome category
 * @returns {string} - Tailwind CSS class for the color
 */
export function getBiomeCategoryColor(category) {
  return BIOME_COLORS[category] || BIOME_COLORS['Unknown'];
}

/**
 * Aggregate biome counts by parent category
 * @param {Object} rawBiomeDistribution - Object with biome adjectives as keys and counts as values
 * @returns {Object} - Object with parent categories as keys and counts as values
 */
export function aggregateBiomesByCategory(rawBiomeDistribution) {
  const categoryDistribution = {};

  for (const [biome, count] of Object.entries(rawBiomeDistribution)) {
    const category = getBiomeCategory(biome);
    categoryDistribution[category] = (categoryDistribution[category] || 0) + count;
  }

  return categoryDistribution;
}
