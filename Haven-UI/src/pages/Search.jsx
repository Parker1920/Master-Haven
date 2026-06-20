/**
 * Search — full categorized results page.
 *
 * Route: /search?q=...
 * Auth: Public
 *
 * Backs the "View all results →" link from SearchOverlay's popover. Hits
 * /api/search with a higher per-category limit (24) and presents each
 * category as a stand-alone section with its own "Load more" affordance via
 * `limit` query param. Single endpoint = single round-trip = simplest UX.
 *
 * Filters / scope are NOT applied here: this page is reached by a user who
 * explicitly wanted broader visibility (the popover already shows the
 * scope-narrowed view). If the user wants scoped search, they use the
 * popover inside the Systems browser. Keeps the routes intent-clear.
 */

import React, { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import axios from 'axios'
import { systemPath } from '../utils/systemUrl'

const SECTION_LIMIT = 24

export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const q = (searchParams.get('q') || '').trim()

  const [input, setInput] = useState(q)
  useEffect(() => { setInput(q) }, [q])

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (q.length < 2) {
      setData(null)
      return
    }
    setLoading(true)
    axios.get('/api/search', { params: { q, limit: SECTION_LIMIT } })
      .then((r) => setData(r.data || null))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [q])

  function handleSubmit(e) {
    e.preventDefault()
    const trimmed = (input || '').trim()
    if (!trimmed) return
    setSearchParams({ q: trimmed }, { replace: false })
  }

  const totals = data?.totals || {}
  const grandTotal = (totals.communities || 0) + (totals.regions || 0) + (totals.contributors || 0) + (totals.systems || 0)
  const parsedKind = data?.parsed_kind

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold" style={{ color: 'var(--app-text)' }}>Search</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
          Find systems, communities, members, and named regions — paste a glyph code or NMSPortals link to jump straight in.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="haven-card p-4">
        <label className="text-xs uppercase tracking-wider font-semibold" style={{ color: 'var(--muted)' }}>Query</label>
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            placeholder="e.g. ekimo, GHUB, Sea of Gidzenuf, 40593F006FAC, or a NMSPortals URL"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="haven-input flex-1 px-3 py-2.5 text-sm"
            autoFocus
          />
          <button type="submit" className="haven-btn-primary px-4 py-2.5 rounded-lg text-sm font-semibold">
            Search
          </button>
        </div>
        {parsedKind && parsedKind !== 'free' && (
          <p className="text-[11px] mt-2" style={{ color: 'var(--app-accent-2)' }}>
            Detected: {parsedKind === 'nmsportal' ? 'NMSPortals link — extracted the embedded glyph code' : parsedKind === 'glyph_full' ? 'full 12-char glyph code' : '11-char glyph suffix (the dedup key)'}
          </p>
        )}
      </form>

      {q.length < 2 ? (
        <div className="haven-card p-12 text-center" style={{ color: 'var(--muted)' }}>
          Type at least 2 characters to search.
        </div>
      ) : loading && !data ? (
        <div className="haven-card p-12 text-center" style={{ color: 'var(--muted)' }}>Searching…</div>
      ) : grandTotal === 0 ? (
        <div className="haven-card p-12 text-center" style={{ color: 'var(--muted)' }}>
          No matches for <span className="mono">{q}</span>
        </div>
      ) : (
        <>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>
            {grandTotal.toLocaleString()} total results
          </div>

          {(data.communities && data.communities.length > 0) && (
            <CommunitiesSection rows={data.communities} total={totals.communities} navigate={navigate} />
          )}
          {(data.regions && data.regions.length > 0) && (
            <RegionsSection rows={data.regions} total={totals.regions} />
          )}
          {(data.contributors && data.contributors.length > 0) && (
            <ContributorsSection rows={data.contributors} total={totals.contributors} navigate={navigate} q={q} />
          )}
          {(data.systems && data.systems.length > 0) && (
            <SystemsSection rows={data.systems} total={totals.systems} navigate={navigate} q={q} />
          )}
        </>
      )}
    </div>
  )
}

function SectionShell({ title, count, total, children, footer }) {
  return (
    <section className="haven-card overflow-hidden p-0">
      <header className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-soft)' }}>
        <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>{title}</h2>
        <span className="text-xs mono" style={{ color: 'var(--app-primary)' }}>
          {count}{total > count ? ` of ${total}` : ''}
        </span>
      </header>
      <div>{children}</div>
      {footer && <footer className="px-4 py-2" style={{ borderTop: '1px solid var(--border-soft)', background: 'rgba(0,0,0,0.15)' }}>{footer}</footer>}
    </section>
  )
}

