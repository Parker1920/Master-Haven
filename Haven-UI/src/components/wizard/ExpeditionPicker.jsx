import React, { useEffect, useState } from 'react'
import { getExpeditions, createExpedition } from '../../utils/api'
import Button from '../Button'

// Wizard v1 expedition picker (mockup #v11-expedition-select 5860-5885,
// v11ChangeExpedition 9769). Lets the submitter:
//   - Choose an existing community expedition
//   - "+ Create new expedition" inline (logged-in only)
//   - See an "📍 Active expedition" pill once selected
//
// Per Parker's Phase 0 answer #5: the whole community can see expeditions.
//
// Props:
//   value: number | null
//   onChange(id|null, expeditionObj?)
//   disabled?: boolean — set when caller is anonymous (server enforces)
export default function ExpeditionPicker({ value, onChange, disabled }) {
  const [expeditions, setExpeditions] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [creatingErr, setCreatingErr] = useState(null)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    getExpeditions({ status: 'active' })
      .then((d) => {
        if (mounted) setExpeditions(d.expeditions || [])
      })
      .catch(() => mounted && setExpeditions([]))
      .finally(() => mounted && setLoading(false))
    return () => { mounted = false }
  }, [])

  const selected = expeditions.find((e) => e.id === value)

  async function handleCreate() {
    setCreatingErr(null)
    if (!newName.trim()) return
    try {
      const res = await createExpedition({ name: newName.trim() })
      const exp = res.expedition
      setExpeditions((prev) => [exp, ...prev])
      onChange(exp.id, exp)
      setNewName('')
      setCreating(false)
    } catch (err) {
      setCreatingErr(err.response?.data?.detail || err.message || 'Failed to create')
    }
  }

  return (
    <div>
      {selected ? (
        <div
          className="flex items-center justify-between gap-3 p-3 rounded"
          style={{ backgroundColor: 'rgba(168, 85, 247, 0.12)', border: '1px solid var(--app-accent-2)' }}
        >
          <div className="min-w-0">
            <span className="inline-block text-xs font-semibold mr-2" style={{ color: 'var(--app-accent-2)' }}>📍 Active expedition</span>
            <span className="font-semibold">{selected.name}</span>
            <span className="text-xs opacity-60 ml-2">
              {selected.system_count || 0} systems
            </span>
          </div>
          <button
            type="button"
            onClick={() => onChange(null, null)}
            className="text-xs opacity-70 hover:opacity-100 underline"
          >
            Clear
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="flex-1 min-w-[200px] p-2 rounded"
            style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
            value={value || ''}
            onChange={(e) => {
              const id = e.target.value ? Number(e.target.value) : null
              const exp = expeditions.find((x) => x.id === id) || null
              onChange(id, exp)
            }}
            disabled={disabled || loading}
          >
            <option value="">{loading ? 'Loading…' : '— No expedition —'}</option>
            {expeditions.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} ({e.system_count || 0} systems)
              </option>
            ))}
          </select>
          {!disabled && (
            <button
              type="button"
              onClick={() => setCreating((v) => !v)}
              className="text-xs px-2 py-1 rounded"
              style={{ backgroundColor: 'var(--app-accent-2)', color: '#fff' }}
            >
              + Create new
            </button>
          )}
        </div>
      )}

      {creating && !selected && (
        <div className="mt-2 flex items-center gap-2">
          <input
            type="text"
            className="flex-1 p-2 rounded text-sm"
            style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
            placeholder="e.g. Hyades Charting Run, May 2026"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            maxLength={100}
          />
          <Button onClick={handleCreate} disabled={!newName.trim()}>
            Create
          </Button>
          <Button variant="ghost" onClick={() => { setCreating(false); setNewName(''); setCreatingErr(null) }}>
            Cancel
          </Button>
        </div>
      )}
      {creatingErr && (
        <p className="text-xs text-red-400 mt-1">{creatingErr}</p>
      )}
      {disabled && (
        <p className="text-xs opacity-60 mt-1">
          Sign in to create or pick expeditions for your community.
        </p>
      )}
    </div>
  )
}
