import React, { useEffect, useState, useContext, useRef } from 'react'
import axios from 'axios'
import { useLocation, useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import PlanetEditor from '../components/PlanetEditor'
import Modal from '../components/Modal'
import GlyphPicker from '../components/GlyphPicker'
import { AuthContext } from '../utils/AuthContext'
import { generateRandomStationPosition } from '../utils/stationPlacement'
import SearchableSelect from '../components/SearchableSelect'
import { GALAXIES, REALITIES } from '../data/galaxies'

function useQuery(){ return new URLSearchParams(useLocation().search) }

export default function Wizard(){
  const query = useQuery();
  const navigate = useNavigate();
  const auth = useContext(AuthContext)
  const { isAdmin, isSuperAdmin, isPartner, user } = auth || {}
  const edit = query.get('edit')
  const [system, setSystem] = useState({ id:'', name:'', galaxy:'Euclid', reality:'Normal', glyph_code:'', x:'', y:'', z:'', description:'', planets: [], space_station: null, region_x: null, region_y: null, region_z: null, glyph_planet: 0, glyph_solar_system: 1, discord_tag: null, star_type: '', economy_type: '', economy_level: '', conflict_level: '', dominant_lifeform: '' })
  const [planetModalOpen, setPlanetModalOpen] = useState(false)
  const [editingPlanetIndex, setEditingPlanetIndex] = useState(null)
  const [editingPlanet, setEditingPlanet] = useState(null)
  const [hasStation, setHasStation] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [discordTags, setDiscordTags] = useState([])
  const [editExplanation, setEditExplanation] = useState('')
  const [originalTag, setOriginalTag] = useState(null)
  // Personal discord username for non-community submissions
  const [personalDiscordUsername, setPersonalDiscordUsername] = useState('')
  const [personalDiscordModalOpen, setPersonalDiscordModalOpen] = useState(false)
  const [pendingPersonalSelection, setPendingPersonalSelection] = useState(false)

  // Fetch available discord tags for dropdown (all users can assign tags)
  useEffect(() => {
    axios.get('/api/discord_tags').then(r => {
      setDiscordTags(r.data.tags || [])
    }).catch(() => {})
  }, [])

  useEffect(()=>{
    if(edit){
      axios.get(`/api/systems/${encodeURIComponent(edit)}`).then(r=>{
        setSystem(r.data)
        setOriginalTag(r.data.discord_tag)
      }).catch(()=>{})
    }
  }, [edit])

  const explicitSubmitRef = useRef(false);

  async function submit(e){ e.preventDefault();
    // Only allow submit when user explicitly clicked the submit button.
    if(!explicitSubmitRef.current){
      // Reset just in case and ignore accidental/implicit submits
      explicitSubmitRef.current = false;
      return;
    }
    // Reset explicit submit flag for next action
    explicitSubmitRef.current = false;
    // Client-side validation for nested planets & moons
    if(!system.name || !system.name.trim()) { alert('System name is required'); return; }
    if(!system.star_type) { alert('Star Color is required'); return; }
    if(!system.economy_type) { alert('Economy Type is required'); return; }
    if(!system.economy_level) { alert('Economy Tier is required'); return; }
    if(!system.conflict_level) { alert('Conflict Level is required'); return; }
    if(!system.dominant_lifeform) { alert('Dominant Lifeform is required'); return; }
    if(system.planets){
      for(const p of system.planets){
        if(!p.name || !p.name.trim()){ alert('All planets must have a name'); return; }
        if(p.moons){
          for(const m of p.moons){
            if(!m.name || !m.name.trim()){ alert('All moons must have a name'); return; }
          }
        }
      }
    }

    // Discord community is now REQUIRED for all non-admin submissions
    if (!system.discord_tag && !isAdmin) {
      alert('Discord Community is required. Please select a community or choose "Personal" if you are not affiliated with a community.');
      return;
    }

    // If personal is selected, discord username is required
    if (system.discord_tag === 'personal' && !personalDiscordUsername.trim()) {
      alert('Discord username is required for personal submissions.');
      setPersonalDiscordModalOpen(true);
      return;
    }

    setIsSubmitting(true)
    try{
      if(isAdmin){
        // Admin: save directly to database
        // For partners editing untagged systems, include explanation
        const payload = { ...system }
        if (isPartner && edit && !originalTag && editExplanation) {
          payload.edit_explanation = editExplanation
        }
        const r = await axios.post('/api/save_system', payload);

        // Check if edit was queued for approval
        if (r.data.status === 'pending_approval') {
          alert(`Your edit has been submitted for super admin approval.\n\nRequest ID: ${r.data.request_id}\n\n${r.data.message}`);
        } else {
          alert('System saved successfully!');
        }
        navigate('/systems');
      } else {
        // Non-admin: submit for approval
        const payload = { ...system }
        // Include personal discord username if personal tag selected
        if (system.discord_tag === 'personal' && personalDiscordUsername.trim()) {
          payload.personal_discord_username = personalDiscordUsername.trim()
        }
        const r = await axios.post('/api/submit_system', payload);
        alert(`System submitted for approval!\n\nSubmission ID: ${r.data.submission_id}\nSystem Name: ${r.data.system_name}\n\nAn admin will review your submission.`);
        navigate('/systems');
      }
    } catch(err){
      const errorMsg = err.response?.data?.detail || err.message || err;
      alert(`${isAdmin ? 'Save' : 'Submission'} failed: ${errorMsg}`);
    } finally {
      setIsSubmitting(false)
    }
  }

  // Check if partner is editing an untagged system (requires explanation)
  const needsEditExplanation = isPartner && edit && !originalTag

  // Prevent accidental submits from pressing Enter in text inputs.
  // Allow Enter for textareas and when focused on the actual submit button.
  function handleKeyDown(e){
    if(e.key === 'Enter'){
      const tag = (e.target && e.target.tagName) ? e.target.tagName.toUpperCase() : '';
      const type = (e.target && e.target.type) ? String(e.target.type).toLowerCase() : '';
      if(tag === 'TEXTAREA') return; // allow new line
      if(type === 'submit' || tag === 'BUTTON') return; // allow submitting via button or submit element
      // Otherwise, prevent the Enter key from submitting the form
      e.preventDefault();
    }
  }

  function setField(k,v){ setSystem(s => ({...s, [k]: v})) }

  function handleGlyphDecoded(decodedData) {
    // Update system with decoded coordinates and region info
    setSystem(s => ({
      ...s,
      x: decodedData.x,
      y: decodedData.y,
      z: decodedData.z,
      region_x: decodedData.region_x,
      region_y: decodedData.region_y,
      region_z: decodedData.region_z,
      glyph_planet: decodedData.planet,
      glyph_solar_system: decodedData.solar_system,
      glyph_code: decodedData.glyph
    }))
  }

  function addPlanet(){
    setEditingPlanetIndex(-1)
    // Initialize ALL planet fields with defaults to ensure they're saved
    setEditingPlanet({
      name: '',
      biome: '',
      weather: '',
      sentinel: 'None',
      fauna: 'N/A',
      flora: 'N/A',
      materials: '',
      base_location: '',
      photo: '',
      notes: '',
      moons: []
    })
    setPlanetModalOpen(true)
  }

  function editPlanet(i){
    setEditingPlanetIndex(i)
    setEditingPlanet(system.planets[i])
    setPlanetModalOpen(true)
  }

  function commitPlanet(planet){
    const planets = [...(system.planets || [])]
    if(editingPlanetIndex === -1){
      planets.push(planet)
    } else {
      planets[editingPlanetIndex] = planet
    }
    setSystem({...system, planets})
    setPlanetModalOpen(false)
  }

  function updatePlanet(idx, val){
    const planets = [...(system.planets || [])]
    planets[idx] = val
    setSystem({...system, planets})
  }

  function removePlanet(idx){
    const planets = [...(system.planets || [])]
    planets.splice(idx, 1)
    setSystem({...system, planets})
  }

  function toggleStation(checked){
    setHasStation(checked)
    if(checked){
      // Generate random position for station
      const position = generateRandomStationPosition(system.planets || [])
      setSystem({...system, space_station: {
        name: `${system.name || 'System'} Station`,
        race: 'Gek',
        sell_percent: 80,
        buy_percent: 50,
        ...position
      }})
    } else {
      setSystem({...system, space_station: null})
    }
  }

  function regenerateStationPosition(){
    if(hasStation && system.space_station){
      const position = generateRandomStationPosition(system.planets || [])
      setSystem({...system, space_station: {
        ...system.space_station,
        ...position
      }})
      alert(`New position generated:\nX: ${position.x}\nY: ${position.y}\nZ: ${position.z}\nAttempts: ${position.attempts}${position.fallback ? ' (fallback used)' : ''}`)
    }
  }

  function setStationField(k,v){
    if(system.space_station){
      setSystem({...system, space_station: {...system.space_station, [k]: v}})
    }
  }

  return (
    <div>
      <Card className="max-w-4xl">
        <form onSubmit={submit} onKeyDown={handleKeyDown}>
        <label className="block mb-2">System Name <input placeholder="Name" aria-label="Name" className="w-full mt-1" value={system.name || ''} onChange={e=>setField('name', e.target.value)} required/></label>

        <div className="mt-4">
          <h3 className="text-lg font-semibold mb-2 text-purple-300">Portal Glyph Coordinates</h3>
          <GlyphPicker
            value={system.glyph_code}
            onChange={(code) => setField('glyph_code', code)}
            onDecoded={handleGlyphDecoded}
          />
        </div>

        {/* Display decoded coordinates (read-only) */}
        {system.x && system.y && system.z && (
          <div className="mt-4 p-3 bg-gray-800 rounded border border-green-500">
            <div className="text-sm text-gray-300">
              <span className="text-green-300 font-semibold">Coordinates:</span> X: {system.x}, Y: {system.y}, Z: {system.z}
              {system.region_x !== null && (
                <span className="ml-3">
                  <span className="text-purple-300 font-semibold">Region:</span> [{system.region_x}, {system.region_y}, {system.region_z}]
                </span>
              )}
            </div>
          </div>
        )}

        {/* Reality and Galaxy Selection */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              Reality <span className="text-red-400">*</span>
            </label>
            <select
              className="w-full p-2 border rounded bg-gray-700 border-gray-600"
              value={system.reality || 'Normal'}
              onChange={e => setField('reality', e.target.value)}
              required
            >
              {REALITIES.map(r => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Permadeath is separate from all other game modes
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Galaxy <span className="text-red-400">*</span>
            </label>
            <SearchableSelect
              options={GALAXIES.map(g => ({ value: g.name, label: `${g.index}: ${g.name}` }))}
              value={system.galaxy || 'Euclid'}
              onChange={v => setField('galaxy', v || 'Euclid')}
              placeholder="Search by number or name..."
            />
            <p className="text-xs text-gray-500 mt-1">
              Search by galaxy index (0-255) or name
            </p>
          </div>
        </div>

        {/* System Attributes - Required */}
        <div className="mt-4 p-4 bg-gray-800/50 rounded border border-gray-700">
          <h3 className="text-lg font-semibold mb-3 text-cyan-300">System Attributes</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Star Color */}
            <div>
              <label className="block text-sm font-medium mb-1">
                Star Color <span className="text-red-400">*</span>
              </label>
              <select
                className={`w-full p-2 border rounded bg-gray-700 ${!system.star_type ? 'border-red-500' : 'border-gray-600'}`}
                value={system.star_type || ''}
                onChange={e => setField('star_type', e.target.value)}
                required
              >
                <option value="">-- Select --</option>
                <option value="Yellow">Yellow</option>
                <option value="Red">Red</option>
                <option value="Green">Green</option>
                <option value="Blue">Blue</option>
                <option value="Purple">Purple</option>
              </select>
            </div>

            {/* Economy Type */}
            <div>
              <label className="block text-sm font-medium mb-1">
                Economy Type <span className="text-red-400">*</span>
              </label>
              <select
                className={`w-full p-2 border rounded bg-gray-700 ${!system.economy_type ? 'border-red-500' : 'border-gray-600'}`}
                value={system.economy_type || ''}
                onChange={e => setField('economy_type', e.target.value)}
                required
              >
                <option value="">-- Select --</option>
                <option value="Trading">Trading</option>
                <option value="Mining">Mining</option>
                <option value="Manufacturing">Manufacturing</option>
                <option value="Technology">Technology</option>
                <option value="Scientific">Scientific</option>
                <option value="Power Generation">Power Generation</option>
                <option value="Mass Production">Mass Production</option>
                <option value="Pirate">Pirate</option>
                <option value="None">None (Abandoned)</option>
              </select>
            </div>

            {/* Economy Tier */}
            <div>
              <label className="block text-sm font-medium mb-1">
                Economy Tier <span className="text-red-400">*</span>
              </label>
              <select
                className={`w-full p-2 border rounded bg-gray-700 ${!system.economy_level ? 'border-red-500' : 'border-gray-600'}`}
                value={system.economy_level || ''}
                onChange={e => setField('economy_level', e.target.value)}
                required
              >
                <option value="">-- Select --</option>
                <option value="T1">T1 (Low)</option>
                <option value="T2">T2 (Medium)</option>
                <option value="T3">T3 (High)</option>
                <option value="T4">T4 (Pirate)</option>
              </select>
            </div>

            {/* Conflict Level */}
            <div>
              <label className="block text-sm font-medium mb-1">
                Conflict Level <span className="text-red-400">*</span>
              </label>
              <select
                className={`w-full p-2 border rounded bg-gray-700 ${!system.conflict_level ? 'border-red-500' : 'border-gray-600'}`}
                value={system.conflict_level || ''}
                onChange={e => setField('conflict_level', e.target.value)}
                required
              >
                <option value="">-- Select --</option>
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
              </select>
            </div>

            {/* Dominant Lifeform */}
            <div>
              <label className="block text-sm font-medium mb-1">
                Dominant Lifeform <span className="text-red-400">*</span>
              </label>
              <select
                className={`w-full p-2 border rounded bg-gray-700 ${!system.dominant_lifeform ? 'border-red-500' : 'border-gray-600'}`}
                value={system.dominant_lifeform || ''}
                onChange={e => setField('dominant_lifeform', e.target.value)}
                required
              >
                <option value="">-- Select --</option>
                <option value="Gek">Gek</option>
                <option value="Vy'keen">Vy'keen</option>
                <option value="Korvax">Korvax</option>
                <option value="None">None (Abandoned)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Discord Tag Selection - REQUIRED for all users */}
        <div className="mt-3">
          <label className="block text-sm font-medium mb-1">
            Discord Community <span className="text-red-400">*</span>
          </label>
          <select
            className={`w-full p-2 border rounded bg-gray-700 ${!system.discord_tag ? 'border-red-500' : ''}`}
            value={system.discord_tag || ''}
            onChange={e => {
              const value = e.target.value
              if (value === 'personal') {
                // Open modal to collect discord username
                setPersonalDiscordModalOpen(true)
                setPendingPersonalSelection(true)
              } else {
                setField('discord_tag', value || null)
                // Clear personal discord username if switching away from personal
                if (system.discord_tag === 'personal') {
                  setPersonalDiscordUsername('')
                }
              }
            }}
            required
          >
            <option value="">-- Select a Community (Required) --</option>
            {discordTags.map(t => (
              <option key={t.tag} value={t.tag}>{t.name} ({t.tag})</option>
            ))}
            <option value="personal">Personal (No Community Affiliation)</option>
          </select>
          <p className="text-xs text-gray-500 mt-1">
            Select which Discord community this system belongs to, or "Personal" if not affiliated with a community.
          </p>
          {/* Show personal discord username if personal is selected */}
          {system.discord_tag === 'personal' && personalDiscordUsername && (
            <div className="mt-2 p-2 bg-fuchsia-900/30 border border-fuchsia-500 rounded flex justify-between items-center">
              <span className="text-fuchsia-300">
                Discord Username: <strong>{personalDiscordUsername}</strong>
              </span>
              <button
                type="button"
                onClick={() => setPersonalDiscordModalOpen(true)}
                className="text-xs px-2 py-1 bg-fuchsia-600 text-white rounded hover:bg-fuchsia-700"
              >
                Edit
              </button>
            </div>
          )}
        </div>

        {/* Warning/explanation for partners editing untagged systems */}
        {needsEditExplanation && (
          <div className="mt-4 p-4 bg-yellow-900/30 border border-yellow-700 rounded">
            <p className="text-yellow-400 font-semibold mb-2">
              This system is untagged. Your edit will require super admin approval.
            </p>
            <label className="block">
              <span className="text-sm">Explanation for edit (required)</span>
              <textarea
                className="w-full mt-1 p-2 border rounded bg-gray-700"
                value={editExplanation}
                onChange={e => setEditExplanation(e.target.value)}
                placeholder="Explain why you need to edit this system..."
                rows={3}
                required
              />
            </label>
          </div>
        )}

        <label className="block mt-3">Description <textarea aria-label="System description" className="w-full mt-1" value={system.description || ''} onChange={e=>setField('description', e.target.value)} /></label>
        <div className="mt-4">
          <h3 className="text-md font-semibold mb-2">Planets</h3>
          <div>
            {(system.planets || []).map((p, i) => (
              <div key={i} className="mb-2">
                <PlanetEditor index={i} planet={p} onChange={updatePlanet} onRemove={removePlanet} />
                <div className="mt-1 flex space-x-2">
                  <button className="px-3 py-1 bg-sky-600 text-white rounded" onClick={() => editPlanet(i)}>Edit</button>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-2">
            <button type="button" onClick={addPlanet} className="px-3 py-1 bg-green-600 rounded">➕ Add Planet</button>
          </div>
        </div>

        <div className="mt-4 border-t pt-4">
          <h3 className="text-md font-semibold mb-2">Space Station</h3>
          <label className="flex items-center space-x-2 mb-3">
            <input
              type="checkbox"
              checked={hasStation}
              onChange={(e) => toggleStation(e.target.checked)}
              className="w-4 h-4"
            />
            <span>🛸 Has Space Station (randomly placed)</span>
          </label>

          {hasStation && system.space_station && (
            <div className="ml-6 p-3 bg-purple-900/30 rounded border border-purple-700">
              <div className="mb-2">
                <label className="block text-sm">Station Name</label>
                <input
                  className="w-full mt-1"
                  value={system.space_station.name || ''}
                  onChange={(e) => setStationField('name', e.target.value)}
                  placeholder="Station Name"
                />
              </div>

              <div className="mb-2">
                <label className="block text-sm">Race</label>
                <select
                  className="w-full mt-1"
                  value={system.space_station.race || 'Gek'}
                  onChange={(e) => setStationField('race', e.target.value)}
                >
                  <option value="Gek">Gek</option>
                  <option value="Korvax">Korvax</option>
                  <option value="Vy'keen">Vy'keen</option>
                  <option value="Unknown">Unknown</option>
                </select>
              </div>

              <div className="grid grid-cols-3 gap-2 mb-2">
                <div>
                  <label className="block text-sm">X</label>
                  <input
                    type="number"
                    step="0.1"
                    className="w-full mt-1 bg-gray-100"
                    value={system.space_station.x || 0}
                    onChange={(e) => setStationField('x', parseFloat(e.target.value))}
                    readOnly={false}
                  />
                </div>
                <div>
                  <label className="block text-sm">Y</label>
                  <input
                    type="number"
                    step="0.1"
                    className="w-full mt-1 bg-gray-100"
                    value={system.space_station.y || 0}
                    onChange={(e) => setStationField('y', parseFloat(e.target.value))}
                    readOnly={false}
                  />
                </div>
                <div>
                  <label className="block text-sm">Z</label>
                  <input
                    type="number"
                    step="0.1"
                    className="w-full mt-1 bg-gray-100"
                    value={system.space_station.z || 0}
                    onChange={(e) => setStationField('z', parseFloat(e.target.value))}
                    readOnly={false}
                  />
                </div>
              </div>

              <button
                type="button"
                onClick={regenerateStationPosition}
                className="px-3 py-1 bg-purple-600 text-white rounded text-sm"
              >
                🎲 Regenerate Random Position
              </button>

              {system.space_station.fallback && (
                <div className="mt-2 text-xs text-yellow-300 bg-yellow-900/30 border border-yellow-700 p-2 rounded">
                  ⚠️ Fallback position used - couldn't find collision-free spot after 100 attempts
                </div>
              )}
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-col space-y-2">
          {!isAdmin && (
            <div className="text-sm text-yellow-300 bg-yellow-900/30 border border-yellow-700 p-2 rounded">
              Note: You are not logged in as admin. Your system will be submitted for approval.
            </div>
          )}
          <div className="flex space-x-2">
            <Button className="btn-primary" type="submit" onClick={() => { explicitSubmitRef.current = true }} disabled={isSubmitting}>
              {isSubmitting ? 'Submitting...' : (isAdmin ? 'Save System' : 'Submit for Approval')}
            </Button>
            <Button className="bg-gray-200 text-gray-800" onClick={()=> navigate('/systems')} disabled={isSubmitting}>Cancel</Button>
          </div>
        </div>
        {planetModalOpen && (
        <Modal title={editingPlanetIndex === -1 ? 'Add Planet' : 'Edit Planet'} onClose={() => setPlanetModalOpen(false)}>
          <PlanetEditor planet={editingPlanet} index={editingPlanetIndex} onChange={(i,p)=>{ setEditingPlanet(p) }} onRemove={() => {}} onSave={commitPlanet} />
        </Modal>
      )}

        {/* Personal Discord Username Modal */}
        {personalDiscordModalOpen && (
          <Modal
            title="Personal Discord Username"
            onClose={() => {
              setPersonalDiscordModalOpen(false)
              // If they cancel without entering a username, don't set personal tag
              if (pendingPersonalSelection && !personalDiscordUsername.trim()) {
                setPendingPersonalSelection(false)
              }
            }}
          >
            <div className="space-y-4">
              <p className="text-sm text-gray-300">
                Since you selected "Personal" (no community affiliation), please provide your Discord username
                so we can contact you if we need more information about your submission.
              </p>
              <div>
                <label className="block text-sm font-semibold mb-2">
                  Discord Username <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  className="w-full p-2 border rounded bg-gray-700 text-white"
                  value={personalDiscordUsername}
                  onChange={e => setPersonalDiscordUsername(e.target.value)}
                  placeholder="e.g., username or username#1234"
                  autoFocus
                />
                <p className="text-xs text-gray-500 mt-1">
                  Enter your Discord username so we can DM you if needed.
                </p>
              </div>
              <div className="flex space-x-2">
                <Button
                  className="btn-primary bg-fuchsia-600 hover:bg-fuchsia-700"
                  onClick={() => {
                    if (!personalDiscordUsername.trim()) {
                      alert('Discord username is required')
                      return
                    }
                    // Set the discord_tag to personal and close modal
                    setField('discord_tag', 'personal')
                    setPendingPersonalSelection(false)
                    setPersonalDiscordModalOpen(false)
                  }}
                >
                  Confirm
                </Button>
                <Button
                  className="bg-gray-600 text-white hover:bg-gray-500"
                  onClick={() => {
                    setPersonalDiscordModalOpen(false)
                    setPendingPersonalSelection(false)
                    setPersonalDiscordUsername('')
                  }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </Modal>
        )}
        </form>
      </Card>
    </div>
  )
}
