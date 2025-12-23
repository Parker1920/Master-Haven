import React from 'react'
import { useInactivityAware } from '../hooks/useInactivityAware'

export default function InactivityOverlay() {
  const { isDisconnected, reconnect } = useInactivityAware()

  if (!isDisconnected) return null

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div
        className="p-8 rounded-xl shadow-2xl max-w-md w-full text-center"
        style={{ backgroundColor: 'var(--app-card)' }}
      >
        {/* Pause Icon */}
        <div
          className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center"
          style={{ background: 'rgba(240, 173, 78, 0.2)' }}
        >
          <span className="text-3xl">&#9208;</span>
        </div>

        {/* Heading */}
        <h2
          className="text-xl font-semibold mb-2"
          style={{ color: 'var(--app-text)' }}
        >
          Session Paused
        </h2>

        {/* Description */}
        <p className="mb-6" style={{ color: 'var(--muted)' }}>
          Your session was paused due to inactivity to save resources.
          Click below to resume all live connections.
        </p>

        {/* Reconnect Button */}
        <button
          onClick={reconnect}
          className="w-full py-3 px-6 rounded-lg font-semibold text-white transition-all duration-300 hover:scale-105"
          style={{
            background: 'linear-gradient(135deg, var(--app-primary) 0%, #00a89a 100%)',
            boxShadow: '0 4px 20px rgba(0, 194, 179, 0.4)'
          }}
        >
          Reconnect
        </button>
      </div>
    </div>
  )
}