function CommunitiesSection({ rows, total, navigate }) {
  return (
    <SectionShell title="🌐 Communities" count={rows.length} total={total}>
      <div className="divide-y" style={{ borderColor: 'var(--border-soft)' }}>
        {rows.map((c) => (
          <button
            key={c.tag}
            type="button"
            onClick={() => navigate(`/community-stats/${encodeURIComponent(c.tag)}`)}
            className="w-full px-4 py-3 saved-row text-left flex items-center justify-between gap-3"
            style={{ borderBottom: '1px solid var(--border-soft)' }}
          >
            <div className="min-w-0">
              <div className="text-base font-medium truncate">{c.display_name}</div>
              <div className="text-xs mono" style={{ color: 'var(--muted)' }}>
                {c.tag}{c.unregistered ? ' · unregistered' : ''}
              </div>
            </div>
            <span className="text-xs mono shrink-0" style={{ color: 'var(--muted)' }}>{(c.system_count || 0).toLocaleString()} systems</span>
          </button>
        ))}
      </div>
    </SectionShell>
  )
}

function RegionsSection({ rows, total }) {
  return (
    <SectionShell title="🗺️ Regions" count={rows.length} total={total}>
      <div className="divide-y" style={{ borderColor: 'var(--border-soft)' }}>
        {rows.map((r, i) => {
          const href = `/systems?reality=${encodeURIComponent(r.reality || 'Normal')}&galaxy=${encodeURIComponent(r.galaxy || 'Euclid')}&rx=${r.region_x}&ry=${r.region_y}&rz=${r.region_z}${r.custom_name ? `&rname=${encodeURIComponent(r.custom_name)}` : ''}`
          return (
            <Link
              key={`${r.region_x},${r.region_y},${r.region_z},${i}`}
              to={href}
              className="block px-4 py-3 saved-row"
              style={{ borderBottom: '1px solid var(--border-soft)' }}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-base font-medium truncate">{r.custom_name || '(unnamed)'}</div>
                  <div className="text-xs mono" style={{ color: 'var(--muted)' }}>
                    {r.galaxy || 'Euclid'} · {r.region_x},{r.region_y},{r.region_z}
                  </div>
                </div>
                <span className="text-xs mono shrink-0" style={{ color: 'var(--muted)' }}>{(r.system_count || 0).toLocaleString()} systems</span>
              </div>
            </Link>
          )
        })}
      </div>
    </SectionShell>
  )
}

function ContributorsSection({ rows, total, navigate, q }) {
  return (
    <SectionShell title="👤 Contributors" count={rows.length} total={total}>
      <div className="divide-y" style={{ borderColor: 'var(--border-soft)' }}>
        {rows.map((c, i) => (
          <button
            key={`${c.username}-${i}`}
            type="button"
            onClick={() => navigate(`/search?q=${encodeURIComponent(c.username || q)}`)}
            className="w-full px-4 py-3 saved-row text-left flex items-center justify-between gap-3"
            style={{ borderBottom: '1px solid var(--border-soft)' }}
            title="Re-search for this contributor's name"
          >
            <div className="min-w-0">
              <div className="text-base font-medium truncate">{c.username || '—'}</div>
              <div className="text-xs mono" style={{ color: 'var(--muted)' }}>
                {c.source === 'anonymous' ? 'unregistered' : 'registered profile'}
              </div>
            </div>
            <span className="text-xs mono shrink-0" style={{ color: 'var(--muted)' }}>{(c.system_count || 0).toLocaleString()} systems</span>
          </button>
        ))}
      </div>
    </SectionShell>
  )
}

function SystemsSection({ rows, total, navigate }) {
  const footer = total > rows.length ? (
    <div className="text-xs" style={{ color: 'var(--muted)' }}>
      Showing first {rows.length} of {total.toLocaleString()}. Narrow with filters in the <Link to="/systems" className="font-medium" style={{ color: 'var(--app-primary)' }}>Systems browser</Link>.
    </div>
  ) : null
  return (
    <SectionShell title="⭐ Systems" count={rows.length} total={total} footer={footer}>
      <div className="divide-y" style={{ borderColor: 'var(--border-soft)' }}>
        {rows.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => navigate(systemPath(s))}
            className="w-full px-4 py-3 saved-row text-left flex items-center justify-between gap-3"
            style={{ borderBottom: '1px solid var(--border-soft)' }}
          >
            <div className="min-w-0">
              <div className="text-base font-medium truncate">{s.name}</div>
              <div className="text-xs mono truncate" style={{ color: 'var(--muted)' }}>
                {s.glyph_code || `(${s.region_x}, ${s.region_y}, ${s.region_z})`}
                {s.galaxy ? ` · ${s.galaxy}` : ''}
                {s.region_name ? ` · ${s.region_name}` : ''}
                {s.match_reason && s.match_reason.kind !== 'glyph' && (
                  <span className="ml-1.5" style={{ color: 'var(--app-accent-2)' }}>
                    · matched on {s.match_reason.kind}: {s.match_reason.snippet}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {s.discord_tag && s.discord_tag !== 'personal' && (
                <span className="pill pill-purple text-[10px]">{s.discord_tag}</span>
              )}
              {s.star_type && (
                <span className={`pill pill-star-${(s.star_type || '').toLowerCase()} text-[10px]`}>{s.star_type}</span>
              )}
              {s.completeness_grade && (
                <span className="text-[10px] mono px-1.5 py-0.5 rounded" style={{ background: 'rgba(255,255,255,0.08)' }}>{s.completeness_grade}</span>
              )}
            </div>
          </button>
        ))}
      </div>
    </SectionShell>
  )
}
