import React, { useState } from 'react'
import { uploadPhoto } from '../utils/api'
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

export default function MoonEditor({moon, index, onChange, onRemove, onSave}){
  const [uploading, setUploading] = useState(false)

  function setField(k, v){
    const m = {...moon, [k]: v}
    onChange(index, m)
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
    <div className="p-2 border rounded my-2 bg-white/5">
      {/* Top row: Moon Name, Biome, Weather - stacks on mobile */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <div>
          <label className="block text-sm">Moon Name</label>
          <input placeholder="Moon name" className="mt-1 p-1 rounded w-full" value={moon.name || ''} onChange={e => setField('name', e.target.value)} />
        </div>
        <div>
          <label className="block text-sm">Biome</label>
          <div className="mt-1">
            <SearchableSelect
              options={biomeOptions}
              value={moon.biome || ''}
              onChange={(val) => setField('biome', val)}
              placeholder="Search biome..."
            />
          </div>
        </div>
        <div>
          <label className="block text-sm">Weather</label>
          <div className="mt-1">
            <SearchableSelect
              options={weatherOptions}
              value={moon.weather || ''}
              onChange={(val) => setField('weather', val)}
              placeholder="Search weather..."
            />
          </div>
        </div>
      </div>
      {/* Second row: Sentinels, Flora, Fauna, Materials, Notes, Photo */}
      <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        <div>
          <label className="block text-sm">Sentinels</label>
          <div className="mt-1">
            <SearchableSelect
              options={sentinelOptions}
              value={moon.sentinel || ''}
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
              value={moon.flora || ''}
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
              value={moon.fauna || ''}
              onChange={(val) => setField('fauna', val)}
              placeholder="Search fauna..."
            />
          </div>
        </div>
        <div>
          <label className="block text-sm">Materials</label>
          <div className="mt-1">
            <SearchableSelect
              options={resourcesOptions}
              value={moon.materials || ''}
              onChange={(val) => setField('materials', val)}
              placeholder="Search resources..."
              isMulti={true}
            />
          </div>
        </div>
        <div>
          <label className="block text-sm">Notes</label>
          <input placeholder="Optional notes" className="mt-1 p-1 rounded w-full" value={moon.notes || ''} onChange={e => setField('notes', e.target.value)} />
        </div>
        <div>
          <label className="block text-sm">Photo</label>
          <input aria-label="Moon Photo" type="file" onChange={upload} className="mt-1" />
          {uploading && <div className="muted text-sm mt-1">Uploading...</div>}
          {!uploading && moon.photo && (
            <div className="mt-2 relative inline-block group">
              <img
                src={moon.photo.startsWith('http') ? moon.photo : `/haven-ui-photos/${moon.photo.replace(/^photos[\\/]/, '').split(/[\\/]/).pop()}`}
                alt="Moon photo"
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
              <div className="text-xs text-gray-400 mt-1 break-all">{moon.photo}</div>
            </div>
          )}
        </div>
      </div>
      <div className="mt-3 flex justify-between items-center">
        <div>
          {onSave && (
            <button type="button" onClick={() => onSave(moon)} className="px-3 py-1.5 bg-blue-600 rounded text-sm">Save</button>
          )}
        </div>
        <button type="button" onClick={() => onRemove(index)} className="px-3 py-1.5 bg-red-600 rounded text-sm">Remove Moon</button>
      </div>
    </div>
  )
}
