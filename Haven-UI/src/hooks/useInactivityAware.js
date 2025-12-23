import { useContext } from 'react'
import { InactivityContext } from '../utils/InactivityContext'

/**
 * Custom hook for components with real-time features (WebSockets, polling).
 * Provides inactivity state and functions to register connection cleanup/restore callbacks.
 *
 * Usage:
 * const { isDisconnected, registerConnection, unregisterConnection } = useInactivityAware()
 *
 * useEffect(() => {
 *   if (isDisconnected) return
 *
 *   const ws = new WebSocket(url)
 *   wsRef.current = ws
 *
 *   registerConnection('my-websocket', {
 *     cleanup: () => wsRef.current?.close(),
 *     restore: () => connectWebSocket()
 *   })
 *
 *   return () => {
 *     unregisterConnection('my-websocket')
 *     ws.close()
 *   }
 * }, [isDisconnected])
 */
export function useInactivityAware() {
  const context = useContext(InactivityContext)

  if (!context) {
    // Return safe defaults if used outside provider
    return {
      isDisconnected: false,
      disconnect: () => {},
      reconnect: () => {},
      registerConnection: () => {},
      unregisterConnection: () => {},
      timeoutMs: 0
    }
  }

  return context
}

export default useInactivityAware
