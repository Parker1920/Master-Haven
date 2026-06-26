/**
 * System Submission Wizard — v1 rebuild (May 2026).
 *
 * Replaces the prior single-form wizard. New shape:
 *  - Mode gate: Easy (4 steps) vs Advanced (single page, sidebar nav).
 *  - Sticky top progress bar driven by completeness score.
 *  - Sticky mode toolbar with autosave indicator + Help button.
 *  - Optional preview panel (right column) showing live system state.
 *  - localStorage drafts (1s debounce + 10s safety net).
 *  - Edit-mode banner with prior edit history when ?edit=<id>.
 *  - Validation summary with click-to-focus.
 *  - Conflict resolution modal at submit (mocked for now until backend
 *    surfaces per-field divergences).
 *  - Co-authors chip input + expedition picker.
 *  - Post-submit success screen with "Submit Another" preserving identity.
 *
 * Mockup is the design contract: C:\Master-Haven\wizard-mockup-v1_1.html.
 * Backend contract: routes/approvals.py (submit_system), control_room_api.py
 * (save_system), routes/expeditions.py, routes/wizard.py.
 */
import React, { useEffect, useMemo, useState, useContext, useRef, useCallback } from 'react'
import axios from 'axios'
import { useLocation, useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import Modal from '../components/Modal'
import GlyphPicker from '../components/GlyphPicker'
import PlanetEditor from '../components/PlanetEditor'
import SearchableSelect from '../components/SearchableSelect'
import ProfileClaimModal from '../components/ProfileClaimModal'
import { AuthContext } from '../utils/AuthContext'
import { generateStationPosition } from '../utils/stationPlacement'
import { getTradeGoodsForEconomyAndTier } from '../utils/economyTradeGoods'
import { GALAXIES, REALITIES } from '../data/galaxies'
import { PLANET_DEFAULTS, MOON_DEFAULTS } from '../data/bodyDefaults'
import { checkExistingSystem } from '../utils/api'

import useDebounce from '../hooks/useDebounce'
import useWizardDraft, { readDraft, clearDraft } from '../hooks/useWizardDraft'
import useCompletenessScore from '../hooks/useCompletenessScore'
import useFormDirty from '../hooks/useFormDirty'

import WizardModeGate from '../components/wizard/WizardModeGate'
import WizardSidebar from '../components/wizard/WizardSidebar'
import WizardPreviewPanel from '../components/wizard/WizardPreviewPanel'
import WizardAdvancedPreview from '../components/wizard/WizardAdvancedPreview'
import WizardProgressBar from '../components/wizard/WizardProgressBar'
import WizardModeToolbar from '../components/wizard/WizardModeToolbar'
import EditModeBanner from '../components/wizard/EditModeBanner'
import ConflictResolutionModal from '../components/wizard/ConflictResolutionModal'
import CoAuthorChipInput from '../components/wizard/CoAuthorChipInput'
import ExpeditionPicker from '../components/wizard/ExpeditionPicker'
import EventPicker from '../components/wizard/EventPicker'
import RestoreDraftBanner from '../components/wizard/RestoreDraftBanner'
import HelpPanel from '../components/wizard/HelpPanel'
import HelpChip from '../components/wizard/HelpChip'
import { systemPath } from '../utils/systemUrl'
import HelpFab from '../components/wizard/HelpFab'
import ValidationSummary from '../components/wizard/ValidationSummary'
import SuccessScreen from '../components/wizard/SuccessScreen'
import DiscoveryInlineList from '../components/wizard/DiscoveryInlineList'
import DiscoverySubmitModal from '../components/DiscoverySubmitModal'

// Fields tracked by the conflict-resolution check on edit submit.
// Planets/moons are deep arrays — too noisy for per-field conflicts; we only
// surface system-level scalar conflicts here.
const CONFLICT_FIELDS = [
  { key: 'name', label: 'System Name' },
  { key: 'star_type', label: 'Star Color' },
  { key: 'economy_type', label: 'Economy Type' },
  { key: 'economy_level', label: 'Economy Tier' },
  { key: 'conflict_level', label: 'Conflict Level' },
  { key: 'dominant_lifeform', label: 'Dominant Lifeform' },
  { key: 'stellar_classification', label: 'Spectral Class' },
  { key: 'game_version', label: 'Game Version' },
  { key: 'description', label: 'Description' },
]

// Fields tracked for diff-highlighting on edit mode (broader than CONFLICT_FIELDS
// since diff highlights are visual cues, not blockers).
const DIFFABLE_FIELDS = new Set([
  'name', 'galaxy', 'reality', 'star_type', 'economy_type', 'economy_level',
  'conflict_level', 'dominant_lifeform', 'stellar_classification', 'game_version',
  'description', 'glyph_code', 'discord_tag',
])

function valuesDiffer(a, b) {
  const norm = (v) => (v == null || v === '' ? null : String(v))
  return norm(a) !== norm(b)
}

// "1st" / "2nd" / "3rd" / "4th"... used by the region context counter.
function ordinalSuffix(n) {
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return s[(v - 20) % 10] || s[v] || s[0]
}

// ===========================================================================
// Constants
// ===========================================================================
const SECTIONS = [
  { id: 'portal', label: 'Portal Address' },
  { id: 'attrs', label: 'System Attributes' },
  { id: 'planets', label: 'Planets & Moons' },
  { id: 'station', label: 'Space Station' },
  { id: 'discoveries', label: 'Discoveries' },
  { id: 'identity', label: 'Identity' },
  { id: 'submit', label: 'Submit' },
]

const EMPTY_SYSTEM = {
  id: '',
  name: '',
  galaxy: '',
  reality: '',
  glyph_code: '',
  x: '', y: '', z: '',
  region_x: null, region_y: null, region_z: null,
  glyph_planet: 0, glyph_solar_system: 1,
  description: '',
  star_type: '',
  economy_type: '',
  economy_level: '',
  conflict_level: '',
  dominant_lifeform: '',
  stellar_classification: '',
  game_version: '',     // wizard v1
  game_mode: 'Normal',  // wizard v1.56 — was silently defaulted backend-side
  discord_tag: null,
  planets: [],
  space_station: null,
  // Definitive "this system has no space station" flag (1.79.0). Distinct from
  // a null space_station, which just means "not documented yet".
  no_space_station: false,
  // wizard v1 identity extras
  coauthors: [],
  expedition_id: null,
  event_id: null,       // event participation (opt-in competition)
  submitter_notes: '',
}

// PLANET_DEFAULTS / MOON_DEFAULTS now live in ../data/bodyDefaults (imported
// above) so the count-dropdown generator and the manual "Add Moon" modal build
// identical body shells.

// ===========================================================================
// Component
// ===========================================================================
function useQuery() {
  return new URLSearchParams(useLocation().search)
}

export default function Wizard() {
  const query = useQuery()
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const { isAdmin, isPartner, user } = auth || {}
  const editId = query.get('edit')
  const isEditMode = !!editId

  // ----- Top-level UI state -----
  const [flow, setFlow] = useState(null)          // null | 'easy' | 'advanced'
  const [activeSection, setActiveSection] = useState('portal')
  const [easyStep, setEasyStep] = useState(0)
  const [requiredOnly, setRequiredOnly] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [helpAnchor, setHelpAnchor] = useState(null)
  // openHelpAt(anchor) is passed down to HelpChip and HelpFab so any
  // (?) icon next to a confusing field can deep-link into the panel.
  const openHelpAt = (anchor) => { setHelpAnchor(anchor || null); setHelpOpen(true) }

  // Restore-draft banner state
  const [draftSnapshot, setDraftSnapshot] = useState(null)
  const [draftBannerOpen, setDraftBannerOpen] = useState(false)
  const draftLoadedRef = useRef(false)

  // Submit/result state
  const [system, setSystem] = useState(EMPTY_SYSTEM)
  const [originalSystem, setOriginalSystem] = useState(null)  // edit-mode baseline (loaded from server)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitResult, setSubmitResult] = useState(null)
  const [submitError, setSubmitError] = useState(null)

  // Discoveries — owned by the wizard so DiscoveryInlineList stays controlled.
  // Co-submitted on the system payload as `discoveries_draft` (resolved to
  // planet/moon links BY NAME by the backend); never a separate per-discovery
  // POST. One route for both trusted and member submissions.
  const [discoveries, setDiscoveries] = useState([])
  // Edit mode only: live discoveries already linked to this system. Each row
  // has an Edit button that opens the shared discovery submit modal in edit
  // mode — that change rides through pending_discoveries (edit_discovery_id)
  // and normal approval, separate from this system's own edit. New discoveries
  // are added in the editable list below (they ride as `discoveries_draft`).
  const [existingDiscoveries, setExistingDiscoveries] = useState([])
  // The existing discovery currently open in the edit modal (null = closed).
  const [editingDiscovery, setEditingDiscovery] = useState(null)

  // Same-name soft warning (mockup v11CheckSameName 9937)
  const [sameNameMatches, setSameNameMatches] = useState([])
  const debouncedNameForLookup = useDebounce(system.name, 600)

  // Region naming — Option B (deferred): proposed name is held in local
  // state and submitted ATOMICALLY with the system payload so the user's
  // discord identity is guaranteed to be attached. No live API call here.
  const [regionInfo, setRegionInfo] = useState(null)
  const [regionLoading, setRegionLoading] = useState(false)
  const [proposedRegionName, setProposedRegionName] = useState('')
  const [regionNameSavedAt, setRegionNameSavedAt] = useState(null)  // timestamp for the "✓ Saved" flash

  // Discord/identity state
  const [discordTags, setDiscordTags] = useState([])
  const [submitterDiscordUsername, setSubmitterDiscordUsername] = useState('')
  const [personalDiscordUsername, setPersonalDiscordUsername] = useState('')
  const [personalModalOpen, setPersonalModalOpen] = useState(false)

  // Profile claim flow
  const [profileModalOpen, setProfileModalOpen] = useState(false)
  const [profileModalStatus, setProfileModalStatus] = useState(null)
  const [profileSuggestions, setProfileSuggestions] = useState([])
  const [resolvedProfileId, setResolvedProfileId] = useState(null)
  const [pendingSubmitPayload, setPendingSubmitPayload] = useState(null)

  // Existing-system pull banner (when 12 glyphs entered and a match is found)
  const [existingMatch, setExistingMatch] = useState(null)

  // Conflict resolution modal
  const [conflictModalOpen, setConflictModalOpen] = useState(false)
  const [conflicts, setConflicts] = useState([])

  // ----- Planet modal state -----
  const [planetModalOpen, setPlanetModalOpen] = useState(false)
  const [editingPlanetIndex, setEditingPlanetIndex] = useState(null)
  const [editingPlanet, setEditingPlanet] = useState(null)

  // ----- Has-station toggle (mirrors space_station presence) -----
  const [hasStation, setHasStation] = useState(false)

  // ----- Refs -----
  const explicitSubmitRef = useRef(false)
  // Once the user types into the System Name field, the procgen / region-info
  // useEffect must STOP auto-overwriting their input — even on subsequent
  // reality/galaxy changes that re-trigger /api/namegen. The stale
  // `_lastProceduralName` sentinel alone wasn't enough: if the user typed a
  // name that matched the last procgen, OR cleared the field intending to
  // retype, the auto-fill kicked in and clobbered intent.
  const userEditedNameRef = useRef(false)
  // Same dual-guard for the proposed region name. Pre-fix the field had only
  // a `prev || newName` short-circuit, which silently dropped namegen updates
  // when the user changed galaxy (state was already non-empty from the prior
  // galaxy's auto-fill, so the OR never reached the new value).
  // `userEditedRegionRef` flips on user keystroke; `lastProceduralRegionRef`
  // remembers what auto-gen last wrote so we can tell "still the suggestion"
  // from "user customized it".
  const userEditedRegionRef = useRef(false)
  const lastProceduralRegionRef = useRef('')
  // Captures the originally-loaded space_station on edit so toggling the
  // station off/on doesn't replace a real loaded station with an
  // auto-generated placeholder. Cleared on submit / Submit Another.
  const originalStationRef = useRef(null)
  // Captures full coauthor objects {username, profile_id, credited_at}
  // on edit-mode load so we can preserve metadata on round-trip. The
  // CoAuthorChipInput renders simple string usernames, so the system
  // state only holds strings — this ref carries the rest so buildPayload
  // can re-attach profile_id / credited_at on submit.
  const originalCoauthorsRef = useRef([])

  // ----- Hooks: drafts / completeness / dirty tracking -----
  const profileId = user?.profileId || user?.profile_id || null
  const { lastSavedAt, clear: clearWizardDraft } = useWizardDraft(
    isEditMode ? null : system,    // skip drafts in edit mode (we're working off live data)
    profileId,
    { enabled: !isEditMode && flow != null }
  )
  const completeness = useCompletenessScore(system)
  // Form-dirty tracking for the beforeunload guard. We capture markClean
  // so the unload prompt doesn't fire after a successful submit or
  // Submit-Another reset.
  const { markClean: markFormClean } = useFormDirty(system, originalSystem)

  // ===========================================================================
  // Initialization
  // ===========================================================================

  // Edit-mode load + originalSystem capture
  useEffect(() => {
    if (!editId) return
    axios.get(`/api/systems/${encodeURIComponent(editId)}`)
      .then((r) => {
        const data = r.data || {}
        const merged = { ...EMPTY_SYSTEM, ...data }
        // Normalize coauthors to string[] (response is [{username, profile_id, credited_at}])
        // and stash the full objects so submit can re-attach metadata for
        // names that survived the edit — preserves credited_at + profile_id
        // for users who weren't removed.
        originalCoauthorsRef.current = Array.isArray(data.coauthors) ? data.coauthors : []
        merged.coauthors = (data.coauthors || []).map((c) => c.username)
        setSystem(merged)
        setOriginalSystem(merged)
        setHasStation(!!(data.space_station && Object.keys(data.space_station).length > 0))
        // Capture the loaded station so toggleStation can restore it instead
        // of replacing it with an auto-generated placeholder on toggle off/on.
        originalStationRef.current = data.space_station ? { ...data.space_station } : null
        // Hydrate live discoveries into a read-only sidecar list so the
        // Discoveries section actually shows what's already attached. Previous
        // behavior left this empty on edit, so editors couldn't see what
        // discoveries existed without leaving the wizard.
        setExistingDiscoveries(Array.isArray(data.discoveries) ? data.discoveries : [])
        // Edit mode skips the gate
        setFlow('advanced')
      })
      .catch(() => {})
  }, [editId])

  // Open the shared discovery submit modal in edit mode for an existing
  // discovery. Enrich with the system id/name (the get_system discoveries
  // payload may predate the system_id field, so fall back to the edited system)
  // so the modal can load the planet/moon dropdowns.
  const handleEditExistingDiscovery = useCallback((d) => {
    if (!d) return
    setEditingDiscovery({
      ...d,
      system_id: d.system_id || system?.id || editId,
      system_name: d.system_name || system?.name,
    })
  }, [system, editId])

  // Discord tag list
  useEffect(() => {
    axios.get('/api/discord_tags')
      .then((r) => setDiscordTags(r.data.tags || []))
      .catch(() => {})
  }, [])

  // Profile pre-fill (default reality / galaxy / discord_tag / username)
  useEffect(() => {
    if (!user || isEditMode) return
    if (user.username && !submitterDiscordUsername) setSubmitterDiscordUsername(user.username)
    setSystem((prev) => {
      const next = { ...prev }
      if (user.defaultCivTag && !prev.discord_tag) next.discord_tag = user.defaultCivTag
      if (user.defaultReality && !prev.reality) next.reality = user.defaultReality
      if (user.defaultGalaxy && !prev.galaxy) next.galaxy = user.defaultGalaxy
      if (user.lastGameVersion && !prev.game_version) next.game_version = user.lastGameVersion
      return next
    })
  }, [user, isEditMode]) // eslint-disable-line react-hooks/exhaustive-deps

  // Restore-draft banner: read on mount, only when not editing and gate is open
  useEffect(() => {
    if (isEditMode) return
    if (draftLoadedRef.current) return
    draftLoadedRef.current = true
    const draft = readDraft(profileId)
    if (draft && draft.glyph_code) {
      setDraftSnapshot(draft)
      setDraftBannerOpen(true)
    }
  }, [isEditMode, profileId])

  // Region info + procedural name lookup whenever glyphs+galaxy+reality change
  useEffect(() => {
    if (system.region_x == null || system.region_y == null || system.region_z == null) {
      setRegionInfo(null)
      return
    }
    const reality = system.reality || 'Normal'
    const galaxy = system.galaxy || 'Euclid'
    setRegionLoading(true)
    axios.get(`/api/regions/${system.region_x}/${system.region_y}/${system.region_z}`, { params: { reality, galaxy } })
      .then((r) => {
        setRegionInfo(r.data)
        if (system.glyph_code?.length === 12) {
          axios.get('/api/namegen', { params: { glyph: system.glyph_code, galaxy } })
            .then((ng) => {
              setSystem((s) => {
                // Procgen must never overwrite a name the user has touched.
                // userEditedNameRef flips true on any keystroke in the name
                // input (see SectionPortal). The legacy `_lastProceduralName`
                // sentinel stays as a secondary guard for the auto-suggested
                // initial fill (so re-decode doesn't fight itself when the
                // user hasn't typed yet).
                if (userEditedNameRef.current) return s
                const cur = s.name || ''
                if (!cur || cur === s._lastProceduralName) {
                  return { ...s, name: ng.data.system_name, _lastProceduralName: ng.data.system_name }
                }
                return s
              })
              if (!r.data?.custom_name) {
                // Mirror the system-name pattern: only auto-fill when the user
                // hasn't customized the field. Allow overwrite when current
                // value is empty OR still equals the last value we wrote
                // (i.e., user hasn't customized after the prior galaxy's gen).
                setProposedRegionName((prev) => {
                  if (userEditedRegionRef.current) return prev
                  const newName = ng.data.region_name || ''
                  // Overwrite when: empty, OR still equal to the last value we
                  // auto-filled, OR we've never auto-filled this session
                  // (lastProceduralRegionRef === ''). The last clause is the
                  // safety net: with userEditedRegionRef already false above, a
                  // non-empty prev when we've auto-filled nothing can only be a
                  // stale value carried across a reset — never a user edit — so
                  // it's always safe to replace.
                  if (!prev || prev === lastProceduralRegionRef.current || !lastProceduralRegionRef.current) {
                    lastProceduralRegionRef.current = newName
                    return newName
                  }
                  return prev
                })
              }
            })
            .catch(() => {})
        }
      })
      .catch(() => setRegionInfo(null))
      .finally(() => setRegionLoading(false))
    // glyph_code is read inside (the namegen system-name suggestion). Without
    // it in the deps, changing the glyph within the same region voxel (same
    // rx/ry/rz) wouldn't refresh the suggested name.
  }, [system.region_x, system.region_y, system.region_z, system.reality, system.galaxy, system.glyph_code])

  // Same-name soft warning (mockup v11CheckSameName 9937). Debounced. Skipped
  // while editing the system that already owns this name (so we don't warn the
  // user about themselves) and skipped for the auto-generated procedural name.
  useEffect(() => {
    const name = (debouncedNameForLookup || '').trim()
    if (!name || name.length < 3) { setSameNameMatches([]); return }
    if (system._lastProceduralName && name === system._lastProceduralName) {
      setSameNameMatches([])
      return
    }
    let cancelled = false
    axios.get('/api/systems/search', { params: { q: name, limit: 5 } })
      .then((r) => {
        if (cancelled) return
        const results = (r.data?.results || r.data || [])
          .filter((s) => s.name && s.name.toLowerCase() === name.toLowerCase())
          .filter((s) => !originalSystem || String(s.id) !== String(originalSystem.id))
        setSameNameMatches(results)
      })
      .catch(() => !cancelled && setSameNameMatches([]))
    return () => { cancelled = true }
  }, [debouncedNameForLookup, system._lastProceduralName, originalSystem])

  // Existing-system pull check (mockup v11CheckExistingSystem 9540).
  // Fires when 12 glyphs are entered + galaxy/reality known.
  useEffect(() => {
    if (isEditMode) { setExistingMatch(null); return }
    if (!system.glyph_code || system.glyph_code.length !== 12) { setExistingMatch(null); return }
    if (!system.galaxy) return
    let cancelled = false
    checkExistingSystem(system.glyph_code, system.galaxy, system.reality || 'Normal')
      .then((d) => {
        if (cancelled) return
        if (d.exists) setExistingMatch(d)
        else setExistingMatch(null)
      })
      .catch(() => !cancelled && setExistingMatch(null))
    return () => { cancelled = true }
  }, [system.glyph_code, system.galaxy, system.reality, isEditMode])

  // ===========================================================================
  // Helpers
  // ===========================================================================
  function setField(k, v) {
    setSystem((s) => ({ ...s, [k]: v }))
  }

  function handleGlyphDecoded(decodedData) {
    setSystem((s) => ({
      ...s,
      x: decodedData.x, y: decodedData.y, z: decodedData.z,
      region_x: decodedData.region_x, region_y: decodedData.region_y, region_z: decodedData.region_z,
      glyph_planet: decodedData.planet,
      glyph_solar_system: decodedData.solar_system,
      glyph_code: decodedData.glyph,
    }))
  }

  function pullExistingIntoForm() {
    if (!existingMatch?.summary) return
    const s = existingMatch.summary
    // Detect every field that's already populated and would be replaced by a
    // non-empty value from the existing system. Surface them so the user
    // explicitly opts in instead of silently losing typed input.
    const candidateFields = [
      ['name', 'System Name'],
      ['galaxy', 'Galaxy'],
      ['reality', 'Reality'],
      ['star_type', 'Star Color'],
      ['economy_type', 'Economy Type'],
      ['economy_level', 'Economy Tier'],
      ['conflict_level', 'Conflict Level'],
      ['dominant_lifeform', 'Dominant Lifeform'],
      ['stellar_classification', 'Stellar Classification'],
      ['description', 'Description'],
      ['game_version', 'Game Version'],
      ['expedition_id', 'Expedition'],
    ]
    const wouldOverwrite = candidateFields
      .filter(([k]) => system[k] && s[k] && String(system[k]).trim() !== String(s[k]).trim())
      .map(([, label]) => label)
    if (wouldOverwrite.length > 0) {
      const ok = window.confirm(
        `Pulling existing data will replace the values you've entered for:\n\n` +
        wouldOverwrite.map((l) => `  • ${l}`).join('\n') +
        `\n\nFields you haven't filled in will be populated normally.\n\nProceed?`
      )
      if (!ok) return
    }
    setSystem((prev) => ({
      ...prev,
      name: s.name || prev.name,
      galaxy: s.galaxy || prev.galaxy,
      reality: s.reality || prev.reality,
      star_type: s.star_type || prev.star_type,
      economy_type: s.economy_type || prev.economy_type,
      economy_level: s.economy_level || prev.economy_level,
      conflict_level: s.conflict_level || prev.conflict_level,
      dominant_lifeform: s.dominant_lifeform || prev.dominant_lifeform,
      stellar_classification: s.stellar_classification || prev.stellar_classification,
      description: s.description || prev.description,
      game_version: s.game_version || prev.game_version,
      expedition_id: s.expedition_id || prev.expedition_id,
    }))
    // Pull-existing is an explicit user choice to adopt this name — mark it
    // edited so /api/namegen can't overwrite it after the fact.
    if (s.name) userEditedNameRef.current = true
    setExistingMatch(null)
  }

  // Restore draft handlers
  function restoreDraft() {
    if (!draftSnapshot) return
    setSystem((prev) => ({ ...prev, ...draftSnapshot }))
    setHasStation(!!draftSnapshot.space_station)
    setDraftBannerOpen(false)
    setDraftSnapshot(null)
    // The restored draft has a name the user previously typed — protect it
    // from /api/namegen overwrite the same way fresh typed input is
    // protected, so changing reality/galaxy after restore doesn't clobber it.
    if (draftSnapshot.name) userEditedNameRef.current = true
  }
  function dismissDraft() {
    clearWizardDraft()
    setDraftBannerOpen(false)
    setDraftSnapshot(null)
  }

  // Planet management (matches existing behavior)
  function addPlanet() {
    setEditingPlanetIndex(-1)
    setEditingPlanet({ ...PLANET_DEFAULTS })
    setPlanetModalOpen(true)
  }
  // --- Body-count generator (planets + moons, capped at 6 combined) --------
  // Two dropdowns (in SectionPlanets) drive these so the user picks counts
  // instead of clicking "Add" repeatedly. A celestial body counts as "has
  // data" once the user touches anything beyond a bare generated shell — used
  // so REDUCING a count never silently deletes filled-in work without a confirm.
  function bodyHasData(b) {
    if (!b) return false
    const nm = (b.name || '').trim()
    if (nm && !/^(Planet|Moon) \d+$/.test(nm)) return true
    if ((b.biome || '').trim() || (b.weather || '').trim()) return true
    if ((b.materials || '').trim() || (b.base_location || '').trim() || (b.notes || '').trim()) return true
    if (b.photo) return true
    if ((b.fauna && b.fauna !== 'N/A') || (b.flora && b.flora !== 'N/A')) return true
    if (b.sentinel && b.sentinel !== 'None') return true
    for (const k of [
      'has_rings', 'is_dissonant', 'is_infested', 'extreme_weather', 'water_world', 'vile_brood',
      'ancient_bones', 'salvageable_scrap', 'storm_crystals', 'gravitino_balls', 'is_gas_giant',
      'is_bubble', 'is_floating_islands', 'swarm_debris', 'trash_debris',
      'high_sentinel_activity', 'aggressive_sentinel_activity',
    ]) {
      if (b[k]) return true
    }
    if ((b.moons || []).length) return true
    return false
  }
  function countMoons(planets) {
    return (planets || []).reduce((n, p) => n + ((p.moons || []).length), 0)
  }
  // Trim total moons down to `target`, removing from the LAST planet backwards.
  // EMPTY shells go first (no data loss); only if that isn't enough do filled
  // moons get touched. Returns { planets, ok } — ok=false means the caller's
  // change couldn't be applied without losing data (and was declined / blocked),
  // so the caller should keep the original state.
  //   confirm   — ask before removing a FILLED moon (direct moon-count change).
  //   emptyOnly — never remove a filled moon; signal ok=false instead (used when
  //               raising the planet count squeezes the combined cap).
  function trimMoons(planets, target, { confirm = false, emptyOnly = false } = {}) {
    let total = countMoons(planets)
    if (total <= target) return { planets, ok: true }
    const next = planets.map((p) => ({ ...p, moons: [...(p.moons || [])] }))
    // Pass 1: drop empty moon shells (last planet first).
    for (let pi = next.length - 1; pi >= 0 && total > target; pi -= 1) {
      const moons = next[pi].moons
      for (let mi = moons.length - 1; mi >= 0 && total > target; mi -= 1) {
        if (!bodyHasData(moons[mi])) { moons.splice(mi, 1); total -= 1 }
      }
    }
    if (total <= target) return { planets: next, ok: true }
    if (emptyOnly) return { planets, ok: false }  // remaining would be filled moons — block
    // Pass 2: filled moons — confirm before removing.
    if (confirm && !window.confirm(`Remove ${total - target} moon(s) with data you've entered?`)) {
      return { planets, ok: false }
    }
    for (let pi = next.length - 1; pi >= 0 && total > target; pi -= 1) {
      const moons = next[pi].moons
      while (moons.length && total > target) { moons.pop(); total -= 1 }
    }
    return { planets: next, ok: true }
  }
  // Set the number of planets (0-6). Generates empty shells when increasing,
  // trims from the end when decreasing (confirm if a filled planet would go),
  // then enforces the 6-body cap by trimming excess EMPTY moons. If filled
  // moons would have to be dropped to fit, the increase is blocked instead.
  function setPlanetCount(n) {
    n = Math.max(0, Math.min(6, n))
    setSystem((s) => {
      let planets = [...(s.planets || [])]
      const have = planets.length
      if (n > have) {
        for (let i = have; i < n; i += 1) planets.push({ ...PLANET_DEFAULTS, name: `Planet ${i + 1}` })
      } else if (n < have) {
        const toRemove = planets.slice(n)
        if (toRemove.some(bodyHasData) && !window.confirm(`Remove ${have - n} planet(s)? Some have data you've entered.`)) {
          return s
        }
        planets = planets.slice(0, n)
      }
      const { planets: trimmed, ok } = trimMoons(planets, Math.max(0, 6 - n), { emptyOnly: true })
      if (!ok) {
        window.alert('Reduce the moon count first — those filled moons would push this system past the 6-body cap.')
        return s
      }
      return { ...s, planets: trimmed }
    })
  }
  // Set the TOTAL number of moons across the system (0 .. 6 - planets). New
  // moons attach to the FIRST planet (reassign via the moon "Orbits" selector);
  // trimming removes empty shells first, then filled moons with a confirm.
  function setMoonCount(m) {
    setSystem((s) => {
      const planets = (s.planets || []).map((p) => ({ ...p, moons: [...(p.moons || [])] }))
      if (!planets.length) return s  // need at least one planet to hold a moon
      const cap = Math.max(0, 6 - planets.length)
      m = Math.max(0, Math.min(cap, m))
      let current = countMoons(planets)
      if (m > current) {
        const first = planets[0]
        while (current < m) {
          first.moons.push({ ...MOON_DEFAULTS, name: `Moon ${first.moons.length + 1}` })
          current += 1
        }
        return { ...s, planets }
      }
      if (m < current) {
        const { planets: trimmed, ok } = trimMoons(planets, m, { confirm: true })
        return ok ? { ...s, planets: trimmed } : s
      }
      return s
    })
  }
  // Move a moon from one planet to another (the per-moon "Orbits" selector).
  function reassignMoon(fromIdx, moonIdx, toIdx) {
    if (fromIdx === toIdx) return
    setSystem((s) => {
      const planets = (s.planets || []).map((p) => ({ ...p, moons: [...(p.moons || [])] }))
      if (!planets[fromIdx] || !planets[toIdx]) return s
      const [moon] = planets[fromIdx].moons.splice(moonIdx, 1)
      if (!moon) return s
      planets[toIdx].moons.push(moon)
      return { ...s, planets }
    })
  }
  function editPlanet(i) {
    setEditingPlanetIndex(i)
    setEditingPlanet(system.planets[i])
    setPlanetModalOpen(true)
  }
  function commitPlanet(planet) {
    const planets = [...(system.planets || [])]
    if (editingPlanetIndex === -1) planets.push(planet)
    else planets[editingPlanetIndex] = planet
    setSystem((s) => ({ ...s, planets }))
    setPlanetModalOpen(false)
  }
  function updatePlanet(idx, val) {
    const planets = [...(system.planets || [])]
    planets[idx] = val
    setSystem((s) => ({ ...s, planets }))
  }
  function removePlanet(idx) {
    const planets = [...(system.planets || [])]
    planets.splice(idx, 1)
    setSystem((s) => ({ ...s, planets }))
  }

  // Station management — three mutually-exclusive states:
  //   'has'     → the system has a station (fill in details)
  //   'none'    → the system definitively has NO station (no_space_station=1)
  //   'unknown' → not documented yet (both cleared) — the neutral default
  function setStationMode(mode) {
    if (mode === 'has') {
      setHasStation(true)
      // Restore the originally-loaded station (edit mode) instead of replacing
      // its name/race/trade_goods/position with auto-generated defaults. Only
      // fall through to the generator when there's nothing to restore — new
      // submissions, or a station the user explicitly cleared after editing.
      if (originalStationRef.current) {
        const loaded = originalStationRef.current
        setSystem((s) => ({ ...s, space_station: { ...loaded }, no_space_station: false }))
        return
      }
      const position = generateStationPosition(system.planets || [])
      const goods = getTradeGoodsForEconomyAndTier(system.economy_type || 'None', system.economy_level || 'T3')
      setSystem((s) => ({
        ...s,
        space_station: {
          name: `${s.name || 'System'} Station`,
          race: s.dominant_lifeform || 'Gek',
          trade_goods: goods.map((g) => g.id),
          ...position,
        },
        no_space_station: false,
      }))
    } else if (mode === 'none') {
      // Definitively no station — clear any station data and flag it so the
      // grade/scoring treats it as complete (not "missing").
      setHasStation(false)
      setSystem((s) => ({ ...s, space_station: null, no_space_station: true }))
    } else {
      // 'unknown' — not documented yet.
      setHasStation(false)
      setSystem((s) => ({ ...s, space_station: null, no_space_station: false }))
    }
  }
  function setStationField(k, v) {
    if (!system.space_station) return
    setSystem((s) => ({ ...s, space_station: { ...s.space_station, [k]: v } }))
  }
  function toggleTradeGood(id) {
    if (!system.space_station) return
    const cur = system.space_station.trade_goods || []
    const next = cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]
    setSystem((s) => ({ ...s, space_station: { ...s.space_station, trade_goods: next } }))
  }

  // Region naming — Option B (deferred). The "Save" button just stashes
  // the proposed name in local state so it ships with the main system
  // submission. Identity is attached server-side at that point. The flash
  // timestamp drives the "✓ Saved" confirmation in the UI.
  function saveRegionNameLocally() {
    if (!proposedRegionName.trim()) return
    setRegionNameSavedAt(Date.now())
  }

  // ===========================================================================
  // Diff map (edit mode) — tracks per-field changes vs original-loaded system.
  // Drives the .changed amber highlight on inputs (mockup .changed CSS).
  // ===========================================================================
  const diffMap = useMemo(() => {
    if (!isEditMode || !originalSystem) return {}
    const out = {}
    DIFFABLE_FIELDS.forEach((k) => {
      if (valuesDiffer(system[k], originalSystem[k])) out[k] = true
    })
    return out
  }, [isEditMode, originalSystem, system])

  // ===========================================================================
  // Validation
  // ===========================================================================
  const validationIssues = useMemo(() => {
    const issues = []
    // sectionAnchor falls back to the section's anchor id (e.g. "portal") so
    // ValidationSummary's jumpTo can still scroll into the right neighborhood
    // when the specific fieldId isn't currently in the DOM (e.g. region-name
    // input only renders for unnamed regions).
    const push = (id, label, fieldId, sectionAnchor) => issues.push({ id, label, fieldId, sectionAnchor })
    // Edit-mode relaxation: legacy / extractor systems were ingested before
    // some "required" fields existed (game_mode, stellar_classification, even
    // economy_level on abandoned systems). Treating every gap as a hard error
    // on edit blocks small fixes (a typo, a photo upload) behind backfilling
    // unrelated fields the editor never touched. Strategy: skip a required
    // check on edit when the field is still equal to the originally-loaded
    // value (i.e., user didn't make it worse).
    const editPreserved = (key) => isEditMode && originalSystem &&
      String(system[key] ?? '') === String(originalSystem[key] ?? '')
    if (!system.name?.trim() && !editPreserved('name')) push('name', 'System Name is required', 'wiz-system-name', 'portal')
    if (!system.reality && !editPreserved('reality')) push('reality', 'Reality is required', 'wiz-reality', 'portal')
    if (!system.galaxy && !editPreserved('galaxy')) push('galaxy', 'Galaxy is required', 'wiz-galaxy', 'portal')
    if ((!system.glyph_code || system.glyph_code.length !== 12) && !editPreserved('glyph_code')) push('glyphs', 'Portal Glyph Code (12 chars) is required', 'wiz-glyphs', 'portal')
    if (!system.star_type && !editPreserved('star_type')) push('star', 'Star Color is required', 'wiz-star-type', 'attrs')
    if (!system.economy_type && !editPreserved('economy_type')) push('econ', 'Economy Type is required', 'wiz-economy-type', 'attrs')
    const abandoned = system.economy_type === 'None' || system.economy_type === 'Abandoned'
    if (!abandoned && !system.economy_level && !editPreserved('economy_level')) push('tier', 'Economy Tier is required', 'wiz-economy-level', 'attrs')
    if (!abandoned && !system.conflict_level && !editPreserved('conflict_level')) push('conflict', 'Conflict Level is required', 'wiz-conflict-level', 'attrs')
    if (!system.dominant_lifeform && !editPreserved('dominant_lifeform')) push('lifeform', 'Dominant Lifeform is required', 'wiz-lifeform', 'attrs')
    if (!system.discord_tag && !isAdmin) push('community', 'Discord Community is required', 'wiz-discord-tag', 'identity')
    if (!isAdmin && !submitterDiscordUsername.trim()) push('user', 'Your Discord Username is required', 'wiz-submitter-username', 'identity')
    if (system.discord_tag === 'personal' && !personalDiscordUsername.trim()) {
      push('personal', 'Personal Discord username is required', 'wiz-discord-tag', 'identity')
    }
    // Region naming required when unnamed. Option B: validation now checks
    // that proposedRegionName is filled locally (the backend will defer the
    // actual submission to commit time, attached to the user's identity).
    // wiz-region-input may not exist if region info hasn't loaded yet —
    // sectionAnchor 'portal' is the fallback.
    // Require a proposed name when the region is NOT confirmed already-named.
    // This includes the case where regionInfo is null (a failed/in-flight
    // lookup) — previously that silently waived the rule and let an unnamed
    // region through. Scoped to new submissions; an edit shouldn't be blocked
    // by a transient region lookup. If the region turns out to already be
    // named, the backend ignores the proposed name.
    const regionConfirmedNamed = regionInfo && (regionInfo.custom_name || regionInfo.pending_name)
    if (!isEditMode && system.region_x != null && system.region_y != null && !regionConfirmedNamed) {
      if (!proposedRegionName.trim()) {
        push('region', 'Region name proposal is required', 'wiz-region-input', 'portal')
      } else if (!isAdmin && !submitterDiscordUsername.trim()) {
        // Without a Discord username the region name lands attributed to
        // nobody — the submitter can't claim it later. Block unless admin
        // (admins direct-write regions and don't need attribution).
        push('region-attribution', 'Discord username required to propose a region name', 'wiz-submitter-username', 'identity')
      }
    }
    // Planets/moons must have names if present
    ;(system.planets || []).forEach((p, i) => {
      if (!p.name?.trim()) push(`planet-${i}`, `Planet #${i + 1} needs a name`, 'wiz-planets', 'planets')
      ;(p.moons || []).forEach((m, j) => {
        if (!m.name?.trim()) push(`moon-${i}-${j}`, `Moon ${j + 1} of planet ${i + 1} needs a name`, 'wiz-planets', 'planets')
      })
    })
    // NMS systems hold at most 6 celestial bodies (planets + moons combined).
    // The count dropdowns enforce this, but guard the submit too in case bodies
    // were added another way.
    {
      const _bodies = (system.planets || []).reduce((n, p) => n + 1 + ((p.moons || []).length), 0)
      if (_bodies > 6) push('body-cap', `A system can have at most 6 bodies (planets + moons); you have ${_bodies}`, 'wiz-planets', 'planets')
    }
    // Duplicate body names break the discovery-promotion pipeline on approval
    // (_promote_draft_discoveries uses (planet, moon) tuples as map keys with
    // setdefault — second match wins NULL link). Block at submit time so the
    // user can rename one before they're silently dropped.
    const planetNameCounts = new Map()
    ;(system.planets || []).forEach((p) => {
      const n = p.name?.trim().toLowerCase()
      if (n) planetNameCounts.set(n, (planetNameCounts.get(n) || 0) + 1)
    })
    planetNameCounts.forEach((count, n) => {
      if (count > 1) push(`dup-planet-${n}`, `Duplicate planet name "${n}" — rename to keep discovery links intact`, 'wiz-planets', 'planets')
    })
    ;(system.planets || []).forEach((p, i) => {
      const moonNameCounts = new Map()
      ;(p.moons || []).forEach((m) => {
        const n = m.name?.trim().toLowerCase()
        if (n) moonNameCounts.set(n, (moonNameCounts.get(n) || 0) + 1)
      })
      moonNameCounts.forEach((count, n) => {
        if (count > 1) push(`dup-moon-${i}-${n}`, `Duplicate moon name "${n}" under planet "${p.name || `#${i + 1}`}"`, 'wiz-planets', 'planets')
      })
    })
    return issues
  }, [system, isAdmin, regionInfo, submitterDiscordUsername, personalDiscordUsername, proposedRegionName, isEditMode, originalSystem])

  // ===========================================================================
  // Section status (for sidebar icons)
  // ===========================================================================
  const sectionStatus = useMemo(() => {
    function s(filled, total) {
      if (total === 0) return 'empty'
      if (filled === 0) return 'empty'
      if (filled >= total) return 'complete'
      return 'partial'
    }
    const portalFilled = (system.glyph_code?.length === 12 ? 1 : 0) + (system.galaxy ? 1 : 0) + (system.reality ? 1 : 0) + (system.name ? 1 : 0)
    const attrsFilled = ['star_type', 'economy_type', 'dominant_lifeform'].filter((k) => system[k]).length
    const planetsFilled = (system.planets || []).length > 0 ? 1 : 0
    const stationFilled = (system.space_station || system.no_space_station) ? 1 : 0
    const identityFilled = (system.discord_tag ? 1 : 0) + (submitterDiscordUsername ? 1 : 0)
    const submitFilled = validationIssues.length === 0 ? 1 : 0
    return {
      portal: s(portalFilled, 4),
      attrs: s(attrsFilled, 3),
      planets: s(planetsFilled, 1),
      station: stationFilled === 1 ? 'complete' : 'empty',
      discoveries: 'empty',
      identity: s(identityFilled, 2),
      submit: s(submitFilled, 1),
    }
  }, [system, submitterDiscordUsername, validationIssues])

  const sidebarSections = SECTIONS.map((s) => ({ ...s, status: sectionStatus[s.id] || 'empty' }))

  // ===========================================================================
  // Submit
  // ===========================================================================
  function buildPayload() {
    const payload = { ...system }
    delete payload._lastProceduralName
    // Re-attach coauthor metadata for names that survived this edit. Names
    // the editor newly added stay as plain strings; the backend treats
    // string entries as "new credit, no metadata" (credited_at = now).
    if (Array.isArray(system.coauthors) && originalCoauthorsRef.current.length) {
      const origByName = new Map(
        originalCoauthorsRef.current
          .map((c) => [String(c.username || '').toLowerCase(), c])
          .filter(([k]) => k)
      )
      payload.coauthors = system.coauthors.map((u) => {
        const orig = origByName.get(String(u || '').toLowerCase())
        return orig ? { ...orig, username: u } : u
      })
    }
    // Capture which wizard flow built this submission so the approval page
    // can re-render the same preview card the user saw at submit time
    // (easy → portrait WizardPreviewPanel; advanced → landscape WizardAdvancedPreview).
    if (flow) payload.wizard_flow = flow
    if (submitterDiscordUsername.trim()) {
      payload.personal_discord_username = submitterDiscordUsername.trim()
    }
    if (system.discord_tag === 'personal' && personalDiscordUsername.trim()) {
      payload.personal_discord_username = personalDiscordUsername.trim()
    }
    if (profileId) payload.profile_id = profileId
    // Deferred region name submission (Option B). Backend writes it to
    // pending_region_names (public) or regions (admin direct-save) only
    // when the region is actually unnamed and not already pending.
    if (proposedRegionName.trim()) {
      payload.proposed_region_name = proposedRegionName.trim()
    }
    return payload
  }

  // ----- Conflict resolution: detect mid-air-collision on edit -----
  // Re-fetch the system at submit time, compare to the originally-loaded
  // baseline AND to what the user is submitting. A conflict exists for field
  // F when:  fresh[F] !== original[F]  (someone else changed it)
  //   AND   mine[F]  !== original[F]   (you also changed it)
  //   AND   fresh[F] !== mine[F]       (and your value differs from theirs)
  // If any conflicts: pop the modal so the user picks per-field.
  async function detectEditConflicts(payload) {
    if (!isEditMode || !originalSystem || !editId) return []
    try {
      const r = await axios.get(`/api/systems/${encodeURIComponent(editId)}`)
      const fresh = r.data || {}
      const out = []
      CONFLICT_FIELDS.forEach(({ key, label }) => {
        const orig = originalSystem[key]
        const mine = payload[key]
        const theirs = fresh[key]
        if (valuesDiffer(theirs, orig) && valuesDiffer(mine, orig) && valuesDiffer(theirs, mine)) {
          out.push({
            field: key,
            fieldLabel: label,
            mine,
            theirs,
            theirsGameVersion: fresh.game_version || null,
          })
        }
      })
      return out
    } catch {
      return []  // best-effort — never block on conflict-check failure
    }
  }

  // v1.64.0 — build a single draft entry suitable for the
  // pending_systems.discoveries_draft JSON column. Resolves the wizard's
  // synthetic planet-N / `planet::moon::idx` picker IDs back to real names
  // by walking the local system.planets state, since those IDs are
  // meaningless once the submission hits the backend.
  function buildDiscoveryDraftEntry(d, sysState) {
    const allPlanets = (sysState?.planets || []).filter((p) => !p.is_moon)
    const synthPlanetId = (p, i) => p.id ?? `planet-${i}`
    const synthMoonId = (p, m, mi) =>
      m.id ?? `${p.name || 'planet'}::${m.name || 'moon'}::${mi}`

    let planet_name = null
    let moon_name = null
    if (d.location_type === 'planet' && d.planet_id != null && d.planet_id !== '') {
      const idx = allPlanets.findIndex((p, i) => String(synthPlanetId(p, i)) === String(d.planet_id))
      if (idx >= 0) planet_name = allPlanets[idx].name || null
    } else if (d.location_type === 'moon' && d.moon_id != null && d.moon_id !== '') {
      outer: for (const p of allPlanets) {
        const moons = p.moons || []
        for (let mi = 0; mi < moons.length; mi += 1) {
          if (String(synthMoonId(p, moons[mi], mi)) === String(d.moon_id)) {
            planet_name = p.name || null
            moon_name = moons[mi].name || null
            break outer
          }
        }
      }
    }

    // Photo + evidence — first photo is the primary photo_url, the rest plus
    // any external URLs become the comma-joined evidence list.
    const photos = (d.photos || []).filter((p) => p.path)
    const photoUrl = photos[0]?.path || null
    const externalUrls = (d.evidence_urls || '')
      .split('\n').map((s) => s.trim()).filter(Boolean)
    const allEvidence = [...photos.slice(1).map((p) => p.path), ...externalUrls]

    // Surface coordinates — float-or-null, nulled for space discoveries.
    const toCoord = (v) => {
      if (v === '' || v == null) return null
      const f = parseFloat(v)
      return Number.isNaN(f) ? null : f
    }
    const isSpace = (d.location_type || 'planet') === 'space'

    return {
      discovery_name: d.discovery_name.trim(),
      discovery_type: d.discovery_type,
      description: d.description?.trim() || null,
      planet_name,
      moon_name,
      location_type: d.location_type || 'planet',
      location_name: d.location_name?.trim() || null,
      latitude: isSpace ? null : toCoord(d.latitude),
      longitude: isSpace ? null : toCoord(d.longitude),
      photo_url: photoUrl,
      evidence_urls: allEvidence.length ? allEvidence.join(',') : null,
      type_metadata: d.type_metadata && Object.keys(d.type_metadata).length ? d.type_metadata : null,
      game_version: d.game_version || null,
      submit_for_record: !!d.submit_for_record,
    }
  }

  // NOTE: the wizard no longer has a separate discovery-submission route.
  // Co-submitted discoveries ride on the system payload as `discoveries_draft`
  // (built in doSubmit via buildDiscoveryDraftEntry) for BOTH trusted and
  // member submissions, and the backend promotes them by NAME when the
  // planets/moons get ids (save_system for trusted, approve_system on
  // approval for members). The old per-discovery `submitDiscoveries` →
  // /api/submit_discovery loop was removed — it sent a synthetic planet id
  // that got nulled, silently unlinking every co-submitted discovery.
  // The standalone /api/submit_discovery endpoint still exists for submitting
  // a discovery against an EXISTING system outside the wizard (DiscoverySubmitModal).

  async function doSubmit(overrideConflicts = null) {
    if (validationIssues.length > 0) return
    setIsSubmitting(true)
    setSubmitError(null)
    try {
      let payload = buildPayload()

      // Conflict detection runs only on edit submit and only if we haven't
      // already resolved conflicts in this submit attempt.
      if (isEditMode && !overrideConflicts) {
        const detected = await detectEditConflicts(payload)
        if (detected.length) {
          setConflicts(detected)
          setConflictModalOpen(true)
          // The modal's onResolve calls doSubmit(choices) and we resume there.
          setIsSubmitting(false)
          return
        }
      }
      // Apply per-field conflict resolutions, if the user just made choices.
      if (overrideConflicts && conflicts.length) {
        conflicts.forEach((c) => {
          if (overrideConflicts[c.field] === 'theirs') {
            payload[c.field] = c.theirs
          }
        })
      }

      // Snapshot what the user just submitted so the success screen can
      // re-render the exact preview card they saw at submit time.
      const submittedSnapshot = { ...system }

      // ONE upload route for co-submitted discoveries. Build the
      // discoveries_draft once and attach it to the payload for BOTH the
      // trusted (save_system) and member (submit_system) paths. Each entry
      // references its planet/moon BY NAME; the backend resolves the link when
      // the planets/moons get ids — save_system promotes immediately (trusted),
      // approve_system promotes on approval (member). There is no longer a
      // second per-discovery /api/submit_discovery round-trip for admins (that
      // route sent a synthetic id that got nulled, so links were silently lost).
      //
      // Built here, before the profile-lookup early-returns, so the draft
      // survives the profile-claim modal resubmit paths (handleProfileUse /
      // handleProfileCreatedContinue stash this exact payload).
      const draftReady = discoveries
        .filter((d) => d.discovery_type && d.discovery_name?.trim())
        .slice(0, 20)
        .map((d) => buildDiscoveryDraftEntry(d, system))
      if (draftReady.length) {
        payload.discoveries_draft = draftReady
      }

      if (isAdmin) {
        const r = await axios.post('/api/save_system', payload)
        if (r.data.status === 'pending_approval') {
          // Untagged-edit approval path — the whole payload (incl.
          // discoveries_draft) is queued and promotes when approved.
          setSubmitResult({
            status: 'pending',
            submission_id: r.data.request_id,
            system_name: system.name,
            submitted_discoveries: draftReady.length,
            submitted_system: submittedSnapshot,
            wizard_flow: flow,
          })
        } else {
          // Trusted direct save — the system AND its discoveries went live in
          // one transaction. The backend promoted the drafts (resolving links
          // by name) and reports how many it inserted.
          setSubmitResult({
            status: 'saved',
            system_id: r.data.system_id,
            system_name: r.data.saved?.name || system.name,
            discoveries_ok: r.data.discoveries_promoted ?? draftReady.length,
            discoveries_failed: 0,
            submitted_system: submittedSnapshot,
            wizard_flow: flow,
          })
        }
        clearWizardDraft()
        markFormClean()
      } else {
        // Public path. discoveries_draft is already on the payload (built
        // above), so it rides the pending row and promotes on approval.

        // Profile-lookup gate
        const lookupName = submitterDiscordUsername.trim() || personalDiscordUsername.trim()
        if (lookupName && !profileId) {
          try {
            const lookup = await axios.post('/api/profiles/lookup', { username: lookupName })
            const ld = lookup.data
            if (ld.status === 'found') {
              payload.profile_id = ld.profile.id
            } else if (ld.status === 'suggestions') {
              setProfileSuggestions(ld.suggestions)
              setProfileModalStatus('suggestions')
              setProfileModalOpen(true)
              setPendingSubmitPayload(payload)
              return
            } else {
              setProfileModalStatus('not_found')
              setProfileModalOpen(true)
              setPendingSubmitPayload(payload)
              return
            }
          } catch (lookupErr) {
            // M-W3: lookup failed (transient 500 / network). Submit anyway
            // — losing identity-linking is worse than not submitting at
            // all — but stash a warning so the success screen can prompt
            // the user to retry from My Profile.
            payload._profile_lookup_failed = true
          }
        }
        const lookupFailed = payload._profile_lookup_failed === true
        delete payload._profile_lookup_failed
        const r = await axios.post('/api/submit_system', payload)
        setSubmitResult({
          status: 'pending',
          submission_id: r.data.submission_id,
          system_name: r.data.system_name,
          // v1.64.0: discoveries ride along on the pending row and get
          // approved with the system, so we report the count we shipped.
          submitted_discoveries: draftReady.length,
          submitted_system: submittedSnapshot,
          wizard_flow: flow,
          warning: lookupFailed
            ? 'Profile lookup failed during submission; this submission is not linked to your profile yet. You can claim it from My Profile once the system is approved.'
            : null,
        })
        clearWizardDraft()
        markFormClean()
      }
    } catch (err) {
      // FastAPI returns either a string `detail` (custom HTTPException) or
      // a list of `{loc, msg, type}` validation errors. Flatten to a
      // human-readable string instead of `[object Object]`.
      const detail = err.response?.data?.detail
      let pretty
      if (typeof detail === 'string') {
        pretty = detail
      } else if (Array.isArray(detail)) {
        pretty = detail.map((d) => {
          const path = Array.isArray(d.loc) ? d.loc.filter((p) => p !== 'body').join('.') : ''
          const msg = d.msg || JSON.stringify(d)
          return path ? `${path}: ${msg}` : msg
        }).join(' • ')
      } else if (detail && typeof detail === 'object') {
        pretty = JSON.stringify(detail)
      } else {
        pretty = err.message || String(err)
      }
      setSubmitError(pretty)
    } finally {
      setIsSubmitting(false)
    }
  }

  function handleSubmitClick() {
    explicitSubmitRef.current = true
    doSubmit()
  }

  // Submit Another (preserve identity)
  function handleSubmitAnother() {
    setSubmitResult(null)
    setSubmitError(null)
    setExistingMatch(null)
    setHasStation(false)
    setDiscoveries([])
    setSameNameMatches([])
    userEditedNameRef.current = false
    userEditedRegionRef.current = false
    lastProceduralRegionRef.current = ''
    originalStationRef.current = null
    // Clear the region-name STATE too, not just the refs that guard it.
    // Resetting lastProceduralRegionRef to '' while leaving a stale
    // proposedRegionName non-empty made the namegen guard (see the region
    // effect) read the leftover value as "user-customized" and refuse to
    // overwrite it — so the next system inherited the prior system's region
    // name. Reset them together so the invariant holds: after Submit Another,
    // proposedRegionName === '' === lastProceduralRegionRef.current.
    setProposedRegionName('')
    setRegionNameSavedAt(null)
    setRegionInfo(null)
    setSystem((s) => ({
      ...EMPTY_SYSTEM,
      reality: s.reality,
      galaxy: s.galaxy,
      discord_tag: s.discord_tag,
      coauthors: s.coauthors,
      expedition_id: s.expedition_id,
      event_id: s.event_id,
      game_version: s.game_version,
      // Submit Another should preserve the difficulty the player set —
      // they're still in the same NMS session.
      game_mode: s.game_mode,
    }))
    setActiveSection('portal')
    setEasyStep(0)
    // Reset dirty baseline so the new identity-preserved state isn't
    // immediately flagged as dirty against the prior submission.
    markFormClean()
  }

  // Keyboard: Esc closes help, Cmd/Ctrl+Enter submits, Cmd/Ctrl+S manual save (clear draft as a way to "commit")
  useEffect(() => {
    function handler(e) {
      if (e.key === 'Escape') {
        if (helpOpen) setHelpOpen(false)
      } else if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        if (!submitResult) handleSubmitClick()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [helpOpen, submitResult]) // eslint-disable-line react-hooks/exhaustive-deps

  // Profile claim handlers
  async function handleProfileUse(pid) {
    setProfileModalOpen(false)
    if (!pendingSubmitPayload) return
    try {
      const payload = { ...pendingSubmitPayload, profile_id: pid }
      // discoveries_draft is already on the payload (attached in doSubmit
      // before the lookup branch). Read length for the success screen.
      const draftCount = Array.isArray(payload.discoveries_draft) ? payload.discoveries_draft.length : 0
      const r = await axios.post('/api/submit_system', payload)
      setSubmitResult({
        status: 'pending',
        submission_id: r.data.submission_id,
        system_name: r.data.system_name,
        submitted_discoveries: draftCount,
        submitted_system: { ...system },
        wizard_flow: flow,
      })
      clearWizardDraft()
      markFormClean()
    } catch (err) {
      setSubmitError(err.response?.data?.detail || err.message)
    } finally {
      setPendingSubmitPayload(null)
      setIsSubmitting(false)
    }
  }
  async function handleProfileCreate(profileData) {
    try {
      const res = await axios.post('/api/profiles/create', profileData)
      setResolvedProfileId(res.data.profile.id)
      setProfileModalStatus('created')
    } catch (err) {
      setSubmitError(err.response?.data?.detail || err.message)
      setIsSubmitting(false)
    }
  }
  async function handleProfileCreatedContinue() {
    setProfileModalOpen(false)
    if (!pendingSubmitPayload || !resolvedProfileId) return
    try {
      const payload = { ...pendingSubmitPayload, profile_id: resolvedProfileId }
      const draftCount = Array.isArray(payload.discoveries_draft) ? payload.discoveries_draft.length : 0
      const r = await axios.post('/api/submit_system', payload)
      setSubmitResult({
        status: 'pending',
        submission_id: r.data.submission_id,
        system_name: r.data.system_name,
        submitted_discoveries: draftCount,
        submitted_system: { ...system },
        wizard_flow: flow,
      })
      clearWizardDraft()
      markFormClean()
    } catch (err) {
      setSubmitError(err.response?.data?.detail || err.message)
    } finally {
      setPendingSubmitPayload(null)
      setIsSubmitting(false)
    }
  }

  // ===========================================================================
  // Render
  // ===========================================================================

  // Mode gate (unless we're editing or in flow already)
  if (!flow && !isEditMode) {
    return (
      <div className="space-y-8 mt-4">
        {draftBannerOpen && (
          <div className="max-w-4xl mx-auto">
            <RestoreDraftBanner
              savedAt={draftSnapshot?.savedAt}
              onRestore={() => { restoreDraft(); setFlow('advanced') }}
              onDismiss={dismissDraft}
            />
          </div>
        )}
        <div className="text-center max-w-3xl mx-auto px-4">
          <h1 className="text-3xl sm:text-4xl font-bold mb-2">Map a New System</h1>
          <p className="opacity-80">
            Pick how you want to chart your discovery. You can switch between the two flows at any time.
          </p>
        </div>
        <WizardModeGate onChoose={setFlow} />
      </div>
    )
  }

  // Post-submit success screen
  if (submitResult) {
    return (
      <SuccessScreen
        result={submitResult}
        onSubmitAnother={handleSubmitAnother}
        onViewSystem={submitResult.system_id ? () => navigate(systemPath({ id: submitResult.system_id, name: submitResult.system_name, glyph_code: submitResult.glyph_code })) : null}
        onViewLeaderboard={() => navigate('/analytics')}
      />
    )
  }

  // Form rendering
  return (
    <>
      <WizardProgressBar percent={completeness.percent} grade={completeness.grade} />
      <HelpPanel
        open={helpOpen}
        onClose={() => { setHelpOpen(false); setHelpAnchor(null) }}
        initialAnchor={helpAnchor}
      />
      {/* Mobile-only floating Help button — always visible while scrolling
          (toolbar's "? Help" can be off-screen on mobile). */}
      <HelpFab
        isOpen={helpOpen}
        onClick={() => {
          if (helpOpen) { setHelpOpen(false); setHelpAnchor(null) }
          else { setHelpAnchor(null); setHelpOpen(true) }
        }}
      />

      {/* Basic flow has no sidebar/preview, so the form would stretch across
          the full container width on widescreen monitors (1320-1800px) and
          inputs/glyph tiles get visually blown up. Cap Basic to a comfortable
          form width; Advanced keeps the full grid since its sidebar + preview
          already eat the side margins. */}
      <div className={flow === 'easy' ? 'max-w-3xl mx-auto w-full' : ''}>

      {/* Banners stack — above the sticky container, scroll away normally */}
      {(draftBannerOpen || (isEditMode && originalSystem)) && (
        <div className="space-y-2 mt-3">
          {draftBannerOpen && (
            <RestoreDraftBanner
              savedAt={draftSnapshot?.savedAt}
              onRestore={restoreDraft}
              onDismiss={dismissDraft}
            />
          )}
          {isEditMode && originalSystem && <EditModeBanner system={originalSystem} />}
        </div>
      )}

      {/* SINGLE sticky container holding the toolbar AND (on mobile) the
          section pill nav. One sticky element means zero gap between them
          on every device — no rem/px rounding, no ResizeObserver, no
          two-element timing window. `data-wizard-sticky` lets scroll-to-
          anchor handlers below measure the combined height.

          Border + rounding live on THIS container (not the inner toolbar)
          so the box stays closed when the pill nav isn't rendered below —
          Basic flow on any viewport, or Advanced flow on lg+ desktop. */}
      <div
        data-wizard-sticky
        className="sticky top-0 z-20 mt-3 rounded-lg overflow-hidden"
        style={{
          backgroundColor: 'var(--app-card)',
          border: '1px solid var(--app-accent-3)',
        }}
      >
        <WizardModeToolbar
          flow={flow}
          onFlowChange={setFlow}
          requiredOnly={requiredOnly}
          onRequiredOnlyChange={setRequiredOnly}
          isEditMode={isEditMode}
          helpOpen={helpOpen}
          onToggleHelp={() => setHelpOpen((v) => !v)}
          lastSavedAt={lastSavedAt}
        />
        {/* Mobile-only section nav — same sticky parent as the toolbar so
            they're always pixel-flush. Desktop uses the sidebar's nav. */}
        {flow === 'advanced' && (
          <div
            className="lg:hidden p-2"
            style={{
              backgroundColor: 'var(--app-card)',
              borderTop: '1px solid var(--app-accent-3)',
            }}
          >
            <nav className="flex flex-row overflow-x-auto gap-1">
              {sidebarSections.map((s) => {
                const active = s.id === activeSection
                const icon = s.status === 'complete' ? '✓' : s.status === 'partial' ? '◐' : '○'
                const iconColor = s.status === 'complete' ? '#22c55e' : s.status === 'partial' ? 'var(--app-accent-amber)' : 'var(--app-accent-3)'
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => {
                      setActiveSection(s.id)
                      const el = document.getElementById(s.id)
                      if (el) {
                        const stickyH = document.querySelector('[data-wizard-sticky]')?.offsetHeight || 120
                        const top = el.getBoundingClientRect().top + window.scrollY - (stickyH + 16)
                        window.scrollTo({ top: Math.max(0, top), left: 0 })
                      }
                    }}
                    className={`flex items-center gap-2 px-3 py-2 rounded text-sm whitespace-nowrap transition-colors ${
                      active ? 'font-semibold' : 'opacity-70 hover:opacity-100'
                    }`}
                    style={{
                      backgroundColor: active ? 'var(--app-primary)' : 'transparent',
                      color: active ? '#fff' : 'inherit',
                    }}
                  >
                    <span style={{ color: active ? '#fff' : iconColor }}>{icon}</span>
                    <span>{s.label}</span>
                  </button>
                )
              })}
            </nav>
          </div>
        )}
      </div>

      {/* Existing-system match banner — below the sticky container, scrolls away */}
      {existingMatch && (
        <div
          className="rounded-lg p-3 mt-2 flex flex-wrap items-center gap-3"
          style={{ backgroundColor: 'rgba(168, 85, 247, 0.12)', border: '1px solid var(--app-accent-2)' }}
        >
          <span className="text-xl">⚡</span>
          <div className="flex-1 text-sm">
            <span className="font-semibold">This system is already in Haven: {existingMatch.name}</span>
            <span className="opacity-70"> — {existingMatch.edit_count || 0} prior edit{existingMatch.edit_count !== 1 ? 's' : ''}.</span>
          </div>
          <Button onClick={pullExistingIntoForm}>Pull existing data</Button>
          <button
            type="button"
            onClick={() => setExistingMatch(null)}
            className="text-xs opacity-70 hover:opacity-100 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Advanced flow: landscape preview banner ABOVE the form area.
          Mounted outside the flex-row below so it spans the content width
          and the form/sidebar layout stays untouched.

          Desktop (lg+): always rendered exactly as before.
          Mobile (<lg): wrapped in a collapsed-by-default <details> so it
          doesn't eat half the viewport on top of the sticky toolbar+pill
          nav. Summary chip surfaces grade so the user gets the key signal
          without expanding. */}
      {flow === 'advanced' && (
        <>
          <div className="hidden lg:block">
            <WizardAdvancedPreview system={system} gradeInfo={completeness} />
          </div>
          <details
            className="lg:hidden mt-2 rounded-lg overflow-hidden"
            style={{ border: '1px solid var(--app-accent-3)', backgroundColor: 'var(--app-card)' }}
          >
            <summary
              className="cursor-pointer select-none px-3 py-2 flex items-center justify-between text-xs font-semibold"
              style={{ listStyle: 'none' }}
            >
              <span className="flex items-center gap-2">
                <span className="opacity-70">📊 Live preview</span>
                {completeness?.grade && completeness.grade !== '—' && (
                  <span
                    className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                    style={{
                      backgroundColor: 'var(--app-primary)',
                      color: '#fff',
                    }}
                  >
                    {completeness.grade}
                    {completeness.percent != null ? ` · ${Math.round(completeness.percent)}%` : ''}
                  </span>
                )}
              </span>
              <span className="opacity-50 text-[10px]">tap to expand</span>
            </summary>
            <div className="border-t" style={{ borderColor: 'var(--app-accent-3)' }}>
              <WizardAdvancedPreview system={system} gradeInfo={completeness} />
            </div>
          </details>
        </>
      )}

      {/* Form flex container */}
      <div className={`mt-2 lg:mt-4 flex flex-col lg:flex-row gap-4 ${flow === 'advanced' ? '' : 'lg:flex-col'}`}>
        {flow === 'advanced' && (
          <WizardSidebar
            sections={sidebarSections}
            activeId={activeSection}
            onJump={(id) => {
              setActiveSection(id)
              const el = document.getElementById(id)
              if (el) {
                const stickyH = document.querySelector('[data-wizard-sticky]')?.offsetHeight || 120
                const top = el.getBoundingClientRect().top + window.scrollY - (stickyH + 16)
                window.scrollTo({ top: Math.max(0, top), left: 0 })
              }
            }}
            gradeInfo={completeness}
          />
        )}

        <div className="flex-1 min-w-0 space-y-4">
          {/* Sections — Advanced shows all (one active highlighted via id), Easy shows current step. */}

          {(flow === 'advanced' || (flow === 'easy' && easyStep === 0)) && (
            <SectionPortal
              system={system}
              setField={setField}
              handleGlyphDecoded={handleGlyphDecoded}
              regionInfo={regionInfo}
              regionLoading={regionLoading}
              proposedRegionName={proposedRegionName}
              setProposedRegionName={(v) => { userEditedRegionRef.current = true; setProposedRegionName(v); setRegionNameSavedAt(null) }}
              regionNameSavedAt={regionNameSavedAt}
              onSaveRegionName={saveRegionNameLocally}
              diffMap={diffMap}
              sameNameMatches={sameNameMatches}
              userEditedNameRef={userEditedNameRef}
            />
          )}

          {(flow === 'advanced' || (flow === 'easy' && easyStep === 2)) && (
            <SectionAttrs system={system} setField={setField} setSystem={setSystem} requiredOnly={requiredOnly} diffMap={diffMap} openHelp={openHelpAt} />
          )}

          {(flow === 'advanced' || (flow === 'easy' && easyStep === 3)) && (
            <SectionPlanets
              system={system}
              addPlanet={addPlanet}
              editPlanet={editPlanet}
              updatePlanet={updatePlanet}
              removePlanet={removePlanet}
              setPlanetCount={setPlanetCount}
              setMoonCount={setMoonCount}
              reassignMoon={reassignMoon}
              openHelp={openHelpAt}
            />
          )}

          {flow === 'advanced' && (
            <SectionStation
              system={system}
              setStationMode={setStationMode}
              setStationField={setStationField}
              toggleTradeGood={toggleTradeGood}
              requiredOnly={requiredOnly}
            />
          )}

          {flow === 'advanced' && (
            <SectionDiscoveries
              system={system}
              discoveries={discoveries}
              setDiscoveries={setDiscoveries}
              existingDiscoveries={existingDiscoveries}
              onEditExisting={handleEditExistingDiscovery}
              defaultGameVersion={system.game_version}
              requiredOnly={requiredOnly}
              openHelp={openHelpAt}
            />
          )}

          {(flow === 'advanced' || (flow === 'easy' && easyStep === 1)) && (
            <SectionIdentity
              system={system}
              setField={setField}
              discordTags={discordTags}
              isAdmin={isAdmin}
              submitterDiscordUsername={submitterDiscordUsername}
              setSubmitterDiscordUsername={setSubmitterDiscordUsername}
              personalDiscordUsername={personalDiscordUsername}
              setPersonalDiscordUsername={setPersonalDiscordUsername}
              personalModalOpen={personalModalOpen}
              setPersonalModalOpen={setPersonalModalOpen}
              isLoggedIn={!!profileId}
              requiredOnly={requiredOnly}
            />
          )}

          {(flow === 'advanced' || (flow === 'easy' && easyStep === 3)) && (
            <SectionSubmit
              issues={validationIssues}
              system={system}
              setField={setField}
              isAdmin={isAdmin}
              isSubmitting={isSubmitting}
              submitError={submitError}
              onSubmit={handleSubmitClick}
              onCancel={() => navigate('/systems')}
            />
          )}

          {/* Easy-flow stepper controls */}
          {flow === 'easy' && (
            <div className="flex justify-between mt-4">
              <Button
                variant="ghost"
                onClick={() => easyStep > 0 ? setEasyStep((s) => s - 1) : setFlow(null)}
              >
                {easyStep > 0 ? 'Back' : 'Change Flow'}
              </Button>
              {easyStep < 3 ? (
                <Button onClick={() => setEasyStep((s) => s + 1)}>Next →</Button>
              ) : null}
            </div>
          )}
        </div>

        {/* Easy flow keeps the portrait sticky right column. Advanced flow's
            preview mounts as a top banner ABOVE this flex container (see
            the WizardAdvancedPreview mount above). Mounting both inside
            this flex row broke the form layout — advanced preview claimed
            `w-full` which collapsed the form column. */}
        {flow === 'easy' && <WizardPreviewPanel system={system} gradeInfo={completeness} />}
      </div>

      </div>{/* /max-w wrapper (Basic flow only) */}

      {/* Planet edit modal */}
      {planetModalOpen && (
        <Modal title={editingPlanetIndex === -1 ? 'Add Planet' : 'Edit Planet'} onClose={() => setPlanetModalOpen(false)}>
          <PlanetEditor
            planet={editingPlanet}
            index={editingPlanetIndex}
            onChange={(_i, p) => setEditingPlanet(p)}
            onRemove={() => {}}
            onSave={commitPlanet}
            openHelp={openHelpAt}
          />
        </Modal>
      )}

      {/* Conflict resolution — resumes doSubmit() with the user's per-field picks */}
      {conflictModalOpen && (
        <ConflictResolutionModal
          conflicts={conflicts}
          onResolve={(choices) => {
            setConflictModalOpen(false)
            // Pre-apply the picks to local state so the form reflects what was sent.
            setSystem((prev) => {
              const next = { ...prev }
              conflicts.forEach((c) => { if (choices[c.field] === 'theirs') next[c.field] = c.theirs })
              return next
            })
            // Resume the submit with the applied resolutions.
            doSubmit(choices)
          }}
          onCancel={() => { setConflictModalOpen(false); setConflicts([]) }}
        />
      )}

      {/* Profile claim */}
      {profileModalOpen && (
        <ProfileClaimModal
          status={profileModalStatus}
          suggestions={profileSuggestions}
          username={submitterDiscordUsername.trim() || personalDiscordUsername.trim()}
          onUse={handleProfileUse}
          onCreate={handleProfileCreate}
          onContinue={handleProfileCreatedContinue}
          onClose={() => { setProfileModalOpen(false); setPendingSubmitPayload(null); setIsSubmitting(false) }}
        />
      )}

      {/* Edit an existing discovery attached to this system. Runs the shared
          discovery edit flow (→ pending_discoveries, edit_discovery_id), which
          is approved separately from this system's own edit. */}
      <DiscoverySubmitModal
        isOpen={!!editingDiscovery}
        editDiscovery={editingDiscovery}
        onClose={() => setEditingDiscovery(null)}
        onSuccess={() => setEditingDiscovery(null)}
      />

      {/* Personal Discord username modal (when discord_tag === 'personal') */}
      {personalModalOpen && (
        <Modal title="Personal Discord Username" onClose={() => setPersonalModalOpen(false)}>
          <div className="space-y-3">
            <p className="text-sm opacity-80">
              You picked "Personal". Enter the Discord username we should credit.
            </p>
            <input
              type="text"
              autoFocus
              className="w-full p-2 rounded"
              style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
              value={personalDiscordUsername}
              onChange={(e) => setPersonalDiscordUsername(e.target.value)}
              placeholder="username or username#1234"
            />
            <div className="flex gap-2">
              <Button onClick={() => {
                if (!personalDiscordUsername.trim()) return
                setField('discord_tag', 'personal')
                setPersonalModalOpen(false)
              }}>Confirm</Button>
              <Button variant="ghost" onClick={() => setPersonalModalOpen(false)}>Cancel</Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}

// ===========================================================================
// Section components — kept inline for one-file readability. Each one is
// presentational and consumes the parent's state via props.
// ===========================================================================

function Section({ id, title, accent, children }) {
  return (
    <Card className="scroll-mt-32" thin>
      <a id={id} />
      <h3 className="text-lg font-semibold mb-3" style={{ color: accent || 'var(--app-primary)' }}>
        {title}
      </h3>
      {children}
    </Card>
  )
}

// Helper: border color for a field, reflecting diff highlight + required state.
function fieldBorder(key, diffMap, value, required = false) {
  if (diffMap?.[key]) return 'var(--app-accent-amber)'
  if (required && (value == null || value === '')) return '#ef4444'
  return 'var(--app-accent-3)'
}

function SectionPortal({
  system, setField, handleGlyphDecoded, regionInfo, regionLoading,
  proposedRegionName, setProposedRegionName,
  regionNameSavedAt, onSaveRegionName,
  diffMap, sameNameMatches, userEditedNameRef,
}) {
  return (
    <Section id="portal" title="01 · Portal Address">
      <div id="wiz-system-name" className="mb-3">
        <label className="block text-sm font-medium mb-1">System Name</label>
        <input
          className="w-full p-2 rounded"
          style={{
            backgroundColor: 'var(--app-bg)',
            border: `1px solid ${fieldBorder('name', diffMap, system.name)}`,
            backgroundImage: diffMap?.name ? 'linear-gradient(rgba(255,180,76,0.05),rgba(255,180,76,0.05))' : undefined,
          }}
          placeholder="Auto-generated from glyphs — verify in-game"
          value={system.name || ''}
          onChange={(e) => {
            if (userEditedNameRef) userEditedNameRef.current = true
            setField('name', e.target.value)
          }}
        />
        {/* Same-name soft warning (mockup v11CheckSameName 9937) */}
        {sameNameMatches && sameNameMatches.length > 0 && (
          <div
            className="mt-2 p-2 rounded text-xs"
            style={{ backgroundColor: 'rgba(255,180,76,0.12)', border: '1px solid var(--app-accent-amber)', color: 'var(--app-accent-amber)' }}
          >
            ⚠ A system named <span className="font-semibold">{sameNameMatches[0].name}</span> already exists
            {sameNameMatches[0].galaxy ? ` in ${sameNameMatches[0].galaxy}` : ''}.
            <span className="opacity-80"> Same names are allowed but please double-check this is your intent.</span>
          </div>
        )}
      </div>

      <div id="wiz-glyphs">
        <label className="block text-sm font-medium mb-2">Portal Glyph Code <span className="text-red-400">*</span></label>
        <GlyphPicker
          value={system.glyph_code}
          onChange={(code) => setField('glyph_code', code)}
          onDecoded={handleGlyphDecoded}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
        <div id="wiz-reality">
          <label className="block text-sm font-medium mb-1">Reality <span className="text-red-400">*</span></label>
          <select
            className="w-full p-2 rounded"
            style={{ backgroundColor: 'var(--app-bg)', border: `1px solid ${fieldBorder('reality', diffMap, system.reality, true)}` }}
            value={system.reality || ''}
            onChange={(e) => setField('reality', e.target.value)}
          >
            <option value="">— Select —</option>
            {REALITIES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
        <div id="wiz-galaxy">
          <label className="block text-sm font-medium mb-1">Galaxy <span className="text-red-400">*</span></label>
          <SearchableSelect
            options={GALAXIES.map((g) => ({ value: g.name, label: `${g.index}: ${g.name}` }))}
            value={system.galaxy || ''}
            onChange={(v) => setField('galaxy', v || '')}
            placeholder="— Select Galaxy —"
          />
        </div>
      </div>

      {/* Region info */}
      {system.region_x != null && (
        <div className="mt-4 p-3 rounded" style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}>
          {regionLoading ? (
            <div className="text-sm opacity-70">Looking up region…</div>
          ) : regionInfo ? (
            <div>
              <div className="text-sm opacity-80 mb-2">
                Region <span className="font-mono">[{regionInfo.region_x}, {regionInfo.region_y}, {regionInfo.region_z}]</span> · {regionInfo.reality} / {regionInfo.galaxy}
              </div>
              {/* Region context counter (mockup #v11-region-context 5540) */}
              {typeof regionInfo.system_count === 'number' && (
                <div className="text-xs mb-2" style={{ color: 'var(--app-primary)' }}>
                  {regionInfo.system_count === 0
                    ? '🌟 You\'re the first to map this region!'
                    : `🗺️ You're the ${regionInfo.system_count + 1}${ordinalSuffix(regionInfo.system_count + 1)} submission in this region (${regionInfo.system_count} already mapped).`}
                </div>
              )}
              {regionInfo.custom_name ? (
                <div className="text-green-400 font-semibold">{regionInfo.custom_name}</div>
              ) : regionInfo.pending_name ? (
                <div className="text-yellow-400">
                  Pending name: <span className="font-semibold">{regionInfo.pending_name.proposed_name}</span>
                  <span className="opacity-60 ml-2">by {regionInfo.pending_name.submitted_by}</span>
                </div>
              ) : (
                <div>
                  <div className="text-sm text-amber-300 mb-2">
                    This region has no name. A region name is required before submission. <span className="text-red-400">*</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      id="wiz-region-input"
                      type="text"
                      className="flex-1 p-2 rounded text-sm"
                      style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                      placeholder="Proposed region name…"
                      value={proposedRegionName}
                      onChange={(e) => setProposedRegionName(e.target.value)}
                      maxLength={50}
                    />
                    <Button onClick={onSaveRegionName} disabled={!proposedRegionName.trim()}>
                      Save
                    </Button>
                  </div>
                  {/* Saved-locally state: green badge with the proposed name + Edit affordance */}
                  {proposedRegionName.trim() && regionNameSavedAt && (
                    <div
                      className="mt-2 flex items-center justify-between gap-2 px-2 py-1.5 rounded text-xs"
                      style={{ backgroundColor: 'rgba(34,197,94,0.12)', border: '1px solid #22c55e', color: '#86efac' }}
                    >
                      <span>
                        ✓ Proposed: <span className="font-semibold">{proposedRegionName.trim()}</span>
                      </span>
                      <span className="opacity-80">
                        Will submit with your system.
                      </span>
                    </div>
                  )}
                  <p className="text-xs opacity-60 mt-1.5">
                    Region name will be submitted with your system so your discord identity is attached.
                  </p>
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}
    </Section>
  )
}

function SectionAttrs({ system, setField, setSystem, requiredOnly, diffMap = {}, openHelp }) {
  const abandoned = system.economy_type === 'None' || system.economy_type === 'Abandoned'
  return (
    <Section id="attrs" title="02 · System Attributes" accent="var(--app-accent-2)">
      {/* Auto-fit grid: as many columns as fit, each at least 180px wide.
          Mobile (~280px container) → 1 col. Desktop 1280px (form col
          ~440px) → 2 cols at ~210px. Widescreen 1920px (form col ~800px)
          → 3-4 cols, no dead space. 180px min keeps "Dominant Lifeform *
          (?)" on one line without overflow. */}
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}
      >
        <div id="wiz-star-type">
          <label className="block text-sm font-medium mb-1">Star Color <span className="text-red-400">*</span></label>
          <select
            className="w-full p-2 rounded"
            style={{ backgroundColor: 'var(--app-bg)', border: `1px solid ${fieldBorder('star_type', diffMap, system.star_type, true)}` }}
            value={system.star_type || ''}
            onChange={(e) => setField('star_type', e.target.value)}
          >
            <option value="">— Select —</option>
            <option value="Yellow">☀ Yellow</option>
            <option value="Red">🔴 Red</option>
            <option value="Green">🟢 Green</option>
            <option value="Blue">🔵 Blue</option>
            <option value="Purple">🟣 Purple</option>
          </select>
        </div>
        <div id="wiz-economy-type">
          <label className="block text-sm font-medium mb-1">Economy Type <span className="text-red-400">*</span></label>
          <select
            className="w-full p-2 rounded"
            style={{ backgroundColor: 'var(--app-bg)', border: `1px solid ${fieldBorder('economy_type', diffMap, system.economy_type, true)}` }}
            value={system.economy_type || ''}
            onChange={(e) => {
              const v = e.target.value
              if (v === 'None' || v === 'Abandoned') {
                setSystem((s) => ({ ...s, economy_type: v, economy_level: 'None', conflict_level: 'None' }))
              } else {
                setSystem((s) => ({
                  ...s,
                  economy_type: v,
                  economy_level: s.economy_level === 'None' ? '' : s.economy_level,
                  conflict_level: s.conflict_level === 'None' ? '' : s.conflict_level,
                }))
              }
            }}
          >
            <option value="">— Select —</option>
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
        <div id="wiz-economy-level">
          <label className="block text-sm font-medium mb-1">
            Economy Tier {!abandoned && <span className="text-red-400">*</span>}
            <HelpChip anchor="wealth-tier" onOpen={openHelp} label="Help: Wealth Tier" />
          </label>
          <select
            className="w-full p-2 rounded"
            style={{ backgroundColor: 'var(--app-bg)', border: `1px solid ${fieldBorder('economy_level', diffMap, system.economy_level)}`, opacity: abandoned ? 0.5 : 1 }}
            value={system.economy_level || ''}
            onChange={(e) => setField('economy_level', e.target.value)}
            disabled={abandoned}
          >
            <option value="">— Select —</option>
            <option value="T1">★ (Low)</option>
            <option value="T2">★★ (Medium)</option>
            <option value="T3">★★★ (High)</option>
            <option value="T4">☠ (Pirate)</option>
            <option value="None">⭕ None</option>
          </select>
        </div>
        <div id="wiz-conflict-level">
          <label className="block text-sm font-medium mb-1">
            Conflict Level {!abandoned && <span className="text-red-400">*</span>}
            <HelpChip anchor="conflict-level" onOpen={openHelp} label="Help: Conflict Level" />
          </label>
          <select
            className="w-full p-2 rounded"
            style={{ backgroundColor: 'var(--app-bg)', border: `1px solid ${fieldBorder('conflict_level', diffMap, system.conflict_level)}`, opacity: abandoned ? 0.5 : 1 }}
            value={system.conflict_level || ''}
            onChange={(e) => setField('conflict_level', e.target.value)}
            disabled={abandoned}
          >
            <option value="">— Select —</option>
            <option value="Low">🔥 Low</option>
            <option value="Medium">🔥🔥 Medium</option>
            <option value="High">🔥🔥🔥 High</option>
            <option value="Pirate">☠️ Pirate</option>
            <option value="None">⭕ None</option>
          </select>
        </div>
        <div id="wiz-lifeform">
          <label className="block text-sm font-medium mb-1">
            Dominant Lifeform <span className="text-red-400">*</span>
            <HelpChip anchor="lifeform" onOpen={openHelp} label="Help: None vs Abandoned" />
          </label>
          <select
            className="w-full p-2 rounded"
            style={{ backgroundColor: 'var(--app-bg)', border: `1px solid ${fieldBorder('dominant_lifeform', diffMap, system.dominant_lifeform, true)}` }}
            value={system.dominant_lifeform || ''}
            onChange={(e) => setField('dominant_lifeform', e.target.value)}
          >
            <option value="">— Select —</option>
            <option value="Gek">🐸 Gek</option>
            <option value="Vy'keen">⚔️ Vy'keen</option>
            <option value="Korvax">🤖 Korvax</option>
            <option value="None">⭕ None — no dominant lifeform</option>
            <option value="Abandoned">🚫 Abandoned — empty buildings, no race</option>
          </select>
        </div>
        {!requiredOnly && (
          <div>
            <label className="block text-sm font-medium mb-1">
              Spectral Class
              <HelpChip anchor="spectral-class" onOpen={openHelp} label="Help: Spectral Class" />
            </label>
            <input
              type="text"
              className="w-full p-2 rounded font-mono"
              style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
              value={system.stellar_classification || ''}
              onChange={(e) => setField('stellar_classification', e.target.value.slice(0, 6))}
              placeholder="G2pf, M7, O3f…"
            />
          </div>
        )}
        {!requiredOnly && (
          <div>
            <label className="block text-sm font-medium mb-1">NMS Game Version</label>
            <input
              type="text"
              className="w-full p-2 rounded"
              style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
              value={system.game_version || ''}
              onChange={(e) => setField('game_version', e.target.value)}
              placeholder="6.18, Worlds Part 2, Voyagers…"
            />
          </div>
        )}
        {!requiredOnly && (
          <div id="wiz-game-mode">
            <label className="block text-sm font-medium mb-1">Game Mode</label>
            <select
              className="w-full p-2 rounded"
              style={{ backgroundColor: 'var(--app-bg)', border: `1px solid ${fieldBorder('game_mode', diffMap, system.game_mode)}` }}
              value={system.game_mode || 'Normal'}
              onChange={(e) => setField('game_mode', e.target.value)}
            >
              <option value="Normal">Normal</option>
              <option value="Creative">Creative</option>
              <option value="Relaxed">Relaxed</option>
              <option value="Survival">Survival</option>
              <option value="Permadeath">Permadeath</option>
              <option value="Custom">Custom</option>
            </select>
          </div>
        )}
      </div>
      {!requiredOnly && (
        <div className="mt-3">
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea
            className="w-full p-2 rounded"
            style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)', minHeight: 80 }}
            value={system.description || ''}
            onChange={(e) => setField('description', e.target.value)}
          />
        </div>
      )}
    </Section>
  )
}

function SectionPlanets({ system, addPlanet, editPlanet, updatePlanet, removePlanet, setPlanetCount, setMoonCount, reassignMoon, openHelp }) {
  const planets = system.planets || []
  const planetCount = planets.length
  const moonCount = planets.reduce((n, p) => n + ((p.moons || []).length), 0)
  const totalBodies = planetCount + moonCount
  const atCap = totalBodies >= 6
  const moonMax = Math.max(0, 6 - planetCount)
  const selectStyle = { backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }
  return (
    <Section id="planets" title="03 · Planets & Moons">
      <div id="wiz-planets">
        {/* Body-count generator — NMS systems hold up to 6 bodies (planets +
            moons combined). Pick the counts and shells are generated for you. */}
        <div className="flex flex-wrap items-end gap-4 mb-3 p-3 rounded" style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}>
          <div>
            <label className="block text-xs font-medium mb-1 opacity-80">Planets</label>
            <select
              className="p-2 rounded text-sm"
              style={selectStyle}
              value={planetCount}
              onChange={(e) => setPlanetCount(Number(e.target.value))}
            >
              {[0, 1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1 opacity-80">Moons</label>
            <select
              className="p-2 rounded text-sm disabled:opacity-50"
              style={selectStyle}
              value={moonCount}
              disabled={planetCount === 0}
              onChange={(e) => setMoonCount(Number(e.target.value))}
              title={planetCount === 0 ? 'Add a planet first — moons orbit a planet' : `Up to ${moonMax} with ${planetCount} planet(s)`}
            >
              {Array.from({ length: moonMax + 1 }, (_, n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div className="text-sm">
            <span className="opacity-70">Bodies: </span>
            <span className="font-semibold" style={{ color: atCap ? 'var(--app-accent-amber)' : 'var(--app-primary)' }}>
              {totalBodies} / 6
            </span>
            {planetCount > 0 && (
              <span className="opacity-60 ml-2">New moons attach to {planets[0]?.name || 'Planet 1'} — use “Orbits” to move them.</span>
            )}
          </div>
        </div>

        {planets.map((p, i) => (
          <div key={i} className="mb-2">
            <PlanetEditor
              index={i}
              planet={p}
              planets={planets}
              onChange={updatePlanet}
              onRemove={removePlanet}
              onReassignMoon={(moonIdx, toIdx) => reassignMoon(i, moonIdx, toIdx)}
              openHelp={openHelp}
            />
            <div className="mt-1">
              <button type="button" onClick={() => editPlanet(i)} className="px-3 py-1.5 bg-sky-600 text-white rounded text-sm">Edit</button>
            </div>
          </div>
        ))}
        {planetCount === 0 && (
          <p className="text-sm opacity-70 mb-2">No planets yet. Pick a planet count above (or “Add Planet”) to score the Planets categories.</p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button onClick={addPlanet} disabled={atCap}>+ Add Planet</Button>
        </div>
        {atCap && (
          <p className="text-xs opacity-60 mt-1">Maximum of 6 celestial bodies reached.</p>
        )}
      </div>
    </Section>
  )
}

function SectionStation({ system, setStationMode, setStationField, toggleTradeGood, requiredOnly }) {
  // Tri-state derived from the system: a present station = 'has', the explicit
  // no_space_station flag = 'none', otherwise 'unknown' (not documented yet).
  const mode = system.space_station ? 'has' : (system.no_space_station ? 'none' : 'unknown')
  return (
    <Section id="station" title="04 · Space Station" accent="var(--app-accent-2)">
      <div className="flex flex-col gap-2 mb-3">
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="station-mode"
            className="w-4 h-4"
            checked={mode === 'has'}
            onChange={() => setStationMode('has')}
          />
          <span>🛸 Has a space station</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="station-mode"
            className="w-4 h-4"
            checked={mode === 'none'}
            onChange={() => setStationMode('none')}
          />
          <span>🚫 No space station <span className="opacity-60 text-sm">(this system has none)</span></span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="station-mode"
            className="w-4 h-4"
            checked={mode === 'unknown'}
            onChange={() => setStationMode('unknown')}
          />
          <span>❔ Not documented yet</span>
        </label>
      </div>
      {mode === 'has' && system.space_station && (
        <div className="ml-6 p-3 rounded" style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-2)' }}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-sm">Station Name</label>
              <input
                className="w-full mt-1 p-2 rounded"
                style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                value={system.space_station.name || ''}
                onChange={(e) => setStationField('name', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm">Race</label>
              <select
                className="w-full mt-1 p-2 rounded"
                style={{ backgroundColor: 'var(--app-card)', border: '1px solid var(--app-accent-3)' }}
                value={system.space_station.race || 'Gek'}
                onChange={(e) => setStationField('race', e.target.value)}
              >
                <option value="Gek">Gek</option>
                <option value="Korvax">Korvax</option>
                <option value="Vy'keen">Vy'keen</option>
                <option value="Unknown">Unknown</option>
              </select>
            </div>
          </div>
          {!requiredOnly && (
            <>
              <div className="text-xs opacity-70 mb-2">
                Distance: {system.space_station.orbitalRadius?.toFixed(1) || '?'} units · {system.space_station.slot || 'auto-placed'}
              </div>
              {system.economy_type && system.economy_type !== 'None' && system.economy_type !== 'Abandoned' && (
                <div>
                  <div className="text-sm font-medium mb-2">
                    Trade Goods Sold
                    <span className="text-xs opacity-60 ml-2">
                      ({system.economy_type} · {system.economy_level || 'tier?'})
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 max-h-48 overflow-y-auto p-2 rounded" style={{ backgroundColor: 'var(--app-card)' }}>
                    {getTradeGoodsForEconomyAndTier(system.economy_type, system.economy_level).map((good) => (
                      <label key={good.id} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          className="w-3 h-3"
                          checked={(system.space_station.trade_goods || []).includes(good.id)}
                          onChange={() => toggleTradeGood(good.id)}
                        />
                        <span>{good.name}<span className="opacity-50 text-xs ml-1">(T{good.tier})</span></span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </Section>
  )
}

function SectionDiscoveries({ system, discoveries, setDiscoveries, existingDiscoveries = [], onEditExisting, defaultGameVersion, requiredOnly, openHelp }) {
  if (requiredOnly) return null
  // Flatten moons across planets so the discovery card can pick by name+parent.
  const planetList = (system.planets || []).filter((p) => !p.is_moon)
  const moonList = planetList.flatMap((p) =>
    (p.moons || []).map((m, mi) => ({
      ...m,
      id: m.id ?? `${p.name || 'planet'}::${m.name || 'moon'}::${mi}`,
      parentPlanetName: p.name,
    }))
  )
  return (
    <Section id="discoveries" title="05 · Discoveries">
      {existingDiscoveries.length > 0 && (
        <div
          className="mb-4 p-3 rounded"
          style={{ backgroundColor: 'rgba(124,217,234,0.07)', border: '1px solid var(--app-primary)' }}
        >
          <div className="text-xs font-semibold uppercase tracking-wider opacity-80 mb-2">
            Existing discoveries on this system ({existingDiscoveries.length})
          </div>
          <ul className="space-y-1 text-sm">
            {existingDiscoveries.map((d) => {
              const loc = d.moon_name ? `${d.planet_name} · ${d.moon_name}` : (d.planet_name || (d.location_type === 'space' ? 'In space' : 'Unlinked'))
              return (
                <li key={d.id} className="flex items-baseline gap-2">
                  <span className="px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wider opacity-80" style={{ backgroundColor: 'rgba(255,255,255,0.08)' }}>
                    {d.discovery_type || 'discovery'}
                  </span>
                  <span className="font-medium">{d.discovery_name}</span>
                  <span className="opacity-60 text-xs">— {loc}</span>
                  {!d.planet_id && !d.moon_id && d.location_type !== 'space' && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300">⚠ unlinked</span>
                  )}
                  {onEditExisting && (
                    <button
                      type="button"
                      onClick={() => onEditExisting(d)}
                      className="ml-auto shrink-0 px-2 py-0.5 rounded text-[11px] font-medium"
                      style={{ backgroundColor: 'rgba(124,217,234,0.15)', border: '1px solid var(--app-primary)', color: 'var(--app-primary)' }}
                    >
                      Edit
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
          <div className="text-[11px] opacity-60 mt-2">
            Edits to these go to the approval queue (separate from this system's edit). Add brand-new discoveries below.
          </div>
        </div>
      )}
      <DiscoveryInlineList
        value={discoveries}
        onChange={setDiscoveries}
        planets={planetList.map((p, i) => ({ ...p, id: p.id ?? `planet-${i}` }))}
        moons={moonList}
        defaultGameVersion={defaultGameVersion}
        openHelp={openHelp}
      />
    </Section>
  )
}

function SectionIdentity({
  system, setField, discordTags, isAdmin,
  submitterDiscordUsername, setSubmitterDiscordUsername,
  personalDiscordUsername, setPersonalDiscordUsername,
  personalModalOpen, setPersonalModalOpen,
  isLoggedIn, requiredOnly,
}) {
  return (
    <Section id="identity" title="06 · Identity" accent="var(--app-accent-2)">
      <div id="wiz-discord-tag" className="mb-3">
        <label className="block text-sm font-medium mb-1">
          Discord Community <span className="text-red-400">*</span>
        </label>
        <select
          className="w-full p-2 rounded"
          style={{ backgroundColor: 'var(--app-bg)', border: `1px solid ${system.discord_tag ? 'var(--app-accent-3)' : '#ef4444'}` }}
          value={system.discord_tag || ''}
          onChange={(e) => {
            const v = e.target.value
            if (v === 'personal') {
              setPersonalModalOpen(true)
            } else {
              setField('discord_tag', v || null)
              if (system.discord_tag === 'personal') setPersonalDiscordUsername('')
            }
          }}
        >
          <option value="">— Select Community (Required) —</option>
          {discordTags.map((t) => (
            <option key={t.tag} value={t.tag}>{t.name} ({t.tag})</option>
          ))}
          <option value="personal">Personal (No Community Affiliation)</option>
        </select>
        {system.discord_tag === 'personal' && personalDiscordUsername && (
          <div className="mt-2 p-2 rounded text-xs flex items-center justify-between" style={{ backgroundColor: 'rgba(168, 85, 247, 0.12)', border: '1px solid var(--app-accent-2)' }}>
            <span>Discord: <strong>{personalDiscordUsername}</strong></span>
            <button type="button" onClick={() => setPersonalModalOpen(true)} className="opacity-70 hover:opacity-100 underline">Edit</button>
          </div>
        )}
      </div>

      {!isAdmin && (
        <div id="wiz-submitter-username" className="mb-3">
          <label className="block text-sm font-medium mb-1">
            Your Discord Username <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            className="w-full p-2 rounded"
            style={{ backgroundColor: 'var(--app-bg)', border: `1px solid ${submitterDiscordUsername.trim() ? 'var(--app-accent-3)' : '#ef4444'}` }}
            value={submitterDiscordUsername}
            onChange={(e) => setSubmitterDiscordUsername(e.target.value)}
            placeholder="username or username#1234"
          />
          <p className="text-xs opacity-60 mt-1">Required so we can credit you and contact you about your submission.</p>
        </div>
      )}

      {!requiredOnly && (
        <>
          <div className="mb-3">
            <label className="block text-sm font-medium mb-1">Co-Authors</label>
            <CoAuthorChipInput
              value={system.coauthors || []}
              onChange={(list) => setField('coauthors', list)}
            />
          </div>
          <div className="mb-3">
            <label className="block text-sm font-medium mb-1">Expedition</label>
            <ExpeditionPicker
              value={system.expedition_id}
              onChange={(id) => setField('expedition_id', id)}
              disabled={!isLoggedIn}
            />
          </div>
          <EventPicker
            value={system.event_id}
            onChange={(id) => setField('event_id', id)}
            kind="submission"
          />
        </>
      )}
    </Section>
  )
}

function SectionSubmit({ issues, system, setField, isAdmin, isSubmitting, submitError, onSubmit, onCancel }) {
  return (
    <Section id="submit" title="07 · Submit">
      <ValidationSummary issues={issues} />

      {!isAdmin && (
        <div
          className="text-sm mb-3 p-2 rounded"
          style={{ backgroundColor: 'rgba(255, 180, 76, 0.12)', border: '1px solid var(--app-accent-amber)' }}
        >
          You are not an admin. Your submission will go to the approval queue.
        </div>
      )}

      <div className="mb-3">
        <label className="block text-sm font-medium mb-1">Notes for the reviewer (optional, admin-only)</label>
        <textarea
          className="w-full p-2 rounded text-sm"
          style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)', minHeight: 60 }}
          value={system.submitter_notes || ''}
          onChange={(e) => setField('submitter_notes', e.target.value)}
          placeholder="Anything the approver should know — context, caveats, screenshots posted in Discord, etc."
        />
      </div>

      {submitError && (
        <div className="mb-3 p-2 rounded text-sm text-red-300" style={{ backgroundColor: 'rgba(239,68,68,0.15)' }}>
          {submitError}
        </div>
      )}

      <div className="flex gap-2">
        <Button onClick={onSubmit} disabled={isSubmitting || issues.length > 0}>
          {isSubmitting ? 'Submitting…' : (isAdmin ? 'Save System' : 'Submit for Approval')}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={isSubmitting}>Cancel</Button>
      </div>
    </Section>
  )
}
