// Discovery type-specific metadata fields. Must stay in sync with the
// backend DISCOVERY_TYPE_FIELDS dict in routes/discoveries.py and the
// records-eligibility map in routes/wizard.py (RECORD_DEFS).
//
// Each field can declare:
//   key           — payload field name (also the records-map metric key)
//   label         — UI label
//   placeholder   — input placeholder
//   numeric       — true if this should accept numeric input + participate in
//                   record-beat detection
//   recordKind    — 'numeric' (MAX), 'rank_class' (S>A>B>C),
//                   'rank_rich' (Extraordinary>Rare>Common). Frontend uses
//                   this to decide whether a value beats the current record.

import { TYPE_INFO } from './discoveryTypes'

export const DISCOVERY_TYPE_FIELDS = {
  '🦗': [
    { key: 'species_name', label: 'Species Name', placeholder: 'Proc-gen name from scanner' },
    { key: 'behavior', label: 'Behavior', placeholder: 'Aggressive, Passive, Herd Animal…' },
    { key: 'height', label: 'Height (m)', placeholder: '11.8', numeric: true, recordKind: 'numeric' },
    { key: 'weight', label: 'Weight (kg)', placeholder: '420', numeric: true, recordKind: 'numeric' },
  ],
  '🌿': [
    { key: 'species_name', label: 'Species Name', placeholder: 'Proc-gen name from scanner' },
    { key: 'biome', label: 'Biome', placeholder: 'Toxic Swamps, Lush Forest…' },
  ],
  '💎': [
    { key: 'resource_type', label: 'Resource Type', placeholder: 'Storm Crystals, Runaway Mold…' },
    { key: 'deposit_richness', label: 'Deposit Richness', placeholder: 'Common, Rare, Extraordinary', recordKind: 'rank_rich' },
  ],
  '🏛️': [
    { key: 'age_era', label: 'Age / Era', placeholder: 'Pre-Atlas, Ancient, Unknown' },
    { key: 'associated_race', label: 'Associated Race', placeholder: "Gek, Korvax, Vy'keen…" },
  ],
  '📜': [
    { key: 'language_status', label: 'Language / Decryption', placeholder: 'Gek Language, Encrypted…' },
    { key: 'author_origin', label: 'Author / Origin', placeholder: 'Unknown Traveler, Atlas Entity…' },
  ],
  '🦴': [
    { key: 'species_type', label: 'Species Type', placeholder: 'Large Predator, Aquatic Life…' },
    { key: 'estimated_age', label: 'Estimated Age', placeholder: 'Ancient, Millions of years old…' },
  ],
  '👽': [
    { key: 'structure_type', label: 'Structure Type', placeholder: 'Monolith, Portal, Observatory…' },
    { key: 'operational_status', label: 'Status', placeholder: 'Functional, Dormant, Damaged…' },
  ],
  '🚀': [
    { key: 'ship_type', label: 'Ship Type', placeholder: 'Hauler, Fighter, Explorer, Exotic…' },
    { key: 'ship_class', label: 'Ship Class', placeholder: 'C, B, A, S', recordKind: 'rank_class' },
    { key: 'slots', label: 'Slots', placeholder: '48', numeric: true, recordKind: 'numeric' },
    { key: 'manoeuvrability', label: 'Manoeuvrability', placeholder: '+45', numeric: true, recordKind: 'numeric' },
    { key: 'damage', label: 'Damage', placeholder: '+25', numeric: true, recordKind: 'numeric' },
    { key: 'shield', label: 'Shield', placeholder: '+30', numeric: true, recordKind: 'numeric' },
  ],
  '⚙️': [
    { key: 'tool_type', label: 'Multi-tool Type', placeholder: 'Pistol, Rifle, Experimental…' },
    { key: 'tool_class', label: 'Class', placeholder: 'C, B, A, S', recordKind: 'rank_class' },
    { key: 'damage', label: 'Damage', placeholder: '+18', numeric: true, recordKind: 'numeric' },
    { key: 'mining', label: 'Mining', placeholder: '+22', numeric: true, recordKind: 'numeric' },
    { key: 'scan', label: 'Scan', placeholder: '+45', numeric: true, recordKind: 'numeric' },
  ],
  '📖': [
    { key: 'story_type', label: 'Story Type', placeholder: 'Journal Entry, Theory, Fiction…' },
  ],
  '🏠': [
    { key: 'base_type', label: 'Base Type', placeholder: 'Farm, Trading Post, Monument…' },
  ],
  '🆕': [],
}

// Reverse lookup: emoji → type-info key (used by record-beat detection).
// Records map uses string keys ('starship', 'multitool', etc.); discovery
// rows store the emoji as discovery_type. Keep this in lockstep with
// routes/wizard.py:TYPE_EMOJI_TO_KEY.
export const EMOJI_TO_TYPE_KEY = Object.fromEntries(
  Object.entries(TYPE_INFO).map(([k, v]) => [v.emoji, k])
)

export const DISCOVERY_TYPE_OPTIONS = [
  { value: '', label: 'Select type…' },
  ...Object.values(TYPE_INFO).map((t) => ({ value: t.emoji, label: `${t.emoji} ${t.label}` })),
]

const CLASS_RANK = { S: 4, A: 3, B: 2, C: 1 }
const RICH_RANK = { Extraordinary: 3, Rare: 2, Common: 1 }

/**
 * Compare a freshly-entered field value to the current Haven record.
 * Returns true if `value` beats the record (strictly greater rank).
 *
 * Records map shape from /api/wizard/records:
 *   { records: { "starship.ship_class": { value: "S" }, "fauna.height": { value: 11.8 }, ... } }
 */
export function beatsRecord(typeEmoji, fieldKey, fieldDef, value, records) {
  if (!fieldDef?.recordKind || value == null || value === '') return false
  const typeKey = EMOJI_TO_TYPE_KEY[typeEmoji]
  if (!typeKey) return false
  const rec = records?.[`${typeKey}.${fieldKey}`]
  if (!rec) return value !== '' // first-of-its-kind also counts as a record
  if (fieldDef.recordKind === 'numeric') {
    const num = parseFloat(String(value).replace(/[^-\d.]/g, ''))
    if (Number.isNaN(num)) return false
    return num > parseFloat(rec.value)
  }
  if (fieldDef.recordKind === 'rank_class') {
    return (CLASS_RANK[String(value).trim().toUpperCase()] || 0) > (CLASS_RANK[rec.value] || 0)
  }
  if (fieldDef.recordKind === 'rank_rich') {
    const v = String(value).trim()
    const norm = v.charAt(0).toUpperCase() + v.slice(1).toLowerCase()
    return (RICH_RANK[norm] || 0) > (RICH_RANK[rec.value] || 0)
  }
  return false
}

/**
 * Format the current record for inline display:
 *   "Current Haven record: 11.8 on Tessen Prime (by Stars)"
 * Returns null when no record exists yet.
 */
export function formatRecordHint(typeEmoji, fieldKey, records) {
  const typeKey = EMOJI_TO_TYPE_KEY[typeEmoji]
  if (!typeKey) return null
  const rec = records?.[`${typeKey}.${fieldKey}`]
  if (!rec) return null
  const display = rec.raw || rec.value
  return `Current Haven record: ${display}${rec.system_name ? ` on ${rec.system_name}` : ''}${rec.holder ? ` (by ${rec.holder})` : ''}`
}
