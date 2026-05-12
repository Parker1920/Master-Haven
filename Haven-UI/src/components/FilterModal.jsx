/**
 * FilterModal — centered modal for Systems Tab v2.0 filter editing.
 *
 * Sections (per spec section 3.2):
 *   - Quick Presets at top — single-click apply
 *   - Star Properties (color OR-multi, stellar class single)
 *   - Economy & Politics (type single, tier OR-multi, conflict OR-multi, lifeform single)
 *   - Planet Properties (has_moons tri-state, planet count range, biome single, sentinel single)
 *   - Data Quality (grade OR-multi)
 *   - Resources (substring text)
 *
 * Auto-applies on close — filter state is bound directly to SystemsContext
 * via useFilters, so changes propagate live to the level grids behind the
 * modal. The Apply button is mostly UX reassurance.
 *
 * Filter options for the single-select dropdowns are fetched lazily from
 * /api/systems/filter-options when the modal first opens.
 */

import React, { useEffect, useState } from 'react'
import axios from 'axios'
import useFilters from '../hooks/useFilters'

const STAR_SWATCHES = [
  { value: 'Yellow', color: '#facc15' },
  { value: 'Red', color: '#ef4444' },
  { value: 'Blue', color: '#3b82f6' },
  { value: 'Green', color: '#10b981' },
  { value: 'Purple', color: '#a855f7' },
]

const ECONOMY_TIERS = ['T1', 'T2', 'T3']
const CONFLICT_LEVELS = ['Low', 'Medium', 'High']
const GRADES = ['S', 'A', 'B', 'C']

const PRESETS = {
  paradise: {
    label: '⭐ Paradise hunting',
    filters: { biome: 'Lush', is_complete: ['S', 'A'] },
  },
  wealthy: {
    label: '💎 Wealthy + safe',
    filters: { economy_level: ['T3'], conflict_level: ['Low'] },
  },
  lowsentinel: {
    label: '🛡️ Low sentinel',
    filters: { sentinel_level: 'Low' },
  },
  stubcleanup: {
    label: '🌑 Stub cleanup',
    filters: { is_complete: ['C'] },
  },
}

