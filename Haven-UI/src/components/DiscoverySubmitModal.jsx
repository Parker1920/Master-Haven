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

// Simplified type-specific fields (2-3 per type, matching backend DISCOVERY_TYPE_FIELDS)
const TYPE_FIELDS = {
  '🦗': [
    { key: 'species_name', label: 'Species Name', placeholder: 'Proc-gen name from scanner' },
    { key: 'behavior', label: 'Behavior', placeholder: 'Aggressive, Passive, Herd Animal...' },
  ],
  '🌿': [
    { key: 'species_name', label: 'Species Name', placeholder: 'Proc-gen name from scanner' },
    { key: 'biome', label: 'Biome', placeholder: 'Toxic Swamps, Lush Forest...' },
  ],
  '💎': [
    { key: 'resource_type', label: 'Resource Type', placeholder: 'Storm Crystals, Runaway Mold...' },
    { key: 'deposit_richness', label: 'Deposit Richness', placeholder: 'Common, Rare, Extraordinary' },
  ],
  '🏛️': [
    { key: 'age_era', label: 'Age / Era', placeholder: 'Pre-Atlas, Ancient, Unknown' },
    { key: 'associated_race', label: 'Associated Race', placeholder: "Gek, Korvax, Vy'keen..." },
  ],
  '📜': [
    { key: 'language_status', label: 'Language / Decryption', placeholder: 'Gek Language, Encrypted...' },
    { key: 'author_origin', label: 'Author / Origin', placeholder: 'Unknown Traveler, Atlas Entity...' },
  ],
  '🦴': [
    { key: 'species_type', label: 'Species Type', placeholder: 'Large Predator, Aquatic Life...' },
    { key: 'estimated_age', label: 'Estimated Age', placeholder: 'Ancient, Millions of years old...' },
  ],
  '👽': [
    { key: 'structure_type', label: 'Structure Type', placeholder: 'Monolith, Portal, Observatory...' },
    { key: 'operational_status', label: 'Status', placeholder: 'Functional, Dormant, Damaged...' },
  ],
  '🚀': [
    { key: 'ship_type', label: 'Ship Type', placeholder: 'Hauler, Fighter, Explorer, Exotic...' },
    { key: 'ship_class', label: 'Ship Class', placeholder: 'C, B, A, S' },
  ],
  '⚙️': [
    { key: 'tool_type', label: 'Multi-tool Type', placeholder: 'Pistol, Rifle, Experimental...' },
    { key: 'tool_class', label: 'Class', placeholder: 'C, B, A, S' },
  ],
  '📖': [
    { key: 'story_type', label: 'Story Type', placeholder: 'Journal Entry, Theory, Fiction...' },
  ],
  '🏠': [
    { key: 'base_type', label: 'Base Type', placeholder: 'Farm, Trading Post, Monument...' },
  ],
  '🆕': [],
}

// Galaxy options for stub creation
const GALAXIES = [
  'Euclid', 'Hilbert Dimension', 'Calypso', 'Hesperius Dimension', 'Hyades',
  'Ickjamatew', 'Budullangr', 'Kikolgallr', 'Eltiensleen', 'Eissentam'
]

