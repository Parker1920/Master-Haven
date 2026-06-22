import React, { useEffect, useState, useContext, useMemo } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import Modal from '../components/Modal'
import { AuthContext } from '../utils/AuthContext'
import { formatDate } from '../hooks/useDateFormat'

/**
 * Civilization Management (replaces Partner Management — migration 1.80.0 / PR-B)
 * Route: /admin/civilizations
 * Auth: Super admin only
 *
 * One page covers what used to be Partner Management + Sub-Admin Management:
 *   - List civilizations (one card per civilization entity, NOT per user).
 *   - Click a civ to open a detail modal with its full membership roster.
 *   - Add, promote/demote, remove members. Roles: leader / co_leader / sub_admin.
 *   - Edit civ brand: display_name, region_color, default features.
 *   - "Found new civilization" creates the civ + seeds the first leader.
 *
 * Backed by /api/civilizations (see backend/routes/civilizations.py).
 */

const ROLES = [
  { id: 'leader', label: 'Leader', desc: 'Founder-tier; same powers as a co-leader.' },
  { id: 'co_leader', label: 'Co-Leader', desc: 'Identical perms to leader; civ co-runner.' },
  { id: 'sub_admin', label: 'Sub-Admin', desc: 'Delegated approval/edit perms.' },
]

const FEATURE_DEFAULTS = [
  { id: 'system_create', label: 'Create Systems' },
  { id: 'system_edit', label: 'Edit Systems' },
  { id: 'approvals', label: 'View Approvals' },
  { id: 'batch_approvals', label: 'Batch Approvals' },
  { id: 'stats', label: 'View Statistics' },
  { id: 'settings', label: 'Theme Settings' },
  { id: 'csv_import', label: 'CSV Import' },
  { id: 'war_room', label: 'War Room (all moderators)' },
]

// Most features here only govern SUB-ADMINS — leaders and co-leaders ALWAYS get
// the full set by role (granted server-side in _recompute_profile_features). So
// seeding this default non-empty means a civ founded by a super admin who never
// touches the grid still has working sub-admins instead of zero-access ones.
//
// EXCEPTION: 'war_room' is civ-scoped, not by-role. Checking it grants the War
// Room to EVERY moderator of this civ (leaders, co-leaders AND sub-admins);
// unchecking removes it from all of them. A civ leader does NOT get the War Room
// just for being a leader — only when this box is checked (or the civ is enrolled
// via War Room Admin, which checks it for you).
const DEFAULT_SUB_ADMIN_FEATURES = ['approvals', 'system_create', 'system_edit', 'stats']

// Roles whose holders are full-power within the civ (access granted by role,
// not by the per-civ feature default). Mirrors the backend LEADER_FEATURES rule.
const LEADER_ROLES = ['leader', 'co_leader']

