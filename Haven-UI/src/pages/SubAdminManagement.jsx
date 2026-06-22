import React, { useEffect, useState, useContext, useMemo } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import Modal from '../components/Modal'
import { AuthContext } from '../utils/AuthContext'
import { formatDate } from '../hooks/useDateFormat'

/**
 * Sub-Admin Moderation
 * Route: /admin/sub-admins  (also mounted as the "Sub-Admins" tab in AccessControl)
 * Auth: Any admin (super admin, or a civ leader/co-leader)
 *
 * This page no longer CREATES accounts. Sub-admins are civilization_members
 * with role='sub_admin' on the new civ system (migration 1.80.0). The legacy
 * username+password sub_admin_accounts creation flow was retired — it wrote to
 * a dead-end table that login shadowed behind any same-named user_profile.
 *
 * What you can do here (the "moderation" surface Parker asked for):
 *   - See every sub-admin you can manage, grouped by civilization.
 *   - Add a sub-admin by elevating an EXISTING profile (username lookup).
 *   - Change each sub-admin's features (per-member override vs civ default).
 *   - Toggle "can approve personal uploads".
 *   - Revoke (remove) a sub-admin from a civ.
 *
 * All writes go through the canonical civ-member endpoints:
 *   GET    /api/sub_admins                                   (roster, repurposed)
 *   POST   /api/civilizations/{civ_id}/members               (elevate, role=sub_admin)
 *   PUT    /api/civilizations/{civ_id}/members/{profile_id}  (features / personal cap)
 *   DELETE /api/civilizations/{civ_id}/members/{profile_id}  (revoke)
 *
 * Adding leaders / co-leaders and editing civ brand still live on the
 * Civilization Management page (/admin/civilizations).
 */

// The partner-grade granular features a sub-admin can be granted per-member.
// Mirrors FEATURE_DEFAULTS in CivilizationManagement.jsx and LEADER_FEATURES on
// the backend. 'war_room' is intentionally ABSENT: it is civ-scoped (controlled
// by the civ's feature grid in Civilization Management, applied to ALL
// moderators), not a per-member grant. The backend strips war_room from any
// sub-admin override, so listing it here would be a no-op at best and a
// misleading toggle at worst.
const AVAILABLE_FEATURES = [
  { id: 'system_create', label: 'Create Systems' },
  { id: 'system_edit', label: 'Edit Systems' },
  { id: 'approvals', label: 'View Approvals' },
  { id: 'batch_approvals', label: 'Batch Approvals' },
  { id: 'stats', label: 'View Statistics' },
  { id: 'settings', label: 'Theme Settings' },
  { id: 'csv_import', label: 'CSV Import' },
]

// Roles whose holder can manage a civ's roster (add/edit/revoke sub-admins).
const LEADER_ROLES = ['leader', 'co_leader']

