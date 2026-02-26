// Adjective tier color mappings for fauna, flora, and sentinel values.
// Tiers sourced from NMS-Haven-Extractor RARITY_*/SENTINEL_* maps (authoritative game data).

// --- Fauna / Flora tiers (identical adjective sets) ---

const HIGH = new Set([
  'Rich', 'Abundant', 'High', 'Ample', 'Frequent', 'Full',
  'Generous', 'Numerous', 'Copious', 'Thriving', 'Flourishing',
]);

const MID = new Set([
  'Average', 'Regular', 'Moderate', 'Common', 'Typical', 'Ordinary',
  'Standard', 'Normal', 'Usual', 'Fair', 'Medium', 'Adequate', 'Sufficient',
]);

const LOW = new Set([
  'Sparse', 'Rare', 'Scarce', 'Uncommon', 'Infrequent', 'Limited',
  'Few', 'Low', 'Minimal', 'Sporadic', 'Occasional', 'Intermittent',
]);

const NONE = new Set([
  'Absent', 'None', 'Devoid', 'Undetected', 'Lacking', 'Barren',
  'Nonexistent', 'Empty', 'Not Present', 'Deficient', 'N/A',
]);

const WEIRD = new Set([
  'Displaced', 'Unusual', 'Twisted', 'Infected', 'Invasive',
  'From Elsewhere', 'Misplaced', 'Lost', 'Between Worlds',
  'Diseased', 'Forfeited', 'Uprooted', 'Viral', 'Screaming',
]);

// Fauna-only value
const FAUNA_EXTRA = new Set(['Synthetic']);

// --- Sentinel tiers ---

const SENTINEL_NONE = new Set([
  'None', 'Absent', 'Not Present', 'None Present', 'Missing',
]);

const SENTINEL_LOW = new Set([
  'Low', 'Minimal', 'Low Security', 'Limited', 'Infrequent',
  'Sparse', 'Isolated', 'Remote', 'Irregular Patrols',
  'Spread Thin', 'Intermittent', 'Few',
]);

const SENTINEL_DEFAULT = new Set([
  'Attentive', 'Enforcing', 'Frequent', 'Require Orthodoxy',
  'Require Obedience', 'Regular Patrols', 'Unwavering',
  'Observant', 'Ever-present',
]);

const SENTINEL_AGGRESSIVE = new Set([
  'Aggressive', 'Frenzied', 'High Security', 'Hostile Patrols',
  'Threatening', 'Hateful', 'Zealous', 'Malicious', 'Inescapable',
]);

const SENTINEL_CORRUPT = new Set([
  'Corrupted', 'Forsaken', 'Rebellious', 'Answer To None',
  'Sharded from the Atlas', 'Dissonant', 'De-Harmonised',
]);

// --- Color getters ---

export function getFaunaColor(value) {
  if (!value) return 'text-gray-500';
  if (HIGH.has(value) || FAUNA_EXTRA.has(value)) return 'text-yellow-400';
  if (MID.has(value)) return 'text-blue-300';
  if (LOW.has(value)) return 'text-orange-400';
  if (NONE.has(value)) return 'text-gray-500';
  if (WEIRD.has(value)) return 'text-purple-400';
  return 'text-gray-300';
}

export function getFloraColor(value) {
  if (!value) return 'text-gray-500';
  if (HIGH.has(value)) return 'text-green-400';
  if (MID.has(value)) return 'text-blue-300';
  if (LOW.has(value)) return 'text-orange-400';
  if (NONE.has(value)) return 'text-gray-500';
  if (WEIRD.has(value)) return 'text-purple-400';
  return 'text-gray-300';
}

export function getSentinelColor(value) {
  if (!value) return 'text-gray-500';
  if (SENTINEL_AGGRESSIVE.has(value)) return 'text-red-400';
  if (SENTINEL_DEFAULT.has(value)) return 'text-yellow-400';
  if (SENTINEL_LOW.has(value)) return 'text-green-400';
  if (SENTINEL_CORRUPT.has(value)) return 'text-purple-400';
  if (SENTINEL_NONE.has(value)) return 'text-gray-500';
  return 'text-gray-300';
}