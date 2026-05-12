import React, { useState } from 'react'
import { uploadPhoto, getPhotoUrl } from '../utils/api'
import Modal from './Modal'
import SearchableSelect from './SearchableSelect'
import HelpChip from './wizard/HelpChip'
import {
  biomeAdjectives,
  weatherAdjectives,
  sentinelAdjectives,
  floraAdjectives,
  faunaAdjectives,
  resourcesList,
  exoticTrophyList,
  toSelectOptions
} from '../data/adjectives'

// Pre-compute options for react-select (shared across all instances)
const biomeOptions = toSelectOptions(biomeAdjectives)
const weatherOptions = toSelectOptions(weatherAdjectives)
const sentinelOptions = toSelectOptions(sentinelAdjectives)
const floraOptions = toSelectOptions(floraAdjectives)
const faunaOptions = toSelectOptions(faunaAdjectives)
const resourcesOptions = toSelectOptions(resourcesList)
const exoticTrophyOptions = toSelectOptions(exoticTrophyList)

// Special attributes shared by planets and moons
const SHARED_ATTRIBUTES = [
  { key: 'has_rings', label: 'Has Rings', icon: '\u{1FA90}' },
  { key: 'is_dissonant', label: 'Dissonant', icon: '\u{1F50A}' },
  { key: 'is_infested', label: 'Infested', icon: '\u{1F9A0}' },
  { key: 'extreme_weather', label: 'Extreme Weather', icon: '\u{26A1}' },
  { key: 'water_world', label: 'Water World', icon: '\u{1F30A}' },
  { key: 'vile_brood', label: 'Vile Brood', icon: '\u{1F480}' },
  { key: 'is_bubble', label: 'Bubble Planet', icon: '\u{1FAE7}' },
  { key: 'is_floating_islands', label: 'Floating Islands', icon: '\u{1F3DD}' },
]

// Planet-only attributes
const PLANET_ONLY_ATTRIBUTES = [
  { key: 'is_gas_giant', label: 'Gas Giant', icon: '\u{1F310}' },
]

/**
 * Unified editor for planets and moons.
 *
 * Props:
 *   type       - "planet" or "moon"
 *   body       - the planet/moon data object
 *   index      - position in the parent array
 *   onChange   - (index, updatedBody) callback
 *   onRemove   - (index) callback
 *   onSave     - optional (body) callback for save button
 *   children   - optional extra content (e.g. moon list for planets)
 */
