import React, { useEffect, useState } from 'react'
import Button from '../Button'
import PhotoUploader from './PhotoUploader'
import LocationTypePicker from './LocationTypePicker'
import HelpChip from './HelpChip'
import { TYPE_INFO } from '../../data/discoveryTypes'
import {
  DISCOVERY_TYPE_FIELDS,
  DISCOVERY_TYPE_OPTIONS,
  beatsRecord,
  formatRecordHint,
} from '../../data/discoveryTypeFields'
import { getWizardRecords } from '../../utils/api'

// Wizard v1 inline discoveries (mockup #adv-discoveries 5794-5815).
//
// Replaces the prior modal-launching stub. The wizard's parent owns the
// `discoveries` array on the system state; this component renders one
// expandable card per entry plus an "Add Discovery" button.
//
// Each card has:
//   - Type chip + name + planet/moon/space target
//   - Expandable body with:
//       location_name, type-specific metadata fields (with record hints +
//       auto-flag of submit_for_record on numeric beats), evidence URLs,
//       per-entry game version, photos (drag-reorder, ★ main, paste), notes
//
// Submission timing:
//   The parent doesn't submit discoveries up-front. After the system save
//   returns a system_id, the parent loops these entries and POSTs each via
//   /api/submit_discovery with `system_id` set. For pending public submits
//   without a system_id, the entries are saved alongside the draft and shown
//   to the user post-submit with a note that they'll be submitted on approve.
//
// Props:
//   value: discovery[] — list of in-progress entries
//   onChange(next: discovery[])
//   planets: planet[] — from system.planets, for target dropdowns
//   moons: moon[] — flattened {id, name, parentPlanetName} list
//   defaultGameVersion: string — pre-fill new entries
const EMPTY_DISCOVERY = {
  discovery_type: '',
  discovery_name: '',
  description: '',
  location_type: 'planet',
  planet_id: null,
  moon_id: null,
  location_name: '',
  type_metadata: {},
  evidence_urls: '',
  game_version: '',
  photos: [],
  submit_for_record: false,
}

