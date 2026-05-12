/**
 * Lightbox — fullscreen photo viewer for System Detail.
 *
 * Per spec section 8.5:
 *   - Click outside the image area closes
 *   - Keyboard: ←/→ navigate, Esc closes
 *   - Counter pill in the top-left, close button top-right
 *   - Caption + uploader meta below the image
 *
 * Photos prop shape: [{ url, caption?, uploadedBy?, uploadedAt? }]
 */

import React, { useCallback, useEffect, useRef } from 'react'

export default function Lightbox({ photos, index, onClose, onChange }) {
  const safeIndex = Math.max(0, Math.min(index ?? 0, photos.length - 1))
  const photo = photos[safeIndex]
  // LOW-1: focus trap + return-focus-on-close. Capture the previously-
  // focused element on mount and restore on unmount; trap Tab inside the
  // dialog so keyboard users can't escape to the page underneath.
  const closeBtnRef = useRef(null)
  const containerRef = useRef(null)
  const returnFocusRef = useRef(null)

  const next = useCallback(() => {
    if (photos.length < 2) return
    onChange((safeIndex + 1) % photos.length)
  }, [photos.length, safeIndex, onChange])

  const prev = useCallback(() => {
    if (photos.length < 2) return
    onChange((safeIndex - 1 + photos.length) % photos.length)
  }, [photos.length, safeIndex, onChange])

  useEffect(() => {
    // Snapshot the element to return focus to on unmount.
    returnFocusRef.current = document.activeElement
    // Move focus into the dialog so keyboard users start here.
    closeBtnRef.current?.focus()
    return () => {
      try { returnFocusRef.current?.focus?.() } catch { /* ignore */ }
    }
  }, [])

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') { e.preventDefault(); onClose() }
      else if (e.key === 'ArrowRight') { e.preventDefault(); next() }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); prev() }
      else if (e.key === 'Tab') {
        // Trap Tab inside the dialog.
        const root = containerRef.current
        if (!root) return
        const focusables = root.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        if (!focusables.length) return
        const first = focusables[0]
        const last = focusables[focusables.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault(); last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault(); first.focus()
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, next, prev])

  if (!photo) return null

  return (
    <div
      ref={containerRef}
      onClick={onClose}
      className="fixed inset-0 z-[70] flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.9)' }}
      role="dialog"
      aria-modal="true"
      aria-label="Photo viewer"
    >
      <button
        ref={closeBtnRef}
        type="button"
        onClick={(e) => { e.stopPropagation(); onClose() }}
        className="absolute top-4 right-4 w-10 h-10 rounded-full flex items-center justify-center"
        style={{ background: 'rgba(0,0,0,0.6)', color: 'white', backdropFilter: 'blur(4px)' }}
        aria-label="Close lightbox"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      <div className="absolute top-4 left-4 mono text-xs px-3 py-1.5 rounded-full" style={{ background: 'rgba(0,0,0,0.6)', color: 'white', backdropFilter: 'blur(4px)' }}>
        {safeIndex + 1} / {photos.length}
      </div>

      {photos.length > 1 && (
        <>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); prev() }}
            className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full flex items-center justify-center"
            style={{ background: 'rgba(0,0,0,0.6)', color: 'white', backdropFilter: 'blur(4px)' }}
            aria-label="Previous photo"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); next() }}
            className="absolute right-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full flex items-center justify-center"
            style={{ background: 'rgba(0,0,0,0.6)', color: 'white', backdropFilter: 'blur(4px)' }}
            aria-label="Next photo"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </>
      )}

      <div
        onClick={(e) => e.stopPropagation()}
        className="max-w-[90vw] max-h-[80vh] flex flex-col items-center gap-4"
      >
        <img
          src={photo.url}
          alt={photo.caption || ''}
          className="rounded-lg object-contain"
          style={{ maxWidth: 'min(80vw, 1200px)', maxHeight: 'min(70vh, 800px)' }}
        />
        {(photo.caption || photo.uploadedBy) && (
          <div className="text-center max-w-[600px] px-4">
            {photo.caption && (
              <p className="text-sm" style={{ color: 'rgba(255,255,255,0.85)' }}>{photo.caption}</p>
            )}
            {photo.uploadedBy && (
              <p className="text-[10px] mt-1.5" style={{ color: 'var(--muted)' }}>
                Uploaded by {photo.uploadedBy}{photo.uploadedAt ? ` · ${photo.uploadedAt}` : ''}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