export default function CivilizationManagement() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [civs, setCivs] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const [detail, setDetail] = useState(null)        // selected civ detail (with members)
  const [detailLoading, setDetailLoading] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [editDraft, setEditDraft] = useState(null)  // brand-edit form state

  // Add-member modal
  const [addMemberOpen, setAddMemberOpen] = useState(false)
  const [addProfileQuery, setAddProfileQuery] = useState('')
  const [addRole, setAddRole] = useState('sub_admin')

  // Create-civ modal
  // Create-civ modal
  const [createOpen, setCreateOpen] = useState(false)
  const [createDraft, setCreateDraft] = useState({
    tag: '', display_name: '', region_color: '#00C2B3',
    founder_username: '', enabled_features_default: [...DEFAULT_SUB_ADMIN_FEATURES],
  })

  // Archive confirmation modal
  const [archiveTarget, setArchiveTarget] = useState(null)  // civ object to archive/unarchive
  const [archiving, setArchiving] = useState(false)

  useEffect(() => {
    if (!auth.isSuperAdmin) {
      alert('Super admin access required')
      navigate('/systems')
      return
    }
    loadCivs()
  }, [auth.isSuperAdmin, navigate])

  async function loadCivs() {
    setLoading(true)
    try {
      const r = await axios.get('/api/civilizations')
      setCivs(r.data.civilizations || [])
    } catch (err) {
      alert('Failed to load civilizations: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  async function openDetail(civ) {
    setDetail({ ...civ, members: [] })   // optimistic shell so the modal opens fast
    setDetailLoading(true)
    setEditMode(false)
    try {
      const r = await axios.get(`/api/civilizations/${civ.id}`)
      setDetail(r.data)
      setEditDraft({
        display_name: r.data.display_name,
        region_color: r.data.region_color || '#00C2B3',
        enabled_features_default: r.data.enabled_features_default || [],
        default_reality: r.data.default_reality || '',
        default_galaxy: r.data.default_galaxy || '',
      })
    } catch (err) {
      alert('Failed to load civilization detail: ' + (err.response?.data?.detail || err.message))
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }

  async function saveBrand() {
    if (!detail || !editDraft) return
    try {
      await axios.put(`/api/civilizations/${detail.id}`, editDraft)
      setEditMode(false)
      await openDetail({ ...detail, ...editDraft })
      await loadCivs()
    } catch (err) {
      alert('Failed to save: ' + (err.response?.data?.detail || err.message))
    }
  }

  async function changeMemberRole(profileId, newRole) {
    try {
      await axios.put(`/api/civilizations/${detail.id}/members/${profileId}`, { role: newRole })
      await openDetail(detail)
    } catch (err) {
      alert('Failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  async function toggleMemberCap(profileId, current) {
    try {
      await axios.put(`/api/civilizations/${detail.id}/members/${profileId}`, {
        can_approve_personal_uploads: !current,
      })
      await openDetail(detail)
    } catch (err) {
      alert('Failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  // Set a sub-admin's per-member feature override. Pass a feature-id array to
  // override the civ default, or null to clear the override (inherit the civ
  // default again). Leaders/co-leaders ignore this — they're full-power by role.
  async function setMemberFeatures(profileId, features) {
    try {
      await axios.put(`/api/civilizations/${detail.id}/members/${profileId}`, {
        enabled_features: features,
      })
      await openDetail(detail)
    } catch (err) {
      alert('Failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  async function removeMember(profileId, username) {
    if (!confirm(`Remove ${username} from ${detail.display_name}?`)) return
    try {
      await axios.delete(`/api/civilizations/${detail.id}/members/${profileId}`)
      await openDetail(detail)
      await loadCivs()
    } catch (err) {
      alert('Failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  async function addMember() {
    const q = addProfileQuery.trim()
    if (!q) return
    try {
      // Resolve profile by username via /api/profiles/lookup
      const lookup = await axios.post('/api/profiles/lookup', { username: q })
      if (lookup.data.status !== 'found') {
        alert('Profile not found. Use exact username — fuzzy match not enabled in this UI.')
        return
      }
      await axios.post(`/api/civilizations/${detail.id}/members`, {
        profile_id: lookup.data.profile.id,
        role: addRole,
      })
      setAddMemberOpen(false)
      setAddProfileQuery('')
      setAddRole('sub_admin')
      await openDetail(detail)
      await loadCivs()
    } catch (err) {
      alert('Failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  async function createCiv() {
    const tag = createDraft.tag.trim()
    const founder = createDraft.founder_username.trim()
    if (!tag || !founder) {
      alert('tag and founder username are required')
      return
    }
    try {
      const lookup = await axios.post('/api/profiles/lookup', { username: founder })
      if (lookup.data.status !== 'found') {
        alert('Founder profile not found. Create the profile first via the wizard, then come back here.')
        return
      }
      await axios.post('/api/civilizations', {
        tag,
        display_name: createDraft.display_name.trim() || tag,
        region_color: createDraft.region_color,
        founder_profile_id: lookup.data.profile.id,
        enabled_features_default: createDraft.enabled_features_default,
      })
      setCreateOpen(false)
      setCreateDraft({ tag: '', display_name: '', region_color: '#00C2B3',
                       founder_username: '', enabled_features_default: [...DEFAULT_SUB_ADMIN_FEATURES] })
      await loadCivs()
    } catch (err) {
      alert('Failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  async function toggleArchive(civ) {
    setArchiving(true)
    try {
      await axios.put(`/api/civilizations/${civ.id}`, { is_active: !civ.is_active })
      setArchiveTarget(null)
      // If we're in the detail modal for the same civ, refresh it
      if (detail && detail.id === civ.id) {
        await openDetail({ ...civ, is_active: !civ.is_active })
      }
      await loadCivs()
    } catch (err) {
      alert('Failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setArchiving(false)
    }
  }

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase()
    const filtered = q
      ? civs.filter(c =>
          c.tag.toLowerCase().includes(q) ||
          c.display_name.toLowerCase().includes(q)
        )
      : civs
    return {
      active: filtered.filter(c => c.is_active),
      archived: filtered.filter(c => !c.is_active),
    }
  }, [civs, search])

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold">Civilization Management</h1>
          <p className="opacity-70 text-sm">
            Manage civilizations and their member rosters. Each civilization can have
            multiple leaders, co-leaders, and sub-admins — all with identical
            scoping perms within their civ.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>+ Found new civilization</Button>
      </div>

      <div className="mb-4">
        <input
          type="text"
          placeholder="Search by tag or display name..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="haven-input w-full px-3 py-2"
        />
      </div>

      {loading && <div className="opacity-60">Loading…</div>}
      {!loading && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {visible.active.map(civ => (
              <CivCard key={civ.id} civ={civ} onClick={() => openDetail(civ)} />
            ))}
            {visible.active.length === 0 && visible.archived.length === 0 && (
              <div className="opacity-60 col-span-full">No civilizations match.</div>
            )}
          </div>

          {visible.archived.length > 0 && (
            <div className="mt-8">
              <h2 className="text-lg font-semibold opacity-60 mb-3 flex items-center gap-2">
                <span>Archived Civilizations</span>
                <span className="text-xs font-normal px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: 'rgba(239,68,68,0.15)', color: '#ef4444' }}>
                  {visible.archived.length}
                </span>
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {visible.archived.map(civ => (
                  <CivCard key={civ.id} civ={civ} onClick={() => openDetail(civ)} />
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Detail modal */}
      {detail && (
        <Modal
          title={editMode ? `Editing ${detail.display_name}` : detail.display_name}
          onClose={() => { setDetail(null); setEditMode(false) }}
        >
          <div className="space-y-4">
            {/* Brand panel */}
            <div className="border-b pb-3" style={{ borderColor: 'var(--border-soft)' }}>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold">Brand</h4>
                {!editMode ? (
                  <Button variant="ghost" onClick={() => setEditMode(true)}>Edit</Button>
                ) : (
                  <div className="flex gap-2">
                    <Button variant="ghost" onClick={() => setEditMode(false)}>Cancel</Button>
                    <Button onClick={saveBrand}>Save</Button>
                  </div>
                )}
              </div>
              {!editMode ? (
                <div className="text-sm space-y-1">
                  <p><strong>Tag:</strong> <code>{detail.tag}</code></p>
                  <p><strong>Display:</strong> {detail.display_name}</p>
                  <p className="flex items-center gap-2">
                    <strong>Color:</strong>
                    <span className="inline-block w-4 h-4 rounded" style={{ backgroundColor: detail.region_color || '#666' }} />
                    <code>{detail.region_color || '—'}</code>
                  </p>
                  <p><strong>Default features:</strong> {(detail.enabled_features_default || []).join(', ') || '—'}</p>
                  <div className="flex items-center gap-3 mt-2">
                    <strong>Status:</strong>
                    {detail.is_active ? (
                      <>
                        <span className="text-xs px-2 py-0.5 rounded-full"
                              style={{ backgroundColor: 'rgba(0,194,179,0.15)', color: '#00C2B3' }}>
                          Active
                        </span>
                        <button
                          className="text-xs px-2 py-1 rounded border cursor-pointer"
                          style={{ borderColor: '#ef4444', color: '#ef4444', background: 'transparent' }}
                          onClick={() => setArchiveTarget(detail)}
                        >
                          Archive Civilization
                        </button>
                      </>
                    ) : (
                      <>
                        <span className="text-xs px-2 py-0.5 rounded-full"
                              style={{ backgroundColor: 'rgba(239,68,68,0.15)', color: '#ef4444' }}>
                          Archived
                        </span>
                        <button
                          className="text-xs px-2 py-1 rounded border cursor-pointer"
                          style={{ borderColor: '#00C2B3', color: '#00C2B3', background: 'transparent' }}
                          onClick={() => setArchiveTarget(detail)}
                        >
                          Unarchive Civilization
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-sm space-y-2">
                  <label className="block">
                    <span className="opacity-70">Display name</span>
                    <input
                      type="text"
                      className="haven-input w-full mt-0.5 px-2 py-1"
                      value={editDraft.display_name}
                      onChange={e => setEditDraft(d => ({ ...d, display_name: e.target.value }))}
                    />
                  </label>
                  <label className="block">
                    <span className="opacity-70">Region color</span>
                    <input
                      type="color"
                      className="ml-2 align-middle"
                      value={editDraft.region_color}
                      onChange={e => setEditDraft(d => ({ ...d, region_color: e.target.value }))}
                    />
                    <code className="ml-2 text-xs">{editDraft.region_color}</code>
                  </label>
                  <div>
                    <span className="opacity-70 text-xs">Default features for sub-admins (leaders &amp; co-leaders always get full access; War Room applies to ALL moderators of this civ):</span>
                    <div className="grid grid-cols-2 gap-1 mt-1">
                      {FEATURE_DEFAULTS.map(f => (
                        <label key={f.id} className="flex items-center gap-1 text-xs">
                          <input
                            type="checkbox"
                            checked={editDraft.enabled_features_default.includes(f.id)}
                            onChange={() => {
                              const set = new Set(editDraft.enabled_features_default)
                              set.has(f.id) ? set.delete(f.id) : set.add(f.id)
                              setEditDraft(d => ({ ...d, enabled_features_default: [...set] }))
                            }}
                          />
                          {f.label}
                        </label>
                      ))}
                    </div>
                  </div>
                  {/* is_active is now controlled via the Archive/Unarchive buttons below,
                      not through the edit form — too impactful for an unceremonious checkbox */}
                </div>
              )}
            </div>

            {/* Members panel */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold">
                  Members{' '}
                  <span className="opacity-60 text-xs">
                    ({detail.members?.length || 0} total)
                  </span>
                </h4>
                <Button variant="ghost" onClick={() => setAddMemberOpen(true)}>+ Add member</Button>
              </div>

              {detailLoading && <div className="opacity-60 text-sm">Loading members…</div>}

              {detail.members?.length === 0 && !detailLoading && (
                <div className="opacity-60 text-sm">No members yet.</div>
              )}

              <div className="space-y-2">
                {(detail.members || []).map(m => (
                  <MemberRow
                    key={m.profile_id}
                    member={m}
                    civDefaults={detail.enabled_features_default || []}
                    onChangeRole={r => changeMemberRole(m.profile_id, r)}
                    onToggleCap={() => toggleMemberCap(m.profile_id, m.can_approve_personal_uploads)}
                    onSetFeatures={features => setMemberFeatures(m.profile_id, features)}
                    onRemove={() => removeMember(m.profile_id, m.username)}
                  />
                ))}
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* Add-member modal */}
      {addMemberOpen && (
        <Modal title="Add member" onClose={() => setAddMemberOpen(false)}>
          <div className="space-y-3">
            <label className="block text-sm">
              <span className="opacity-70">Exact username</span>
              <input
                type="text"
                className="haven-input w-full mt-1 px-2 py-1"
                value={addProfileQuery}
                onChange={e => setAddProfileQuery(e.target.value)}
                placeholder="username (case-insensitive)"
              />
            </label>
            <label className="block text-sm">
              <span className="opacity-70">Role</span>
              <select
                className="haven-input w-full mt-1 px-2 py-1"
                value={addRole}
                onChange={e => setAddRole(e.target.value)}
              >
                {ROLES.map(r => <option key={r.id} value={r.id}>{r.label} — {r.desc}</option>)}
              </select>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setAddMemberOpen(false)}>Cancel</Button>
              <Button onClick={addMember}>Add</Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Create-civ modal */}
      {createOpen && (
        <Modal title="Found new civilization" onClose={() => setCreateOpen(false)}>
          <div className="space-y-3">
            <label className="block text-sm">
              <span className="opacity-70">Tag (the discord_tag on every system, e.g. "GHUB"). Cannot be changed.</span>
              <input
                type="text"
                className="haven-input w-full mt-1 px-2 py-1"
                value={createDraft.tag}
                onChange={e => setCreateDraft(d => ({ ...d, tag: e.target.value }))}
              />
            </label>
            <label className="block text-sm">
              <span className="opacity-70">Display name</span>
              <input
                type="text"
                className="haven-input w-full mt-1 px-2 py-1"
                value={createDraft.display_name}
                onChange={e => setCreateDraft(d => ({ ...d, display_name: e.target.value }))}
                placeholder="(defaults to tag)"
              />
            </label>
            <label className="block text-sm">
              <span className="opacity-70">Region color</span>
              <input
                type="color"
                className="ml-2 align-middle"
                value={createDraft.region_color}
                onChange={e => setCreateDraft(d => ({ ...d, region_color: e.target.value }))}
              />
            </label>
            <label className="block text-sm">
              <span className="opacity-70">Founder username (must already have a profile)</span>
              <input
                type="text"
                className="haven-input w-full mt-1 px-2 py-1"
                value={createDraft.founder_username}
                onChange={e => setCreateDraft(d => ({ ...d, founder_username: e.target.value }))}
              />
            </label>
            <div>
              <span className="opacity-70 text-xs">Default features for sub-admins (leaders &amp; co-leaders always get full access; War Room applies to ALL moderators of this civ):</span>
              <div className="grid grid-cols-2 gap-1 mt-1">
                {FEATURE_DEFAULTS.map(f => (
                  <label key={f.id} className="flex items-center gap-1 text-xs">
                    <input
                      type="checkbox"
                      checked={createDraft.enabled_features_default.includes(f.id)}
                      onChange={() => {
                        const set = new Set(createDraft.enabled_features_default)
                        set.has(f.id) ? set.delete(f.id) : set.add(f.id)
                        setCreateDraft(d => ({ ...d, enabled_features_default: [...set] }))
                      }}
                    />
                    {f.label}
                  </label>
                ))}
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button onClick={createCiv}>Found</Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Archive / Unarchive confirmation modal */}
      {archiveTarget && (
        <Modal
          title={archiveTarget.is_active ? 'Archive Civilization' : 'Unarchive Civilization'}
          onClose={() => setArchiveTarget(null)}
        >
          <div className="space-y-4 text-sm">
            {archiveTarget.is_active ? (
              <>
                <p>
                  You are about to <strong>archive</strong> the civilization{' '}
                  <strong>{archiveTarget.display_name}</strong> ({archiveTarget.tag}).
                </p>
                <div className="p-3 rounded text-xs space-y-1"
                     style={{ backgroundColor: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)' }}>
                  <p><strong>This will:</strong></p>
                  <p>- Sever all member connections (members drop to basic access)</p>
                  <p>- Hide all systems, discoveries, and regions from public view</p>
                  <p>- Remove the civ from all dropdowns, stats, and the 3D map</p>
                  <p>- Region colors will no longer render on the map</p>
                  <p className="mt-2 opacity-80">
                    Members and data are preserved — this is reversible by unarchiving.
                  </p>
                </div>
              </>
            ) : (
              <>
                <p>
                  You are about to <strong>unarchive</strong> the civilization{' '}
                  <strong>{archiveTarget.display_name}</strong> ({archiveTarget.tag}).
                </p>
                <div className="p-3 rounded text-xs space-y-1"
                     style={{ backgroundColor: 'rgba(0,194,179,0.1)', border: '1px solid rgba(0,194,179,0.3)' }}>
                  <p><strong>This will:</strong></p>
                  <p>- Restore all member connections and recompute their permissions</p>
                  <p>- Make all systems, discoveries, and regions publicly visible again</p>
                  <p>- Re-add the civ to dropdowns, stats, and the 3D map</p>
                </div>
              </>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setArchiveTarget(null)} disabled={archiving}>
                Cancel
              </Button>
              <Button
                onClick={() => toggleArchive(archiveTarget)}
                disabled={archiving}
                style={archiveTarget.is_active
                  ? { backgroundColor: '#ef4444', borderColor: '#ef4444' }
                  : { backgroundColor: '#00C2B3', borderColor: '#00C2B3' }
                }
              >
                {archiving
                  ? 'Processing…'
                  : archiveTarget.is_active ? 'Archive' : 'Unarchive'
                }
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

function CivCard({ civ, onClick }) {
  return (
    <button
      onClick={onClick}
      className="haven-card haven-card-hover text-left p-4 w-full"
      style={{
        borderColor: civ.region_color || 'var(--border-card)',
        opacity: civ.is_active ? 1 : 0.55,
      }}
    >
      <div className="flex items-baseline justify-between mb-1">
        <span className="font-bold">{civ.tag}</span>
        <span
          className="inline-block w-3 h-3 rounded-full"
          style={{ backgroundColor: civ.region_color || 'var(--muted)' }}
        />
      </div>
      <div className="text-sm opacity-90 mb-3 truncate">{civ.display_name}</div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <Stat label="Members" value={civ.member_count} />
        <Stat label="Leaders" value={civ.leader_count} />
        <Stat label="Systems" value={civ.system_count} />
      </div>
      {!civ.is_active && (
        <div className="mt-2 text-[10px] uppercase tracking-wider"
             style={{ color: '#ef4444' }}>Archived</div>
      )}
    </button>
  )
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-base font-bold">{value ?? '—'}</div>
      <div className="text-[10px] uppercase opacity-60 tracking-wider">{label}</div>
    </div>
  )
}

function MemberRow({ member, civDefaults, onChangeRole, onToggleCap, onSetFeatures, onRemove }) {
  const isLeader = LEADER_ROLES.includes(member.role)
  // null/absent enabled_features means "inherit civ default"; an array means
  // this member has an explicit per-member override.
  const hasOverride = Array.isArray(member.enabled_features)
  const [expanded, setExpanded] = useState(false)
  const [draft, setDraft] = useState(
    () => new Set(hasOverride ? member.enabled_features : (civDefaults || []))
  )

  // Re-seed the draft after a save round-trips (member.enabled_features
  // changes via openDetail) or when the role flips the inheritance source.
  useEffect(() => {
    setDraft(new Set(hasOverride ? member.enabled_features : (civDefaults || [])))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [member.enabled_features, member.role])

  function toggle(id) {
    setDraft(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className="haven-card px-3 py-2 text-sm space-y-2">
      <div className="flex items-center gap-2">
        <div className="flex-1 min-w-0">
          <div className="font-medium truncate">{member.display_name || member.username}</div>
          <div className="text-xs opacity-60 truncate">
            {member.username}
            {member.last_login_at && ` · last login ${formatDate(member.last_login_at)}`}
          </div>
        </div>
        <select
          value={member.role}
          onChange={e => onChangeRole(e.target.value)}
          className="haven-input px-2 py-1 text-xs"
        >
          {ROLES.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
        </select>
        <label className="flex items-center gap-1 text-xs" title="Can approve personal-tagged uploads">
          <input
            type="checkbox"
            checked={!!member.can_approve_personal_uploads}
            onChange={onToggleCap}
          />
          <span className="opacity-70">Approve personal</span>
        </label>
        <button
          onClick={() => setExpanded(e => !e)}
          className="pill pill-muted pill-clickable"
          title="View / edit this member's permissions"
        >
          {expanded ? 'Hide perms' : 'Perms'}
        </button>
        <button
          onClick={onRemove}
          className="pill pill-red pill-clickable"
        >
          Remove
        </button>
      </div>

      {expanded && (
        <div className="border-t pt-2" style={{ borderColor: 'var(--border-soft)' }}>
          {isLeader ? (
            <div className="text-xs opacity-70">
              Full access — {member.role === 'co_leader' ? 'co-leader' : 'leader'} role grants every
              feature within the civ automatically. Demote to Sub-Admin to scope permissions.
            </div>
          ) : (
            <>
              <div className="text-xs opacity-70 mb-1">
                {hasOverride
                  ? 'Custom permissions (per-member override).'
                  : 'Inheriting the civ default permission set. Saving creates a per-member override.'}
              </div>
              <div className="grid grid-cols-2 gap-1">
                {/* War Room is civ-scoped (controlled by the civ's feature grid,
                    applied to all moderators) — not a per-member toggle, so it's
                    excluded here. */}
                {FEATURE_DEFAULTS.filter(f => f.id !== 'war_room').map(f => (
                  <label key={f.id} className="flex items-center gap-1 text-xs">
                    <input
                      type="checkbox"
                      checked={draft.has(f.id)}
                      onChange={() => toggle(f.id)}
                    />
                    {f.label}
                  </label>
                ))}
              </div>
              <div className="text-[11px] opacity-60 mt-1">
                War Room access is set at the civilization level (edit the civ &amp; check War Room), not per member.
              </div>
              <div className="flex gap-2 mt-2">
                <button
                  onClick={() => onSetFeatures([...draft].filter(x => x !== 'war_room'))}
                  className="pill pill-emerald pill-clickable"
                >
                  Save permissions
                </button>
                {hasOverride && (
                  <button
                    onClick={() => onSetFeatures(null)}
                    className="pill pill-muted pill-clickable"
                    title="Clear the override and inherit the civ default again"
                  >
                    Reset to civ default
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
