import React, { useState } from 'react'
import CelestialBodyEditor from './CelestialBodyEditor'
import MoonEditor from './MoonEditor'
import Modal from './Modal'
import { MOON_DEFAULTS } from '../data/bodyDefaults'

/**
 * Planet editor - thin wrapper around CelestialBodyEditor that adds moon management.
 * Props:
 *   planet, index, onChange, onRemove, onSave, openHelp
 *   planets        - full planet list (for the moon "Orbits" reassignment dropdown)
 *   onReassignMoon - (moonIdx, toPlanetIdx) => void, move a moon to another planet
 */
export default function PlanetEditor({ planet, index, onChange, onRemove, onSave, openHelp, planets = [], onReassignMoon }) {
  const [moonModalOpen, setMoonModalOpen] = useState(false)
  const [editingMoonIndex, setEditingMoonIndex] = useState(null)
  const [editingMoon, setEditingMoon] = useState(null)

  // 6-body cap (planets + moons combined). Disable "Add Moon" at the cap.
  const totalBodies = (planets || []).reduce((n, p) => n + 1 + ((p.moons || []).length), 0)
  const atCap = (planets && planets.length) ? totalBodies >= 6 : false

  function setField(k, v) {
    const p = { ...planet, [k]: v }
    onChange(index, p)
  }

  function openAddMoonModal() {
    setEditingMoonIndex(-1)
    setEditingMoon({ ...MOON_DEFAULTS })
    setMoonModalOpen(true)
  }

  function updateMoon(i, val) {
    const moons = [...(planet.moons || [])]
    moons[i] = val
    setField('moons', moons)
  }

  function removeMoon(i) {
    const moons = [...(planet.moons || [])]
    moons.splice(i, 1)
    setField('moons', moons)
  }

  function editMoon(i) {
    setEditingMoonIndex(i)
    setEditingMoon(planet.moons[i])
    setMoonModalOpen(true)
  }

  function commitMoon(moon) {
    const moons = [...(planet.moons || [])]
    if (editingMoonIndex === -1) {
      moons.push(moon)
    } else {
      moons[editingMoonIndex] = moon
    }
    setField('moons', moons)
    setMoonModalOpen(false)
  }

  return (
    <CelestialBodyEditor
      type="planet"
      body={planet}
      index={index}
      onChange={onChange}
      onRemove={onRemove}
      onSave={onSave}
      openHelp={openHelp}
    >
      {/* Moon management — planet-only feature */}
      <div className="mt-3 mb-1">
        <button
          type="button"
          onClick={openAddMoonModal}
          disabled={atCap}
          className="px-3 py-1.5 bg-green-600 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          title={atCap ? 'System already has 6 celestial bodies (planets + moons)' : 'Add a moon to this planet'}
        >
          Add Moon
        </button>
      </div>
      <div className="mt-1">
        {(planet.moons || []).map((m, i) => (
          <div key={i}>
            <MoonEditor index={i} moon={m} onChange={updateMoon} onRemove={removeMoon} />
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              <button type="button" onClick={() => editMoon(i)} className="px-2 py-1 bg-sky-600 text-white rounded">Edit Moon</button>
              {planets.length > 1 && onReassignMoon && (
                <label className="text-xs opacity-80 flex items-center gap-1">
                  Orbits:
                  <select
                    value={index}
                    onChange={(e) => onReassignMoon(i, Number(e.target.value))}
                    className="p-1 rounded text-xs"
                    style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                  >
                    {planets.map((pp, pi) => (
                      <option key={pi} value={pi}>{pp.name || `Planet ${pi + 1}`}</option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          </div>
        ))}
      </div>
      {moonModalOpen && (
        <Modal title={editingMoonIndex === -1 ? 'Add Moon' : 'Edit Moon'} onClose={() => setMoonModalOpen(false)}>
          <MoonEditor moon={editingMoon} index={editingMoonIndex} onChange={(idx, m) => setEditingMoon(m)} onSave={commitMoon} onRemove={() => setMoonModalOpen(false)} openHelp={openHelp} />
        </Modal>
      )}
    </CelestialBodyEditor>
  )
}
