import React, { useState, useEffect, useContext, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import Card from '../components/Card'
import SearchableSelect from '../components/SearchableSelect'
import { AuthContext } from '../utils/AuthContext'
import { GALAXIES } from '../data/galaxies'
import { normalizeUsernameForUrl } from '../posters/_shared/identity'

const TIER_LABELS = { 1: 'Super Admin', 2: 'Partner', 3: 'Sub-Admin', 4: 'Member', 5: 'Member (Read-Only)' }
const TIER_COLORS = { 1: 'text-yellow-400', 2: 'text-blue-400', 3: 'text-teal-400', 4: 'text-green-400', 5: 'text-gray-400' }

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
    axios.get('/api/communities').then(r => setCommunities(r.data.communities || [])).catch(() => {})
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

  if (loading) return <div className="text-gray-400 text-center py-12">Loading profile...</div>
  if (!profile) return <div className="text-gray-400 text-center py-12">Not authenticated</div>

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
              <div className={`text-sm ${TIER_COLORS[profile.tier] || 'text-gray-400'}`}>
                {TIER_LABELS[profile.tier] || `Tier ${profile.tier}`}
              </div>
            </div>
            {profile.stats && (
              <div className="text-right text-sm text-gray-400">
                <div>{profile.stats.systems} systems</div>
                <div>{profile.stats.discoveries} discoveries</div>
              </div>
            )}
          </div>

          {/* Tier 5 promotion banner */}
          {isReadOnly && (
            <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-3">
              <div className="text-yellow-400 font-medium text-sm">Set a password to unlock profile editing</div>
              <div className="text-yellow-500/70 text-xs mt-1">
                With a password you can edit your display name, default community, reality, and galaxy preferences.
              </div>
              <button
                onClick={() => setShowSetPassword(true)}
                className="mt-2 px-3 py-1 bg-yellow-600 hover:bg-yellow-500 text-white text-sm rounded transition-colors"
              >
                Set Password
              </button>
            </div>
          )}

          {/* Profile details */}
          {editing ? (
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Display Name</label>
                <input
                  value={form.display_name}
                  onChange={e => setForm({ ...form, display_name: e.target.value })}
                  className="w-full p-2 bg-gray-700 rounded text-white"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Default Community</label>
                <select
                  value={form.default_civ_tag}
                  onChange={e => setForm({ ...form, default_civ_tag: e.target.value })}
                  className="w-full p-2 bg-gray-700 rounded text-white"
                >
                  <option value="">None</option>
                  {communities.map(c => (
                    <option key={c.tag} value={c.tag}>{c.name || c.tag}</option>
                  ))}
                  <option value="personal">Personal</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Default Reality</label>
                  <select
                    value={form.default_reality || ''}
                    onChange={e => setForm({ ...form, default_reality: e.target.value })}
                    className="w-full p-2 bg-gray-700 rounded text-white"
                  >
                    <option value="">Not set</option>
                    <option value="Normal">Normal</option>
                    <option value="Permadeath">Permadeath</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Default Galaxy</label>
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
                <button onClick={saveProfile} disabled={saving} className="btn">
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
                <button onClick={() => setEditing(false)} className="btn bg-gray-600">Cancel</button>
              </div>
            </div>
          ) : (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Display Name</span>
                <span>{profile.display_name || profile.username}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Default Community</span>
                <span>{profile.default_civ_tag || 'Not set'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Default Reality</span>
                <span className={!profile.default_reality ? 'text-gray-600' : ''}>{profile.default_reality || 'Not set'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Default Galaxy</span>
                <span className={!profile.default_galaxy ? 'text-gray-600' : ''}>{profile.default_galaxy || 'Not set'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Password</span>
                <span>{profile.has_password ? 'Set' : 'Not set'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Member Since</span>
                <span>{profile.created_at ? new Date(profile.created_at).toLocaleDateString() : 'Unknown'}</span>
              </div>
              <div className="flex gap-2 pt-2">
                {!isReadOnly && (
                  <button onClick={() => setEditing(true)} className="btn text-sm">Edit Profile</button>
                )}
                <button onClick={() => setShowSetPassword(true)} className="btn text-sm bg-gray-600">
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

        {/* Source tabs */}
        {totalSystems > 0 && (
          <div className="flex gap-1 mb-4 border-b border-gray-700 pb-2">
            <button
              onClick={() => handleSourceTab('all')}
              className={`px-3 py-1.5 text-sm rounded-t transition-colors ${
                sourceTab === 'all' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              All <span className="text-xs text-gray-500 ml-1">{totalSystems}</span>
            </button>
            <button
              onClick={() => handleSourceTab('manual')}
              className={`px-3 py-1.5 text-sm rounded-t transition-colors ${
                sourceTab === 'manual' ? 'bg-cyan-900/50 text-cyan-400' : 'text-gray-400 hover:text-cyan-400'
              }`}
            >
              Manual <span className="text-xs opacity-60 ml-1">{manualCount}</span>
            </button>
            <button
              onClick={() => handleSourceTab('haven_extractor')}
              className={`px-3 py-1.5 text-sm rounded-t transition-colors ${
                sourceTab === 'haven_extractor' ? 'bg-purple-900/50 text-purple-400' : 'text-gray-400 hover:text-purple-400'
              }`}
            >
              Extractor <span className="text-xs opacity-60 ml-1">{extractorCount}</span>
            </button>
          </div>
        )}

        {subsLoading ? (
          <div className="text-gray-400 text-sm">Loading...</div>
        ) : (
          <div className="space-y-4">
            {/* Pending submissions */}
            {submissions.pending.length > 0 && sourceTab === 'all' && (
              <div>
                <h3 className="text-sm font-medium text-yellow-400 mb-2">Pending Approval ({submissions.pending.length})</h3>
                <div className="space-y-1">
                  {submissions.pending.map(p => (
                    <div key={`p-${p.id}`} className="flex items-center justify-between py-1.5 px-2 bg-gray-800 rounded text-sm">
                      <div className="flex items-center gap-2">
                        <span className={`w-1.5 h-1.5 rounded-full ${p.source === 'haven_extractor' ? 'bg-purple-400' : 'bg-cyan-400'}`} />
                        <span className="text-white">{p.system_name}</span>
                        <span className="text-gray-500">{p.galaxy} / {p.reality}</span>
                      </div>
                      <span className="text-xs px-2 py-0.5 rounded bg-yellow-600/30 text-yellow-400">pending</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Approved systems */}
            {submissions.systems.length > 0 ? (
              <div>
                <h3 className="text-sm font-medium text-green-400 mb-2">
                  Approved Systems ({submissions.total})
                </h3>
                <div className="space-y-1">
                  {submissions.systems.map(s => (
                    <a
                      key={s.id}
                      href={`/haven-ui/systems/${s.id}`}
                      className="flex items-center justify-between py-1.5 px-2 bg-gray-800 hover:bg-gray-700 rounded text-sm transition-colors block"
                    >
                      <div className="flex items-center gap-2">
                        <span className={`w-1.5 h-1.5 rounded-full ${s.source === 'haven_extractor' ? 'bg-purple-400' : 'bg-cyan-400'}`}
                              title={s.source === 'haven_extractor' ? 'Haven Extractor' : 'Manual Upload'} />
                        <span className="text-white">{s.name}</span>
                        <span className="text-gray-500">{s.galaxy}</span>
                        {s.discord_tag && <span className="text-cyan-400 text-xs">{s.discord_tag}</span>}
                      </div>
                      {s.is_complete !== null && s.is_complete !== undefined && (
                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                          s.is_complete >= 85 ? 'bg-yellow-600/30 text-yellow-400' :
                          s.is_complete >= 65 ? 'bg-green-600/30 text-green-400' :
                          s.is_complete >= 40 ? 'bg-blue-600/30 text-blue-400' :
                          'bg-gray-600/30 text-gray-400'
                        }`}>{
                          s.is_complete >= 85 ? 'S' :
                          s.is_complete >= 65 ? 'A' :
                          s.is_complete >= 40 ? 'B' : 'C'
                        }</span>
                      )}
                    </a>
                  ))}
                </div>

                {/* Pagination */}
                {submissions.total_pages > 1 && (
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-700">
                    <button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="px-3 py-1 text-sm bg-gray-700 rounded disabled:opacity-30 hover:bg-gray-600 transition-colors"
                    >
                      Previous
                    </button>
                    <span className="text-sm text-gray-400">
                      Page {page} of {submissions.total_pages}
                    </span>
                    <button
                      onClick={() => setPage(p => Math.min(submissions.total_pages, p + 1))}
                      disabled={page >= submissions.total_pages}
                      className="px-3 py-1 text-sm bg-gray-700 rounded disabled:opacity-30 hover:bg-gray-600 transition-colors"
                    >
                      Next
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-gray-500 text-sm">
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
                <label className="block text-sm text-gray-400 mb-1">Current Password</label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={e => setCurrentPassword(e.target.value)}
                  className="w-full p-2 bg-gray-700 rounded text-white"
                />
              </div>
            )}
            <div>
              <label className="block text-sm text-gray-400 mb-1">New Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                placeholder="At least 4 characters"
                className="w-full p-2 bg-gray-700 rounded text-white"
              />
            </div>
            <div className="flex gap-2">
              <button onClick={handleSetPassword} disabled={pwSaving} className="btn">
                {pwSaving ? 'Saving...' : (profile.has_password ? 'Change Password' : 'Set Password')}
              </button>
              <button onClick={() => { setShowSetPassword(false); setPwMessage('') }} className="btn bg-gray-600">Cancel</button>
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
        <a href={liveUrl} target="_blank" rel="noopener noreferrer"
          className="text-xs text-cyan-400 hover:text-cyan-300">
          View live →
        </a>
      </div>

      {optOut ? (
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6 text-center">
          <div className="text-gray-400 text-sm">Your card is set to private.</div>
          <div className="text-gray-500 text-xs mt-1">Toggle below to make it public again.</div>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden flex justify-center">
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
          className="px-3 py-1.5 text-xs bg-cyan-600 hover:bg-cyan-700 text-white rounded transition"
        >
          {copied ? 'Link copied ✓' : 'Copy share link'}
        </button>
        <a
          href={pngUrl}
          download={`voyager-${slug}.png`}
          className="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 text-white rounded transition"
        >
          Download PNG
        </a>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 text-white rounded transition disabled:opacity-50"
        >
          {refreshing ? 'Refreshing…' : 'Refresh data'}
        </button>
        <label className="ml-auto flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
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
