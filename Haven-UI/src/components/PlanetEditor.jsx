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
      biome: '',
      weather: '',
      sentinel: 'None',
      fauna: 'N/A',
      flora: 'N/A',
      materials: '',
      notes: '',
      photo: null
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
      <div className="flex items-center justify-between gap-2">
        <div className="flex-1">
          <label className="block text-sm">Planet Name</label>
          <input className="mt-1 p-1 rounded w-full" value={planet.name || ''} onChange={e => setField('name', e.target.value)} placeholder="Planet name" />
        </div>
        <div className="w-32">
          <label className="block text-sm">Biome</label>
          <select className="w-full mt-1 p-1 rounded" value={planet.biome || ''} onChange={e => setField('biome', e.target.value)}>
            <option value="">-- Select --</option>
            <option value="Lush">Lush</option>
            <option value="Barren">Barren</option>
            <option value="Dead">Dead</option>
            <option value="Scorched">Scorched</option>
            <option value="Frozen">Frozen</option>
            <option value="Toxic">Toxic</option>
            <option value="Radioactive">Radioactive</option>
            <option value="Marsh">Marsh</option>
            <option value="Exotic">Exotic</option>
          </select>
        </div>
        <div className="w-36">
          <label className="block text-sm">Weather</label>
          <select className="w-full mt-1 p-1 rounded" value={planet.weather || ''} onChange={e => setField('weather', e.target.value)}>
            <option value="">-- Select --</option>
            <option value="Clear">Clear</option>
            <option value="Dusty">Dusty</option>
            <option value="Humid">Humid</option>
            <option value="Superheated">Superheated</option>
            <option value="Freezing">Freezing</option>
            <option value="Toxic Rain">Toxic Rain</option>
            <option value="Irradiated">Irradiated</option>
            <option value="Extreme Storms">Extreme Storms</option>
            <option value="Electric">Electric</option>
            <option value="Blissful">Blissful</option>
          </select>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-3">
        <div>
          <label className="block text-sm">Sentinels</label>
          <select className="w-full mt-1 p-1 rounded" value={planet.sentinel || ''} onChange={e => setField('sentinel', e.target.value)}>
            <option value="">-- Select --</option>
            <option value="None">None</option>
            <option value="Limited">Limited</option>
            <option value="Low Security">Low Security</option>
            <option value="Normal">Normal</option>
            <option value="High Security">High Security</option>
            <option value="Aggressive">Aggressive</option>
            <option value="Frenzied">Frenzied</option>
            <option value="Corrupted">Corrupted</option>
          </select>
        </div>
        <div>
          <label className="block text-sm">Flora</label>
          <select aria-label="Planet Flora" className="mt-1 p-1 rounded w-full" value={planet.flora || ''} onChange={e => setField('flora', e.target.value)}>
            <option value="">-- Select --</option>
            <option value="None">None</option>
            <option value="Sparse">Sparse</option>
            <option value="Low">Low</option>
            <option value="Average">Average</option>
            <option value="High">High</option>
            <option value="Abundant">Abundant</option>
            <option value="Lush">Lush</option>
          </select>
        </div>
        <div>
          <label className="block text-sm">Fauna</label>
          <select aria-label="Planet Fauna" className="mt-1 p-1 rounded w-full" value={planet.fauna || ''} onChange={e => setField('fauna', e.target.value)}>
            <option value="">-- Select --</option>
            <option value="None">None</option>
            <option value="Sparse">Sparse</option>
            <option value="Low">Low</option>
            <option value="Ample">Ample</option>
            <option value="Full">Full</option>
            <option value="Bountiful">Bountiful</option>
            <option value="Copious">Copious</option>
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