export default function DiscoveryInlineList({
  value = [],
  onChange,
  planets = [],
  moons = [],
  defaultGameVersion = '',
  openHelp,
}) {
  const [expanded, setExpanded] = useState(() => new Set([0]))
  const [records, setRecords] = useState({})

  // Load Haven records once. Cached for the lifetime of the wizard.
  useEffect(() => {
    let cancelled = false
    getWizardRecords()
      .then((d) => { if (!cancelled) setRecords(d.records || {}) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  function add() {
    const next = [...value, { ...EMPTY_DISCOVERY, game_version: defaultGameVersion }]
    onChange(next)
    setExpanded((prev) => new Set([...prev, next.length - 1]))
  }

  function update(idx, patch) {
    const next = value.map((d, i) => (i === idx ? { ...d, ...patch } : d))
    onChange(next)
  }

  function updateMeta(idx, key, val, fieldDef) {
    const cur = value[idx]
    const meta = { ...(cur.type_metadata || {}), [key]: val }
    const patch = { type_metadata: meta }
    // Auto-flag submit_for_record when a numeric/rank field beats the record
    if (fieldDef?.recordKind && beatsRecord(cur.discovery_type, key, fieldDef, val, records)) {
      patch.submit_for_record = true
    }
    update(idx, patch)
  }

  function remove(idx) {
    const next = value.filter((_, i) => i !== idx)
    onChange(next)
    setExpanded((prev) => {
      const out = new Set()
      prev.forEach((i) => {
        if (i < idx) out.add(i)
        else if (i > idx) out.add(i - 1)
      })
      return out
    })
  }

  function toggle(idx) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm opacity-80">
          {value.length === 0
            ? 'Add fauna, flora, ships, multi-tools, or any other discovery.'
            : `${value.length} discover${value.length === 1 ? 'y' : 'ies'} on this system.`}
        </p>
        <Button onClick={add}>+ Add Discovery</Button>
      </div>

      <div className="space-y-2">
        {value.map((d, idx) => (
          <DiscoveryCard
            key={idx}
            index={idx}
            discovery={d}
            planets={planets}
            moons={moons}
            isExpanded={expanded.has(idx)}
            onToggle={() => toggle(idx)}
            onChange={(patch) => update(idx, patch)}
            onMetaChange={(key, val, def) => updateMeta(idx, key, val, def)}
            onRemove={() => remove(idx)}
            records={records}
            openHelp={openHelp}
          />
        ))}
      </div>
    </div>
  )
}

function DiscoveryCard({
  index, discovery, planets, moons, isExpanded, onToggle, onChange, onMetaChange, onRemove, records, openHelp,
}) {
  const typeInfo = Object.values(TYPE_INFO).find((t) => t.emoji === discovery.discovery_type)
  const fields = DISCOVERY_TYPE_FIELDS[discovery.discovery_type] || []

  // Compute a per-card "record beaten" badge for the header
  const beatRecord = fields.some(
    (f) => f.recordKind && beatsRecord(discovery.discovery_type, f.key, f, discovery.type_metadata?.[f.key], records)
  )

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ backgroundColor: 'var(--app-bg)', border: `1px solid ${beatRecord ? 'var(--app-accent-amber)' : 'var(--app-accent-3)'}` }}
    >
      {/* Header row (always visible) */}
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center gap-2 p-3 text-left hover:opacity-90"
      >
        <span className="text-xl flex-shrink-0">
          {discovery.discovery_type || '🆕'}
        </span>
        <div className="flex-1 min-w-0">
          <div className="font-semibold truncate">
            {discovery.discovery_name || <span className="opacity-60 italic">Untitled discovery</span>}
          </div>
          <div className="text-xs opacity-70 truncate">
            {typeInfo?.label || 'Pick a type'} · {discovery.location_type}
            {discovery.location_name ? ` · ${discovery.location_name}` : ''}
          </div>
        </div>
        {beatRecord && (
          <span
            className="text-xs px-2 py-0.5 rounded font-semibold flex-shrink-0"
            style={{ backgroundColor: 'var(--app-accent-amber)', color: '#1a1a1a' }}
          >
            ★ Beats record
          </span>
        )}
        {discovery.submit_for_record && !beatRecord && (
          <span
            className="text-xs px-2 py-0.5 rounded flex-shrink-0"
            style={{ backgroundColor: 'rgba(255,180,76,0.15)', color: 'var(--app-accent-amber)' }}
          >
            ★ Record
          </span>
        )}
        <span className="text-xs opacity-60 flex-shrink-0">{isExpanded ? '▾' : '▸'}</span>
      </button>

      {isExpanded && (
        <div className="p-3 pt-0 space-y-3">
          {/* Type + name */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <div>
              <label className="block text-xs font-medium mb-1 opacity-80">Type</label>
              <select
                className="w-full p-2 rounded text-sm"
                style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                value={discovery.discovery_type || ''}
                onChange={(e) => onChange({ discovery_type: e.target.value, type_metadata: {} })}
              >
                {DISCOVERY_TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 opacity-80">Name</label>
              <input
                type="text"
                className="w-full p-2 rounded text-sm"
                style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                value={discovery.discovery_name || ''}
                onChange={(e) => onChange({ discovery_name: e.target.value })}
                placeholder="e.g. Giant Sand Worm"
              />
            </div>
          </div>

          {/* Target */}
          <div>
            <label className="block text-xs font-medium mb-1 opacity-80">Target</label>
            <LocationTypePicker
              value={discovery.location_type}
              onChange={(v) => onChange({
                location_type: v,
                planet_id: v === 'planet' ? discovery.planet_id : null,
                moon_id: v === 'moon' ? discovery.moon_id : null,
              })}
              compact
            />
            {discovery.location_type === 'planet' && (
              <select
                className="w-full mt-2 p-2 rounded text-sm"
                style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                value={discovery.planet_id || ''}
                onChange={(e) => onChange({ planet_id: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">— Pick a planet —</option>
                {planets.map((p, i) => <option key={p.id || i} value={p.id || i}>{p.name || `Planet ${i + 1}`}</option>)}
              </select>
            )}
            {discovery.location_type === 'moon' && (
              <select
                className="w-full mt-2 p-2 rounded text-sm"
                style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                value={discovery.moon_id || ''}
                onChange={(e) => onChange({ moon_id: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">— Pick a moon —</option>
                {moons.map((m, i) => <option key={m.id || i} value={m.id || i}>
                  {m.name || `Moon ${i + 1}`}{m.parentPlanetName ? ` (${m.parentPlanetName})` : ''}
                </option>)}
              </select>
            )}
            <input
              type="text"
              className="w-full mt-2 p-2 rounded text-sm"
              style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
              value={discovery.location_name || ''}
              onChange={(e) => onChange({ location_name: e.target.value })}
              placeholder="Specific location (optional, e.g. 'near the trading post')"
            />
          </div>

          {/* Type-specific metadata fields */}
          {fields.length > 0 && (
            <div className="rounded p-2" style={{ backgroundColor: 'rgba(255,255,255,0.03)', border: '1px solid var(--app-accent-3)' }}>
              <div className="text-xs uppercase tracking-wide opacity-60 mb-2">Type details</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {fields.map((f) => {
                  const val = discovery.type_metadata?.[f.key] || ''
                  const beat = f.recordKind && beatsRecord(discovery.discovery_type, f.key, f, val, records)
                  const hint = formatRecordHint(discovery.discovery_type, f.key, records)
                  return (
                    <div key={f.key}>
                      <label className="block text-xs font-medium mb-1 opacity-80">{f.label}</label>
                      <input
                        type={f.numeric ? 'text' : 'text'}
                        inputMode={f.numeric ? 'decimal' : undefined}
                        className="w-full p-2 rounded text-sm"
                        style={{
                          backgroundColor: 'var(--app-card)',
                          border: `1px solid ${beat ? 'var(--app-accent-amber)' : 'var(--app-accent-3)'}`,
                        }}
                        value={val}
                        onChange={(e) => onMetaChange(f.key, e.target.value, f)}
                        placeholder={f.placeholder}
                      />
                      {hint && (
                        <div className="text-[10px] opacity-60 mt-0.5">{hint}</div>
                      )}
                      {beat && (
                        <div className="text-[10px] mt-0.5 font-semibold" style={{ color: 'var(--app-accent-amber)' }}>
                          ★ This beats the current Haven record!
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Description */}
          <div>
            <label className="block text-xs font-medium mb-1 opacity-80">Description</label>
            <textarea
              className="w-full p-2 rounded text-sm"
              style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)', minHeight: 60 }}
              value={discovery.description || ''}
              onChange={(e) => onChange({ description: e.target.value })}
              placeholder="Notes, behaviors, anything reviewers should know."
            />
          </div>

          {/* Photos */}
          <div>
            <label className="block text-xs font-medium mb-1 opacity-80">Photos</label>
            <PhotoUploader
              value={discovery.photos || []}
              onChange={(next) => onChange({ photos: typeof next === 'function' ? next(discovery.photos || []) : next })}
              pasteTarget={isExpanded && index === 0}
            />
          </div>

          {/* Evidence URLs + game version */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <div>
              <label className="block text-xs font-medium mb-1 opacity-80">Evidence URLs</label>
              <textarea
                className="w-full p-2 rounded text-sm"
                style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)', minHeight: 50 }}
                value={discovery.evidence_urls || ''}
                onChange={(e) => onChange({ evidence_urls: e.target.value })}
                placeholder="One URL per line — Imgur, YouTube, etc."
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 opacity-80">Game version</label>
              <input
                type="text"
                className="w-full p-2 rounded text-sm"
                style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                value={discovery.game_version || ''}
                onChange={(e) => onChange({ game_version: e.target.value })}
                placeholder="6.18, Voyagers…"
              />
              <label className="flex items-center gap-2 mt-3 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!discovery.submit_for_record}
                  onChange={(e) => onChange({ submit_for_record: e.target.checked })}
                  className="w-4 h-4"
                />
                <span>
                  ★ Submit for Wonder of Haven record consideration
                  {openHelp && <HelpChip anchor="records" onOpen={openHelp} label="Help: ★ Submit for Record" />}
                </span>
              </label>
            </div>
          </div>

          <div className="flex justify-end pt-2 border-t" style={{ borderColor: 'var(--app-accent-3)' }}>
            <button
              type="button"
              onClick={onRemove}
              className="text-xs text-red-400 hover:text-red-300 underline-offset-2 hover:underline"
            >
              Remove this discovery
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