export default function FilterModal({ open, onClose }) {
  const { filters, setFilters, toggleMulti, setSingle, clearFilters } = useFilters()
  const [options, setOptions] = useState({})

  useEffect(() => {
    if (!open) return
    let cancelled = false
    axios.get('/api/systems/filter-options').then((r) => { if (!cancelled) setOptions(r.data || {}) }).catch(() => {})
    return () => { cancelled = true }
  }, [open])

  // Esc to close
  useEffect(() => {
    if (!open) return
    function onKey(e) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  function applyPreset(key) {
    const p = PRESETS[key]
    if (!p) return
    setFilters((prev) => ({ ...prev, ...p.filters }))
  }

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 backdrop-fade active"
      />
      <aside className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none modal-open">
        <div className="filter-modal-panel pointer-events-auto w-full max-w-[520px] max-h-[88vh] flex flex-col haven-card overflow-hidden p-0">
          <Header onClose={onClose} />

          <div className="p-5 space-y-5 overflow-y-auto scrollbar-thin flex-1 min-h-0">
            <Presets onApply={applyPreset} />

            <Section title="★ Star Properties" defaultOpen>
              <MultiSelectGrid
                label="Star Color"
                hint="any of selected"
                values={STAR_SWATCHES}
                renderItem={(item, active) => (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => toggleMulti('star_type', item.value)}
                    className="aspect-square rounded-lg"
                    style={{
                      background: item.color,
                      boxShadow: active ? '0 0 0 2px var(--app-primary), 0 0 0 4px var(--app-card)' : 'none',
                    }}
                    title={item.value}
                    aria-pressed={active}
                  />
                )}
                selected={filters.star_type || []}
                gridCols="grid-cols-6"
              />
            </Section>

            <Section title="⚖ Economy & Politics" defaultOpen>
              <SelectField
                label="Economy Type"
                value={filters.economy_type || ''}
                onChange={(v) => setSingle('economy_type', v)}
                options={options.economy_types || ['Wealthy', 'Trading', 'Scientific', 'Manufacturing', 'High Tech', 'Power Generation', 'Mining', 'Medical', 'Advertising', 'Agriculture', 'Fishing', 'Tourism', 'Pirate', 'Abandoned']}
                placeholder="Any economy"
              />
              <PillToggleGroup
                label="Economy Tier"
                hint="any of"
                items={ECONOMY_TIERS}
                selected={filters.economy_level || []}
                onToggle={(v) => toggleMulti('economy_level', v)}
                colorClass="pill-teal"
              />
              <PillToggleGroup
                label="Conflict Level"
                hint="any of"
                items={CONFLICT_LEVELS}
                selected={filters.conflict_level || []}
                onToggle={(v) => toggleMulti('conflict_level', v)}
                colorClass="pill-emerald"
              />
              <SelectField
                label="Dominant Lifeform"
                value={filters.dominant_lifeform || ''}
                onChange={(v) => setSingle('dominant_lifeform', v)}
                options={options.lifeforms || ['Gek', "Vy'keen", 'Korvax', 'Uninhabited', 'Robots', 'Atlas', 'Diplomats']}
                placeholder="Any lifeform"
              />
            </Section>

            <Section title="🌍 Planet Properties">
              <TriState
                label="Has Moons"
                value={filters.has_moons == null ? null : !!filters.has_moons}
                onChange={(v) => setSingle('has_moons', v)}
              />
              <div>
                <label className="text-[11px] block mb-1" style={{ color: 'var(--muted)' }}>Planet count</label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    placeholder="Min"
                    value={filters.min_planets ?? ''}
                    onChange={(e) => setSingle('min_planets', e.target.value ? parseInt(e.target.value, 10) : null)}
                    className="haven-input px-3 py-2 text-sm"
                  />
                  <input
                    type="number"
                    placeholder="Max"
                    value={filters.max_planets ?? ''}
                    onChange={(e) => setSingle('max_planets', e.target.value ? parseInt(e.target.value, 10) : null)}
                    className="haven-input px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <SelectField
                label="Biome"
                value={filters.biome || ''}
                onChange={(v) => setSingle('biome', v)}
                options={options.biomes || ['Lush', 'Barren', 'Exotic', 'Scorched', 'Frozen', 'Toxic', 'Radioactive', 'Dead', 'Marsh', 'Volcanic', 'Infested', 'Desolate', 'Airless', 'Gas Giant']}
                placeholder="Any biome"
              />
              <SelectField
                label="Sentinel Level"
                value={filters.sentinel_level || ''}
                onChange={(v) => setSingle('sentinel_level', v)}
                options={options.sentinels || ['Low', 'Standard', 'High', 'Aggressive', 'Frenzied', 'None']}
                placeholder="Any sentinel level"
              />
            </Section>

            <Section title="✓ Data Quality">
              <PillToggleGroup
                label="Completeness Grade"
                hint="any of"
                items={GRADES}
                selected={filters.is_complete || []}
                onToggle={(v) => toggleMulti('is_complete', v)}
                colorClass="pill-amber"
              />
            </Section>

            <Section title="⛏ Resources">
              <div>
                <label className="text-[11px] block mb-1" style={{ color: 'var(--muted)' }}>Specific resource present</label>
                <input
                  type="text"
                  placeholder="e.g. Indium, Activated Indium…"
                  value={filters.resource || ''}
                  onChange={(e) => setSingle('resource', e.target.value)}
                  className="haven-input w-full px-3 py-2 text-sm"
                />
              </div>
            </Section>
          </div>

          <div
            className="px-5 py-4 flex items-center gap-3 flex-shrink-0"
            style={{ background: 'var(--app-card)', borderTop: '1px solid var(--border-soft)' }}
          >
            <button onClick={clearFilters} className="haven-btn-ghost px-3 py-2.5 rounded-lg text-sm font-medium">
              Clear
            </button>
            <button onClick={onClose} className="haven-btn-primary flex-1 px-3 py-2.5 rounded-lg text-sm font-semibold">
              Apply &amp; close
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}

function Header({ onClose }) {
  return (
    <div
      className="px-5 py-4 flex items-center justify-between flex-shrink-0"
      style={{ background: 'var(--app-card)', borderBottom: '1px solid var(--border-soft)' }}
    >
      <div>
        <h3 className="text-lg font-semibold">Filters</h3>
        <p className="text-xs" style={{ color: 'var(--muted)' }}>Auto-applies on close · or hit Apply</p>
      </div>
      <button onClick={onClose} className="p-1.5 rounded hover:bg-white/5" aria-label="Close filters">
        <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}

function Presets({ onApply }) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--muted)' }}>
        Quick Presets
      </label>
      <div className="grid grid-cols-2 gap-2 mt-2">
        {Object.entries(PRESETS).map(([k, p]) => (
          <button
            key={k}
            type="button"
            onClick={() => onApply(k)}
            className="haven-btn-ghost px-3 py-2 rounded-lg text-xs text-left"
          >
            {p.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function Section({ title, defaultOpen, children }) {
  return (
    <details open={defaultOpen}>
      <summary className="flex items-center justify-between cursor-pointer">
        <span className="text-xs font-semibold uppercase tracking-wider">{title}</span>
        <svg className="chev w-4 h-4" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </summary>
      <div className="mt-3 space-y-3">{children}</div>
    </details>
  )
}

function MultiSelectGrid({ label, hint, values, renderItem, selected, gridCols }) {
  return (
    <div>
      <label className="text-[11px] mb-1 flex items-center justify-between" style={{ color: 'var(--muted)' }}>
        <span>
          {label}{' '}
          {hint && <span className="text-[10px]" style={{ color: 'var(--app-primary)' }}>({hint})</span>}
        </span>
        {selected.length > 0 && (
          <span style={{ color: 'var(--app-primary)' }}>{selected.length} selected</span>
        )}
      </label>
      <div className={`grid ${gridCols} gap-1.5`}>
        {values.map((item) => renderItem(item, selected.includes(item.value)))}
      </div>
    </div>
  )
}

function PillToggleGroup({ label, hint, items, selected, onToggle, colorClass }) {
  return (
    <div>
      <label className="text-[11px] mb-1 flex items-center justify-between" style={{ color: 'var(--muted)' }}>
        <span>
          {label}{' '}
          {hint && <span className="text-[10px]" style={{ color: 'var(--app-primary)' }}>({hint})</span>}
        </span>
      </label>
      <div className="grid grid-cols-4 gap-1.5">
        {items.map((item) => {
          const active = selected.includes(item)
          return (
            <button
              key={item}
              type="button"
              onClick={() => onToggle(item)}
              className={active ? `pill ${colorClass} justify-center px-2 py-2 rounded text-xs font-bold` : 'haven-btn-ghost px-2 py-2 rounded text-xs'}
              aria-pressed={active}
            >
              {item}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function SelectField({ label, value, onChange, options, placeholder }) {
  return (
    <div>
      <label className="text-[11px] block mb-1" style={{ color: 'var(--muted)' }}>{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="haven-input w-full px-3 py-2 text-sm"
      >
        <option value="">{placeholder}</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

function TriState({ label, value, onChange }) {
  return (
    <div>
      <label className="text-[11px] mb-1 flex items-center justify-between" style={{ color: 'var(--muted)' }}>
        <span>{label}</span>
        <span style={{ color: 'var(--app-primary)' }}>{value === true ? 'Yes' : value === false ? 'No' : 'Any'}</span>
      </label>
      <div className="grid grid-cols-3 gap-1.5">
        <button
          type="button"
          onClick={() => onChange(null)}
          className={value == null ? 'pill pill-blue justify-center px-2 py-1.5 rounded text-xs font-medium' : 'haven-btn-ghost px-2 py-1.5 rounded text-xs'}
        >
          Any
        </button>
        <button
          type="button"
          onClick={() => onChange(true)}
          className={value === true ? 'pill pill-blue justify-center px-2 py-1.5 rounded text-xs font-medium' : 'haven-btn-ghost px-2 py-1.5 rounded text-xs'}
        >
          Yes
        </button>
        <button
          type="button"
          onClick={() => onChange(false)}
          className={value === false ? 'pill pill-blue justify-center px-2 py-1.5 rounded text-xs font-medium' : 'haven-btn-ghost px-2 py-1.5 rounded text-xs'}
        >
          No
        </button>
      </div>
    </div>
  )
}