export default function DiscoverySubmitModal({ isOpen, onClose, onSuccess }) {
  const [form, setForm] = useState({
    discovery_name: '',
    discovery_type: '',
    description: '',
    system_id: '',
    planet_id: '',
    moon_id: '',
    location_type: 'planet',
    location_name: '',
    discord_username: '',
    discord_tag: '',
    evidence_urls: ''
  })

  const [typeMetadata, setTypeMetadata] = useState({})
  const [photos, setPhotos] = useState([])
  const [systems, setSystems] = useState([])
  const [communities, setCommunities] = useState([])
  const [selectedSystem, setSelectedSystem] = useState(null)
  const [systemSearch, setSystemSearch] = useState('')
  const [showSystemDropdown, setShowSystemDropdown] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [uploadingPhotos, setUploadingPhotos] = useState(false)

  // Stub system creation state
  const [showCreateSystem, setShowCreateSystem] = useState(false)
  const [stubForm, setStubForm] = useState({ name: '', galaxy: 'Euclid', glyph_code: '' })
  const [creatingStub, setCreatingStub] = useState(false)
  const [isStubSystem, setIsStubSystem] = useState(false)

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
        location_type: 'planet',
        location_name: '',
        discord_username: '',
        discord_tag: '',
        evidence_urls: ''
      })
      setTypeMetadata({})
      setPhotos([])
      setSelectedSystem(null)
      setSystemSearch('')
      setError('')
      setSuccessMessage('')
      setShowCreateSystem(false)
      setStubForm({ name: '', galaxy: 'Euclid', glyph_code: '' })
      setIsStubSystem(false)
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
      .then(data => {
        setSelectedSystem(data)
        setIsStubSystem(!!data.is_stub)
      })
      .catch(() => setSelectedSystem(null))
  }, [form.system_id])

  // Clear type metadata when discovery type changes
  useEffect(() => {
    setTypeMetadata({})
  }, [form.discovery_type])

  function setField(key, value) {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  function selectSystem(sys) {
    setField('system_id', sys.id)
    setField('planet_id', '')
    setField('moon_id', '')
    setSystemSearch(sys.name)
    setShowSystemDropdown(false)
    setShowCreateSystem(false)
    setIsStubSystem(!!sys.is_stub)
  }

  function clearSystem() {
    setField('system_id', '')
    setField('planet_id', '')
    setField('moon_id', '')
    setSystemSearch('')
    setSelectedSystem(null)
    setIsStubSystem(false)
  }

  // Create stub system
  async function handleCreateStub(e) {
    e.preventDefault()
    if (!stubForm.name.trim()) return

    setCreatingStub(true)
    try {
      const res = await fetch('/api/systems/stub', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: stubForm.name.trim(),
          galaxy: stubForm.galaxy,
          glyph_code: stubForm.glyph_code.trim() || null,
          discord_tag: form.discord_tag || null
        })
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Failed to create system')
      }

      const data = await res.json()
      // Auto-select the created/found system
      setField('system_id', data.system_id)
      setSystemSearch(data.name)
      setShowCreateSystem(false)
      setIsStubSystem(data.is_stub !== false)
      setShowSystemDropdown(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setCreatingStub(false)
    }
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
    setSuccessMessage('')

    // Validation
    if (!form.discovery_name.trim()) {
      setError('Discovery Name is required')
      return
    }
    if (!form.discovery_type) {
      setError('Discovery Type is required')
      return
    }
    if (!form.system_id) {
      setError('System is required. Search for a system or create a new one.')
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

      const externalUrls = form.evidence_urls.split('\n').map(s => s.trim()).filter(Boolean)
      const allEvidence = [...evidencePhotos, ...externalUrls]

      // Build type_metadata from filled fields
      const metadata = {}
      const fields = TYPE_FIELDS[form.discovery_type] || []
      for (const field of fields) {
        if (typeMetadata[field.key]?.trim()) {
          metadata[field.key] = typeMetadata[field.key].trim()
        }
      }

      const payload = {
        discovery_name: form.discovery_name.trim(),
        discovery_type: form.discovery_type,
        description: form.description.trim() || null,
        system_id: form.system_id,
        planet_id: form.planet_id ? parseInt(form.planet_id) : null,
        moon_id: form.moon_id ? parseInt(form.moon_id) : null,
        location_type: form.location_type,
        location_name: form.location_name.trim() || null,
        discord_username: form.discord_username.trim(),
        discord_tag: form.discord_tag,
        photo_url: primaryPhoto || null,
        evidence_urls: allEvidence.length > 0 ? allEvidence.join(',') : null,
        type_metadata: Object.keys(metadata).length > 0 ? metadata : null
      }

      const res = await fetch('/api/submit_discovery', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || errData.message || 'Failed to submit discovery')
      }

      setSuccessMessage('Discovery submitted for approval! A community leader will review it shortly.')
      setTimeout(() => {
        onSuccess?.()
      }, 2000)
    } catch (err) {
      setError(err.message || 'An error occurred')
    } finally {
      setIsSubmitting(false)
    }
  }

  const planets = (selectedSystem?.planets || []).filter(p => !p.is_moon)
  const allPlanetsIncludingMoons = selectedSystem?.planets || []
  const selectedPlanet = allPlanetsIncludingMoons.find(p => p.id === parseInt(form.planet_id))
  // Flatten all moons across all planets for the moon dropdown
  const allMoons = planets.flatMap(p => (p.moons || []).map(m => ({ ...m, parentPlanetName: p.name })))
  const typeFields = TYPE_FIELDS[form.discovery_type] || []

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Submit Discovery">
      <form onSubmit={handleSubmit}>
        {error && (
          <div className="mb-4 p-3 rounded text-sm" style={{ backgroundColor: 'rgba(239,68,68,0.2)', color: '#fca5a5' }}>
            {error}
          </div>
        )}
        {successMessage && (
          <div className="mb-4 p-3 rounded text-sm" style={{ backgroundColor: 'rgba(34,197,94,0.2)', color: '#86efac' }}>
            {successMessage}
          </div>
        )}

        {/* Location Section - System Required */}
        <div className="mb-6">
          <h4 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--app-primary)' }}>
            Location <span className="text-red-400">*</span>
          </h4>
          <FormField label={<>System <span className="text-red-400">*</span></>} hint="Search for the system where you made this discovery">
            <div className="relative">
              <div className="flex gap-2">
                <input
                  ref={systemSearchRef}
                  type="text"
                  className="flex-1 p-2 rounded"
                  style={{ backgroundColor: 'var(--app-bg)', border: `1px solid ${form.system_id ? 'var(--app-primary)' : 'var(--app-accent-3)'}` }}
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

              {/* System search results dropdown */}
              {showSystemDropdown && systemSearch.length >= 2 && (
                <div
                  className="absolute z-10 w-full mt-1 rounded shadow-lg max-h-60 overflow-y-auto"
                  style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                >
                  {systems.map(sys => (
                    <div
                      key={sys.id}
                      className="p-2 cursor-pointer hover:opacity-80"
                      style={{ borderBottom: '1px solid var(--app-accent-3)' }}
                      onClick={() => selectSystem(sys)}
                    >
                      <div className="font-medium flex items-center gap-2">
                        {sys.name}
                        {sys.is_stub === 1 && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 font-medium">Stub</span>
                        )}
                      </div>
                      {sys.galaxy && <div className="text-xs muted">{sys.galaxy}{sys.planet_count ? ` - ${sys.planet_count} planets` : ''}</div>}
                    </div>
                  ))}

                  {/* Create New System button */}
                  <div
                    className="p-3 cursor-pointer text-center font-medium"
                    style={{ color: 'var(--app-primary)', borderTop: '2px solid var(--app-accent-3)' }}
                    onClick={() => {
                      setShowSystemDropdown(false)
                      setShowCreateSystem(true)
                      setStubForm(prev => ({ ...prev, name: systemSearch }))
                    }}
                  >
                    + Create New System
                  </div>
                </div>
              )}

              {/* No results message with create option */}
              {showSystemDropdown && systemSearch.length >= 2 && systems.length === 0 && (
                <div
                  className="absolute z-10 w-full mt-1 rounded shadow-lg"
                  style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                >
                  <div className="p-3 text-sm muted text-center">No systems found</div>
                  <div
                    className="p-3 cursor-pointer text-center font-medium"
                    style={{ color: 'var(--app-primary)', borderTop: '1px solid var(--app-accent-3)' }}
                    onClick={() => {
                      setShowSystemDropdown(false)
                      setShowCreateSystem(true)
                      setStubForm(prev => ({ ...prev, name: systemSearch }))
                    }}
                  >
                    + Create New System
                  </div>
                </div>
              )}
            </div>
          </FormField>

          {/* Selected system badge */}
          {form.system_id && isStubSystem && (
            <div className="mb-3 p-2 rounded text-sm flex items-center gap-2" style={{ backgroundColor: 'rgba(234,179,8,0.15)', border: '1px solid rgba(234,179,8,0.3)' }}>
              <span className="text-yellow-400 font-medium">Stub System</span>
              <span className="text-yellow-200/70">- This system has minimal data. It will need to be fully updated later.</span>
            </div>
          )}

          {/* Inline stub creation form */}
          {showCreateSystem && (
            <div className="mb-4 p-4 rounded" style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-primary)' }}>
              <h5 className="text-sm font-semibold mb-3" style={{ color: 'var(--app-primary)' }}>Create New System (Stub)</h5>
              <p className="text-xs muted mb-3">This creates a minimal system record. Full details can be added later.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                <FormField label={<>System Name <span className="text-red-400">*</span></>}>
                  <input
                    type="text"
                    className="w-full p-2 rounded"
                    style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                    value={stubForm.name}
                    onChange={e => setStubForm(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="System name"
                  />
                </FormField>
                <FormField label="Galaxy">
                  <select
                    className="w-full p-2 rounded"
                    style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                    value={stubForm.galaxy}
                    onChange={e => setStubForm(prev => ({ ...prev, galaxy: e.target.value }))}
                  >
                    {GALAXIES.map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                </FormField>
              </div>
              <FormField label="Glyph Code (optional)" hint="12-character hex portal code">
                <input
                  type="text"
                  className="w-full p-2 rounded font-mono"
                  style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                  value={stubForm.glyph_code}
                  onChange={e => setStubForm(prev => ({ ...prev, glyph_code: e.target.value }))}
                  placeholder="e.g., 0042FA556C30"
                  maxLength={12}
                />
              </FormField>
              <div className="flex gap-2 mt-3">
                <Button type="button" onClick={handleCreateStub} disabled={creatingStub || !stubForm.name.trim()}>
                  {creatingStub ? 'Creating...' : 'Create System'}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setShowCreateSystem(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {/* Location Type Selector */}
          {form.system_id && (
            <>
              <FormField label="Location Type">
                <div className="flex rounded overflow-hidden" style={{ border: '1px solid var(--app-accent-3)' }}>
                  {[
                    { value: 'planet', label: 'Planet' },
                    { value: 'moon', label: 'Moon' },
                    { value: 'space', label: 'Space' }
                  ].map(opt => (
                    <button
                      key={opt.value}
                      type="button"
                      className="flex-1 py-2 px-3 text-sm font-medium transition-colors"
                      style={{
                        backgroundColor: form.location_type === opt.value ? 'var(--app-primary)' : 'var(--app-bg)',
                        color: form.location_type === opt.value ? '#fff' : 'inherit',
                        borderRight: opt.value !== 'space' ? '1px solid var(--app-accent-3)' : 'none'
                      }}
                      onClick={() => {
                        setField('location_type', opt.value)
                        if (opt.value === 'space') {
                          setField('planet_id', '')
                          setField('moon_id', '')
                        }
                        if (opt.value === 'planet') {
                          setField('moon_id', '')
                        }
                        if (opt.value === 'moon') {
                          setField('planet_id', '')
                        }
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </FormField>

              {/* Planet or Moon dropdown (not both) */}
              {form.location_type === 'planet' && (
                isStubSystem && (!planets || planets.length === 0) ? (
                  <FormField label="Planet Name" hint="This stub system has no planets yet - type the name">
                    <input
                      type="text"
                      className="w-full p-2 rounded"
                      style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                      value={form.location_name}
                      onChange={e => setField('location_name', e.target.value)}
                      placeholder="Enter planet name..."
                    />
                  </FormField>
                ) : (
                  <FormField label="Planet">
                    <select
                      className="w-full p-2 rounded"
                      style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                      value={form.planet_id}
                      onChange={e => setField('planet_id', e.target.value)}
                    >
                      <option value="">Select planet...</option>
                      {planets.map(p => (
                        <option key={p.id} value={p.id}>{p.name || `Planet ${p.planet_index || p.id}`}</option>
                      ))}
                    </select>
                  </FormField>
                )
              )}

              {form.location_type === 'moon' && (
                isStubSystem && allMoons.length === 0 ? (
                  <FormField label="Moon Name" hint="This stub system has no moons yet - type the name">
                    <input
                      type="text"
                      className="w-full p-2 rounded"
                      style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                      value={form.location_name}
                      onChange={e => setField('location_name', e.target.value)}
                      placeholder="Enter moon name..."
                    />
                  </FormField>
                ) : (
                  <FormField label="Moon">
                    <select
                      className="w-full p-2 rounded"
                      style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                      value={form.moon_id}
                      onChange={e => setField('moon_id', e.target.value)}
                    >
                      <option value="">Select moon...</option>
                      {allMoons.map(m => (
                        <option key={m.id} value={m.id}>
                          {m.name || `Moon ${m.id}`}{m.parentPlanetName ? ` (${m.parentPlanetName})` : ''}
                        </option>
                      ))}
                    </select>
                  </FormField>
                )
              )}
              )}

              {form.location_type !== 'space' && !isStubSystem && (
                <FormField label="Specific Location" hint="Optional: coordinates, landmark, etc.">
                  <input
                    type="text"
                    className="w-full p-2 rounded"
                    style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                    value={form.location_name}
                    onChange={e => setField('location_name', e.target.value)}
                    placeholder="e.g., Trading Post, Near portal, Coordinates +45.2, -12.8"
                  />
                </FormField>
              )}
            </>
          )}
        </div>

        {/* Basic Info Section */}
        <div className="mb-6">
          <h4 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--app-primary)' }}>
            Discovery Info
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
            <FormField label={<>Discovery Type <span className="text-red-400">*</span></>}>
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

          {/* Dynamic Type-Specific Fields */}
          {typeFields.length > 0 && (
            <div className="mt-3 p-3 rounded" style={{ backgroundColor: 'rgba(255,255,255,0.03)', border: '1px solid var(--app-accent-3)' }}>
              <div className="text-xs muted mb-2 uppercase tracking-wide">Type Details</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {typeFields.map(field => (
                  <FormField key={field.key} label={field.label}>
                    <input
                      type="text"
                      className="w-full p-2 rounded"
                      style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
                      value={typeMetadata[field.key] || ''}
                      onChange={e => setTypeMetadata(prev => ({ ...prev, [field.key]: e.target.value }))}
                      placeholder={field.placeholder}
                    />
                  </FormField>
                ))}
              </div>
            </div>
          )}

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
        <div className="flex justify-between items-center pt-4" style={{ borderTop: '1px solid var(--app-accent-3)' }}>
          <div className="text-xs muted">Submissions require approval from a community leader</div>
          <div className="flex gap-3">
            <Button type="button" variant="ghost" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || uploadingPhotos || !!successMessage}>
              {isSubmitting ? 'Submitting...' : 'Submit for Approval'}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