export default function CelestialBodyEditor({ type = 'planet', body, index, onChange, onRemove, onSave, children, openHelp }) {
  const [uploading, setUploading] = useState(false)
  const [attrsModalOpen, setAttrsModalOpen] = useState(false)

  const isPlanet = type === 'planet'
  const label = isPlanet ? 'Planet' : 'Moon'
  const data = body || {}

  // Wonders Page Notes — the procgen narrative NMS prints on a planet/moon's
  // Log Exploration Guide page (visible in the Wonders catalogue after upload).
  // Collapsed by default to keep the card lean; auto-expanded if any field is
  // already populated so loaded systems don't hide their data.
  const wondersHasData = !!(body && (body.estimated_age || body.core_element || body.lore_notes || body.root_structure || body.nutrient_source))
  const [wondersOpen, setWondersOpen] = useState(wondersHasData)

  function setField(k, v) {
    const updated = { ...data, [k]: v }
    onChange(index, updated)
  }

  async function upload(e) {
    setUploading(true)
    try {
      const file = e.target.files[0]
      if (!file) return
      const res = await uploadPhoto(file)
      setField('photo', res.path)
    } catch (err) {
      alert('Upload failed: ' + err)
    }
    setUploading(false)
  }

  // Combine attributes based on type
  const attributes = isPlanet
    ? [...SHARED_ATTRIBUTES, ...PLANET_ONLY_ATTRIBUTES]
    : SHARED_ATTRIBUTES

  // Count active attributes for badge
  const activeAttrCount = attributes.filter(a => !!data[a.key]).length + (data.exotic_trophy ? 1 : 0)

  return (
    <div className={`${isPlanet ? 'p-3 my-3' : 'p-2 my-2'} border rounded bg-white/5`}>
      {/* ONE grid for all fields so items flow continuously (no orphan rows).
          PLANET cards: auto-fit columns ≥200px wide — adapts to viewport.
            • Mobile (~280px content) → 1 col
            • Desktop 1280px (form col ~440px) → 2 cols
            • Widescreen 1440-1920px → 3-4 cols, no dead space
          MOON cards: simple 1→3 col responsive — moons live nested
          inside planet cards so they don't have as much horizontal room.
          Mobile gap-5 (20px) for breathing room against the dark theme;
          sm+ collapses to the original 12px (planet) / 8px (moon). */}
      <div
        className={`grid ${isPlanet ? '' : 'grid-cols-1 sm:grid-cols-3'} gap-5 sm:gap-${isPlanet ? '3' : '2'}`}
        style={isPlanet ? { gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' } : undefined}
      >
        <div>
          <label className="block text-sm">{label} Name</label>
          <input
            className="mt-1 p-1 rounded w-full"
            value={data.name || ''}
            onChange={e => setField('name', e.target.value)}
            placeholder={`${label} name`}
          />
        </div>
        <div>
          <label className="block text-sm">Biome</label>
          <div className="mt-1">
            <SearchableSelect options={biomeOptions} value={data.biome || ''} onChange={val => setField('biome', val)} placeholder="Search biome..." />
          </div>
        </div>
        <div>
          <label className="block text-sm">Weather</label>
          <div className="mt-1">
            <SearchableSelect options={weatherOptions} value={data.weather || ''} onChange={val => setField('weather', val)} placeholder="Search weather..." />
          </div>
        </div>
        <div>
          <label className="block text-sm">Sentinels</label>
          <div className="mt-1">
            <SearchableSelect options={sentinelOptions} value={data.sentinel || ''} onChange={val => setField('sentinel', val)} placeholder="Search sentinels..." />
          </div>
        </div>
        <div>
          <label className="block text-sm">Flora</label>
          <div className="mt-1">
            <SearchableSelect options={floraOptions} value={data.flora || ''} onChange={val => setField('flora', val)} placeholder="Search flora..." />
          </div>
        </div>
        <div>
          <label className="block text-sm">Fauna</label>
          <div className="mt-1">
            <SearchableSelect options={faunaOptions} value={data.fauna || ''} onChange={val => setField('fauna', val)} placeholder="Search fauna..." />
          </div>
        </div>
        <div>
          <label className="block text-sm">{isPlanet ? 'Resources / Materials' : 'Materials'}</label>
          <div className="mt-1">
            <SearchableSelect options={resourcesOptions} value={data.materials || ''} onChange={val => setField('materials', val)} placeholder="Search resources..." isMulti={true} />
          </div>
        </div>
        {isPlanet && (
          <div>
            <label className="block text-sm">Base Location</label>
            <input aria-label="Planet Base" placeholder="Base location" className="mt-1 p-1 rounded w-full" value={data.base_location || ''} onChange={e => setField('base_location', e.target.value)} />
          </div>
        )}
        <div>
          <label className="block text-sm">Photo</label>
          <input aria-label={`${label} Photo`} type="file" onChange={upload} className="mt-1" />
          {uploading && <div className="muted text-sm mt-1">Uploading...</div>}
          {!uploading && data.photo && (
            <div className="mt-2 relative inline-block group">
              <img src={getPhotoUrl(data.photo)} alt={`${label} photo`} className="max-w-full sm:max-w-xs max-h-32 rounded border border-gray-600" />
              <button type="button" onClick={() => setField('photo', null)} className="absolute -top-2 -right-2 w-6 h-6 bg-red-600 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-sm font-bold" title="Remove photo">X</button>
              <div className="text-xs text-gray-400 mt-1 break-all">{data.photo}</div>
            </div>
          )}
        </div>
        <div>
          <label className="block text-sm">Notes</label>
          <input placeholder={isPlanet ? 'Notes' : 'Optional notes'} className="mt-1 p-1 rounded w-full" value={data.notes || ''} onChange={e => setField('notes', e.target.value)} />
        </div>
      </div>

      {/* Action buttons */}
      <div className="mt-3 flex flex-wrap gap-2 items-center">
        <button type="button" onClick={() => setAttrsModalOpen(true)} className="px-3 py-1.5 bg-purple-600 rounded text-sm">
          {label} Attributes
          {activeAttrCount > 0 && <span className="ml-1.5 px-1.5 py-0.5 bg-white/20 rounded-full text-xs">{activeAttrCount}</span>}
        </button>
        {onSave && (
          <button type="button" onClick={() => onSave(data)} className="px-3 py-1.5 bg-blue-600 rounded text-sm">Save</button>
        )}
        <button type="button" onClick={() => onRemove(index)} className={`${isPlanet ? '' : 'ml-auto '}px-3 py-1.5 bg-red-600 rounded text-sm`}>Remove {label}</button>
      </div>

      {/* Slot for planet-specific content (moon list, add moon button) */}
      {children}

      {/* Wonders Page Notes — procgen narrative NMS prints on the Log
          Exploration Guide page (surfaced in the Wonders catalogue after
          upload). Collapsible to keep the card lean when unused. */}
      <div className="mt-3 border-t border-white/10 pt-3">
        <button
          type="button"
          onClick={() => setWondersOpen(v => !v)}
          className="w-full flex items-center justify-between text-sm font-semibold text-amber-300 hover:text-amber-200 transition-colors"
        >
          <span className="flex items-center gap-2">
            <span>{wondersOpen ? '▾' : '▸'}</span>
            <span>★ Wonders Page Notes</span>
            {wondersHasData && <span className="px-1.5 py-0.5 bg-amber-500/20 rounded-full text-[10px]">filled</span>}
          </span>
          <span className="text-[11px] opacity-60 font-normal hidden sm:inline">
            Free-form text from NMS Log → Exploration Guide
          </span>
        </button>
        {wondersOpen && (
          <div
            className="mt-3 grid gap-3"
            style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}
          >
            <div>
              <label className="block text-sm">Estimated Age</label>
              <input
                className="mt-1 p-1 rounded w-full"
                placeholder="e.g. approximately 6.04 billion years"
                value={data.estimated_age || ''}
                onChange={e => setField('estimated_age', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm">Primary Core Element</label>
              <input
                className="mt-1 p-1 rounded w-full"
                placeholder="e.g. Gold, Cadmium, Water"
                value={data.core_element || ''}
                onChange={e => setField('core_element', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm">Root Structure</label>
              <input
                className="mt-1 p-1 rounded w-full"
                placeholder="Lush/exotic biomes only"
                value={data.root_structure || ''}
                onChange={e => setField('root_structure', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm">Nutrient Source</label>
              <input
                className="mt-1 p-1 rounded w-full"
                placeholder="Lush/exotic biomes only"
                value={data.nutrient_source || ''}
                onChange={e => setField('nutrient_source', e.target.value)}
              />
            </div>
            <div className="sm:col-span-2" style={{ gridColumn: '1 / -1' }}>
              <label className="block text-sm">Lore Notes</label>
              <textarea
                className="mt-1 p-2 rounded w-full"
                rows={4}
                placeholder={'Paste the procgen blurb from the in-game Wonders entry. e.g. "Once a thriving world before an asteroid impact knocked it from orbit, transforming it into a moon..."'}
                value={data.lore_notes || ''}
                onChange={e => setField('lore_notes', e.target.value)}
              />
            </div>
          </div>
        )}
      </div>

      {/* Attributes Modal */}
      {attrsModalOpen && (
        <Modal title={`${label} Attributes`} onClose={() => setAttrsModalOpen(false)}>
          <div className="space-y-5 pb-48">
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">{label} Specials</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {attributes.map(({ key, label: attrLabel, icon }) => {
                  const active = !!data[key]
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setField(key, active ? 0 : 1)}
                      className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                        active
                          ? 'border-purple-500 bg-purple-500/20 text-purple-200'
                          : 'border-gray-600 bg-white/5 text-gray-400 hover:border-gray-500 hover:bg-white/10'
                      }`}
                    >
                      <span className="text-base">{icon}</span>
                      {attrLabel}
                    </button>
                  )
                })}
              </div>
            </div>
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Exotic Trophy
                {openHelp && <HelpChip anchor="exotic-trophy" onOpen={openHelp} label="Help: Exotic Trophy" />}
              </h3>
              <SearchableSelect options={exoticTrophyOptions} value={data.exotic_trophy || ''} onChange={val => setField('exotic_trophy', val)} placeholder="Search exotic trophy..." />
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
