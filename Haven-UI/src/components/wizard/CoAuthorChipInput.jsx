import React, { useState } from 'react'

// Wizard v1 co-author chip input (mockup 5849-5858, v11AddCoauthor 9738).
// Type a Discord username + press Enter → chip appears. × removes.
//
// Per Parker's Phase 0 answer #2: co-author counts are tracked SEPARATELY
// from primary submission counts on the leaderboard.
export default function CoAuthorChipInput({ value = [], onChange, max = 10 }) {
  const [input, setInput] = useState('')

  function add() {
    const trimmed = input.trim().replace(/^@/, '')
    if (!trimmed) return
    if (value.length >= max) return
    if (value.some((v) => v.toLowerCase() === trimmed.toLowerCase())) {
      setInput('')
      return
    }
    onChange([...value, trimmed])
    setInput('')
  }

  function remove(idx) {
    onChange(value.filter((_, i) => i !== idx))
  }

  function handleKey(e) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      add()
    } else if (e.key === 'Backspace' && !input && value.length) {
      onChange(value.slice(0, -1))
    }
  }

  return (
    <div>
      <div
        className="flex flex-wrap gap-1.5 p-2 rounded min-h-[42px]"
        style={{ backgroundColor: 'var(--app-bg)', border: '1px solid var(--app-accent-3)' }}
      >
        {value.map((u, i) => (
          <span
            key={`${u}-${i}`}
            className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs"
            style={{
              backgroundColor: 'var(--app-accent-2)',
              color: '#fff',
            }}
          >
            <span>{u}</span>
            <button
              type="button"
              onClick={() => remove(i)}
              className="opacity-80 hover:opacity-100 -mr-0.5"
              aria-label={`Remove ${u}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          type="text"
          className="flex-1 min-w-[120px] bg-transparent outline-none text-sm"
          placeholder={value.length === 0 ? 'Add Discord username + Enter…' : ''}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          onBlur={add}
        />
      </div>
      <p className="text-xs opacity-60 mt-1">
        Each co-author gets credit on the leaderboard as a separate column from primary submissions.
      </p>
    </div>
  )
}
