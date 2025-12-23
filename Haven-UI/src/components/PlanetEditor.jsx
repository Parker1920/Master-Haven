import React, { useState } from 'react'
import MoonEditor from './MoonEditor'
import { uploadPhoto } from '../utils/api'
import Modal from './Modal'

export default function PlanetEditor({ planet, index, onChange, onRemove, onSave }){
  const [uploading, setUploading] = useState(false)
  const [moonModalOpen, setMoonModalOpen] = useState(false)
  const [editingMoonIndex, setEditingMoonIndex] = useState(null)
  const [editingMoon, setEditingMoon] = useState(null)

  function setField(k, v){
    const p = {...planet, [k]: v}
    onChange(index, p)
  }

  function openAddMoonModal(){
    setEditingMoonIndex(-1)
    // Initialize ALL moon fields with defaults to ensure they're saved
    setEditingMoon({
      name: '',
      sentinel: 'None',
      fauna: 'N/A',
      flora: 'N/A',
      materials: '',
      orbit_radius: 0.5,
      orbit_speed: 0,
      notes: ''
    })
    setMoonModalOpen(true)
  }

  function updateMoon(i, val){
    const moons = [...(planet.moons || [])]
    moons[i] = val
    setField('moons', moons)
  }

  function removeMoon(i){
    const moons = [...(planet.moons || [])]
    moons.splice(i,1)
    setField('moons', moons)
  }

  function editMoon(i){
    setEditingMoonIndex(i)
    setEditingMoon(planet.moons[i])
    setMoonModalOpen(true)
  }

  function commitMoon(moon){
    const moons = [...(planet.moons || [])]
    if(editingMoonIndex === -1){
      moons.push(moon)
    } else {
      moons[editingMoonIndex] = moon
    }
    setField('moons', moons)
    setMoonModalOpen(false)
  }

  async function upload(e){
    setUploading(true)
    try{
      const file = e.target.files[0]
      if(!file) return
      const res = await uploadPhoto(file)
      setField('photo', res.path)
    }catch(err){
      alert('Upload failed: ' + err)
    }
    setUploading(false)
  }

  return (
    <div className="p-3 my-3 border rounded bg-white/5">
      <div className="flex items-center justify-between">
        <div className="w-full pr-2">
          <label className="block text-sm">Planet Name</label>
          <input className="mt-1 p-1 rounded w-full" value={planet.name || ''} onChange={e => setField('name', e.target.value)} placeholder="Planet name" />
        </div>
        <div className="w-40">
          <label className="block text-sm">Sentinel</label>
          <select className="w-full mt-1 p-1 rounded" value={planet.sentinel || 'None'} onChange={e => setField('sentinel', e.target.value)}>
            <option>None</option>
            <option>Low</option>
            <option>Medium</option>
            <option>High</option>
            <option>Aggressive</option>
          </select>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm">Flora</label>
          <select aria-label="Planet Flora" className="mt-1 p-1 rounded w-full" value={planet.flora || 'N/A'} onChange={e => setField('flora', e.target.value)}>
            <option value="N/A">N/A</option>
            <option value="None">None</option>
            <option value="Sparse">Sparse</option>
            <option value="Low">Low</option>
            <option value="Moderate">Moderate</option>
            <option value="Abundant">Abundant</option>
            <option value="Rich">Rich</option>
          </select>
        </div>
        <div>
          <label className="block text-sm">Fauna</label>
          <select aria-label="Planet Fauna" className="mt-1 p-1 rounded w-full" value={planet.fauna || 'N/A'} onChange={e => setField('fauna', e.target.value)}>
            <option value="N/A">N/A</option>
            <option value="None">None</option>
            <option value="Sparse">Sparse</option>
            <option value="Low">Low</option>
            <option value="Moderate">Moderate</option>
            <option value="Abundant">Abundant</option>
            <option value="Rich">Rich</option>
          </select>
        </div>
        <div>
          <label className="block text-sm">Resources / Materials</label>
          <input aria-label="Planet Materials" placeholder="Comma separated" className="mt-1 p-1 rounded w-full" value={planet.materials || ''} onChange={e => setField('materials', e.target.value)} />
        </div>
        <div>
          <label className="block text-sm">Base Location</label>
          <input aria-label="Planet Base" placeholder="Base location" className="mt-1 p-1 rounded w-full" value={planet.base_location || ''} onChange={e => setField('base_location', e.target.value)} />
        </div>
        <div>
          <label className="block text-sm">Photo</label>
          <input aria-label="Planet Photo" type="file" onChange={upload} className="mt-1" />
          {uploading && <div className="muted text-sm mt-1">Uploading...</div>}
          {!uploading && planet.photo && (
            <div className="mt-2 relative inline-block group">
              <img
                src={planet.photo.startsWith('http') ? planet.photo : `/haven-ui-photos/${planet.photo.replace(/^photos[\\/]/, '').split(/[\\/]/).pop()}`}
                alt="Planet photo"
                className="max-w-xs max-h-32 rounded border border-gray-600"
              />
              <button
                type="button"
                onClick={() => setField('photo', null)}
                className="absolute -top-2 -right-2 w-6 h-6 bg-red-600 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-sm font-bold"
                title="Remove photo"
              >
                X
              </button>
              <div className="text-xs text-gray-400 mt-1 break-all">{planet.photo}</div>
            </div>
          )}
        </div>
        <div>
          <label className="block text-sm">Notes</label>
          <input placeholder="Notes" className="mt-1 p-1 rounded w-full" value={planet.notes || ''} onChange={e => setField('notes', e.target.value)} />
        </div>
      </div>
      <div className="mt-2">
        <button type="button" onClick={openAddMoonModal} className="px-3 py-1 bg-green-600 rounded">➕ Add Moon</button>
        <button type="button" onClick={() => onRemove(index)} className="ml-3 px-3 py-1 bg-red-600 rounded">Remove Planet</button>
        {onSave && (
          <button type="button" onClick={() => onSave(planet)} className="ml-3 px-3 py-1 bg-blue-600 rounded">Save</button>
        )}
      </div>
      <div className="mt-3">
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
          <MoonEditor moon={editingMoon} index={editingMoonIndex} onChange={(idx,m)=>setEditingMoon(m)} onSave={commitMoon} onRemove={() => { setMoonModalOpen(false) }} />
        </Modal>
      )}
    </div>
  )
}
