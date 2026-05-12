import React, { useEffect, useRef, useState } from 'react'

// Wizard v1 photo uploader (mockup v11AttachPhotoUploadEvents 9994).
//
// Features:
//   - Click or drag-and-drop to upload
//   - Paste-to-upload: when this component is mounted, Ctrl+V on the page
//     uploads any image from the clipboard (only fires when the component is
//     visible, via the `paste-target` flag below)
//   - Drag-to-reorder existing tiles
//   - ★ "set as main" star icon per tile (first photo is the main image)
//   - × remove per tile
//
// Props:
//   value: [{ path, file?, preview? }] — `path` is the uploaded server filename
//   onChange(newList)
//   uploadFn(file) — returns Promise<{ path }> (defaults to /api/photos POST)
//   accept: string — MIME accept attr (default 'image/*')
//   maxPhotos: number — soft cap (default 10)
//   pasteTarget: bool — listen for paste events (true on the only-visible instance)

// Matches server-side _PHOTO_MAX_BYTES in routes/csv_import.py. Keep in sync.
const MAX_BYTES = 15 * 1024 * 1024

const DEFAULT_UPLOAD = async (file) => {
  if (file.size > MAX_BYTES) {
    throw new Error(`Image too large (${Math.round(file.size / 1024 / 1024)} MB); max is ${MAX_BYTES / 1024 / 1024} MB`)
  }
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch('/api/photos', { method: 'POST', body: fd, credentials: 'same-origin' })
  if (!res.ok) throw new Error(await res.text())
  const data = await res.json()
  return { path: data.path || data.filename }
}

