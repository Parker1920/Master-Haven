import React, { useState } from 'react'
import MoonEditor from './MoonEditor'
import { uploadPhoto } from '../utils/api'
import Modal from './Modal'
import SearchableSelect from './SearchableSelect'
import {
  biomeAdjectives,
  weatherAdjectives,
  sentinelAdjectives,
  floraAdjectives,
  faunaAdjectives,
  resourcesList,
  toSelectOptions
} from '../data/adjectives'

// Pre-compute options for react-select
const biomeOptions = toSelectOptions(biomeAdjectives)
const weatherOptions = toSelectOptions(weatherAdjectives)
const sentinelOptions = toSelectOptions(sentinelAdjectives)
const floraOptions = toSelectOptions(floraAdjectives)
const faunaOptions = toSelectOptions(faunaAdjectives)
const resourcesOptions = toSelectOptions(resourcesList)

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
      {/* Top row: Planet Name, Biome, Weather - stacks on mobile */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div>
          <label className="block text-sm">Planet Name</label>
          <input className="mt-1 p-1 rounded w-full" value={planet.name || ''} onChange={e => setField('name', e.target.value)} placeholder="Planet name" />
        </div>
        <div>
          <label className="block text-sm">Biome</label>
          <div className="mt-1">
            <SearchableSelect
              options={biomeOptions}
              value={planet.biome || ''}
              onChange={(val) => setField('biome', val)}
              placeholder="Search biome..."
            />
          </div>
        </div>
        <div className="sm:col-span-2 lg:col-span-1">
          <label className="block text-sm">Weather</label>
          <div className="mt-1">
            <SearchableSelect
              options={weatherOptions}
              value={planet.weather || ''}
              onChange={(val) => setField('weather', val)}
              placeholder="Search weather..."
            />
          </div>
        </div>
      </div>
      {/* Second row: Sentinels, Flora, Fauna, Resources, Base, Photo, Notes */}
      <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div>
          <label className="block text-sm">Sentinels</label>
          <div className="mt-1">
            <SearchableSelect
              options={sentinelOptions}
              value={planet.sentinel || ''}
              onChange={(val) => setField('sentinel', val)}
              placeholder="Search sentinels..."
            />
          </div>
        </div>
        <div>
          <label className="block text-sm">Flora</label>
          <div className="mt-1">
            <SearchableSelect
              options={floraOptions}
              value={planet.flora || ''}
              onChange={(val) => setField('flora', val)}
              placeholder="Search flora..."
            />
          </div>
        </div>
        <div>
          <label className="block text-sm">Fauna</label>
          <div className="mt-1">
            <SearchableSelect
              options={faunaOptions}
              value={planet.fauna || ''}
              onChange={(val) => setField('fauna', val)}
              placeholder="Search fauna..."
            />
          </div>
        </div>
        <div>
          <label className="block text-sm">Resources / Materials</label>
          <div className="mt-1">
            <SearchableSelect
              options={resourcesOptions}
              value={planet.materials || ''}
              onChange={(val) => setField('materials', val)}
              placeholder="Search resources..."
              isMulti={true}
            />
          </div>
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
                className="max-w-full sm:max-w-xs max-h-32 rounded border border-gray-600"
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
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" onClick={openAddMoonModal} className="px-3 py-1.5 bg-green-600 rounded text-sm">➕ Add Moon</button>
        <button type="button" onClick={() => onRemove(index)} className="px-3 py-1.5 bg-red-600 rounded text-sm">Remove Planet</button>
        {onSave && (
          <button type="button" onClick={() => onSave(planet)} className="px-3 py-1.5 bg-blue-600 rounded text-sm">Save</button>
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
