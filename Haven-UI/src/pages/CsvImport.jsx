import React, { useState, useContext, useRef } from 'react'
import { AuthContext } from '../utils/AuthContext'
import Card from '../components/Card'
import Button from '../components/Button'

/**
 * CSV Import — Route: /csv-import
 * Auth: Feature-gated (requires csv_import feature flag on the partner/sub-admin account).
 *
 * Two-step flow:
 * 1. Upload CSV → backend returns detected column mappings + preview
 * 2. User reviews/adjusts mappings → confirms import
 *
 * Supports GHUB format (row 0=region, row 1=headers) and dynamic format (row 0=headers).
 * Systems are tagged with the logged-in user's discord_tag and bypass the approval queue.
 */

const FIELD_OPTIONS = [
  { value: 'ignored', label: 'Ignore' },
  { value: 'system_name', label: 'System Name' },
  { value: 'planet_name', label: 'Planet Name' },
  { value: 'galaxy', label: 'Galaxy' },
  { value: 'region', label: 'Region' },
  { value: 'star_colour', label: 'Star Color' },
  { value: 'star_class', label: 'Spectral Class' },
  { value: 'economy_type', label: 'Economy Type' },
  { value: 'conflict_level', label: 'Conflict Level' },
  { value: 'dominant_lifeform', label: 'Race/Lifeform' },
  { value: 'resources', label: 'Resources' },
  { value: 'notes', label: 'Notes/Comments' },
  { value: 'portal_code', label: 'Portal Code (Glyphs)' },
  { value: 'coordinates', label: 'Galactic Coordinates' },
  { value: 'logged_by', label: 'Logged By' },
  { value: 'original_name', label: 'Original System Name' },
  { value: 'nmsportals_link', label: 'NMSPortals Link' },
  { value: 'reference_id', label: 'Reference ID' },
]