/** @param {Object} props @param {boolean} [props.embedded=false] Hides the page title row when mounted inside AccessControl. */
export default function SubAdminManagement({ embedded = false }) {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [subAdmins, setSubAdmins] = useState([])
  const [civs, setCivs] = useState([])          // civs the user can add sub-admins to
  const [loading, setLoading] = useState(true)
  const [actionInProgress, setActionInProgress] = useState(false)

  // Add-sub-admin modal
  const [addOpen, setAddOpen] = useState(false)
  const [addUsername, setAddUsername] = useState('')
  const [addCivId, setAddCivId] = useState('')
  const [addError, setAddError] = useState('')

  useEffect(() => {
    if (!auth.isAdmin) {
      alert('Admin access required')
      navigate('/systems')
      return
    }
    loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isAdmin, navigate])

  async function loadAll() {
    setLoading(true)
    try {
      const [roster, civList] = await Promise.all([
        axios.get('/api/sub_admins'),
        axios.get('/api/civilizations'),
      ])
      setSubAdmins(roster.data.sub_admins || [])
      // Only active civs are valid elevation targets.
      setCivs((civList.data.civilizations || []).filter(c => c.is_active))
    } catch (err) {
      alert('Failed to load sub-admins: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  async function reloadRoster() {
    try {
      const roster = await axios.get('/api/sub_admins')
      setSubAdmins(roster.data.sub_admins || [])
    } catch (err) {
      alert('Failed to refresh: ' + (err.response?.data?.detail || err.message))
    }
  }

  // ---- member edits (shared civ-member endpoints) ----
  async function saveFeatures(member, features) {
    setActionInProgress(true)
    // war_room is civ-scoped (set in Civilization Management), never a per-member
    // grant — strip it so it can't ride into a sub-admin override.
    const cleaned = Array.isArray(features) ? features.filter(f => f !== 'war_room') : features
    try {
      await axios.put(`/api/civilizations/${member.civ_id}/members/${member.profile_id}`, {
        enabled_features: cleaned, // array => override, null => inherit civ default
      })
      await reloadRoster()
    } catch (err) {
      alert('Failed to save permissions: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function toggleCap(member) {
    setActionInProgress(true)
    try {
      await axios.put(`/api/civilizations/${member.civ_id}/members/${member.profile_id}`, {
        can_approve_personal_uploads: !member.can_approve_personal_uploads,
      })
      await reloadRoster()
    } catch (err) {
      alert('Failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function revoke(member) {
    if (!confirm(`Revoke sub-admin for ${member.username} in ${member.civ_display_name}?\n\nTheir account stays — they just lose sub-admin powers for this civ.`)) {
      return
    }
    setActionInProgress(true)
    try {
      await axios.delete(`/api/civilizations/${member.civ_id}/members/${member.profile_id}`)
      await reloadRoster()
    } catch (err) {
      alert('Failed to revoke: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  // Civs the current user can actually elevate a sub-admin into. Super admin:
  // every active civ. Leader/co-leader: only the active civs they lead (the
  // backend 403s otherwise, so don't offer civs that will fail). Derived from
  // the session's civ memberships (role-based), not just "civs I belong to".
  const manageableCivs = useMemo(() => {
    if (auth.isSuperAdmin) return civs
    const ledIds = new Set(
      (auth.user?.civMemberships || [])
        .filter(m => LEADER_ROLES.includes(m.role))
        .map(m => m.civ_id)
    )
    return civs.filter(c => ledIds.has(c.id))
  }, [civs, auth.isSuperAdmin, auth.user])

  function openAdd() {
    setAddUsername('')
    setAddCivId(manageableCivs.length === 1 ? String(manageableCivs[0].id) : '')
    setAddError('')
    setAddOpen(true)
  }

  async function addSubAdmin() {
    const username = addUsername.trim()
    setAddError('')
    if (!username) { setAddError('Enter the exact username of an existing profile.'); return }
    if (!addCivId) { setAddError('Pick a civilization.'); return }

    setActionInProgress(true)
    try {
      // Require an EXISTING profile — no account creation here.
      const lookup = await axios.post('/api/profiles/lookup', { username })
      if (lookup.data.status !== 'found') {
        setAddError('No profile with that exact username. They must sign in / submit at least once first, then you can elevate them.')
        return
      }
      await axios.post(`/api/civilizations/${addCivId}/members`, {
        profile_id: lookup.data.profile.id,
        role: 'sub_admin',
      })
      setAddOpen(false)
      await reloadRoster()
    } catch (err) {
      setAddError(err.response?.data?.detail || err.message)
    } finally {
      setActionInProgress(false)
    }
  }

  // Group roster by civilization for display.
  const grouped = useMemo(() => {
    const map = new Map()
    for (const sa of subAdmins) {
      if (!map.has(sa.civ_id)) {
        map.set(sa.civ_id, { civ_id: sa.civ_id, civ_tag: sa.civ_tag, civ_display_name: sa.civ_display_name, members: [] })
      }
      map.get(sa.civ_id).members.push(sa)
    }
    return [...map.values()]
  }, [subAdmins])

  if (loading) {
    return (
      <div className={embedded ? '' : 'p-4'}>
        <Card><p style={{ color: 'var(--muted)' }}>Loading sub-admins…</p></Card>
      </div>
    )
  }

  return (
    <div className={embedded ? '' : 'p-4'}>
      <div className="flex justify-between items-start mb-4 gap-3 flex-wrap">
        {!embedded ? (
          <div>
            <h2 className="text-2xl font-bold">Sub-Admin Moderation</h2>
            {auth.isSuperAdmin ? (
              <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
                Manage who has sub-admin powers and what they can do. New sub-admins start
                with <strong>no permissions</strong> — grant them explicitly under
                "Edit perms" (or click "Reset to civ default" to apply your civ's standard set).
              </p>
            ) : (
              <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
                Add or remove your civilization's sub-admins. New sub-admins start with
                <strong> no permissions</strong> — a super admin grants what each one can do.
              </p>
            )}
          </div>
        ) : <div />}
        {manageableCivs.length > 0 && (
          <Button className="haven-btn-primary" onClick={openAdd}>+ Add Sub-Admin</Button>
        )}
      </div>

      <div className="haven-card p-3 mb-4 text-sm" style={{ borderColor: 'var(--app-accent-amber)' }}>
        Sub-admins are elevated from existing member profiles — there's no separate
        username/password to create here. To make someone a <strong>leader</strong> or
        <strong> co-leader</strong>, or to edit a civilization's brand, use{' '}
        <button
          className="underline"
          style={{ color: 'var(--app-primary)' }}
          onClick={() => navigate('/admin/civilizations')}
        >
          Civilization Management
        </button>.
      </div>

      {grouped.length === 0 ? (
        <div className="haven-card italic p-4" style={{ color: 'var(--muted)' }}>
          No sub-admins yet. Click <strong>+ Add Sub-Admin</strong> to elevate an existing
          member profile.
        </div>
      ) : (
        <div className="space-y-6">
          {grouped.map(group => (
            <div key={group.civ_id}>
              <div className="flex items-baseline gap-2 mb-2">
                <span className="font-bold">{group.civ_tag}</span>
                <span className="text-sm" style={{ color: 'var(--muted)' }}>{group.civ_display_name}</span>
                <span className="pill pill-muted">{group.members.length}</span>
              </div>
              <div className="space-y-2">
                {group.members.map(m => (
                  <SubAdminRow
                    key={`${m.civ_id}:${m.profile_id}`}
                    member={m}
                    busy={actionInProgress}
                    isSuperAdmin={auth.isSuperAdmin}
                    onSaveFeatures={features => saveFeatures(m, features)}
                    onToggleCap={() => toggleCap(m)}
                    onRevoke={() => revoke(m)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Sub-Admin modal */}
      {addOpen && (
        <Modal title="Add Sub-Admin" onClose={() => setAddOpen(false)}>
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--muted)' }}>
              Elevate an <strong>existing</strong> member profile to sub-admin. The person
              must already have a profile (they've submitted, or set a member password).
              They'll start with <strong>zero permissions</strong> — grant access afterward
              under "Edit perms".
            </p>
            <div>
              <label className="block text-sm font-semibold mb-1">Civilization *</label>
              <select
                className="haven-input w-full p-2"
                value={addCivId}
                onChange={e => setAddCivId(e.target.value)}
              >
                <option value="">— Select civilization —</option>
                {manageableCivs.map(c => (
                  <option key={c.id} value={c.id}>{c.tag} — {c.display_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold mb-1">Username *</label>
              <input
                type="text"
                className="haven-input w-full p-2"
                value={addUsername}
                onChange={e => setAddUsername(e.target.value)}
                placeholder="exact username (case-insensitive)"
                onKeyDown={e => { if (e.key === 'Enter') addSubAdmin() }}
              />
            </div>
            {addError && (
              <div className="haven-card p-2 text-sm" style={{ borderColor: 'var(--app-accent-amber)', color: 'var(--app-text)' }}>
                {addError}
              </div>
            )}
            <div className="flex space-x-2 pt-1">
              <Button className="haven-btn-primary" onClick={addSubAdmin} disabled={actionInProgress}>
                {actionInProgress ? 'Adding…' : 'Add Sub-Admin'}
              </Button>
              <Button className="haven-btn-ghost" onClick={() => setAddOpen(false)}>Cancel</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

function SubAdminRow({ member, busy, isSuperAdmin, onSaveFeatures, onToggleCap, onRevoke }) {
  // null override => inheriting the civ default; an array => per-member override.
  const hasOverride = Array.isArray(member.enabled_features_override)
  const [expanded, setExpanded] = useState(false)
  const [draft, setDraft] = useState(() => new Set(member.enabled_features || []))

  // Re-seed after a save round-trips (member.enabled_features changes).
  useEffect(() => {
    setDraft(new Set(member.enabled_features || []))
  }, [member.enabled_features, member.enabled_features_override])

  function toggle(id) {
    setDraft(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className={`haven-card p-3 text-sm space-y-2 ${member.is_active ? '' : 'opacity-70'}`}>
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold truncate">{member.display_name || member.username}</span>
            {!member.is_active && <span className="pill pill-red">PROFILE INACTIVE</span>}
          </div>
          <div className="text-xs truncate" style={{ color: 'var(--muted)' }}>
            {member.username}
            {member.last_login_at && ` · last login ${formatDate(member.last_login_at)}`}
          </div>
        </div>
        <label className="flex items-center gap-1 text-xs" title="Can approve personal-tagged (no-civ) uploads">
          <input
            type="checkbox"
            checked={!!member.can_approve_personal_uploads}
            onChange={onToggleCap}
            disabled={busy}
          />
          <span style={{ color: 'var(--muted)' }}>Approve personal</span>
        </label>
        {/* Editing a sub-admin's feature set is a permission change → super-admin-only.
            Civ leaders manage the roster (add / revoke + approve-personal), not perms,
            so the editor is hidden for them; the backend also rejects per-member
            feature writes from non-super-admins. */}
        {isSuperAdmin && (
          <button className="pill pill-muted pill-clickable" onClick={() => setExpanded(e => !e)}>
            {expanded ? 'Hide perms' : 'Edit perms'}
          </button>
        )}
        <button className="pill pill-red pill-clickable" onClick={onRevoke} disabled={busy}>
          Revoke
        </button>
      </div>

      {/* Compact feature summary when collapsed */}
      {!expanded && (
        <div className="flex flex-wrap gap-1">
          {(member.enabled_features || []).length === 0 ? (
            <span className="text-xs italic" style={{ color: 'var(--muted)' }}>No features enabled</span>
          ) : (
            (member.enabled_features || []).map(f => (
              <span key={f} className="pill pill-teal">{f}</span>
            ))
          )}
          {!hasOverride && (member.enabled_features || []).length > 0 && (
            <span className="text-xs italic" style={{ color: 'var(--muted)' }}>(civ default)</span>
          )}
        </div>
      )}

      {isSuperAdmin && expanded && (
        <div className="border-t pt-2" style={{ borderColor: 'var(--border-soft)' }}>
          <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>
            {hasOverride
              ? 'Custom permissions (per-member override).'
              : 'Inheriting the civ default permission set — saving creates a per-member override.'}
          </div>
          <div className="grid grid-cols-2 gap-1">
            {/* Only the civ's OWN features are offered — a sub-admin can't be
                granted a feature the civ itself wasn't given. */}
            {AVAILABLE_FEATURES.filter(f => (member.civ_default_features || []).includes(f.id)).map(f => (
              <label key={f.id} className="flex items-center gap-1 text-xs">
                <input type="checkbox" checked={draft.has(f.id)} onChange={() => toggle(f.id)} />
                {f.label}
              </label>
            ))}
            {(member.civ_default_features || []).length === 0 && (
              <span className="text-xs italic col-span-2" style={{ color: 'var(--muted)' }}>
                This civ has no grantable features yet — a super admin sets the civ's feature set first.
              </span>
            )}
          </div>
          <div className="text-[11px] mt-1" style={{ color: 'var(--muted)' }}>
            War Room access is set at the civilization level (Civilization Management → edit
            the civ &amp; check War Room) and applies to all moderators — it isn't a per-member toggle.
          </div>
          <div className="flex gap-2 mt-2">
            <button
              className="pill pill-emerald pill-clickable"
              onClick={() => onSaveFeatures([...draft].filter(x => (member.civ_default_features || []).includes(x)))}
              disabled={busy}
            >
              Save permissions
            </button>
            {hasOverride && (
              <button
                className="pill pill-muted pill-clickable"
                onClick={() => onSaveFeatures(null)}
                disabled={busy}
                title="Clear the override and inherit the civ default again"
              >
                Reset to civ default
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
