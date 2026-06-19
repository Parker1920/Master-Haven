import React, { useState, useEffect, useContext, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import Card from '../components/Card'
import SearchableSelect from '../components/SearchableSelect'
import { AuthContext } from '../utils/AuthContext'
import { GALAXIES } from '../data/galaxies'
import { normalizeUsernameForUrl } from '../posters/_shared/identity'

const TIER_LABELS = { 1: 'Super Admin', 2: 'Partner', 3: 'Sub-Admin', 4: 'Member', 5: 'Member (Read-Only)' }
// 2.0 design contract: tier badges use .pill + variant per CLAUDE.md "Tier badge palette".
const TIER_PILL_VARIANTS = { 1: 'pill-emerald', 2: 'pill-blue', 3: 'pill-teal', 4: 'pill-purple', 5: 'pill-muted' }

export default function Profile() {
  const auth = useContext(AuthContext)
  const navigate = useNavigate()
  const { user, isReadOnly, refreshAuth } = auth
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [communities, setCommunities] = useState([])
  // Password
  const [showSetPassword, setShowSetPassword] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [pwSaving, setPwSaving] = useState(false)
  const [pwMessage, setPwMessage] = useState('')
  // Submissions
  const [submissions, setSubmissions] = useState({ systems: [], pending: [], total: 0, total_pages: 1, source_counts: {} })
  const [subsLoading, setSubsLoading] = useState(true)
  const [sourceTab, setSourceTab] = useState('all') // 'all', 'manual', 'haven_extractor'
  const [page, setPage] = useState(1)
  const perPage = 50

  useEffect(() => {
    if (!user) {
      navigate('/')
      return
    }
    fetchProfile()
    fetchSubmissions()
    // Use /api/discord_tags (canonical since v1.61) — it returns the same
    // shape as /api/communities but also includes the synthetic "Personal"
    // entry at the top, so the hardcoded `<option value="personal">` further
    // down doesn't need to fight a case mismatch with the v1.63.0 normalizer
    // ('personal'/'Personal'/NULL/empty all collapsed to one bucket).
    axios.get('/api/discord_tags')
      .then(r => setCommunities((r.data.tags || []).map(t => ({ tag: t.tag, name: t.name }))))
      .catch(() => {})
  }, [user])

  useEffect(() => {
    fetchSubmissions()
  }, [sourceTab, page])

  async function fetchProfile() {
    try {
      const r = await axios.get('/api/profiles/me', { params: { _t: Date.now() } })
      setProfile({ ...r.data })
      setForm({
        display_name: r.data.display_name || '',
        default_civ_tag: r.data.default_civ_tag || '',
        default_reality: r.data.default_reality || '',
        default_galaxy: r.data.default_galaxy || '',
      })
    } catch {
      // Not authenticated
    } finally {
      setLoading(false)
    }
  }

  async function fetchSubmissions() {
    setSubsLoading(true)
    try {
      const params = { page, per_page: perPage }
      if (sourceTab !== 'all') params.source = sourceTab
      const r = await axios.get('/api/profiles/me/submissions', { params })
      setSubmissions(r.data)
    } catch {
      // Silent
    } finally {
      setSubsLoading(false)
    }
  }

  async function saveProfile() {
    setSaving(true)
    try {
      await axios.put('/api/profiles/me', form)
      await fetchProfile()
      await refreshAuth()
      setEditing(false)
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  async function handleSetPassword() {
    if (newPassword.length < 4) {
      setPwMessage('Password must be at least 4 characters')
      return
    }
    setPwSaving(true)
    setPwMessage('')
    try {
      const body = { new_password: newPassword }
      if (profile?.has_password) {
        body.current_password = currentPassword
      }
      const r = await axios.post('/api/profiles/me/set-password', body)
      setPwMessage(`Password ${profile?.has_password ? 'changed' : 'set'}! Your tier is now: ${TIER_LABELS[r.data.tier] || r.data.tier}`)
      setNewPassword('')
      setCurrentPassword('')
      setShowSetPassword(false)
      await fetchProfile()
      await refreshAuth()
    } catch (err) {
      setPwMessage(err.response?.data?.detail || 'Failed to set password')
    } finally {
      setPwSaving(false)
    }
  }

  function handleSourceTab(tab) {
    setSourceTab(tab)
    setPage(1)
  }

  if (loading) return <div className="muted text-center py-12">Loading profile...</div>
  if (!profile) return <div className="muted text-center py-12">Not authenticated</div>

  const manualCount = submissions.source_counts?.manual || 0
  const extractorCount = submissions.source_counts?.haven_extractor || 0
  const totalSystems = manualCount + extractorCount

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">My Profile</h1>

      <VoyagerCardSection profile={profile} onUpdate={fetchProfile} />

      <Card>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xl font-semibold">{profile.username}</div>
              <div className="mt-1">
                <span className={`pill ${TIER_PILL_VARIANTS[profile.tier] || 'pill-muted'}`}>
                  {TIER_LABELS[profile.tier] || `Tier ${profile.tier}`}
                </span>
              </div>
            </div>
            {profile.stats && (
              <div className="text-right text-sm muted">
                <div>{profile.stats.systems} systems</div>
                <div>{profile.stats.discoveries} discoveries</div>
              </div>
            )}
          </div>

          {/* Tier 5 promotion banner — canonical warning callout pattern */}
          {isReadOnly && (
            <div className="haven-card p-3" style={{ borderColor: 'var(--app-accent-amber)' }}>
              <div className="font-medium text-sm" style={{ color: 'var(--app-accent-amber)' }}>Set a password to unlock profile editing</div>
              <div className="text-xs mt-1 muted">
                With a password you can edit your display name, default community, reality, and galaxy preferences.
              </div>
              <button
                onClick={() => setShowSetPassword(true)}
                className="haven-btn-primary mt-2 text-sm"
              >
                Set Password
              </button>
            </div>
          )}

          {/* Profile details */}
          {editing ? (
            <div className="space-y-3">
              <div>
                <label className="block text-sm muted mb-1">Display Name</label>
                <input
                  value={form.display_name}
                  onChange={e => setForm({ ...form, display_name: e.target.value })}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm muted mb-1">Default Community</label>
                <select
                  value={form.default_civ_tag}
                  onChange={e => setForm({ ...form, default_civ_tag: e.target.value })}
                  className="w-full"
                >
                  {/* "Personal" comes from /api/discord_tags as the first
                      entry — no need for a hardcoded option (which had a
                      case mismatch with the v1.63 normalizer). */}
                  <option value="">None</option>
                  {communities.map(c => (
                    <option key={c.tag} value={c.tag}>{c.name || c.tag}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm muted mb-1">Default Reality</label>
                  <select
                    value={form.default_reality || ''}
                    onChange={e => setForm({ ...form, default_reality: e.target.value })}
                    className="w-full"
                  >
                    <option value="">Not set</option>
                    <option value="Normal">Normal</option>
                    <option value="Permadeath">Permadeath</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm muted mb-1">Default Galaxy</label>
                  <SearchableSelect
                    options={GALAXIES.map(g => ({ value: g.name, label: `${g.index}. ${g.name}` }))}
                    value={form.default_galaxy || ''}
                    onChange={val => setForm({ ...form, default_galaxy: val || '' })}
                    placeholder="Search galaxy..."
                    isClearable={false}
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={saveProfile} disabled={saving} className="haven-btn-primary">
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
                <button onClick={() => setEditing(false)} className="haven-btn-ghost">Cancel</button>
              </div>
            </div>
          ) : (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="muted">Display Name</span>
                <span>{profile.display_name || profile.username}</span>
              </div>
              <div className="flex justify-between">
                <span className="muted">Default Community</span>
                <span>{profile.default_civ_tag || 'Not set'}</span>
              </div>
              <div className="flex justify-between">
                <span className="muted">Default Reality</span>
                <span className={!profile.default_reality ? 'muted' : ''}>{profile.default_reality || 'Not set'}</span>
              </div>
              <div className="flex justify-between">
                <span className="muted">Default Galaxy</span>
                <span className={!profile.default_galaxy ? 'muted' : ''}>{profile.default_galaxy || 'Not set'}</span>
              </div>
              <div className="flex justify-between">
                <span className="muted">Password</span>
                <span>{profile.has_password ? 'Set' : 'Not set'}</span>
              </div>
              <div className="flex justify-between">
                <span className="muted">Member Since</span>
                <span>{profile.created_at ? new Date(profile.created_at).toLocaleDateString() : 'Unknown'}</span>
              </div>
              <div className="flex gap-2 pt-2">
                {!isReadOnly && (
                  <button onClick={() => setEditing(true)} className="haven-btn-primary text-sm">Edit Profile</button>
                )}
                <button onClick={() => setShowSetPassword(true)} className="haven-btn-ghost text-sm">
                  {profile.has_password ? 'Change Password' : 'Set Password'}
                </button>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* My Submissions */}
      <Card>
        <h2 className="text-lg font-semibold mb-3">My Submissions</h2>

        {/* Source tabs — token-driven; active tab gets primary/accent color */}
        {totalSystems > 0 && (
          <div className="flex gap-1 mb-4 pb-2" style={{ borderBottom: '1px solid var(--border-soft)' }}>
            <button
              onClick={() => handleSourceTab('all')}
              className="px-3 py-1.5 text-sm rounded-t transition-colors"
              style={
                sourceTab === 'all'
                  ? { background: 'var(--app-card)', color: 'var(--app-text)' }
                  : { color: 'var(--muted)' }
              }
            >
              All <span className="text-xs ml-1" style={{ color: 'var(--muted)' }}>{totalSystems}</span>
            </button>
            <button
              onClick={() => handleSourceTab('manual')}
              className="px-3 py-1.5 text-sm rounded-t transition-colors"
              style={
                sourceTab === 'manual'
                  ? { background: 'var(--app-card)', color: 'var(--app-primary)' }
                  : { color: 'var(--muted)' }
              }
            >
              Manual <span className="text-xs opacity-60 ml-1">{manualCount}</span>
            </button>
            <button
              onClick={() => handleSourceTab('haven_extractor')}
              className="px-3 py-1.5 text-sm rounded-t transition-colors"
              style={
                sourceTab === 'haven_extractor'
                  ? { background: 'var(--app-card)', color: 'var(--app-accent-2)' }
                  : { color: 'var(--muted)' }
              }
            >
              Extractor <span className="text-xs opacity-60 ml-1">{extractorCount}</span>
            </button>
          </div>
        )}

        {subsLoading ? (
          <div className="muted text-sm">Loading...</div>
        ) : (
          <div className="space-y-4">
            {/* Pending submissions */}
            {submissions.pending.length > 0 && sourceTab === 'all' && (
              <div>
                <h3 className="text-sm font-medium mb-2" style={{ color: 'var(--app-accent-amber)' }}>
                  Pending Approval ({submissions.pending.length})
                </h3>
                <div className="space-y-1">
                  {submissions.pending.map(p => (
                    <div key={`p-${p.id}`} className="haven-card flex items-center justify-between py-1.5 px-2 text-sm">
                      <div className="flex items-center gap-2">
                        <span
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ background: p.source === 'haven_extractor' ? 'var(--app-accent-2)' : 'var(--app-primary)' }}
                        />
                        <span>{p.system_name}</span>
                        <span className="muted">{p.galaxy} / {p.reality}</span>
                      </div>
                      <span className="pill pill-amber">pending</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Approved systems */}
            {submissions.systems.length > 0 ? (
              <div>
                <h3 className="text-sm font-medium mb-2" style={{ color: 'var(--app-primary)' }}>
                  Approved Systems ({submissions.total})
                </h3>
                <div className="space-y-1">
                  {submissions.systems.map(s => {
                    // Map completeness → grade letter + .grade-* utility class.
                    // S+ (fully charted) sits on top of S(85+); then A(65-84),
                    // B(40-64), C(0-39). Prefer the backend-computed
                    // completeness_grade (carries S+); fall back to the score
                    // ladder + is_fully_charted flag when only those are present.
                    const GRADE_CLASS = { 'S+': 'grade-splus', S: 'grade-s', A: 'grade-a', B: 'grade-b', C: 'grade-c' }
                    let gradeLetter = null
                    let gradeClass = ''
                    if (s.completeness_grade) {
                      gradeLetter = s.completeness_grade
                      gradeClass = GRADE_CLASS[s.completeness_grade] || 'grade-c'
                    } else if (s.is_complete !== null && s.is_complete !== undefined) {
                      if (s.is_complete >= 85 && s.is_fully_charted) { gradeLetter = 'S+'; gradeClass = 'grade-splus' }
                      else if (s.is_complete >= 85) { gradeLetter = 'S'; gradeClass = 'grade-s' }
                      else if (s.is_complete >= 65) { gradeLetter = 'A'; gradeClass = 'grade-a' }
                      else if (s.is_complete >= 40) { gradeLetter = 'B'; gradeClass = 'grade-b' }
                      else { gradeLetter = 'C'; gradeClass = 'grade-c' }
                    }
                    return (
                      <a
                        key={s.id}
                        href={`/haven-ui/systems/${encodeURIComponent(s.name)}`}
                        className="haven-card haven-card-hover flex items-center justify-between py-1.5 px-2 text-sm block"
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className="w-1.5 h-1.5 rounded-full"
                            style={{ background: s.source === 'haven_extractor' ? 'var(--app-accent-2)' : 'var(--app-primary)' }}
                            title={s.source === 'haven_extractor' ? 'Haven Extractor' : 'Manual Upload'}
                          />
                          <span>{s.name}</span>
                          <span className="muted">{s.galaxy}</span>
                          {s.discord_tag && (
                            <span className="text-xs" style={{ color: 'var(--app-primary)' }}>{s.discord_tag}</span>
                          )}
                        </div>
                        {gradeLetter && <span className={gradeClass}>{gradeLetter}</span>}
                      </a>
                    )
                  })}
                </div>

                {/* Pagination */}
                {submissions.total_pages > 1 && (
                  <div
                    className="flex items-center justify-between mt-3 pt-3"
                    style={{ borderTop: '1px solid var(--border-soft)' }}
                  >
                    <button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="haven-btn-ghost text-sm"
                    >
                      Previous
                    </button>
                    <span className="text-sm muted">
                      Page {page} of {submissions.total_pages}
                    </span>
                    <button
                      onClick={() => setPage(p => Math.min(submissions.total_pages, p + 1))}
                      disabled={page >= submissions.total_pages}
                      className="haven-btn-ghost text-sm"
                    >
                      Next
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="muted text-sm">
                {sourceTab !== 'all'
                  ? `No ${sourceTab === 'haven_extractor' ? 'extractor' : 'manual'} submissions yet.`
                  : 'No approved systems yet. Submit your first system from the Create page!'}
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Set/Change Password section */}
      {showSetPassword && (
        <Card>
          <h2 className="text-lg font-semibold mb-3">{profile.has_password ? 'Change Password' : 'Set Password'}</h2>
          <div className="space-y-3">
            {profile.has_password && (
              <div>
                <label className="block text-sm muted mb-1">Current Password</label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={e => setCurrentPassword(e.target.value)}
                  className="w-full"
                />
              </div>
            )}
            <div>
              <label className="block text-sm muted mb-1">New Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                placeholder="At least 4 characters"
                className="w-full"
              />
            </div>
            <div className="flex gap-2">
              <button onClick={handleSetPassword} disabled={pwSaving} className="haven-btn-primary">
                {pwSaving ? 'Saving...' : (profile.has_password ? 'Change Password' : 'Set Password')}
              </button>
              <button onClick={() => { setShowSetPassword(false); setPwMessage('') }} className="haven-btn-ghost">Cancel</button>
            </div>
            {pwMessage && (
              <div className={`text-sm ${pwMessage.includes('Failed') || pwMessage.includes('incorrect') ? 'text-red-400' : 'text-green-400'}`}>
                {pwMessage}
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  )
}

// ============================================================================
// VoyagerCardSection — embeds the user's own Voyager Card poster + actions.
// PNG is sourced from /api/posters/voyager/:username.png, kept fresh by
// event-driven invalidation in routes/approvals.py + 24h TTL on the cache.
// ============================================================================

function VoyagerCardSection({ profile, onUpdate }) {
  const slug = useMemo(
    () => normalizeUsernameForUrl(profile?.username || ''),
    [profile?.username]
  )
  const [imgKey, setImgKey] = useState(Date.now())
  const [refreshing, setRefreshing] = useState(false)
  const [copied, setCopied] = useState(false)
  const [optOut, setOptOut] = useState(profile?.poster_public === 0 || profile?.poster_public === false)
  const [savingOptOut, setSavingOptOut] = useState(false)

  // Sync opt-out state when profile reloads
  useEffect(() => {
    setOptOut(profile?.poster_public === 0 || profile?.poster_public === false)
  }, [profile?.poster_public])

  if (!slug) return null

  const pngUrl = `/api/posters/voyager/${encodeURIComponent(slug)}.png?v=${imgKey}`
  const liveUrl = `/haven-ui/voyager/${encodeURIComponent(slug)}`
  const shareUrl = `${window.location.origin}/voyager/${encodeURIComponent(slug)}`

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await axios.post(`/api/posters/voyager/${encodeURIComponent(slug)}/refresh`)
      // Bust browser cache by updating query string
      setImgKey(Date.now())
    } catch (err) {
      // Silent — refresh will happen on next TTL expire
    } finally {
      setRefreshing(false)
    }
  }

  function handleCopy() {
    const ok = (text) => {
      try { return navigator.clipboard?.writeText(text) } catch { return Promise.reject() }
    }
    Promise.resolve(ok(shareUrl))
      .then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800) })
      .catch(() => { window.prompt('Copy your share link:', shareUrl) })
  }

  async function handleOptOutToggle(e) {
    const newVal = e.target.checked  // checked = opted OUT (private)
    setOptOut(newVal)
    setSavingOptOut(true)
    try {
      await axios.put('/api/profiles/me', { poster_public: newVal ? 0 : 1 })
      if (onUpdate) await onUpdate()
      setImgKey(Date.now())
    } catch {
      setOptOut(!newVal)  // Revert on failure
    } finally {
      setSavingOptOut(false)
    }
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">Your Voyager Card</h2>
        <a
          href={liveUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs"
          style={{ color: 'var(--app-primary)' }}
        >
          View live →
        </a>
      </div>

      {optOut ? (
        <div className="haven-card p-6 text-center">
          <div className="muted text-sm">Your card is set to private.</div>
          <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
            Toggle below to make it public again.
          </div>
        </div>
      ) : (
        <div className="haven-card overflow-hidden flex justify-center p-0">
          <img
            src={pngUrl}
            alt={`${profile.username}'s Voyager Card`}
            style={{ maxWidth: '100%', display: 'block' }}
            loading="lazy"
          />
        </div>
      )}

      <div className="flex flex-wrap gap-2 mt-3 items-center">
        <button
          onClick={handleCopy}
          className="haven-btn-primary text-xs"
        >
          {copied ? 'Link copied ✓' : 'Copy share link'}
        </button>
        <a
          href={pngUrl}
          download={`voyager-${slug}.png`}
          className="haven-btn-ghost text-xs"
        >
          Download PNG
        </a>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="haven-btn-ghost text-xs"
        >
          {refreshing ? 'Refreshing…' : 'Refresh data'}
        </button>
        <label
          className="ml-auto flex items-center gap-2 text-xs cursor-pointer"
          style={{ color: 'var(--muted)' }}
        >
          <input
            type="checkbox"
            checked={optOut}
            onChange={handleOptOutToggle}
            disabled={savingOptOut}
            className="rounded"
          />
          Hide from public
        </label>
      </div>
    </Card>
  )
}