export default function CsvImport() {
  const auth = useContext(AuthContext)
  const { isSuperAdmin, isPartner, user } = auth || {}
  const fileInputRef = useRef(null)

  const [file, setFile] = useState(null)
  const [previewing, setPreviewing] = useState(false)
  const [importing, setImporting] = useState(false)
  const [preview, setPreview] = useState(null)
  const [columnMapping, setColumnMapping] = useState([])
  const [result, setResult] = useState(null)

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile && selectedFile.name.endsWith('.csv')) {
      setFile(selectedFile)
      setResult(null)
      setPreview(null)
      setColumnMapping([])
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const droppedFile = e.dataTransfer.files?.[0]
    if (droppedFile && droppedFile.name.endsWith('.csv')) {
      setFile(droppedFile)
      setResult(null)
      setPreview(null)
      setColumnMapping([])
    }
  }

  // Step 1: Preview — send file to /api/csv_preview to get detected column mappings
  const doPreview = async () => {
    if (!file) return
    setPreviewing(true)
    setResult(null)
    setPreview(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await fetch('/api/csv_preview', {
        method: 'POST',
        credentials: 'include',
        body: formData
      })

      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Preview failed')

      setPreview(data)
      setColumnMapping(data.column_mapping || [])
    } catch (e) {
      setResult({ success: false, error: e.message })
    } finally {
      setPreviewing(false)
    }
  }

  // Update a column's mapping
  const updateMapping = (index, newValue) => {
    setColumnMapping(prev => prev.map(cm =>
      cm.index === index ? { ...cm, mapped_to: newValue } : cm
    ))
  }

  // Step 2: Import — send file + confirmed column mapping to /api/import_csv
  const doImport = async () => {
    if (!file) return
    setImporting(true)
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('column_mapping', JSON.stringify(columnMapping))

      const res = await fetch('/api/import_csv', {
        method: 'POST',
        credentials: 'include',
        body: formData
      })

      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Import failed')

      setResult({
        success: true,
        imported: data.imported,
        skipped: data.skipped,
        errors: data.errors,
        totalErrors: data.total_errors,
        regionName: data.region_name,
        systemsGrouped: data.systems_grouped,
        totalRows: data.total_rows_processed,
      })

      setFile(null)
      setPreview(null)
      setColumnMapping([])
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (e) {
      setResult({ success: false, error: e.message })
    } finally {
      setImporting(false)
    }
  }

  const mappedFields = columnMapping.filter(cm => cm.mapped_to !== 'ignored').map(cm => cm.mapped_to)
  const hasCoords = mappedFields.includes('portal_code') || mappedFields.includes('coordinates') || mappedFields.includes('nmsportals_link')
  const hasSystemName = mappedFields.includes('system_name')

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-cyan-400">CSV Import</h1>

      <Card className="bg-gray-800/50">
        <div className="p-4">
          <h3 className="text-lg font-semibold text-white mb-2">Import Star Systems from CSV</h3>
          <p className="text-sm text-gray-400 mb-4">
            Upload a CSV file to bulk-import star systems. Supports multiple formats — column headers are auto-detected.
          </p>

          {/* Drag and drop area */}
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
              ${file ? 'border-cyan-500 bg-cyan-900/10' : 'border-gray-600 hover:border-gray-500'}`}
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileSelect}
              className="hidden"
            />
            {file ? (
              <div>
                <div className="text-lg text-cyan-400 font-semibold">{file.name}</div>
                <div className="text-sm text-gray-400 mt-1">{(file.size / 1024).toFixed(1)} KB</div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setFile(null)
                    setPreview(null)
                    setColumnMapping([])
                    if (fileInputRef.current) fileInputRef.current.value = ''
                  }}
                  className="mt-2 text-sm text-red-400 hover:text-red-300"
                >
                  Remove file
                </button>
              </div>
            ) : (
              <div>
                <div className="text-lg text-gray-300">Drop CSV file here</div>
                <div className="text-sm text-gray-500 mt-1">or click to browse</div>
              </div>
            )}
          </div>

          {/* Preview button */}
          {file && !preview && (
            <div className="mt-4">
              <Button onClick={doPreview} disabled={previewing}>
                {previewing ? 'Analyzing...' : 'Analyze CSV'}
              </Button>
            </div>
          )}

          {/* Column Mapping Preview */}
          {preview && (
            <div className="mt-6 space-y-4">
              {/* Detection summary */}
              <div className="p-3 bg-gray-700/50 rounded border border-gray-600">
                <div className="flex flex-wrap gap-4 text-sm">
                  <span className="text-gray-400">Format: <span className="text-cyan-400 font-medium">{preview.format === 'ghub' ? 'GHUB (region + headers)' : 'Dynamic (headers on row 1)'}</span></span>
                  <span className="text-gray-400">Data rows: <span className="text-white font-medium">{preview.total_data_rows}</span></span>
                  {preview.coord_type && (
                    <span className="text-gray-400">Coordinates: <span className="text-green-400 font-medium">
                      {preview.coord_type === 'portal_glyph' ? 'Portal Glyphs' : preview.coord_type === 'galactic_coords' ? 'Galactic Coords' : 'NMSPortals Link'}
                    </span></span>
                  )}
                  {preview.region_name && (
                    <span className="text-gray-400">Region: <span className="text-yellow-400 font-medium">{preview.region_name}</span></span>
                  )}
                </div>
              </div>

              {/* Column mapping table */}
              <div>
                <h4 className="text-sm font-semibold text-gray-300 mb-2">Column Mapping</h4>
                <p className="text-xs text-gray-500 mb-3">Review and adjust how each CSV column maps to Haven fields.</p>
                <div className="space-y-1.5">
                  {columnMapping.map((cm) => (
                    <div key={cm.index} className={`flex items-center gap-3 px-3 py-1.5 rounded text-sm ${cm.mapped_to !== 'ignored' ? 'bg-gray-700/60' : 'bg-gray-800/30'}`}>
                      <span className="text-gray-400 w-6 text-right text-xs">{cm.index + 1}</span>
                      <span className={`font-medium min-w-[160px] ${cm.mapped_to !== 'ignored' ? 'text-white' : 'text-gray-500'}`}>
                        {cm.csv_column}
                      </span>
                      <span className="text-gray-500">→</span>
                      <select
                        value={cm.mapped_to}
                        onChange={(e) => updateMapping(cm.index, e.target.value)}
                        className={`px-2 py-1 bg-gray-700 border rounded text-sm ${
                          cm.mapped_to !== 'ignored' ? 'border-cyan-600 text-cyan-300' : 'border-gray-600 text-gray-400'
                        }`}
                      >
                        {FIELD_OPTIONS.map(opt => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>

              {/* Data preview table */}
              {preview.preview_rows && preview.preview_rows.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-300 mb-2">Data Preview (first {preview.preview_rows.length} rows)</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr>
                          {columnMapping.filter(cm => cm.mapped_to !== 'ignored').map(cm => (
                            <th key={cm.index} className="px-2 py-1 text-left text-cyan-400 border-b border-gray-700 whitespace-nowrap">
                              {FIELD_OPTIONS.find(f => f.value === cm.mapped_to)?.label || cm.mapped_to}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {preview.preview_rows.map((row, i) => (
                          <tr key={i} className="border-b border-gray-800">
                            {columnMapping.filter(cm => cm.mapped_to !== 'ignored').map(cm => (
                              <td key={cm.index} className="px-2 py-1 text-gray-300 whitespace-nowrap max-w-[200px] truncate">
                                {row[cm.mapped_to] || <span className="text-gray-600">—</span>}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Validation warnings */}
              {!hasCoords && (
                <div className="p-2 bg-red-900/30 border border-red-700 rounded text-sm text-red-300">
                  No coordinate column detected. Map a column to "Portal Code", "Galactic Coordinates", or "NMSPortals Link".
                </div>
              )}
              {!hasSystemName && (
                <div className="p-2 bg-yellow-900/30 border border-yellow-700 rounded text-sm text-yellow-300">
                  No system name column detected. Systems will be named using their glyph code.
                </div>
              )}

              {/* Import button */}
              <div className="flex gap-4">
                <Button onClick={doImport} disabled={importing || !hasCoords}>
                  {importing ? 'Importing...' : `Import ${preview.total_data_rows} Rows`}
                </Button>
                <button
                  onClick={() => { setPreview(null); setColumnMapping([]) }}
                  className="text-sm text-gray-400 hover:text-gray-300"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Results */}
          {result && (
            <div className={`mt-6 p-4 rounded border ${result.success ? 'bg-green-900/30 border-green-700' : 'bg-red-900/30 border-red-700'}`}>
              {result.success ? (
                <div>
                  <h4 className="text-lg font-semibold text-green-400 mb-2">Import Complete</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-gray-400">Systems Imported:</span>
                      <span className="ml-2 text-green-400 font-semibold">{result.imported}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Rows Processed:</span>
                      <span className="ml-2 text-white font-semibold">{result.totalRows}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Skipped:</span>
                      <span className="ml-2 text-yellow-400 font-semibold">{result.skipped}</span>
                    </div>
                    {result.systemsGrouped && (
                      <div>
                        <span className="text-gray-400">Systems Grouped:</span>
                        <span className="ml-2 text-cyan-400 font-semibold">{result.systemsGrouped}</span>
                      </div>
                    )}
                    {result.regionName && (
                      <div className="col-span-2">
                        <span className="text-gray-400">Region:</span>
                        <span className="ml-2 text-cyan-400">{result.regionName}</span>
                      </div>
                    )}
                  </div>
                  {result.errors && result.errors.length > 0 && (
                    <div className="mt-4">
                      <h5 className="text-sm font-semibold text-yellow-400 mb-1">
                        Errors ({result.totalErrors} total, showing first {result.errors.length}):
                      </h5>
                      <ul className="text-xs text-gray-400 space-y-1 max-h-32 overflow-y-auto">
                        {result.errors.map((err, i) => (
                          <li key={i} className="text-red-300">{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <h4 className="text-lg font-semibold text-red-400 mb-2">Import Failed</h4>
                  <p className="text-sm text-red-300">{result.error}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Info about permissions */}
      {isPartner && (
        <Card className="bg-gray-800/50">
          <div className="p-4">
            <h3 className="text-lg font-semibold text-gray-300 mb-2">About CSV Import</h3>
            <ul className="text-sm text-gray-400 space-y-1 list-disc list-inside">
              <li>Imported systems will be tagged with your Discord ({user?.discordTag})</li>
              <li>Duplicate systems (same glyph code) will be skipped</li>
              <li>Systems are imported directly into the database (no approval needed)</li>
              <li>Multiple rows with the same system coordinates are grouped into one system</li>
              <li>Supports portal glyph codes, galactic coordinates, and NMSPortals links</li>
            </ul>
          </div>
        </Card>
      )}
    </div>
  )
}
