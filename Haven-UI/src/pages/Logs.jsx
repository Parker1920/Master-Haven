import React, { useEffect, useRef, useState, useCallback } from 'react'
import Card from '../components/Card'

/**
 * Live Logs Viewer — Route: currently unused / internal only.
 * Auth: None enforced in this component (endpoint-level auth applies).
 *
 * Displays server logs in a scrollable pre block. Fetches initial log
 * lines via REST, then streams new lines over WebSocket.
 *
 * API endpoints:
 *   GET /api/logs        — fetch initial log lines
 *   WS  /ws/logs         — live log stream (WebSocket)
 */
export default function Logs() {
  const [lines, setLines] = useState([])
  const ref = useRef(null)
  const wsRef = useRef(null)

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
    const ws = connectWebSocket()

    return () => {
      ws.close()
    }
  }, [connectWebSocket])

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
