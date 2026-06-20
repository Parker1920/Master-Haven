import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import GlyphDisplay from '../components/GlyphDisplay'
import { resolveGlyphByName } from '../utils/api'
import { GALAXIES } from '../data/galaxies'

// Find Glyph by Name — the inverse of the namegen. You know a system by name
// (from a spreadsheet, a Discord post, the site) and want the portal glyphs to
// travel there in-game. Calls GET /api/glyph/resolve, which resolves the name
// against Haven's uploaded systems server-side (instant, no public-API hop).

const STAR_PILL = {
  yellow: 'pill-star-yellow', blue: 'pill-star-blue', red: 'pill-star-red',
  green: 'pill-star-green', purple: 'pill-star-purple',
}

function starPill(starType) {
  if (!starType) return null
  const key = String(starType).toLowerCase()
  const cls = STAR_PILL[key]
  if (!cls) return null
  return <span className={`pill ${cls}`}>{starType}</span>
}

function gradeClass(grade) {
  if (!grade) return 'grade-c'
  if (grade === 'S+') return 'grade-splus'
  return `grade-${grade.toLowerCase()}`
}

const CONFIDENCE = {
  high: { cls: 'pill-emerald', label: 'High confidence — one exact match' },
  medium: { cls: 'pill-amber', label: 'Several systems share this name — pick the right one below' },
  low: { cls: 'pill-amber', label: 'Many systems share this name — narrow it with a galaxy' },
}

