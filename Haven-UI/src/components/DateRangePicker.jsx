import React, { useState } from 'react'
import DatePicker from 'react-datepicker'
import { format, subDays, subMonths, subYears, startOfWeek, startOfMonth, startOfYear } from 'date-fns'
import 'react-datepicker/dist/react-datepicker.css'

const presets = [
  { label: 'Last 7 days', getValue: () => ({ start: subDays(new Date(), 7), end: new Date() }) },
  { label: 'Last 30 days', getValue: () => ({ start: subDays(new Date(), 30), end: new Date() }) },
  { label: 'This week', getValue: () => ({ start: startOfWeek(new Date()), end: new Date() }) },
  { label: 'This month', getValue: () => ({ start: startOfMonth(new Date()), end: new Date() }) },
  { label: 'This year', getValue: () => ({ start: startOfYear(new Date()), end: new Date() }) },
  { label: 'Last year', getValue: () => ({ start: subYears(new Date(), 1), end: new Date() }) },
  { label: 'All time', getValue: () => ({ start: null, end: null }) },
]

export default function DateRangePicker({ startDate, endDate, onChange, className = '' }) {
  const [isOpen, setIsOpen] = useState(false)

  const handlePreset = (preset) => {
    const { start, end } = preset.getValue()
    onChange({ startDate: start, endDate: end })
    setIsOpen(false)
  }

  const handleStartChange = (date) => {
    onChange({ startDate: date, endDate })
  }

  const handleEndChange = (date) => {
    onChange({ startDate, endDate: date })
  }

  const handleClear = () => {
    onChange({ startDate: null, endDate: null })
    setIsOpen(false)
  }

  const formatDisplay = () => {
    if (!startDate && !endDate) return 'All time'
    if (startDate && endDate) {
      return `${format(startDate, 'MMM d, yyyy')} - ${format(endDate, 'MMM d, yyyy')}`
    }
    if (startDate) return `From ${format(startDate, 'MMM d, yyyy')}`
    if (endDate) return `Until ${format(endDate, 'MMM d, yyyy')}`
    return 'Select dates'
  }

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
        style={{
          background: 'var(--app-card)',
          border: '1px solid rgba(255,255,255,0.1)',
          color: 'var(--app-text)'
        }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <span>{formatDisplay()}</span>
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div
          className="absolute top-full mt-2 right-0 z-50 rounded-xl shadow-2xl p-4"
          style={{
            background: 'var(--app-card)',
            border: '1px solid rgba(255,255,255,0.1)',
            minWidth: '320px'
          }}
        >
          {/* Presets */}
          <div className="mb-4">
            <div className="text-xs font-medium mb-2" style={{ color: 'var(--app-accent-3)' }}>Quick Select</div>
            <div className="flex flex-wrap gap-2">
              {presets.map((preset) => (
                <button
                  key={preset.label}
                  onClick={() => handlePreset(preset)}
                  className="px-2 py-1 rounded text-xs transition-colors hover:opacity-80"
                  style={{
                    background: 'rgba(0, 194, 179, 0.1)',
                    color: 'var(--app-primary)',
                    border: '1px solid rgba(0, 194, 179, 0.2)'
                  }}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          {/* Custom Date Range */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--app-accent-3)' }}>Start Date</label>
              <DatePicker
                selected={startDate}
                onChange={handleStartChange}
                selectsStart
                startDate={startDate}
                endDate={endDate}
                maxDate={endDate || new Date()}
                placeholderText="Start date"
                className="w-full px-3 py-2 rounded-lg text-sm"
                calendarClassName="dark-calendar"
                wrapperClassName="w-full"
              />
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--app-accent-3)' }}>End Date</label>
              <DatePicker
                selected={endDate}
                onChange={handleEndChange}
                selectsEnd
                startDate={startDate}
                endDate={endDate}
                minDate={startDate}
                maxDate={new Date()}
                placeholderText="End date"
                className="w-full px-3 py-2 rounded-lg text-sm"
                calendarClassName="dark-calendar"
                wrapperClassName="w-full"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-between pt-3" style={{ borderTop: '1px solid rgba(255,255,255,0.1)' }}>
            <button
              onClick={handleClear}
              className="text-xs px-3 py-1.5 rounded transition-colors"
              style={{ color: 'var(--app-text)', opacity: 0.7 }}
            >
              Clear
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className="text-xs px-3 py-1.5 rounded font-medium"
              style={{
                background: 'var(--app-primary)',
                color: '#000'
              }}
            >
              Apply
            </button>
          </div>
        </div>
      )}

      {/* Click outside to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  )
}
