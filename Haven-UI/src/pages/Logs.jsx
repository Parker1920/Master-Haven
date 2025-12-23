import React, { useEffect, useRef, useState, useCallback } from 'react'
import Card from '../components/Card'
import { useInactivityAware } from '../hooks/useInactivityAware'

export default function Logs() {
  const [lines, setLines] = useState([])
  const ref = useRef(null)
  const wsRef = useRef(null)
  const { isDisconnected, registerConnection, unregisterConnection } = useInactivityAware()

  const connectWebSocket = useCallback(() => {
    // Fetch initial logs
    fetch('/api/logs')
      .then(r => r.json())
      .then(j => setLines(j.lines || []))
      .catch(() => {})

    // Create WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/logs`)
    ws.onmessage = (e) => setLines(l => [...l, e.data])
    wsRef.current = ws
    return ws
  }, [])

  useEffect(() => {
    // Don't connect if disconnected due to inactivity
    if (isDisconnected) return

    const ws = connectWebSocket()

    // Register with inactivity system
    registerConnection('logs-websocket', {
      cleanup: () => {
        if (wsRef.current) {
          wsRef.current.close()
          wsRef.current = null
        }
      },
      restore: () => {
        connectWebSocket()
      }
    })

    return () => {
      unregisterConnection('logs-websocket')
      ws.close()
    }
  }, [isDisconnected, connectWebSocket, registerConnection, unregisterConnection])

  // Keep scroll at bottom to show newest logs
  useEffect(() => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight
    }
  }, [lines])

  return (
    <div>
      <Card>
        <h2 className="text-lg font-semibold mb-2">Live Logs</h2>
        <pre className="bg-gray-900 text-white p-3 rounded h-72 overflow-auto" ref={ref}>{lines.join('\n')}</pre>
      </Card>
    </div>
  )
}
