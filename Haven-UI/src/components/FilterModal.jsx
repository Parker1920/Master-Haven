/**
 * FilterModal — centered modal for Systems Tab v2.0 filter editing.
 *
 * Sections:
 *   - Quick Presets at top
 *   - Star Properties (color OR-multi, stellar class single)
 *   - Economy & Politics (type single, tier OR-multi, conflict OR-multi, lifeform single)
 *   - Planet Properties (has_moons tri-state, planet count range, biome single, weather single, sentinel single)
 *   - Data Quality (grade OR-multi)
 *   - Resources (single dropdown picked from real options)
 *
 * Auto-applies on close — filter state is URL-synced via SystemsContext, so
 * changes propagate live to the level grids behind the modal AND survive
 * page refresh / sharing.
 *
 * All dropdown options come from /api/systems/filter-options scoped by the
 * current reality + galaxy. We do NOT keep hardcoded fallback lists — if the
 * endpoint returns nothing, the dropdown shows "(no options)" so users don't
 * pick a stale value that returns zero results.
 *
 * Sentinel/lifeform key fix (2026-05-15): pre-fix the modal read
 * `options.lifeforms` / `options.sentinels`, but the backend returns
 * `dominant_lifeforms` / `sentinel_levels`. Every dropdown silently fell back
 * to a hardcoded list that included values like "Low" sentinel — which the
 * NMS extractor never writes, so picking it returned zero systems.
 */

import React, { useEffect, useState } from 'react'
import axios from 'axios'
import useFilters from '../hooks/useFilters'
import { useSystems } from '../contexts/SystemsContext'

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
  stubcleanup: {
    label: '🌑 Stub cleanup',
    filters: { is_complete: ['C'] },
  },
}

export default function FilterModal({ open, onClose }) {
  const { filters, setFilters, toggleMulti, setSingle, clearFilters } = useFilters()
  const { reality, galaxy } = useSystems()
  const [options, setOptions] = useState({})

  useEffect(() => {
    if (!open) return
    let cancelled = false
    const params = new URLSearchParams()
    if (reality) params.append('reality', reality)
    if (galaxy) params.append('galaxy', galaxy)
    axios.get(`/api/systems/filter-options?${params.toString()}`)
      .then((r) => { if (!cancelled) setOptions(r.data || {}) })
      .catch(() => { if (!cancelled) setOptions({}) })
    return () => { cancelled = true }
  }, [open, reality, galaxy])

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

            <Section title="★ Star Class" defaultOpen={false}>
              <SelectField
                label="Stellar Classification"
                value={filters.stellar_classification || ''}
                onChange={(v) => setSingle('stellar_classification', v)}
                options={options.stellar_classifications || []}
                placeholder="Any stellar class"
              />
            </Section>

            <Section title="⚖ Economy & Politics" defaultOpen>
              <SelectField
                label="Economy Type"
                value={filters.economy_type || ''}
                onChange={(v) => setSingle('economy_type', v)}
                options={options.economy_types || []}
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
                options={options.dominant_lifeforms || []}
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
                options={options.biomes || []}
                placeholder="Any biome"
              />
              <SelectField
                label="Weather"
                value={filters.weather || ''}
                onChange={(v) => setSingle('weather', v)}
                options={options.weather_types || []}
                placeholder="Any weather"
              />
              <SelectField
                label="Sentinel Level"
                value={filters.sentinel_level || ''}
                onChange={(v) => setSingle('sentinel_level', v)}
                options={options.sentinel_levels || []}
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
              <MultiSelectField
                label="Resources present"
                hint="any of"
                selected={filters.resource || []}
                onToggle={(v) => toggleMulti('resource', v)}
                options={options.resources || []}
                placeholder="Add a resource…"
              />
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
  // When the current reality+galaxy scope has zero values for this field,
  // surface "(no options)" instead of the optimistic "Any X" placeholder
  // so users don't waste a click expanding an empty dropdown. Per the
  // v1.66.0 spec — was only wired for the Resources field; now universal.
  const isEmpty = !options || options.length === 0
  const effectivePlaceholder = isEmpty ? '(no options)' : placeholder
  return (
    <div>
      <label className="text-[11px] block mb-1" style={{ color: 'var(--muted)' }}>{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="haven-input w-full px-3 py-2 text-sm"
        disabled={isEmpty}
      >
        <option value="">{effectivePlaceholder}</option>
        {(options || []).map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

function MultiSelectField({ label, hint, selected, onToggle, options, placeholder }) {
  // Dropdown-driven multi-select for long option lists (e.g. ~40 resources):
  // pick from the dropdown to add a chip, click a chip's × to remove it. The
  // dropdown only lists not-yet-selected options, so picking always adds.
  // selected is an array (filters.resource); toggleMulti adds/removes.
  const isEmpty = !options || options.length === 0
  const sel = Array.isArray(selected) ? selected : []
  const available = (options || []).filter((o) => !sel.includes(o))
  return (
    <div>
      <label className="text-[11px] mb-1 flex items-center justify-between" style={{ color: 'var(--muted)' }}>
        <span>
          {label}{' '}
          {hint && <span className="text-[10px]" style={{ color: 'var(--app-primary)' }}>({hint})</span>}
        </span>
        {sel.length > 0 && <span style={{ color: 'var(--app-primary)' }}>{sel.length} selected</span>}
      </label>
      {sel.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {sel.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onToggle(s)}
              className="pill pill-teal px-2 py-1 rounded text-xs flex items-center gap-1"
              title={`Remove ${s}`}
            >
              <span>{s}</span>
              <span aria-hidden>×</span>
            </button>
          ))}
        </div>
      )}
      <select
        value=""
        onChange={(e) => { if (e.target.value) onToggle(e.target.value) }}
        className="haven-input w-full px-3 py-2 text-sm"
        disabled={isEmpty}
      >
        <option value="">{isEmpty ? '(no options)' : placeholder}</option>
        {available.map((o) => <option key={o} value={o}>{o}</option>)}
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