export default function PhotoUploader({
  value = [],
  onChange,
  uploadFn = DEFAULT_UPLOAD,
  accept = 'image/*',
  maxPhotos = 10,
  pasteTarget = false,
}) {
  const fileRef = useRef(null)
  const [uploading, setUploading] = useState(0)
  const [dragOver, setDragOver] = useState(false)
  const [dragIdx, setDragIdx] = useState(null)

  async function handleFiles(files) {
    // Filter to images by MIME and reject oversized files client-side so
    // we don't waste a round-trip just to get a 413 back.
    const arr = Array.from(files || []).filter((f) =>
      f.type.startsWith('image/') && f.size <= MAX_BYTES
    )
    if (!arr.length) return
    const room = Math.max(0, maxPhotos - value.length)
    const slice = arr.slice(0, room)
    setUploading((n) => n + slice.length)
    const results = []
    for (const file of slice) {
      const preview = URL.createObjectURL(file)
      results.push({ path: null, preview, uploading: true })
    }
    onChange([...value, ...results])
    // Walk the additions one at a time so partial failures don't lose later uploads.
    for (let i = 0; i < slice.length; i += 1) {
      try {
        const { path } = await uploadFn(slice[i])
        onChange((curRef.current || []).map((p) =>
          p.preview === results[i].preview ? { path, preview: results[i].preview, uploading: false } : p
        ))
      } catch (err) {
        // Mark the failed entry visibly; user can remove it.
        onChange((curRef.current || []).map((p) =>
          p.preview === results[i].preview ? { ...p, uploading: false, error: err.message || 'upload failed' } : p
        ))
      } finally {
        setUploading((n) => n - 1)
      }
    }
  }

  // Keep a ref to the latest value so async onChange callbacks see fresh state.
  const curRef = useRef(value)
  useEffect(() => { curRef.current = value }, [value])

  // Paste-to-upload (only one instance should claim the target on the page).
  useEffect(() => {
    if (!pasteTarget) return
    function onPaste(e) {
      const items = e.clipboardData?.items
      if (!items) return
      const files = []
      for (const it of items) {
        if (it.kind === 'file') {
          const f = it.getAsFile()
          if (f && f.type.startsWith('image/')) files.push(f)
        }
      }
      if (files.length) {
        e.preventDefault()
        handleFiles(files)
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [pasteTarget]) // eslint-disable-line react-hooks/exhaustive-deps

  function removeAt(idx) {
    const next = [...value]
    if (next[idx]?.preview) {
      try { URL.revokeObjectURL(next[idx].preview) } catch { /* ignore */ }
    }
    next.splice(idx, 1)
    onChange(next)
  }

  function makeMain(idx) {
    if (idx === 0) return
    const next = [...value]
    const [picked] = next.splice(idx, 1)
    next.unshift(picked)
    onChange(next)
  }

  // Drag-to-reorder
  function onTileDragStart(e, idx) {
    setDragIdx(idx)
    e.dataTransfer.effectAllowed = 'move'
    try { e.dataTransfer.setData('text/plain', String(idx)) } catch { /* ignore */ }
  }
  function onTileDragOver(e) { e.preventDefault(); e.dataTransfer.dropEffect = 'move' }
  function onTileDrop(e, dropIdx) {
    e.preventDefault()
    if (dragIdx == null || dragIdx === dropIdx) { setDragIdx(null); return }
    const next = [...value]
    const [picked] = next.splice(dragIdx, 1)
    next.splice(dropIdx, 0, picked)
    onChange(next)
    setDragIdx(null)
  }

  // Dropzone handlers
  function onZoneDragOver(e) { e.preventDefault(); setDragOver(true) }
  function onZoneDragLeave() { setDragOver(false) }
  function onZoneDrop(e) {
    e.preventDefault(); setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div>
      <div
        className={`border-2 border-dashed rounded p-4 text-center cursor-pointer transition-colors ${dragOver ? 'opacity-80' : ''}`}
        style={{ borderColor: dragOver ? 'var(--app-primary)' : 'var(--app-accent-3)', backgroundColor: dragOver ? 'rgba(0,194,179,0.08)' : 'transparent' }}
        onClick={() => fileRef.current?.click()}
        onDragOver={onZoneDragOver}
        onDragLeave={onZoneDragLeave}
        onDrop={onZoneDrop}
      >
        <input
          ref={fileRef}
          type="file"
          accept={accept}
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <div className="text-2xl mb-1">📷</div>
        <div className="text-sm">
          {uploading > 0 ? `Uploading ${uploading}…` : 'Click, drag & drop, or paste images'}
        </div>
        <div className="text-xs opacity-60 mt-1">First photo is the main image. Drag tiles to reorder.</div>
      </div>

      {value.length > 0 && (
        <div className="mt-2 grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
          {value.map((p, idx) => {
            const src = p.preview || (p.path ? `/haven-ui-photos/${encodeURIComponent(p.path.split('/').pop())}` : null)
            const isMain = idx === 0
            return (
              <div
                key={idx}
                draggable
                onDragStart={(e) => onTileDragStart(e, idx)}
                onDragOver={onTileDragOver}
                onDrop={(e) => onTileDrop(e, idx)}
                className="relative aspect-square rounded overflow-hidden cursor-move"
                style={{ backgroundColor: 'var(--app-bg)', outline: isMain ? '2px solid var(--app-accent-amber)' : 'none' }}
              >
                {src ? (
                  <img src={src} alt="" className="w-full h-full object-cover pointer-events-none" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-xs opacity-50">No preview</div>
                )}
                {p.uploading && (
                  <div className="absolute inset-0 flex items-center justify-center text-xs" style={{ backgroundColor: 'rgba(0,0,0,0.5)', color: '#fff' }}>
                    Uploading…
                  </div>
                )}
                {p.error && (
                  <div className="absolute inset-0 flex items-center justify-center text-xs px-1 text-center" style={{ backgroundColor: 'rgba(239,68,68,0.6)', color: '#fff' }}>
                    {p.error}
                  </div>
                )}
                {/* Star = main */}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); makeMain(idx) }}
                  className="absolute top-1 left-1 w-6 h-6 rounded-full flex items-center justify-center text-xs"
                  style={{ backgroundColor: isMain ? 'var(--app-accent-amber)' : 'rgba(0,0,0,0.55)', color: isMain ? '#1a1a1a' : '#fff' }}
                  title={isMain ? 'Main image' : 'Set as main'}
                >
                  {isMain ? '★' : '☆'}
                </button>
                {/* Remove */}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); removeAt(idx) }}
                  className="absolute top-1 right-1 w-6 h-6 rounded-full flex items-center justify-center text-sm"
                  style={{ backgroundColor: 'rgba(0,0,0,0.55)', color: '#fff' }}
                  title="Remove"
                >
                  ×
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
