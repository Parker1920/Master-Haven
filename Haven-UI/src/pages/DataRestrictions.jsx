import React, { useEffect, useState, useContext, useMemo } from 'react'
import { AuthContext } from '../utils/AuthContext'
import Card from '../components/Card'
import Button from '../components/Button'

// Restrictable field options with descriptions
const RESTRICTABLE_FIELDS = [
  { id: 'coordinates', label: 'Coordinates', description: 'X, Y, Z position and region coordinates' },
  { id: 'glyph_code', label: 'Portal Glyphs', description: 'Glyph code and portal address' },
  { id: 'discovered_by', label: 'Discoverer', description: 'Who discovered the system and when' },
  { id: 'base_location', label: 'Base Locations', description: 'Base coordinates on planets' },
  { id: 'description', label: 'Description', description: 'System description text' },
  { id: 'star_type', label: 'Star Info', description: 'Star type, economy, conflict level' },
  { id: 'planets', label: 'Planet Details', description: 'Hide detailed planet info (shows count only)' }
]

const MAP_VISIBILITY_OPTIONS = [
  { value: 'normal', label: 'Normal', description: 'Fully visible with all hover details' },
  { value: 'point_only', label: 'Point Only', description: 'Shows as a dot but no hover information' },
  { value: 'hidden', label: 'Hidden', description: 'Does not appear on maps at all' }
]

