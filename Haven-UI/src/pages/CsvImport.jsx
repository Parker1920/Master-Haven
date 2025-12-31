import React, { useState, useContext, useRef } from 'react'
import { AuthContext } from '../utils/AuthContext'
import Card from '../components/Card'
import Button from '../components/Button'

export default function CsvImport() {
  const auth = useContext(AuthContext)
  const { isSuperAdmin, isPartner, user } = auth || {}
  const fileInputRef = useRef(null)

  const [file, setFile] = useState(null)
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile && selectedFile.name.endsWith('.csv')) {
      setFile(selectedFile)
      setResult(null)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const droppedFile = e.dataTransfer.files?.[0]
    if (droppedFile && droppedFile.name.endsWith('.csv')) {
      setFile(droppedFile)
      setResult(null)
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = () => {
    setDragOver(false)
  }

  const doImport = async () => {
    if (!file) return

    setImporting(true)
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await fetch('/api/import_csv', {
        method: 'POST',
        credentials: 'include',
        body: formData
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || 'Import failed')
      }

      setResult({
        success: true,
        imported: data.imported,
        skipped: data.skipped,
        errors: data.errors,
        totalErrors: data.total_errors,
        regionName: data.region_name
      })

      // Clear file selection on success
      setFile(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (e) {
      setResult({
        success: false,
        error: e.message
      })
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-cyan-400">CSV Import</h1>

      <Card className="bg-gray-800/50">
        <div className="p-4">
          <h3 className="text-lg font-semibold text-white mb-2">Import Star Systems from CSV</h3>
          <p className="text-sm text-gray-400 mb-4">
            Upload a CSV file exported from Google Sheets to import star systems directly into the database.
          </p>

          {/* Expected format info */}
          <div className="mb-6 p-3 bg-gray-700/50 rounded border border-gray-600">
            <h4 className="text-sm font-semibold text-gray-300 mb-2">Expected CSV Format:</h4>
            <ul className="text-xs text-gray-400 space-y-1 list-disc list-inside">
              <li><strong>Row 1:</strong> Region name (e.g., "HUB1 - Sea of Xionahui")</li>
              <li><strong>Row 2:</strong> Headers (Coordinates, Original System Name, HUB Tag, New System Name, etc.)</li>
              <li><strong>Row 3+:</strong> Data rows</li>
            </ul>
            <div className="mt-2 text-xs text-gray-400">
              <p><strong>Required columns:</strong> Coordinates (galactic format XXXX:YYYY:ZZZZ:SSSS), New System Name</p>
              <p><strong>Stored in notes:</strong> HUB Tag, Original System Name, Comments/Special Attributes</p>
            </div>
          </div>

          {/* Drag and drop area */}
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
              ${dragOver ? 'border-cyan-400 bg-cyan-900/20' : 'border-gray-600 hover:border-gray-500'}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
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
                <div className="text-sm text-gray-400 mt-1">
                  {(file.size / 1024).toFixed(1)} KB
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setFile(null)
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

          <div className="mt-4 flex gap-4">
            <Button
              onClick={doImport}
              disabled={!file || importing}
            >
              {importing ? 'Importing...' : 'Import Systems'}
            </Button>
          </div>

          {/* Results */}
          {result && (
            <div className={`mt-6 p-4 rounded border ${result.success ? 'bg-green-900/30 border-green-700' : 'bg-red-900/30 border-red-700'}`}>
              {result.success ? (
                <div>
                  <h4 className="text-lg font-semibold text-green-400 mb-2">Import Complete</h4>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-400">Systems Imported:</span>
                      <span className="ml-2 text-green-400 font-semibold">{result.imported}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Systems Skipped:</span>
                      <span className="ml-2 text-yellow-400 font-semibold">{result.skipped}</span>
                    </div>
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
            </ul>
          </div>
        </Card>
      )}
    </div>
  )
}
