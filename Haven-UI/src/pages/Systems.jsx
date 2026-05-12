/**
 * Systems Browser — v2.0 orchestrator.
 *
 * Route: /systems
 * Auth: Public
 *
 * Mounts the v2.0 chrome (URL bar, unified search/filter card, breadcrumbs)
 * and one of four level grids based on the current hierarchy selection.
 * System Detail (Level 5) is a separate route (Phase 5).
 *
 * Shared state (hierarchy, scope, filters, history, dropdowns, recently-
 * viewed) lives in SystemsContext so chrome and level components don't have
 * to prop-drill through this orchestrator.
 */

import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { SystemsProvider, useSystems } from '../contexts/SystemsContext'
import useFilters from '../hooks/useFilters'
import URLBar from '../components/URLBar'
import SearchOverlay from '../components/SearchOverlay'
import FilterPillsRow from '../components/FilterPillsRow'
import BreadcrumbBar from '../components/BreadcrumbBar'
import SavedSearchesDropdown from '../components/SavedSearchesDropdown'
import RecentlyViewedDropdown from '../components/RecentlyViewedDropdown'
import RealitySelector from '../components/RealitySelector'
import GalaxyGrid from '../components/GalaxyGrid'
import RegionBrowser from '../components/RegionBrowser'
import SystemsList from '../components/SystemsList'
import FilterModal from '../components/FilterModal'
import CompareBar from '../components/CompareBar'
import ComparePanel from '../components/ComparePanel'

export default function Systems() {
  return (
    <SystemsProvider>
      <SystemsBrowser />
    </SystemsProvider>
  )
}

function SystemsBrowser() {
  const { level } = useSystems()
  const { activeFilterCount } = useFilters()
  const [filterOpen, setFilterOpen] = useState(false)
  const [comparePanelOpen, setComparePanelOpen] = useState(false)

  return (
    <div className="space-y-4">
      <URLBar />

      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold" style={{ color: 'var(--app-text)' }}>
            Systems Browser
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
            Drill from realities to individual star systems
          </p>
        </div>
        <Link
          to="/wizard"
          className="px-4 py-2 rounded-lg flex items-center gap-2 text-sm haven-btn-primary"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          New System
        </Link>
      </div>

      <div className="haven-card p-3 sm:p-4 space-y-3">
        <div className="flex flex-col lg:flex-row lg:items-start gap-2">
          <div className="flex-1 min-w-0">
            <SearchOverlay />
          </div>

          <div className="flex flex-col sm:flex-row gap-2 lg:items-center">
            <SavedSearchesDropdown />
            <RecentlyViewedDropdown />
            <FiltersButton activeCount={activeFilterCount} onClick={() => setFilterOpen(true)} />
          </div>
        </div>

        <FilterPillsRow />
      </div>

      <BreadcrumbBar />

      <div className="min-h-[400px]">
        {level === 'reality' && <RealitySelector />}
        {level === 'galaxy' && <GalaxyGrid />}
        {level === 'region' && <RegionBrowser />}
        {level === 'system' && <SystemsList />}
      </div>

      <FilterModal open={filterOpen} onClose={() => setFilterOpen(false)} />
      <CompareBar onOpen={() => setComparePanelOpen(true)} />
      <ComparePanel open={comparePanelOpen} onClose={() => setComparePanelOpen(false)} />
    </div>
  )
}

function FiltersButton({ activeCount, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full lg:w-auto px-3 py-2.5 rounded-lg text-sm font-medium flex items-center justify-center gap-2"
      style={{
        background: 'var(--app-primary-dim)',
        color: 'var(--app-primary)',
        border: '1px solid rgba(0, 194, 179, 0.3)',
      }}
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
        />
      </svg>
      Filters
      {activeCount > 0 && (
        <span
          className="mono text-[10px] px-1.5 py-0.5 rounded-full font-bold"
          style={{ background: 'var(--app-primary)', color: '#042422' }}
        >
          {activeCount}
        </span>
      )}
    </button>
  )
}