export default function DataRestrictions() {
  const auth = useContext(AuthContext)
  const { isAdmin, isSuperAdmin } = auth || {}

  const [systems, setSystems] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  // Selection state
  const [selectedIds, setSelectedIds] = useState(new Set())

  // Modal state
  const [editingSystem, setEditingSystem] = useState(null)
  const [showBulkModal, setShowBulkModal] = useState(false)

  // Restriction form state
  const [formHidden, setFormHidden] = useState(false)
  const [formFields, setFormFields] = useState([])
  const [formMapVisibility, setFormMapVisibility] = useState('normal')

  useEffect(() => {
    loadSystems()
  }, [])

  const loadSystems = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/partner/my_systems', { credentials: 'include' })
      if (!res.ok) throw new Error('Failed to load systems')
      const data = await res.json()
      setSystems(data.systems || [])
    } catch (e) {
      console.error('Failed to load systems:', e)
    } finally {
      setLoading(false)
    }
  }

  // Filtered systems based on search
  const filteredSystems = useMemo(() => {
    if (!searchQuery.trim()) return systems
    const q = searchQuery.toLowerCase()
    return systems.filter(s =>
      s.name?.toLowerCase().includes(q) ||
      s.galaxy?.toLowerCase().includes(q) ||
      s.region_name?.toLowerCase().includes(q) ||
      s.discord_tag?.toLowerCase().includes(q)
    )
  }, [systems, searchQuery])

  // Selection handlers
  const toggleSelect = (id) => {
    const newSet = new Set(selectedIds)
    if (newSet.has(id)) {
      newSet.delete(id)
    } else {
      newSet.add(id)
    }
    setSelectedIds(newSet)
  }

  const selectAll = () => {
    setSelectedIds(new Set(filteredSystems.map(s => s.id)))
  }

  const clearSelection = () => {
    setSelectedIds(new Set())
  }

  // Open edit modal for single system
  const openEditModal = (system) => {
    setEditingSystem(system)
    if (system.restriction) {
      setFormHidden(system.restriction.is_hidden_from_public)
      setFormFields(system.restriction.hidden_fields || [])
      setFormMapVisibility(system.restriction.map_visibility || 'normal')
    } else {
      setFormHidden(false)
      setFormFields([])
      setFormMapVisibility('normal')
    }
  }

  // Open bulk edit modal
  const openBulkModal = () => {
    setFormHidden(false)
    setFormFields([])
    setFormMapVisibility('normal')
    setShowBulkModal(true)
  }

  // Close modals
  const closeModal = () => {
    setEditingSystem(null)
    setShowBulkModal(false)
  }

  // Toggle field in form
  const toggleField = (fieldId) => {
    if (formFields.includes(fieldId)) {
      setFormFields(formFields.filter(f => f !== fieldId))
    } else {
      setFormFields([...formFields, fieldId])
    }
  }

  // Save single system restriction
  const saveRestriction = async () => {
    if (!editingSystem) return
    setSaving(true)
    try {
      const res = await fetch('/api/data_restrictions', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_id: editingSystem.id,
          is_hidden_from_public: formHidden,
          hidden_fields: formFields,
          map_visibility: formMapVisibility
        })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to save')
      }
      await loadSystems()
      closeModal()
    } catch (e) {
      alert('Failed to save restriction: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  // Remove single system restriction
  const removeRestriction = async () => {
    if (!editingSystem) return
    if (!confirm('Remove all restrictions from this system?')) return
    setSaving(true)
    try {
      const res = await fetch(`/api/data_restrictions/${editingSystem.id}`, {
        method: 'DELETE',
        credentials: 'include'
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to remove')
      }
      await loadSystems()
      closeModal()
    } catch (e) {
      alert('Failed to remove restriction: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  // Bulk save restrictions
  const saveBulkRestrictions = async () => {
    if (selectedIds.size === 0) return
    setSaving(true)
    try {
      const res = await fetch('/api/data_restrictions/bulk', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_ids: Array.from(selectedIds),
          is_hidden_from_public: formHidden,
          hidden_fields: formFields,
          map_visibility: formMapVisibility
        })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to save')
      }
      const result = await res.json()
      alert(`Restrictions applied: ${result.created} created, ${result.updated} updated, ${result.skipped} skipped`)
      await loadSystems()
      setShowBulkModal(false)
      clearSelection()
    } catch (e) {
      alert('Failed to save restrictions: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  // Bulk remove restrictions
  const bulkRemoveRestrictions = async () => {
    if (selectedIds.size === 0) return
    if (!confirm(`Remove restrictions from ${selectedIds.size} systems?`)) return
    setSaving(true)
    try {
      const res = await fetch('/api/data_restrictions/bulk_remove', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_ids: Array.from(selectedIds)
        })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to remove')
      }
      const result = await res.json()
      alert(`Restrictions removed from ${result.removed} systems (${result.skipped} skipped)`)
      await loadSystems()
      clearSelection()
    } catch (e) {
      alert('Failed to remove restrictions: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  if (!isAdmin) {
    return <div className="text-center py-12 text-gray-500">Please log in to manage data restrictions.</div>
  }

  // Stats
  const totalSystems = systems.length
  const restrictedCount = systems.filter(s => s.has_restriction).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Data Restrictions</h1>
          <p className="text-gray-400 text-sm mt-1">
            Control which data is visible to public viewers. {isSuperAdmin ? 'Viewing all systems.' : 'Viewing your systems.'}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="px-3 py-1 bg-gray-700 rounded">{totalSystems} systems</span>
          <span className="px-3 py-1 bg-yellow-600 rounded">{restrictedCount} restricted</span>
        </div>
      </div>

      {/* Search and Actions */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <input
            type="text"
            placeholder="Search systems..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 px-4 py-2 bg-gray-800 border border-gray-600 rounded focus:outline-none focus:border-cyan-500"
          />
          <div className="flex gap-2">
            <Button onClick={selectAll} variant="secondary" size="sm">Select All</Button>
            <Button onClick={clearSelection} variant="secondary" size="sm">Clear</Button>
          </div>
        </div>

        {/* Bulk Actions */}
        {selectedIds.size > 0 && (
          <div className="mt-4 p-3 bg-gray-800 rounded flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <span className="text-cyan-400 font-medium">{selectedIds.size} systems selected</span>
            <div className="flex gap-2">
              <Button onClick={openBulkModal} variant="primary" size="sm">Apply Restrictions</Button>
              <Button onClick={bulkRemoveRestrictions} variant="danger" size="sm">Remove Restrictions</Button>
            </div>
          </div>
        )}
      </Card>

      {/* Systems List */}
      <Card>
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading systems...</div>
        ) : filteredSystems.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            {systems.length === 0 ? 'No systems found.' : 'No systems match your search.'}
          </div>
        ) : (
          <div className="divide-y divide-gray-700">
            {filteredSystems.map(system => (
              <div
                key={system.id}
                className={`p-4 flex items-center gap-4 hover:bg-gray-800/50 transition-colors ${selectedIds.has(system.id) ? 'bg-gray-800' : ''}`}
              >
                {/* Checkbox */}
                <input
                  type="checkbox"
                  checked={selectedIds.has(system.id)}
                  onChange={() => toggleSelect(system.id)}
                  className="w-5 h-5 rounded border-gray-600 text-cyan-500 focus:ring-cyan-500"
                />

                {/* System Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{system.name}</span>
                    <span className="text-xs px-2 py-0.5 bg-gray-700 rounded">{system.galaxy}</span>
                    {isSuperAdmin && system.discord_tag && (
                      <span className="text-xs px-2 py-0.5 bg-purple-700 rounded">{system.discord_tag}</span>
                    )}
                  </div>
                  <div className="text-sm text-gray-400 mt-1">
                    {system.region_name || `Region (${system.region_x}, ${system.region_y}, ${system.region_z})`}
                  </div>
                </div>

                {/* Restriction Status */}
                <div className="flex items-center gap-3">
                  {system.has_restriction ? (
                    <div className="flex items-center gap-2">
                      {system.restriction.is_hidden_from_public && (
                        <span className="text-xs px-2 py-1 bg-red-600 rounded">HIDDEN</span>
                      )}
                      {system.restriction.hidden_fields?.length > 0 && (
                        <span className="text-xs px-2 py-1 bg-yellow-600 rounded">
                          {system.restriction.hidden_fields.length} fields
                        </span>
                      )}
                      {system.restriction.map_visibility !== 'normal' && (
                        <span className="text-xs px-2 py-1 bg-orange-600 rounded">
                          {system.restriction.map_visibility === 'hidden' ? 'Map Hidden' : 'Point Only'}
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-gray-500">Public</span>
                  )}
                  <Button onClick={() => openEditModal(system)} variant="secondary" size="sm">
                    Configure
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Single System Edit Modal */}
      {editingSystem && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 rounded-lg max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-700">
              <h2 className="text-xl font-bold">Configure Restrictions</h2>
              <p className="text-gray-400 text-sm mt-1">{editingSystem.name}</p>
            </div>

            <div className="p-6 space-y-6">
              {/* Hide from public toggle */}
              <div className="flex items-center justify-between p-4 bg-gray-800 rounded">
                <div>
                  <div className="font-medium">Hide from Public</div>
                  <div className="text-sm text-gray-400">Completely hide this system from non-owners</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formHidden}
                    onChange={(e) => setFormHidden(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:ring-2 peer-focus:ring-cyan-500 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-600"></div>
                </label>
              </div>

              {/* Field restrictions */}
              <div>
                <h3 className="font-medium mb-3">Hide Specific Fields</h3>
                <div className="space-y-2">
                  {RESTRICTABLE_FIELDS.map(field => (
                    <label
                      key={field.id}
                      className="flex items-start gap-3 p-3 bg-gray-800 rounded cursor-pointer hover:bg-gray-750"
                    >
                      <input
                        type="checkbox"
                        checked={formFields.includes(field.id)}
                        onChange={() => toggleField(field.id)}
                        className="w-5 h-5 mt-0.5 rounded border-gray-600 text-cyan-500 focus:ring-cyan-500"
                      />
                      <div>
                        <div className="font-medium">{field.label}</div>
                        <div className="text-sm text-gray-400">{field.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Map visibility */}
              <div>
                <h3 className="font-medium mb-3">Map Visibility</h3>
                <div className="space-y-2">
                  {MAP_VISIBILITY_OPTIONS.map(opt => (
                    <label
                      key={opt.value}
                      className={`flex items-start gap-3 p-3 rounded cursor-pointer ${formMapVisibility === opt.value ? 'bg-cyan-900/30 border border-cyan-500' : 'bg-gray-800 hover:bg-gray-750'}`}
                    >
                      <input
                        type="radio"
                        name="mapVisibility"
                        value={opt.value}
                        checked={formMapVisibility === opt.value}
                        onChange={(e) => setFormMapVisibility(e.target.value)}
                        className="w-5 h-5 mt-0.5 text-cyan-500 focus:ring-cyan-500"
                      />
                      <div>
                        <div className="font-medium">{opt.label}</div>
                        <div className="text-sm text-gray-400">{opt.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="p-6 border-t border-gray-700 flex justify-between">
              <Button onClick={removeRestriction} variant="danger" disabled={saving || !editingSystem.has_restriction}>
                Remove All
              </Button>
              <div className="flex gap-2">
                <Button onClick={closeModal} variant="secondary" disabled={saving}>Cancel</Button>
                <Button onClick={saveRestriction} variant="primary" disabled={saving}>
                  {saving ? 'Saving...' : 'Save'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Edit Modal */}
      {showBulkModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 rounded-lg max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-700">
              <h2 className="text-xl font-bold">Bulk Apply Restrictions</h2>
              <p className="text-gray-400 text-sm mt-1">Apply to {selectedIds.size} selected systems</p>
            </div>

            <div className="p-6 space-y-6">
              {/* Hide from public toggle */}
              <div className="flex items-center justify-between p-4 bg-gray-800 rounded">
                <div>
                  <div className="font-medium">Hide from Public</div>
                  <div className="text-sm text-gray-400">Completely hide these systems from non-owners</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formHidden}
                    onChange={(e) => setFormHidden(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:ring-2 peer-focus:ring-cyan-500 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-600"></div>
                </label>
              </div>

              {/* Field restrictions */}
              <div>
                <h3 className="font-medium mb-3">Hide Specific Fields</h3>
                <div className="space-y-2">
                  {RESTRICTABLE_FIELDS.map(field => (
                    <label
                      key={field.id}
                      className="flex items-start gap-3 p-3 bg-gray-800 rounded cursor-pointer hover:bg-gray-750"
                    >
                      <input
                        type="checkbox"
                        checked={formFields.includes(field.id)}
                        onChange={() => toggleField(field.id)}
                        className="w-5 h-5 mt-0.5 rounded border-gray-600 text-cyan-500 focus:ring-cyan-500"
                      />
                      <div>
                        <div className="font-medium">{field.label}</div>
                        <div className="text-sm text-gray-400">{field.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Map visibility */}
              <div>
                <h3 className="font-medium mb-3">Map Visibility</h3>
                <div className="space-y-2">
                  {MAP_VISIBILITY_OPTIONS.map(opt => (
                    <label
                      key={opt.value}
                      className={`flex items-start gap-3 p-3 rounded cursor-pointer ${formMapVisibility === opt.value ? 'bg-cyan-900/30 border border-cyan-500' : 'bg-gray-800 hover:bg-gray-750'}`}
                    >
                      <input
                        type="radio"
                        name="bulkMapVisibility"
                        value={opt.value}
                        checked={formMapVisibility === opt.value}
                        onChange={(e) => setFormMapVisibility(e.target.value)}
                        className="w-5 h-5 mt-0.5 text-cyan-500 focus:ring-cyan-500"
                      />
                      <div>
                        <div className="font-medium">{opt.label}</div>
                        <div className="text-sm text-gray-400">{opt.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="p-6 border-t border-gray-700 flex justify-end gap-2">
              <Button onClick={closeModal} variant="secondary" disabled={saving}>Cancel</Button>
              <Button onClick={saveBulkRestrictions} variant="primary" disabled={saving}>
                {saving ? 'Applying...' : `Apply to ${selectedIds.size} Systems`}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
