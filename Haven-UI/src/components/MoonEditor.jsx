import React, { useState } from 'react'
import { uploadPhoto } from '../utils/api'

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
      <div className="flex items-center justify-between gap-2">
        <div className="flex-1">
          <label className="block text-sm">Moon Name</label>
          <input placeholder="Moon name" className="mt-1 p-1 rounded w-full" value={moon.name || ''} onChange={e => setField('name', e.target.value)} />
        </div>
        <div className="w-28">
          <label className="block text-sm">Biome</label>
          <select className="w-full mt-1 p-1 rounded" value={moon.biome || ''} onChange={e => setField('biome', e.target.value)}>
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
        <div className="w-32">
          <label className="block text-sm">Weather</label>
          <select className="w-full mt-1 p-1 rounded" value={moon.weather || ''} onChange={e => setField('weather', e.target.value)}>
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
        <div className="pl-2">
          <button type="button" onClick={() => onRemove(index)} className="px-2 py-1 bg-red-600 rounded">Remove Moon</button>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2">
        <div>
          <label className="block text-sm">Sentinels</label>
          <select className="w-full mt-1 p-1 rounded" value={moon.sentinel || ''} onChange={e => setField('sentinel', e.target.value)}>
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
          <select aria-label="Moon Flora" className="mt-1 p-1 rounded w-full" value={moon.flora || ''} onChange={e => setField('flora', e.target.value)}>
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
          <select aria-label="Moon Fauna" className="mt-1 p-1 rounded w-full" value={moon.fauna || ''} onChange={e => setField('fauna', e.target.value)}>
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
          <label className="block text-sm">Materials</label>
          <input aria-label="Moon Materials" placeholder="Comma separated" className="mt-1 p-1 rounded w-full" value={moon.materials || ''} onChange={e => setField('materials', e.target.value)} />
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
              <div className="text-xs text-gray-400 mt-1 break-all">{moon.photo}</div>
            </div>
          )}
        </div>
      </div>
      <div className="mt-2">
        {onSave && (
          <button type="button" onClick={() => onSave(moon)} className="px-3 py-1 bg-blue-600 rounded">Save</button>
        )}
      </div>
    </div>
  )
}
