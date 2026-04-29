// Frontend registry — mirrors backend services/poster_service.py REGISTRY.
//
// Drives PosterRoute.jsx: given a poster type, look up which component to mount
// at what viewport size. Adding a new poster type = one entry here + one
// component file + one registry entry on the backend. Nothing else.
//
// Components are lazy-loaded so only the requested poster ships its bundle.

import { lazy } from 'react'

const VoyagerPoster = lazy(() => import('./VoyagerPoster'))
const VoyagerOG = lazy(() => import('./VoyagerOG'))
const GalaxyAtlas = lazy(() => import('./GalaxyAtlas'))
const AtlasThumb = lazy(() => import('./AtlasThumb'))
const OGSiteCard = lazy(() => import('./OGSiteCard'))
const OGSystemCard = lazy(() => import('./OGSystemCard'))
const OGCommunityCard = lazy(() => import('./OGCommunityCard'))

export const POSTER_REGISTRY = {
  voyager: { component: VoyagerPoster, width: 680, height: 1040 },
  voyager_og: { component: VoyagerOG, width: 1200, height: 630 },
  atlas: { component: GalaxyAtlas, width: 680, height: 920 },
  atlas_thumb: { component: AtlasThumb, width: 400, height: 400 },
  og_site: { component: OGSiteCard, width: 1200, height: 630 },
  og_system: { component: OGSystemCard, width: 1200, height: 630 },
  og_community: { component: OGCommunityCard, width: 1200, height: 630 },
}

export function getPosterEntry(type) {
  return POSTER_REGISTRY[type] || null
}