function GlyphCard({ c, onCopy, copied }) {
  return (
    <div className="haven-card p-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="text-lg font-semibold" style={{ color: 'var(--app-text)' }}>{c.name}</div>
          <div className="text-sm muted flex items-center gap-2 flex-wrap mt-0.5">
            <span>{c.galaxy || 'Unknown galaxy'}</span>
            {c.reality && c.reality !== 'Normal' && <span className="pill pill-muted">{c.reality}</span>}
            {c.region_name && <span>· {c.region_name}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {starPill(c.star_type)}
          {c.completeness_grade && (
            <span className={`text-xl font-extrabold ${gradeClass(c.completeness_grade)}`} title="Completeness grade">
              {c.completeness_grade}
            </span>
          )}
        </div>
      </div>

      {/* The glyph art + copyable code — the whole point of the tool */}
      <div className="mt-3">
        <GlyphDisplay glyphCode={c.glyph_code} size="medium" />
      </div>
      <div className="mt-2 flex items-center gap-2 flex-wrap">
        <code className="font-mono text-sm px-2 py-1 rounded bg-gray-800 tracking-wider" style={{ color: 'var(--app-text)' }}>
          {c.glyph_code}
        </code>
        <button className="haven-btn-ghost text-sm" onClick={() => onCopy(c.glyph_code)}>
          {copied === c.glyph_code ? '✓ Copied' : 'Copy code'}
        </button>
      </div>

      <div className="mt-3 flex items-center justify-between gap-3 flex-wrap text-xs muted">
        <span>
          SSI {c.ssi} · region {c.region_x},{c.region_y},{c.region_z}
          {c.discovered_by ? ` · by ${c.discovered_by}` : ''}
        </span>
        {c.id != null && (
          <Link to={`/systems/${c.id}`} className="haven-btn-ghost text-sm">View system →</Link>
        )}
      </div>
    </div>
  )
}

export default function GlyphFinder() {
  const [name, setName] = useState('')
  const [galaxy, setGalaxy] = useState('')
  const [reality, setReality] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [copied, setCopied] = useState(null)

  const search = async (e) => {
    if (e) e.preventDefault()
    const q = name.trim()
    if (q.length < 2) {
      setError('Enter at least 2 characters of a system name.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await resolveGlyphByName(q, {
        galaxy: galaxy || undefined,
        reality: reality || undefined,
      })
      setResult(data)
      if (data.error) setError(data.error)
    } catch (err) {
      setError('Lookup failed. Please try again.')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const copyCode = async (code) => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(code)
      setTimeout(() => setCopied(null), 1500)
    } catch {
      window.prompt('Copy this glyph code:', code)
    }
  }

  const conf = result && CONFIDENCE[result.confidence]

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--app-text)' }}>Find Glyph by Name</h1>
      <p className="muted mb-5">
        Know a system by name but need the portal address? Type the name and get its
        12-glyph portal code — resolved from every system uploaded to Haven.
      </p>

      <form onSubmit={search} className="haven-card p-4 mb-5">
        <label className="block text-sm muted mb-1">System name</label>
        <input
          className="haven-input w-full"
          placeholder="e.g. Cuomul-Ake"
          value={name}
          onChange={e => setName(e.target.value)}
          autoFocus
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
          <div>
            <label className="block text-sm muted mb-1">Galaxy <span className="opacity-60">(optional — narrows repeats)</span></label>
            <select className="haven-input w-full" value={galaxy} onChange={e => setGalaxy(e.target.value)}>
              <option value="">Any galaxy</option>
              {GALAXIES.map(g => <option key={g.index} value={g.name}>{g.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm muted mb-1">Reality <span className="opacity-60">(optional)</span></label>
            <select className="haven-input w-full" value={reality} onChange={e => setReality(e.target.value)}>
              <option value="">Any</option>
              <option value="Normal">Normal</option>
              <option value="Permadeath">Permadeath</option>
            </select>
          </div>
        </div>
        <button type="submit" className="haven-btn-primary mt-4" disabled={loading}>
          {loading ? 'Searching…' : 'Find glyph'}
        </button>
      </form>

      {error && (
        <div className="haven-card p-3 mb-4" style={{ borderColor: 'var(--app-accent-amber)' }}>
          <span style={{ color: 'var(--app-accent-amber)' }}>{error}</span>
        </div>
      )}

      {result && !loading && (
        <div>
          {result.count > 0 ? (
            <>
              <div className="flex items-center gap-2 mb-3 flex-wrap">
                {conf && <span className={`pill ${conf.cls}`}>{conf.label}</span>}
                <span className="muted text-sm">
                  {result.count} {result.count === 1 ? 'match' : 'matches'} for “{result.query}”
                  {result.galaxy ? ` in ${result.galaxy}` : ''}
                </span>
              </div>
              <div className="space-y-3">
                {result.candidates.map(c => (
                  <GlyphCard key={c.id ?? c.glyph_code} c={c} onCopy={copyCode} copied={copied} />
                ))}
              </div>
            </>
          ) : (
            <div className="haven-card p-4">
              <div className="font-semibold mb-1" style={{ color: 'var(--app-text)' }}>
                No exact match for “{result.query}”{result.galaxy ? ` in ${result.galaxy}` : ''}.
              </div>
              {result.suggestions && result.suggestions.length > 0 ? (
                <>
                  <p className="muted text-sm mb-3">Did you mean one of these?</p>
                  <div className="space-y-2">
                    {result.suggestions.map(s => (
                      <Link
                        key={s.id ?? s.glyph_code}
                        to={`/systems/${s.id}`}
                        className="haven-card haven-card-hover p-3 flex items-center justify-between gap-3"
                      >
                        <div>
                          <div className="font-medium" style={{ color: 'var(--app-text)' }}>{s.name}</div>
                          <div className="text-xs muted">{s.galaxy}{s.region_name ? ` · ${s.region_name}` : ''}</div>
                        </div>
                        <code className="font-mono text-xs px-2 py-1 rounded bg-gray-800 tracking-wider whitespace-nowrap">{s.glyph_code}</code>
                      </Link>
                    ))}
                  </div>
                </>
              ) : (
                <p className="muted text-sm">
                  It may not be uploaded to Haven yet, or the spelling differs.
                  Try without a galaxy filter, or check the exact in-game name.
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {!result && !loading && (
        <div className="haven-card p-4 muted text-sm">
          <div className="mb-2" style={{ color: 'var(--app-text)' }}>How it works</div>
          This finds the portal glyph code for any star system that's been uploaded to Haven —
          by name. Procedurally-generated names repeat across the universe, so if a name turns up
          more than once you'll see every match with its galaxy and region to pick from. Add a
          galaxy to narrow it down.
        </div>
      )}
    </div>
  )
}
