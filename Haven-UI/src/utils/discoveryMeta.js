// Single source for turning a discovery's `type_metadata` blob into something
// renderable. The blob is stored as JSON in `discoveries.type_metadata`; the
// list endpoints (`/browse`, `/recent`) historically returned it as a raw
// string while the detail endpoint returned a parsed object, so every consumer
// has to be defensive about the shape.
//
// Labels are sourced from the curated DISCOVERY_TYPE_FIELDS definitions (the
// same list the wizard uses), falling back to a title-cased key for any field
// that isn't in the curated set.

import { DISCOVERY_TYPE_FIELDS } from '../data/discoveryTypeFields'
import { classColor, richnessColor } from './gradeColors'

// Flatten every type's field defs into key -> label and key -> recordKind maps.
// Keys that repeat across types (species_name, damage, …) carry the same label /
// recordKind, so first-wins is fine.
const KEY_LABELS = {}
const KEY_RECORDKIND = {}
for (const fields of Object.values(DISCOVERY_TYPE_FIELDS)) {
  for (const f of fields) {
    if (f?.key && !(f.key in KEY_LABELS)) KEY_LABELS[f.key] = f.label
    if (f?.key && f.recordKind && !(f.key in KEY_RECORDKIND)) KEY_RECORDKIND[f.key] = f.recordKind
  }
}

/**
 * Color for a metadata value, when the field is a rank: C/B/A/S class fields
 * (ship_class, tool_class) get the class scale; deposit_richness gets the
 * richness scale. Everything else returns null (no tint).
 */
export function metaValueColor(key, value) {
  const rk = KEY_RECORDKIND[key]
  if (rk === 'rank_class') return classColor(value)
  if (rk === 'rank_rich') return richnessColor(value)
  return null
}

export function prettyMetaLabel(key) {
  return (
    KEY_LABELS[key] ||
    String(key).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  )
}

/** Accepts an object, a JSON string, null/undefined — always returns an object. */
export function parseTypeMetadata(raw) {
  if (!raw) return {}
  if (typeof raw === 'object') return raw
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      return parsed && typeof parsed === 'object' ? parsed : {}
    } catch {
      return {}
    }
  }
  return {}
}

/**
 * Returns ordered, render-ready metadata entries for a discovery, skipping
 * empty values: [{ key, label, value }].
 */
export function metaEntries(raw) {
  const obj = parseTypeMetadata(raw)
  return Object.entries(obj)
    .filter(([, v]) => v !== null && v !== undefined && String(v).trim() !== '')
    .map(([key, value]) => ({
      key,
      label: prettyMetaLabel(key),
      value: String(value),
      color: metaValueColor(key, value),
    }))
}
