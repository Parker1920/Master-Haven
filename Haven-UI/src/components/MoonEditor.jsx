import React from 'react'

export default function MoonEditor({moon, index, onChange, onRemove, onSave}){
  function setField(k, v){
    const m = {...moon, [k]: v}
    onChange(index, m)
  }
  return (
    <div className="p-2 border rounded my-2 bg-white/5">
      <div className="flex items-center justify-between">
        <div>
          <label className="block text-sm">Moon Name</label>
          <input placeholder="Moon name" className="mt-1 p-1 rounded w-full" value={moon.name || ''} onChange={e => setField('name', e.target.value)} />
        </div>
        <div className="w-40">
          <label className="block text-sm">Sentinel</label>
          <select className="w-full mt-1 p-1 rounded" value={moon.sentinel || 'None'} onChange={e => setField('sentinel', e.target.value)}>
            <option>None</option>
            <option>Low</option>
            <option>Medium</option>
            <option>High</option>
            <option>Aggressive</option>
          </select>
        </div>
        <div className="pl-2">
          <button type="button" onClick={() => onRemove(index)} className="px-2 py-1 bg-red-600 rounded">Remove Moon</button>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <div>
          <label className="block text-sm">Flora</label>
          <select aria-label="Moon Flora" className="mt-1 p-1 rounded w-full" value={moon.flora || 'N/A'} onChange={e => setField('flora', e.target.value)}>
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
          <select aria-label="Moon Fauna" className="mt-1 p-1 rounded w-full" value={moon.fauna || 'N/A'} onChange={e => setField('fauna', e.target.value)}>
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
          <label className="block text-sm">Materials</label>
          <input aria-label="Moon Materials" placeholder="Comma separated" className="mt-1 p-1 rounded w-full" value={moon.materials || ''} onChange={e => setField('materials', e.target.value)} />
        </div>
        <div>
          <label className="block text-sm">Notes</label>
          <input placeholder="Optional notes" className="mt-1 p-1 rounded w-full" value={moon.notes || ''} onChange={e => setField('notes', e.target.value)} />
          {onSave && (
            <button type="button" onClick={() => onSave(moon)} className="ml-3 mt-2 px-3 py-1 bg-blue-600 rounded">Save</button>
          )}
        </div>
      </div>
    </div>
  )
}
