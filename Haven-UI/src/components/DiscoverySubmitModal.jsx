import React, { useState, useEffect, useRef } from 'react'
import Modal from './Modal'
import Button from './Button'
import FormField from './FormField'

// Discovery types with emojis (matching VH-System-View.html / Keeper bot)
const DISCOVERY_TYPES = [
  { value: '', label: 'Select type...' },
  { value: '🦗', label: '🦗 Fauna' },
  { value: '🌿', label: '🌿 Flora' },
  { value: '💎', label: '💎 Mineral' },
  { value: '🏛️', label: '🏛️ Ancient' },
  { value: '📜', label: '📜 History' },
  { value: '🦴', label: '🦴 Bones' },
  { value: '👽', label: '👽 Alien' },
  { value: '🚀', label: '🚀 Starship' },
  { value: '⚙️', label: '⚙️ Multi-tool' },
  { value: '📖', label: '📖 Lore' },
  { value: '🏠', label: '🏠 Custom Base' },
  { value: '🆕', label: '🆕 Other' }
]

export default function DiscoverySubmitModal({ isOpen, onClose, onSuccess }) {
  const [form, setForm] = useState({
    discovery_name: '',
    discovery_type: '',
    description: '',
    system_id: '',
    planet_id: '',
    moon_id: '',
    location_name: '',
    discord_username: '',
    discord_tag: '',
    evidence_urls: ''
  })

  const [photos, setPhotos] = useState([]) // Array of { file, preview, uploaded, path }
  const [systems, setSystems] = useState([])
  const [communities, setCommunities] = useState([]) // For discord_tag dropdown
  const [selectedSystem, setSelectedSystem] = useState(null)
  const [systemSearch, setSystemSearch] = useState('')
  const [showSystemDropdown, setShowSystemDropdown] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [uploadingPhotos, setUploadingPhotos] = useState(false)

  const fileInputRef = useRef(null)
  const systemSearchRef = useRef(null)

  // Fetch communities for dropdown on mount
  useEffect(() => {
    fetch('/api/discord_tags')
      .then(r => r.json())
      .then(data => setCommunities(data.tags || []))
      .catch(() => setCommunities([{ tag: 'Personal', name: 'Personal (Not affiliated)' }]))
  }, [])

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setForm({
        discovery_name: '',
        discovery_type: '',
        description: '',
        system_id: '',
        planet_id: '',
        moon_id: '',
        location_name: '',
        discord_username: '',
        discord_tag: '',
        evidence_urls: ''
      })
      setPhotos([])
      setSelectedSystem(null)
      setSystemSearch('')
      setError('')
    }
  }, [isOpen])

  // Search systems as user types
  useEffect(() => {
    if (!systemSearch || systemSearch.length < 2) {
      setSystems([])
      return
    }
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/systems/search?q=${encodeURIComponent(systemSearch)}&limit=10`)
        const data = await res.json()
        setSystems(data.results || data || [])
      } catch (e) {
        console.error('System search error:', e)
        setSystems([])
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [systemSearch])

  // Load system details when selected
  useEffect(() => {
    if (!form.system_id) {
      setSelectedSystem(null)
      return
    }
    fetch(`/api/systems/${form.system_id}`)
      .then(r => r.json())
      .then(data => setSelectedSystem(data))
      .catch(() => setSelectedSystem(null))
  }, [form.system_id])

  function setField(key, value) {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  function selectSystem(sys) {
    setField('system_id', sys.id)
    setField('planet_id', '')
    setField('moon_id', '')
    setSystemSearch(sys.name)
    setShowSystemDropdown(false)
  }

  function clearSystem() {
    setField('system_id', '')
    setField('planet_id', '')
    setField('moon_id', '')
    setSystemSearch('')
    setSelectedSystem(null)
  }

  // Photo handling
  async function handlePhotoSelect(e) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    await addPhotos(files)
  }

  async function addPhotos(files) {
    setUploadingPhotos(true)
    const newPhotos = []

    for (const file of files) {
      if (!file.type.startsWith('image/')) continue

      const preview = URL.createObjectURL(file)
      const photoEntry = { file, preview, uploaded: false, path: null }
      newPhotos.push(photoEntry)

      // Upload immediately
      try {
        const formData = new FormData()
        formData.append('file', file)
        const res = await fetch('/api/photos', { method: 'POST', body: formData })
        if (res.ok) {
          const data = await res.json()
          photoEntry.uploaded = true
          photoEntry.path = data.path || data.filename
        }
      } catch (e) {
        console.error('Photo upload error:', e)
      }
    }

    setPhotos(prev => [...prev, ...newPhotos])
    setUploadingPhotos(false)
  }

  function removePhoto(index) {
    setPhotos(prev => {
      const updated = [...prev]
      if (updated[index]?.preview) {
        URL.revokeObjectURL(updated[index].preview)
      }
      updated.splice(index, 1)
      return updated
    })
  }

  // Drag and drop
  function handleDragOver(e) {
    e.preventDefault()
    e.stopPropagation()
  }

  function handleDrop(e) {
    e.preventDefault()
    e.stopPropagation()
    const files = Array.from(e.dataTransfer.files || [])
    if (files.length) addPhotos(files)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    // Validation
    if (!form.discovery_name.trim()) {
      setError('Discovery Name is required')
      return
    }
    if (!form.discord_username.trim()) {
      setError('Discord Username is required')
      return
    }
    if (!form.discord_tag) {
      setError('Community (Discord Tag) is required')
      return
    }

    setIsSubmitting(true)

    try {
      // Build payload
      const uploadedPhotos = photos.filter(p => p.uploaded && p.path)
      const primaryPhoto = uploadedPhotos[0]?.path || ''
      const evidencePhotos = uploadedPhotos.slice(1).map(p => p.path)

      // Combine evidence photos with external URLs
      const externalUrls = form.evidence_urls.split('\n').map(s => s.trim()).filter(Boolean)
      const allEvidence = [...evidencePhotos, ...externalUrls]

      const payload = {
        discovery_name: form.discovery_name.trim(),
        discovery_type: form.discovery_type || null,
        description: form.description.trim() || null,
        system_id: form.system_id ? parseInt(form.system_id) : null,
        planet_id: form.planet_id ? parseInt(form.planet_id) : null,
        moon_id: form.moon_id ? parseInt(form.moon_id) : null,
        location_name: form.location_name.trim() || null,
        discord_username: form.discord_username.trim(),
        discord_tag: form.discord_tag,
        photo_url: primaryPhoto || null,
        evidence_urls: allEvidence.length > 0 ? allEvidence.join(',') : null
      }

      const res = await fetch('/api/discoveries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || errData.message || 'Failed to submit discovery')
      }

      onSuccess?.()
    } catch (err) {
      setError(err.message || 'An error occurred')
    } finally {
      setIsSubmitting(false)
    }
  }

  const planets = selectedSystem?.planets || []
  const selectedPlanet = planets.find(p => p.id === parseInt(form.planet_id))
  const moons = selectedPlanet?.moons || []

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Submit Discovery">
      <form onSubmit={handleSubmit}>
        {error && (
          <div className="mb-4 p-3 rounded text-sm" style={{ backgroundColor: 'rgba(239,68,68,0.2)', color: '#fca5a5' }}>
            {error}
          </div>
        )}

        {/* Basic Info Section */}
        <div className="mb-6">
          <h4 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--app-primary)' }}>
            Basic Info
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField label={<>Discovery Name <span className="text-red-400">*</span></>}>
              <input
                type="text"
                className="w-full p-2 rounded"
                style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                value={form.discovery_name}
                onChange={e => setField('discovery_name', e.target.value)}
                placeholder="e.g., Giant Sand Worm"
              />
            </FormField>
            <FormField label="Discovery Type">
              <select
                className="w-full p-2 rounded"
                style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                value={form.discovery_type}
                onChange={e => setField('discovery_type', e.target.value)}
              >
                {DISCOVERY_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </FormField>
          </div>
          <FormField label="Description">
            <textarea
              className="w-full p-2 rounded"
              style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)', minHeight: 80 }}
              value={form.description}
              onChange={e => setField('description', e.target.value)}
              placeholder="Describe the discovery, any notable characteristics, behaviors, etc."
            />
          </FormField>
        </div>

        {/* Location Section */}
        <div className="mb-6">
          <h4 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--app-primary)' }}>
            Location
          </h4>
          <FormField label="System" hint="Search by system name to link this discovery">
            <div className="relative">
              <div className="flex gap-2">
                <input
                  ref={systemSearchRef}
                  type="text"
                  className="flex-1 p-2 rounded"
                  style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                  value={systemSearch}
                  onChange={e => {
                    setSystemSearch(e.target.value)
                    setShowSystemDropdown(true)
                    if (!e.target.value) clearSystem()
                  }}
                  onFocus={() => setShowSystemDropdown(true)}
                  placeholder="Search for a system..."
                />
                {form.system_id && (
                  <Button type="button" variant="ghost" onClick={clearSystem}>Clear</Button>
                )}
              </div>
              {showSystemDropdown && systems.length > 0 && (
                <div
                  className="absolute z-10 w-full mt-1 rounded shadow-lg max-h-48 overflow-y-auto"
                  style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                >
                  {systems.map(sys => (
                    <div
                      key={sys.id}
                      className="p-2 cursor-pointer hover:opacity-80"
                      style={{ borderBottom: '1px solid var(--app-accent-3)' }}
                      onClick={() => selectSystem(sys)}
                    >
                      <div className="font-medium">{sys.name}</div>
                      {sys.galaxy && <div className="text-xs muted">{sys.galaxy}</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </FormField>

          {selectedSystem && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField label="Planet">
                <select
                  className="w-full p-2 rounded"
                  style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                  value={form.planet_id}
                  onChange={e => {
                    setField('planet_id', e.target.value)
                    setField('moon_id', '')
                  }}
                >
                  <option value="">Select planet...</option>
                  {planets.map(p => (
                    <option key={p.id} value={p.id}>{p.name || `Planet ${p.planet_index || p.id}`}</option>
                  ))}
                </select>
              </FormField>
              <FormField label="Moon (optional)">
                <select
                  className="w-full p-2 rounded"
                  style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                  value={form.moon_id}
                  onChange={e => setField('moon_id', e.target.value)}
                  disabled={!form.planet_id || moons.length === 0}
                >
                  <option value="">Select moon...</option>
                  {moons.map(m => (
                    <option key={m.id} value={m.id}>{m.name || `Moon ${m.id}`}</option>
                  ))}
                </select>
              </FormField>
            </div>
          )}

          <FormField label="Location Name" hint="Specific location on the planet (e.g., 'Near the Archive portal')">
            <input
              type="text"
              className="w-full p-2 rounded"
              style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
              value={form.location_name}
              onChange={e => setField('location_name', e.target.value)}
              placeholder="e.g., Trading Post, Near portal, Coordinates +45.2, -12.8"
            />
          </FormField>
        </div>

        {/* Credits Section */}
        <div className="mb-6">
          <h4 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--app-primary)' }}>
            Credits
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField label={<>Discord Username <span className="text-red-400">*</span></>} hint="Your Discord username for crediting">
              <input
                type="text"
                className="w-full p-2 rounded"
                style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                value={form.discord_username}
                onChange={e => setField('discord_username', e.target.value)}
                placeholder="e.g., username or username#1234"
              />
            </FormField>
            <FormField label={<>Community <span className="text-red-400">*</span></>} hint="Which community are you submitting for?">
              <select
                className="w-full p-2 rounded"
                style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                value={form.discord_tag}
                onChange={e => setField('discord_tag', e.target.value)}
              >
                <option value="">Select community...</option>
                {communities.map(c => (
                  <option key={c.tag} value={c.tag}>{c.name}</option>
                ))}
              </select>
            </FormField>
          </div>
        </div>

        {/* Photos & Evidence Section */}
        <div className="mb-6">
          <h4 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--app-primary)' }}>
            Photos & Evidence
          </h4>

          {/* Photo Upload Area */}
          <div
            className="border-2 border-dashed rounded p-4 mb-4 text-center cursor-pointer transition-colors"
            style={{ borderColor: 'var(--app-accent-3)' }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={handlePhotoSelect}
            />
            <div className="text-3xl mb-2">📷</div>
            <div className="text-sm">
              {uploadingPhotos ? 'Uploading...' : 'Click to upload or drag & drop photos here'}
            </div>
            <div className="text-xs muted mt-1">First photo will be the main image</div>
          </div>

          {/* Photo Previews */}
          {photos.length > 0 && (
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2 mb-4">
              {photos.map((photo, idx) => (
                <div
                  key={idx}
                  className="relative aspect-square rounded overflow-hidden"
                  style={{ backgroundColor: 'var(--app-bg)' }}
                >
                  <img
                    src={photo.preview}
                    alt={`Upload ${idx + 1}`}
                    className="w-full h-full object-cover"
                  />
                  {idx === 0 && (
                    <div className="absolute top-1 left-1 text-xs px-1 rounded" style={{ backgroundColor: 'var(--app-primary)', color: '#fff' }}>
                      Main
                    </div>
                  )}
                  {!photo.uploaded && (
                    <div className="absolute inset-0 flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
                      <div className="text-xs">Uploading...</div>
                    </div>
                  )}
                  <button
                    type="button"
                    className="absolute top-1 right-1 w-5 h-5 rounded-full flex items-center justify-center text-xs"
                    style={{ backgroundColor: 'rgba(0,0,0,0.7)', color: '#fff' }}
                    onClick={(e) => { e.stopPropagation(); removePhoto(idx) }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          <FormField label="Evidence URLs" hint="External links to screenshots, videos, etc. (one per line)">
            <textarea
              className="w-full p-2 rounded"
              style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)', minHeight: 60 }}
              value={form.evidence_urls}
              onChange={e => setField('evidence_urls', e.target.value)}
              placeholder="https://imgur.com/abc123&#10;https://youtube.com/watch?v=xyz"
            />
          </FormField>
        </div>

        {/* Submit Buttons */}
        <div className="flex justify-end gap-3 pt-4" style={{ borderTop: '1px solid var(--app-accent-3)' }}>
          <Button type="button" variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting || uploadingPhotos}>
            {isSubmitting ? 'Submitting...' : 'Submit Discovery'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
