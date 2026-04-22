import React, { useEffect, useState, useContext, useRef } from 'react'
import axios from 'axios'
import { useLocation, useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import PlanetEditor from '../components/PlanetEditor'
import Modal from '../components/Modal'
import GlyphPicker from '../components/GlyphPicker'
import { AuthContext } from '../utils/AuthContext'
import { generateStationPosition } from '../utils/stationPlacement'
import { getTradeGoodsForEconomy, getTradeGoodsForEconomyAndTier } from '../utils/economyTradeGoods'
import SearchableSelect from '../components/SearchableSelect'
import ProfileClaimModal from '../components/ProfileClaimModal'
import { GALAXIES, REALITIES } from '../data/galaxies'

function useQuery(){ return new URLSearchParams(useLocation().search) }

/**
 * System Create/Edit Wizard
 * Route: /wizard (create) or /wizard?edit=<systemId> (edit)
 * Auth: Public for submissions (goes to pending queue); admin for direct save
 *
 * Multi-section form for creating or editing a star system with planets, moons,
 * and space station data. Glyph code entry auto-decodes to region coordinates.
 *
 * NOTE: INTENTIONAL DESIGN -- partners with the SYSTEM_CREATE feature flag bypass
 * the pending queue and save directly to the database via POST /api/save_system.
 * This is intentional because partners are trusted community leaders. The
 * SYSTEM_CREATE flag controls the submission path (direct DB vs pending queue),
 * not just UI visibility. Backend enforcement of this flag is a tracked TODO.
 *
 * Non-admin users submit via POST /api/submit_system (goes to pending_systems
 * for admin review). Discord community tag is required for non-admin submissions.
 *
 * Key APIs:
 *   POST /api/save_system     (admin: direct save)
 *   POST /api/submit_system   (public: submit for approval)
 *   GET  /api/systems/:id     (load existing system for editing)
 *   GET  /api/discord_tags    (community dropdown)
 */
export default function Wizard(){
  const query = useQuery();
  const navigate = useNavigate();
  const auth = useContext(AuthContext)
  const { isAdmin, isSuperAdmin, isPartner, user } = auth || {}
  const edit = query.get('edit')
  const [system, setSystem] = useState({ id:'', name:'', galaxy:'', reality:'', glyph_code:'', x:'', y:'', z:'', description:'', planets: [], space_station: null, region_x: null, region_y: null, region_z: null, glyph_planet: 0, glyph_solar_system: 1, discord_tag: null, star_type: '', economy_type: '', economy_level: '', conflict_level: '', dominant_lifeform: '', stellar_classification: '' })
  const [planetModalOpen, setPlanetModalOpen] = useState(false)
  const [editingPlanetIndex, setEditingPlanetIndex] = useState(null)
  const [editingPlanet, setEditingPlanet] = useState(null)
  const [hasStation, setHasStation] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [discordTags, setDiscordTags] = useState([])
  const [editExplanation, setEditExplanation] = useState('')
  const [originalTag, setOriginalTag] = useState(null)
  // Discord username for all submissions (required for self-submission detection)
  // Blank by default - auto-filled from profile if logged in, otherwise user must enter
  const [submitterDiscordUsername, setSubmitterDiscordUsername] = useState('')
  // Personal discord username for non-community submissions
  const [personalDiscordUsername, setPersonalDiscordUsername] = useState('')
  const [personalDiscordModalOpen, setPersonalDiscordModalOpen] = useState(false)
  const [pendingPersonalSelection, setPendingPersonalSelection] = useState(false)
  // Profile claim modal state
  const [profileModalOpen, setProfileModalOpen] = useState(false)
  const [profileModalStatus, setProfileModalStatus] = useState(null) // 'suggestions' | 'not_found' | 'created'
  const [profileSuggestions, setProfileSuggestions] = useState([])
  const [resolvedProfileId, setResolvedProfileId] = useState(null)
  const [pendingSubmitPayload, setPendingSubmitPayload] = useState(null)
  // Region info state
  const [regionInfo, setRegionInfo] = useState(null)
  const [regionLoading, setRegionLoading] = useState(false)
  const [proposedRegionName, setProposedRegionName] = useState('')
  const [regionSubmitting, setRegionSubmitting] = useState(false)
  const [regionSubmitResult, setRegionSubmitResult] = useState(null)
  const [showRegionRename, setShowRegionRename] = useState(false)

  // Fetch available discord tags for dropdown (all users can assign tags)
  useEffect(() => {
    axios.get('/api/discord_tags').then(r => {
      setDiscordTags(r.data.tags || [])
    }).catch(() => {})
  }, [])

  // Auto-fill from user profile when logged in
  useEffect(() => {
    if (!user) return
    // Auto-fill discord username from profile
    if (user.username && !submitterDiscordUsername) {
      setSubmitterDiscordUsername(user.username)
    }
    // Auto-fill default community tag
    if (user.defaultCivTag && !system.discord_tag && !edit) {
      setSystem(prev => ({ ...prev, discord_tag: user.defaultCivTag }))
    }
    // Auto-fill reality and galaxy from profile defaults
    if (user.defaultReality && !edit) {
      setSystem(prev => ({ ...prev, reality: user.defaultReality }))
    }
    if (user.defaultGalaxy && !edit) {
      setSystem(prev => ({ ...prev, galaxy: user.defaultGalaxy }))
    }
  }, [user])

  useEffect(()=>{
    if(edit){
      axios.get(`/api/systems/${encodeURIComponent(edit)}`).then(r=>{
        setSystem(r.data)
        setOriginalTag(r.data.discord_tag)
        setHasStation(!!(r.data.space_station && Object.keys(r.data.space_station).length > 0))
      }).catch(()=>{})
    }
  }, [edit])

  // Auto-lookup region info when glyphs are decoded and reality/galaxy are set
  useEffect(() => {
    if (system.region_x === null || system.region_y === null || system.region_z === null) {
      setRegionInfo(null)
      return
    }
    const reality = system.reality || 'Normal'
    const galaxy = system.galaxy || 'Euclid'

    setRegionLoading(true)
    setRegionSubmitResult(null)
    setShowRegionRename(false)
    setProposedRegionName('')
    axios.get(`/api/regions/${system.region_x}/${system.region_y}/${system.region_z}`, {
      params: { reality, galaxy }
    })
      .then(r => {
        setRegionInfo(r.data)
        // Generate procedural names when we have glyphs
        if (system.glyph_code?.length === 12) {
          axios.get('/api/namegen', { params: { glyph: system.glyph_code, galaxy } })
            .then(ng => {
              // Update system name if it was auto-generated (not user-edited)
              setSystem(s => {
                const currentName = s.name || ''
                // Only overwrite if empty or if it matches a previous procedural name
                // (user hasn't manually typed something different)
                if (!currentName || currentName === s._lastProceduralName) {
                  return { ...s, name: ng.data.system_name, _lastProceduralName: ng.data.system_name }
                }
                return s
              })
              // Pre-fill region name for unnamed regions
              if (!r.data?.custom_name) {
                setProposedRegionName(ng.data.region_name || '')
              }
            })
            .catch(() => {})
        }
      })
      .catch(() => setRegionInfo(null))
      .finally(() => setRegionLoading(false))
  }, [system.region_x, system.region_y, system.region_z, system.reality, system.galaxy])

  // Submit a proposed region name
  async function submitRegionName() {
    if (!proposedRegionName.trim()) return
    setRegionSubmitting(true)
    setRegionSubmitResult(null)
    try {
      const submitted_by = isAdmin
        ? (user?.display_name || user?.discord_tag || 'admin')
        : (submitterDiscordUsername.trim() || 'anonymous')
      await axios.post(
        `/api/regions/${system.region_x}/${system.region_y}/${system.region_z}/submit`,
        {
          proposed_name: proposedRegionName.trim(),
          submitted_by,
          discord_tag: system.discord_tag || null,
          personal_discord_username: system.discord_tag === 'personal' ? personalDiscordUsername : submitterDiscordUsername.trim() || null,
          reality: system.reality || 'Normal',
          galaxy: system.galaxy || 'Euclid',
          submitter_profile_id: user?.profile_id || null
        }
      )
      setRegionSubmitResult({ success: true, message: 'Region name submitted for approval!' })
      setProposedRegionName('')
      setShowRegionRename(false)
      // Refresh region info to show the new pending name
      const r = await axios.get(`/api/regions/${system.region_x}/${system.region_y}/${system.region_z}`, {
        params: { reality: system.reality || 'Normal', galaxy: system.galaxy || 'Euclid' }
      })
      setRegionInfo(r.data)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to submit region name'
      setRegionSubmitResult({ success: false, message: msg })
    } finally {
      setRegionSubmitting(false)
    }
  }

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
    if(!system.reality) { alert('Reality is required. Please select Normal or Permadeath.'); return; }
    if(!system.galaxy) { alert('Galaxy is required. Please select which galaxy this system is in.'); return; }
    if(!system.glyph_code || system.glyph_code.length !== 12 || !/^[0-9A-Fa-f]{12}$/.test(system.glyph_code)) { alert('Portal Glyph Code is required and must be exactly 12 hex characters (0-9, A-F)'); return; }
    if(!system.star_type) { alert('Star Color is required'); return; }
    if(!system.economy_type) { alert('Economy Type is required'); return; }
    const isAbandoned = system.economy_type === 'None' || system.economy_type === 'Abandoned';
    if(!isAbandoned && !system.economy_level) { alert('Economy Tier is required'); return; }
    if(!isAbandoned && !system.conflict_level) { alert('Conflict Level is required'); return; }
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

    // Region naming is REQUIRED for unnamed regions (only if region coordinates are decoded)
    if (system.region_x !== null && system.region_y !== null && system.region_z !== null) {
      if (regionInfo && !regionInfo.custom_name && !regionInfo.pending_name) {
        alert('This region does not have a name yet. Please propose a region name before submitting your system.');
        return;
      }
    }

    // Discord community is now REQUIRED for all non-admin submissions
    if (!system.discord_tag && !isAdmin) {
      alert('Discord Community is required. Please select a community or choose "Personal" if you are not affiliated with a community.');
      return;
    }

    // Discord username is required for all submissions (for self-submission detection)
    if (!submitterDiscordUsername.trim() && !isAdmin) {
      alert('Your Discord username is required for all submissions.');
      return;
    }

    // If personal is selected, personal discord username is required
    if (system.discord_tag === 'personal' && !personalDiscordUsername.trim()) {
      alert('Discord username is required for personal submissions.');
      setPersonalDiscordModalOpen(true);
      return;
    }

    setIsSubmitting(true)
    try{
      // Submission path split: admins (including partners with system_create) save
      // directly to the systems table; non-admins go to the pending_systems queue.
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
        // Always include submitter discord username for self-submission detection
        if (submitterDiscordUsername.trim()) {
          payload.personal_discord_username = submitterDiscordUsername.trim()
        }
        // Include personal discord username if personal tag selected
        if (system.discord_tag === 'personal' && personalDiscordUsername.trim()) {
          payload.personal_discord_username = personalDiscordUsername.trim()
        }

        // If user is logged in with a profile, attach profile_id
        if (user?.profileId) {
          payload.profile_id = user.profileId
          const r = await axios.post('/api/submit_system', payload);
          alert(`System submitted for approval!\n\nSubmission ID: ${r.data.submission_id}\nSystem Name: ${r.data.system_name}\n\nAn admin will review your submission.`);
          navigate('/systems');
        } else {
          // Not logged in: do profile lookup before submitting
          const lookupName = submitterDiscordUsername.trim() || personalDiscordUsername.trim()
          if (lookupName) {
            try {
              const lookupRes = await axios.post('/api/profiles/lookup', { username: lookupName })
              const lookupData = lookupRes.data

              if (lookupData.status === 'found') {
                // Exact match - attach profile_id and submit
                payload.profile_id = lookupData.profile.id
                const r = await axios.post('/api/submit_system', payload);
                alert(`System submitted for approval!\n\nSubmission ID: ${r.data.submission_id}\nSystem Name: ${r.data.system_name}\n\nAn admin will review your submission.`);
                navigate('/systems');
              } else if (lookupData.status === 'suggestions') {
                // Fuzzy matches - show claim modal, defer submission
                setProfileSuggestions(lookupData.suggestions)
                setProfileModalStatus('suggestions')
                setProfileModalOpen(true)
                setPendingSubmitPayload(payload)
                return // Don't navigate yet
              } else {
                // Not found - show create modal, defer submission
                setProfileModalStatus('not_found')
                setProfileModalOpen(true)
                setPendingSubmitPayload(payload)
                return // Don't navigate yet
              }
            } catch {
              // Profile lookup failed - submit anyway without profile_id
              const r = await axios.post('/api/submit_system', payload);
              alert(`System submitted for approval!\n\nSubmission ID: ${r.data.submission_id}\nSystem Name: ${r.data.system_name}\n\nAn admin will review your submission.`);
              navigate('/systems');
            }
          } else {
            const r = await axios.post('/api/submit_system', payload);
            alert(`System submitted for approval!\n\nSubmission ID: ${r.data.submission_id}\nSystem Name: ${r.data.system_name}\n\nAn admin will review your submission.`);
            navigate('/systems');
          }
        }
      }
    } catch(err){
      const errorMsg = err.response?.data?.detail || err.message || err;
      alert(`${isAdmin ? 'Save' : 'Submission'} failed: ${errorMsg}`);
    } finally {
      setIsSubmitting(false)
    }
  }

  // Profile claim/create handlers for the ProfileClaimModal
  async function handleProfileUse(profileId) {
    setResolvedProfileId(profileId)
    setProfileModalOpen(false)
    // Resume submission with the claimed profile
    if (pendingSubmitPayload) {
      try {
        const payload = { ...pendingSubmitPayload, profile_id: profileId }
        const r = await axios.post('/api/submit_system', payload)
        alert(`System submitted for approval!\n\nSubmission ID: ${r.data.submission_id}\nSystem Name: ${r.data.system_name}\n\nAn admin will review your submission.`)
        navigate('/systems')
      } catch (err) {
        alert(`Submission failed: ${err.response?.data?.detail || err.message}`)
      } finally {
        setPendingSubmitPayload(null)
        setIsSubmitting(false)
      }
    }
  }

  async function handleProfileCreate(profileData) {
    try {
      const createRes = await axios.post('/api/profiles/create', profileData)
      const newProfileId = createRes.data.profile.id
      setResolvedProfileId(newProfileId)
      setProfileModalStatus('created')
      // Modal stays open - user clicks "Continue with Submission" to proceed
    } catch (err) {
      alert(`Profile creation failed: ${err.response?.data?.detail || err.message}`)
      setIsSubmitting(false)
    }
  }

  // Called when user clicks "Continue with Submission" on the created profile modal
  async function handleProfileCreatedContinue() {
    setProfileModalOpen(false)
    if (pendingSubmitPayload && resolvedProfileId) {
      try {
        const payload = { ...pendingSubmitPayload, profile_id: resolvedProfileId }
        const r = await axios.post('/api/submit_system', payload)
        alert(`System submitted for approval!\n\nSubmission ID: ${r.data.submission_id}\nSystem Name: ${r.data.system_name}\n\nAn admin will review your submission.`)
        navigate('/systems')
      } catch (err) {
        alert(`Submission failed: ${err.response?.data?.detail || err.message}`)
      } finally {
        setPendingSubmitPayload(null)
        setIsSubmitting(false)
      }
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

    // Generate procedural names from glyphs
    if (decodedData.glyph && decodedData.glyph.length === 12) {
      const galaxy = system.galaxy || 'Euclid'
      axios.get('/api/namegen', { params: { glyph: decodedData.glyph, galaxy } })
        .then(r => {
          setSystem(s => {
            const currentName = s.name || ''
            if (!currentName || currentName === s._lastProceduralName) {
              return { ...s, name: r.data.system_name, _lastProceduralName: r.data.system_name }
            }
            return { ...s, _lastProceduralName: r.data.system_name }
          })
          if (r.data.region_name) {
            setProposedRegionName(prev => prev || r.data.region_name)
          }
        })
        .catch(() => {})
    }
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
      moons: [],
      has_rings: 0,
      is_dissonant: 0,
      is_infested: 0,
      extreme_weather: 0,
      water_world: 0,
      vile_brood: 0,
      ancient_bones: 0,
      salvageable_scrap: 0,
      storm_crystals: 0,
      gravitino_balls: 0,
      is_gas_giant: 0,
      is_bubble: 0,
      is_floating_islands: 0,
      exotic_trophy: ''
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
      // Auto-generate safe orbital position for station
      const position = generateStationPosition(system.planets || [])
      // Get available trade goods based on economy type AND tier (wealth level)
      const economyGoods = getTradeGoodsForEconomyAndTier(system.economy_type || 'None', system.economy_level || 'T3')
      setSystem({...system, space_station: {
        name: `${system.name || 'System'} Station`,
        race: system.dominant_lifeform || 'Gek',
        trade_goods: economyGoods.map(g => g.id), // Default: all goods available for this tier
        ...position
      }})
    } else {
      setSystem({...system, space_station: null})
    }
  }

  // Toggle a single trade good in the station
  function toggleTradeGood(goodId){
    if(!system.space_station) return
    const currentGoods = system.space_station.trade_goods || []
    const newGoods = currentGoods.includes(goodId)
      ? currentGoods.filter(id => id !== goodId)
      : [...currentGoods, goodId]
    setSystem({...system, space_station: {...system.space_station, trade_goods: newGoods}})
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
        <label className="block mb-2">System Name <input placeholder="Auto-generated from glyphs — verify in-game" aria-label="Name" className="w-full mt-1" value={system.name || ''} onChange={e=>setField('name', e.target.value)} required/></label>

        <div className="mt-4">
          <h3 className="text-lg font-semibold mb-2 text-purple-300">Portal Glyph Coordinates <span className="text-red-400 text-sm">*</span></h3>
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
              className={`w-full p-2 border rounded bg-gray-700 ${!system.reality ? 'border-red-500 text-gray-400' : 'border-gray-600'}`}
              value={system.reality || ''}
              onChange={e => setField('reality', e.target.value)}
              required
            >
              <option value="" disabled>-- Select Reality --</option>
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
              value={system.galaxy || ''}
              onChange={v => setField('galaxy', v || '')}
              placeholder="-- Select Galaxy --"
            />
            <p className="text-xs text-gray-500 mt-1">
              Search by galaxy number (1-256) or name
            </p>
          </div>
        </div>

        {/* Region Information - shown when glyphs decoded + reality/galaxy set */}
        {system.region_x !== null && system.region_y !== null && system.region_z !== null && (
          <div className="mt-4 p-4 bg-gray-800/50 rounded border border-gray-700">
            <h3 className="text-lg font-semibold mb-3 text-purple-300">Region Information</h3>

            {regionLoading ? (
              <div className="text-sm text-gray-400">Looking up region...</div>
            ) : regionInfo ? (
              <div>
                {/* Coordinates always shown */}
                <div className="text-sm text-gray-400 mb-2">
                  Coordinates: <span className="font-mono text-purple-300">[{regionInfo.region_x}, {regionInfo.region_y}, {regionInfo.region_z}]</span>
                  <span className="ml-2 text-gray-500">({regionInfo.reality} / {regionInfo.galaxy})</span>
                  {regionInfo.system_count > 0 && (
                    <span className="ml-2 text-gray-500">{regionInfo.system_count} system{regionInfo.system_count !== 1 ? 's' : ''} mapped</span>
                  )}
                </div>

                {/* Case 1: Region has an approved name */}
                {regionInfo.custom_name && (
                  <div className="p-3 bg-green-900/30 border border-green-700 rounded">
                    <div className="flex items-center justify-between">
                      <span className="text-green-300 font-semibold text-lg">{regionInfo.custom_name}</span>
                      {!showRegionRename && !regionInfo.pending_name && (
                        <button
                          type="button"
                          onClick={() => setShowRegionRename(true)}
                          className="text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded hover:bg-gray-600"
                        >
                          Propose Name Change
                        </button>
                      )}
                    </div>

                    {/* Pending rename for a named region */}
                    {regionInfo.pending_name && (
                      <div className="mt-2 p-2 bg-yellow-900/30 border border-yellow-700 rounded text-sm">
                        <span className="text-yellow-300">Pending rename: </span>
                        <span className="text-yellow-200 font-semibold">{regionInfo.pending_name.proposed_name}</span>
                        <span className="text-gray-500 ml-2">by {regionInfo.pending_name.submitted_by}</span>
                      </div>
                    )}

                    {/* Inline rename form */}
                    {showRegionRename && !regionInfo.pending_name && (
                      <div className="mt-3 flex items-center gap-2">
                        <input
                          type="text"
                          value={proposedRegionName}
                          onChange={e => setProposedRegionName(e.target.value)}
                          placeholder="New region name..."
                          className="flex-1 p-2 border rounded bg-gray-700 border-gray-600 text-sm"
                          maxLength={50}
                        />
                        <button
                          type="button"
                          onClick={submitRegionName}
                          disabled={regionSubmitting || !proposedRegionName.trim()}
                          className="px-3 py-2 bg-purple-600 text-white rounded text-sm hover:bg-purple-500 disabled:opacity-50"
                        >
                          {regionSubmitting ? 'Submitting...' : 'Submit'}
                        </button>
                        <button
                          type="button"
                          onClick={() => { setShowRegionRename(false); setProposedRegionName('') }}
                          className="px-3 py-2 bg-gray-600 text-white rounded text-sm hover:bg-gray-500"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Case 2: No name, has pending submission */}
                {!regionInfo.custom_name && regionInfo.pending_name && (
                  <div className="p-3 bg-yellow-900/30 border border-yellow-700 rounded">
                    <div className="text-yellow-300 text-sm mb-1">Pending region name:</div>
                    <div className="text-yellow-200 font-semibold text-lg">{regionInfo.pending_name.proposed_name}</div>
                    <div className="text-gray-500 text-xs mt-1">
                      Submitted by {regionInfo.pending_name.submitted_by}
                      {regionInfo.pending_name.submission_date && ` on ${new Date(regionInfo.pending_name.submission_date).toLocaleDateString()}`}
                    </div>
                  </div>
                )}

                {/* Case 3: No name, no pending - allow proposal */}
                {!regionInfo.custom_name && !regionInfo.pending_name && (
                  <div className="p-3 bg-amber-900/30 border border-amber-600 rounded">
                    <div className="text-amber-300 text-sm mb-2 font-semibold">This region has no name yet. A region name is required before submission. <span className="text-red-400">*</span></div>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={proposedRegionName}
                        onChange={e => setProposedRegionName(e.target.value)}
                        placeholder="Proposed region name..."
                        className="flex-1 p-2 border rounded bg-gray-700 border-gray-600 text-sm"
                        maxLength={50}
                      />
                      <button
                        type="button"
                        onClick={submitRegionName}
                        disabled={regionSubmitting || !proposedRegionName.trim()}
                        className="px-3 py-2 bg-purple-600 text-white rounded text-sm hover:bg-purple-500 disabled:opacity-50"
                      >
                        {regionSubmitting ? 'Submitting...' : 'Submit'}
                      </button>
                    </div>
                  </div>
                )}

                {/* Success/error feedback */}
                {regionSubmitResult && (
                  <div className={`mt-2 p-2 rounded text-sm ${
                    regionSubmitResult.success
                      ? 'bg-green-900/30 border border-green-700 text-green-300'
                      : 'bg-red-900/30 border border-red-700 text-red-300'
                  }`}>
                    {regionSubmitResult.message}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-sm text-gray-500">Unable to load region information.</div>
            )}
          </div>
        )}

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
                style={{
                  color: system.star_type === 'Yellow' ? '#fbbf24' :
                         system.star_type === 'Red' ? '#ef4444' :
                         system.star_type === 'Green' ? '#22c55e' :
                         system.star_type === 'Blue' ? '#3b82f6' :
                         system.star_type === 'Purple' ? '#a855f7' : 'inherit'
                }}
              >
                <option value="" style={{ color: '#9ca3af' }}>-- Select --</option>
                <option value="Yellow" style={{ color: '#fbbf24' }}>☀ Yellow</option>
                <option value="Red" style={{ color: '#ef4444' }}>🔴 Red</option>
                <option value="Green" style={{ color: '#22c55e' }}>🟢 Green</option>
                <option value="Blue" style={{ color: '#3b82f6' }}>🔵 Blue</option>
                <option value="Purple" style={{ color: '#a855f7' }}>🟣 Purple</option>
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
                onChange={e => {
                  const val = e.target.value;
                  if (val === 'None' || val === 'Abandoned') {
                    setSystem(s => ({...s, economy_type: val, economy_level: 'None', conflict_level: 'None'}));
                  } else {
                    // Clear auto-set values if switching back from None/Abandoned
                    setSystem(s => ({...s, economy_type: val,
                      economy_level: s.economy_level === 'None' ? '' : s.economy_level,
                      conflict_level: s.conflict_level === 'None' ? '' : s.conflict_level
                    }));
                  }
                }}
                required
              >
                <option value="">-- Select --</option>
                <option value="Trading">⚖️ Trading</option>
                <option value="Mining">⛏️ Mining</option>
                <option value="Manufacturing">🏭 Manufacturing</option>
                <option value="Technology">💻 Technology</option>
                <option value="Scientific">🔬 Scientific</option>
                <option value="Power Generation">⚡ Power Generation</option>
                <option value="Mass Production">📦 Mass Production</option>
                <option value="Advanced Materials">🔧 Advanced Materials</option>
                <option value="Pirate">☠️ Pirate</option>
                <option value="None">⭕ None</option>
                <option value="Abandoned">🚫 Abandoned</option>
              </select>
            </div>

            {/* Economy Tier */}
            <div>
              <label className="block text-sm font-medium mb-1">
                Economy Tier {!(system.economy_type === 'None' || system.economy_type === 'Abandoned') && <span className="text-red-400">*</span>}
              </label>
              <select
                className={`w-full p-2 border rounded bg-gray-700 ${!system.economy_level ? 'border-red-500' : 'border-gray-600'} ${(system.economy_type === 'None' || system.economy_type === 'Abandoned') ? 'opacity-50 cursor-not-allowed' : ''}`}
                value={system.economy_level || ''}
                onChange={e => setField('economy_level', e.target.value)}
                required={!(system.economy_type === 'None' || system.economy_type === 'Abandoned')}
                disabled={system.economy_type === 'None' || system.economy_type === 'Abandoned'}
              >
                <option value="">-- Select --</option>
                <option value="T1">★ (Low)</option>
                <option value="T2">★★ (Medium)</option>
                <option value="T3">★★★ (High)</option>
                <option value="T4">☠ (Pirate)</option>
                <option value="None">⭕ None</option>
              </select>
            </div>

            {/* Conflict Level */}
            <div>
              <label className="block text-sm font-medium mb-1">
                Conflict Level {!(system.economy_type === 'None' || system.economy_type === 'Abandoned') && <span className="text-red-400">*</span>}
              </label>
              <select
                className={`w-full p-2 border rounded bg-gray-700 ${!system.conflict_level ? 'border-red-500' : 'border-gray-600'} ${(system.economy_type === 'None' || system.economy_type === 'Abandoned') ? 'opacity-50 cursor-not-allowed' : ''}`}
                value={system.conflict_level || ''}
                onChange={e => setField('conflict_level', e.target.value)}
                required={!(system.economy_type === 'None' || system.economy_type === 'Abandoned')}
                disabled={system.economy_type === 'None' || system.economy_type === 'Abandoned'}
              >
                <option value="">-- Select --</option>
                <option value="Low">🔥 Low</option>
                <option value="Medium">🔥🔥 Medium</option>
                <option value="High">🔥🔥🔥 High</option>
                <option value="Pirate">☠️ Pirate</option>
                <option value="None">⭕ None</option>
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
                <option value="Gek">🐸 Gek</option>
                <option value="Vy'keen">⚔️ Vy'keen</option>
                <option value="Korvax">🤖 Korvax</option>
                <option value="None">👻 None (Abandoned)</option>
              </select>
            </div>

            {/* Stellar Classification */}
            <div>
              <label className="block text-sm font-medium mb-1 flex items-center gap-1.5">
                Spectral Class
                <span className="relative group">
                  <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-gray-600 text-gray-300 text-[10px] font-bold cursor-help select-none">?</span>
                  <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 p-2.5 rounded-lg bg-gray-800 border border-gray-600 shadow-xl text-xs hidden group-hover:block z-50">
                    <span className="block text-gray-300 mb-1.5">Letter + Number (0-9) + Suffix</span>
                    <span className="block text-gray-400 mb-2">e.g. G2pf, M7, O3f, E5p</span>
                    <span className="flex flex-wrap gap-x-2 gap-y-1">
                      <span><span className="text-blue-400 font-medium">O/B</span><span className="text-gray-500"> Blue</span></span>
                      <span><span className="text-yellow-400 font-medium">F/G</span><span className="text-gray-500"> Yellow</span></span>
                      <span><span className="text-red-400 font-medium">K/M</span><span className="text-gray-500"> Red</span></span>
                      <span><span className="text-green-400 font-medium">E</span><span className="text-gray-500"> Green</span></span>
                      <span><span className="text-purple-400 font-medium">X/Y</span><span className="text-gray-500"> Purple</span></span>
                    </span>
                    <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-800"></span>
                  </span>
                </span>
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  className="w-full p-2 border rounded bg-gray-700 border-gray-600 font-mono"
                  value={system.stellar_classification || ''}
                  onChange={e => setField('stellar_classification', e.target.value.slice(0, 6))}
                  placeholder="e.g. G2pf, M7, O3f"
                  style={{
                    color: (() => {
                      const firstChar = (system.stellar_classification || '')[0]?.toUpperCase();
                      switch(firstChar) {
                        case 'O': return '#9999ff';
                        case 'B': return '#aaaaff';
                        case 'A': return '#caf0f8';
                        case 'F': return '#ffffcc';
                        case 'G': return '#fbbf24';
                        case 'K': return '#fb923c';
                        case 'M': return '#ef4444';
                        case 'E': return '#22c55e';
                        case 'X': case 'Y': return '#a855f7';
                        default: return 'inherit';
                      }
                    })()
                  }}
                />
                {system.stellar_classification && (
                  <span className={`px-2 py-1 rounded text-xs font-medium whitespace-nowrap ${
                    (() => {
                      const firstChar = (system.stellar_classification || '')[0]?.toUpperCase();
                      switch(firstChar) {
                        case 'O': case 'B': return 'bg-blue-900 text-blue-200';
                        case 'F': case 'G': return 'bg-yellow-900 text-yellow-200';
                        case 'K': case 'M': return 'bg-red-900 text-red-200';
                        case 'E': return 'bg-green-900 text-green-200';
                        case 'X': case 'Y': return 'bg-purple-900 text-purple-200';
                        default: return 'bg-gray-700 text-gray-300';
                      }
                    })()
                  }`}>
                    {(() => {
                      const firstChar = (system.stellar_classification || '')[0]?.toUpperCase();
                      switch(firstChar) {
                        case 'O': case 'B': return 'Blue';
                        case 'F': case 'G': return 'Yellow';
                        case 'K': case 'M': return 'Red';
                        case 'E': return 'Green';
                        case 'X': case 'Y': return 'Purple';
                        default: return '';
                      }
                    })()}
                  </span>
                )}
              </div>
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

        {/* Your Discord Username - REQUIRED for all submissions */}
        {!isAdmin && (
          <div className="mt-3">
            <label className="block text-sm font-medium mb-1">
              Your Discord Username <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              className={`w-full p-2 border rounded bg-gray-700 ${!submitterDiscordUsername.trim() ? 'border-red-500' : 'border-gray-600'}`}
              value={submitterDiscordUsername}
              onChange={e => setSubmitterDiscordUsername(e.target.value)}
              placeholder="e.g., username or username#1234"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              Your Discord username is required so we can contact you about your submission if needed.
            </p>
          </div>
        )}

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
                <div className="mt-1">
                  <button className="px-3 py-1.5 bg-sky-600 text-white rounded text-sm" onClick={() => editPlanet(i)}>Edit</button>
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
            <span>🛸 Has Space Station</span>
          </label>

          {hasStation && system.space_station && (
            <div className="ml-6 p-3 bg-purple-900/30 rounded border border-purple-700">
              <div className="mb-3">
                <label className="block text-sm">Station Name</label>
                <input
                  className="w-full mt-1"
                  value={system.space_station.name || ''}
                  onChange={(e) => setStationField('name', e.target.value)}
                  placeholder="Station Name"
                />
              </div>

              <div className="mb-3">
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

              {/* Orbital Position (auto-calculated, read-only) */}
              <div className="mb-3 p-2 bg-gray-800 rounded border border-gray-600">
                <div className="text-sm text-gray-400 mb-1">Orbital Position (auto-calculated)</div>
                <div className="text-sm">
                  <span className="text-cyan-300">Distance:</span> {system.space_station.orbitalRadius?.toFixed(1) || '?'} units from star
                </div>
                {system.space_station.slot && (
                  <div className="text-xs text-gray-400 mt-1">
                    Placement: {system.space_station.slot}
                  </div>
                )}
              </div>

              {/* Trade Goods - based on economy type */}
              <div className="mb-2">
                <label className="block text-sm font-medium mb-2">
                  Trade Goods Sold
                  {system.economy_type && system.economy_level && (
                    <span className="text-xs text-gray-400 ml-2">
                      ({system.economy_type} economy, {system.economy_level === 'T3' ? 'High' : system.economy_level === 'T2' ? 'Medium' : system.economy_level === 'T1' ? 'Low' : 'Pirate'} wealth)
                    </span>
                  )}
                </label>
                {!system.economy_type || system.economy_type === 'None' || system.economy_type === 'Abandoned' ? (
                  <div className="text-xs text-gray-500 italic">
                    No trade goods available (abandoned system or no economy type selected)
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 max-h-48 overflow-y-auto p-2 bg-gray-800 rounded">
                    {getTradeGoodsForEconomyAndTier(system.economy_type, system.economy_level).map(good => (
                      <label key={good.id} className="flex items-center space-x-2 text-sm cursor-pointer hover:bg-gray-700 p-1 rounded">
                        <input
                          type="checkbox"
                          checked={(system.space_station.trade_goods || []).includes(good.id)}
                          onChange={() => toggleTradeGood(good.id)}
                          className="w-3 h-3"
                        />
                        <span className="text-gray-200">
                          {good.name}
                          <span className="text-xs text-gray-500 ml-1">(T{good.tier})</span>
                        </span>
                      </label>
                    ))}
                  </div>
                )}
                <p className="text-xs text-gray-500 mt-1">
                  Select which trade goods this station sells (based on economy tier)
                </p>
              </div>

              {system.space_station.fallback && (
                <div className="mt-2 text-xs text-yellow-300 bg-yellow-900/30 border border-yellow-700 p-2 rounded">
                  Station placed in fallback position - system has unusual planet configuration
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
          <div className="flex flex-col sm:flex-row gap-2">
            <Button className="btn-primary w-full sm:w-auto" type="submit" onClick={() => { explicitSubmitRef.current = true }} disabled={isSubmitting}>
              {isSubmitting ? 'Submitting...' : (isAdmin ? 'Save System' : 'Submit for Approval')}
            </Button>
            <Button className="bg-gray-200 text-gray-800 w-full sm:w-auto" onClick={()=> navigate('/systems')} disabled={isSubmitting}>Cancel</Button>
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

        {/* Profile claim/create modal for first-time submitters */}
        {profileModalOpen && (
          <ProfileClaimModal
            status={profileModalStatus}
            suggestions={profileSuggestions}
            username={submitterDiscordUsername.trim() || personalDiscordUsername.trim()}
            onUse={handleProfileUse}
            onCreate={handleProfileCreate}
            onContinue={handleProfileCreatedContinue}
            onClose={() => {
              setProfileModalOpen(false)
              setPendingSubmitPayload(null)
              setIsSubmitting(false)
            }}
          />
        )}
        </form>
      </Card>
    </div>
  )
}
