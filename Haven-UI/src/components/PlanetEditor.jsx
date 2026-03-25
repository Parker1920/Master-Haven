import React, { useState } from 'react'
import CelestialBodyEditor from './CelestialBodyEditor'
import MoonEditor from './MoonEditor'
import Modal from './Modal'

/**
 * Planet editor - thin wrapper around CelestialBodyEditor that adds moon management.
 * Props: planet, index, onChange, onRemove, onSave.
 */
export default function PlanetEditor({ planet, index, onChange, onRemove, onSave }) {
  const [moonModalOpen, setMoonModalOpen] = useState(false)
  const [editingMoonIndex, setEditingMoonIndex] = useState(null)
  const [editingMoon, setEditingMoon] = useState(null)

  function setField(k, v) {
    const p = { ...planet, [k]: v }
    onChange(index, p)
  }

  function openAddMoonModal() {
    setEditingMoonIndex(-1)
    setEditingMoon({
      name: '', biome: '', weather: '', sentinel: 'None',
      fauna: 'N/A', flora: 'N/A', materials: '', notes: '', photo: null,
      has_rings: 0, is_dissonant: 0, is_infested: 0,
      extreme_weather: 0, water_world: 0, vile_brood: 0, exotic_trophy: ''
    })
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
    >
      {/* Moon management — planet-only feature */}
      <div className="mt-3 mb-1">
        <button type="button" onClick={openAddMoonModal} className="px-3 py-1.5 bg-green-600 rounded text-sm">Add Moon</button>
      </div>
      <div className="mt-1">
        {(planet.moons || []).map((m, i) => (
          <div key={i}>
            <MoonEditor index={i} moon={m} onChange={updateMoon} onRemove={removeMoon} />
            <div className="mt-1">
              <button type="button" onClick={() => editMoon(i)} className="px-2 py-1 bg-sky-600 text-white rounded">Edit Moon</button>
            </div>
          </div>
        ))}
      </div>
      {moonModalOpen && (
        <Modal title={editingMoonIndex === -1 ? 'Add Moon' : 'Edit Moon'} onClose={() => setMoonModalOpen(false)}>
          <MoonEditor moon={editingMoon} index={editingMoonIndex} onChange={(idx, m) => setEditingMoon(m)} onSave={commitMoon} onRemove={() => setMoonModalOpen(false)} />
        </Modal>
      )}
    </CelestialBodyEditor>
  )
}
