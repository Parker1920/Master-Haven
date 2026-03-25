// API client helpers for Haven backend. All requests use same-origin credentials (session cookie).
//
// Core helpers: apiGet, apiPost, apiPut, apiDelete
// Typed endpoints: grouped by feature domain for discoverability.
// Usage: import { getSystems, approvePendingSystem } from '../utils/api'

import axios from 'axios'

// ============================================================================
// Core Fetch Helpers
// ============================================================================

/** Fetch JSON from a GET endpoint. Throws on non-OK response. */
export async function apiGet(path){
  const res = await fetch(path, {method: 'GET', credentials: 'same-origin'})
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

/** POST JSON to an endpoint. Optional adminToken sent as X-HAVEN-ADMIN header. */
export async function apiPost(path, body, { adminToken } = {}){
  const headers = { 'Content-Type': 'application/json' }
  if(adminToken) headers['X-HAVEN-ADMIN'] = adminToken
  const res = await fetch(path, { method: 'POST', credentials: 'same-origin', headers, body: JSON.stringify(body) })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

/** PUT JSON to an endpoint. */
export async function apiPut(path, body){
  const res = await fetch(path, { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

/** DELETE an endpoint. */
export async function apiDelete(path){
  const res = await fetch(path, { method: 'DELETE', credentials: 'same-origin' })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

// ============================================================================
// Typed Endpoint Functions
// Each wraps a specific API call with consistent error handling.
// Pages can import these instead of using raw axios/fetch calls.
// ============================================================================

// --- Stats & Dashboard ---
export const getStats = () => axios.get('/api/stats').then(r => r.data)
export const getDailyChanges = () => axios.get('/api/stats/daily_changes').then(r => r.data)
export const getActivityLogs = (limit = 50) => axios.get(`/api/activity_logs?limit=${limit}`).then(r => r.data)
export const getRecentSystems = (limit = 10) => axios.get(`/api/systems/recent?limit=${limit}`).then(r => r.data)

// --- Systems ---
export const getSystems = (params = {}) => axios.get('/api/systems', { params }).then(r => r.data)
export const getSystemDetail = (id) => axios.get(`/api/systems/${id}`).then(r => r.data)
export const searchSystems = (q, params = {}) => axios.get('/api/systems/search', { params: { q, ...params } }).then(r => r.data)
export const getFilterOptions = (params = {}) => axios.get('/api/systems/filter-options', { params }).then(r => r.data)
export const saveSystem = (data) => axios.post('/api/save_system', data).then(r => r.data)
export const deleteSystem = (id) => axios.delete(`/api/systems/${id}`).then(r => r.data)

// --- Galaxies & Regions ---
export const getGalaxies = () => axios.get('/api/galaxies').then(r => r.data)
export const getGalaxySummary = (params = {}) => axios.get('/api/galaxies/summary', { params }).then(r => r.data)
export const getRealitiesSummary = () => axios.get('/api/realities/summary').then(r => r.data)
export const getRegionsGrouped = (params = {}) => axios.get('/api/regions/grouped', { params }).then(r => r.data)
export const getRegionDetail = (rx, ry, rz, params = {}) => axios.get(`/api/regions/${rx}/${ry}/${rz}`, { params }).then(r => r.data)

// --- Pending Systems (Approvals) ---
export const getPendingSystems = (params = {}) => axios.get('/api/pending_systems', { params }).then(r => r.data)
export const getPendingCount = () => axios.get('/api/pending_systems/count').then(r => r.data)
export const getPendingDetail = (id) => axios.get(`/api/pending_systems/${id}`).then(r => r.data)
export const approvePendingSystem = (id) => axios.post(`/api/approve_system/${id}`).then(r => r.data)
export const rejectPendingSystem = (id, data = {}) => axios.post(`/api/reject_system/${id}`, data).then(r => r.data)
export const batchApproveSystems = (ids) => axios.post('/api/approve_systems/batch', { submission_ids: ids }).then(r => r.data)
export const batchRejectSystems = (ids, reason) => axios.post('/api/reject_systems/batch', { submission_ids: ids, reason }).then(r => r.data)

// --- Discoveries ---
export const getDiscoveries = (params = {}) => axios.get('/api/discoveries/browse', { params }).then(r => r.data)
export const getDiscoveryTypes = () => axios.get('/api/discoveries/types').then(r => r.data)
export const getDiscoveryStats = () => axios.get('/api/discoveries/stats').then(r => r.data)
export const submitDiscovery = (data) => axios.post('/api/submit_discovery', data).then(r => r.data)

// --- Analytics ---
export const getSubmissionLeaderboard = (params = {}) => axios.get('/api/analytics/submission-leaderboard', { params }).then(r => r.data)
export const getCommunityStats = (params = {}) => axios.get('/api/analytics/community-stats', { params }).then(r => r.data)
export const getSubmissionsTimeline = (params = {}) => axios.get('/api/analytics/submissions-timeline', { params }).then(r => r.data)
export const getSourceBreakdown = () => axios.get('/api/analytics/source-breakdown').then(r => r.data)
export const getPartnerOverview = (params = {}) => axios.get('/api/analytics/partner-overview', { params }).then(r => r.data)

// --- Public Community Stats ---
export const getCommunityOverview = () => axios.get('/api/public/community-overview').then(r => r.data)
export const getContributors = (params = {}) => axios.get('/api/public/contributors', { params }).then(r => r.data)
export const getActivityTimeline = (params = {}) => axios.get('/api/public/activity-timeline', { params }).then(r => r.data)
export const getDiscoveryBreakdown = () => axios.get('/api/public/discovery-breakdown').then(r => r.data)
export const getCommunityRegions = (params = {}) => axios.get('/api/public/community-regions', { params }).then(r => r.data)

// --- Events ---
export const getEvents = () => axios.get('/api/events').then(r => r.data)
export const getEventDetail = (id) => axios.get(`/api/events/${id}`).then(r => r.data)
export const getEventLeaderboard = (id, params = {}) => axios.get(`/api/events/${id}/leaderboard`, { params }).then(r => r.data)

/** Authenticate with the super admin password. Returns session data. */
export async function adminLogin(password){
  const res = await fetch('/api/admin/login', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

/** End the current admin session. */
export async function adminLogout(){
  const res = await fetch('/api/admin/logout', { method: 'POST', credentials: 'same-origin' })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

/** Check current login state. Returns { logged_in, user_type, username, ... }. */
export async function adminStatus(){
  const res = await fetch('/api/admin/status', { method: 'GET', credentials: 'same-origin' })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

/** Upload a photo file. Returns { filename, thumbnail, original_size, compressed_size }. */
export async function uploadPhoto(file){
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch('/api/photos', { method: 'POST', credentials: 'same-origin', body: formData })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

/**
 * Get the full-size photo URL from a photo path/filename.
 * Handles backslash paths from legacy uploads (Windows-style DB entries),
 * relative paths, external HTTP URLs, and already-constructed /haven-ui-photos/ URLs.
 */
export function getPhotoUrl(photo) {
  if (!photo) return null
  if (photo.startsWith('http')) return photo
  if (photo.startsWith('/haven-ui-photos/') || photo.startsWith('/war-media/')) return photo
  const normalized = photo.replace(/\\/g, '/')
  const parts = normalized.split('/')
  const filename = parts[parts.length - 1]
  return `/haven-ui-photos/${encodeURIComponent(filename)}`
}

/**
 * Get the thumbnail URL for a photo (300px wide WebP).
 * Accepts raw paths (including backslash paths from legacy uploads),
 * already-constructed URLs, or external HTTP URLs.
 * For WebP files, swaps to *_thumb.webp.
 * For legacy files (jpg/png), falls back to the full image (no thumbnail exists).
 */
export function getThumbnailUrl(photo) {
  if (!photo) return null
  if (photo.startsWith('http')) return photo
  // Handle already-constructed URLs - swap .webp to _thumb.webp in place
  if (photo.startsWith('/haven-ui-photos/') || photo.startsWith('/war-media/')) {
    if (photo.endsWith('.webp') && !photo.endsWith('_thumb.webp')) {
      return photo.replace('.webp', '_thumb.webp')
    }
    return photo
  }
  // Raw path from database
  const normalized = photo.replace(/\\/g, '/')
  const parts = normalized.split('/')
  const filename = parts[parts.length - 1]
  if (filename.endsWith('.webp') && !filename.endsWith('_thumb.webp')) {
    const thumbName = filename.replace('.webp', '_thumb.webp')
    return `/haven-ui-photos/${encodeURIComponent(thumbName)}`
  }
  return `/haven-ui-photos/${encodeURIComponent(filename)}`
}
