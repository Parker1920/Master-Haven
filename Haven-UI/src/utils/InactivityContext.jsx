import React, { createContext, useState, useEffect, useRef, useCallback } from 'react'

const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'click']
const DEBOUNCE_MS = 1000
const DEFAULT_TIMEOUT_MS = 60 * 60 * 1000 // 1 hour

export const InactivityContext = createContext({
  isDisconnected: false,
  disconnect: () => {},
  reconnect: () => {},
  registerConnection: () => {},
  unregisterConnection: () => {},
  timeoutMs: DEFAULT_TIMEOUT_MS
})

export function InactivityProvider({ children, timeout = DEFAULT_TIMEOUT_MS }) {
  const [isDisconnected, setIsDisconnected] = useState(false)
  const connectionsRef = useRef(new Map())
  const timeoutIdRef = useRef(null)
  const debounceTimerRef = useRef(null)

  // Reset the inactivity timer
  const resetTimer = useCallback(() => {
    if (timeoutIdRef.current) {
      clearTimeout(timeoutIdRef.current)
    }

    timeoutIdRef.current = setTimeout(() => {
      // Trigger disconnect
      setIsDisconnected(true)
      // Call cleanup on all registered connections
      connectionsRef.current.forEach((callbacks, id) => {
        try {
          callbacks.cleanup?.()
        } catch (e) {
          console.error(`Inactivity cleanup error for ${id}:`, e)
        }
      })
    }, timeout)
  }, [timeout])

  // Set up activity listeners
  useEffect(() => {
    const handleActivity = () => {
      // Debounce activity events
      if (debounceTimerRef.current) return

      debounceTimerRef.current = setTimeout(() => {
        debounceTimerRef.current = null
        // Only reset timer if not disconnected
        if (!isDisconnected) {
          resetTimer()
        }
      }, DEBOUNCE_MS)
    }

    // Add listeners for all activity events
    ACTIVITY_EVENTS.forEach(event => {
      window.addEventListener(event, handleActivity, { passive: true })
    })

    // Start the initial timer
    resetTimer()

    return () => {
      // Cleanup all listeners and timers
      ACTIVITY_EVENTS.forEach(event => {
        window.removeEventListener(event, handleActivity)
      })
      if (timeoutIdRef.current) clearTimeout(timeoutIdRef.current)
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
    }
  }, [isDisconnected, resetTimer])

  // Reconnect function - restores all connections
  const reconnect = useCallback(() => {
    setIsDisconnected(false)
    resetTimer()

    // Call restore on all registered connections
    connectionsRef.current.forEach((callbacks, id) => {
      try {
        callbacks.restore?.()
      } catch (e) {
        console.error(`Inactivity restore error for ${id}:`, e)
      }
    })
  }, [resetTimer])

  // Register a connection with cleanup and restore callbacks
  const registerConnection = useCallback((id, callbacks) => {
    connectionsRef.current.set(id, callbacks)
  }, [])

  // Unregister a connection
  const unregisterConnection = useCallback((id) => {
    connectionsRef.current.delete(id)
  }, [])

  // Manual disconnect (not typically used, but available)
  const disconnect = useCallback(() => {
    setIsDisconnected(true)
    connectionsRef.current.forEach((callbacks, id) => {
      try {
        callbacks.cleanup?.()
      } catch (e) {
        console.error(`Inactivity cleanup error for ${id}:`, e)
      }
    })
  }, [])

  const value = {
    isDisconnected,
    disconnect,
    reconnect,
    registerConnection,
    unregisterConnection,
    timeoutMs: timeout
  }

  return (
    <InactivityContext.Provider value={value}>
      {children}
    </InactivityContext.Provider>
  )
}

export default InactivityContext
