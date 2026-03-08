// API client helpers for Haven backend. All requests use same-origin credentials (session cookie).

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
