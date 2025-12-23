import React, { useEffect, useState, useRef, useCallback } from 'react'
import Card from '../components/Card'
import { useInactivityAware } from '../hooks/useInactivityAware'

export default function RTAI() {
  const [messages, setMessages] = useState([])
  const wsRef = useRef(null)
  const { isDisconnected, registerConnection, unregisterConnection } = useInactivityAware()

  const connectWebSocket = useCallback(() => {
    // Fetch history
    fetch('/api/rtai/history')
      .then(r => r.json())
      .then(j => setMessages(j.messages || []))
      .catch(() => {})

    // Create WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/rtai`)
    ws.onmessage = (e) => setMessages(m => [...m, e.data])
    wsRef.current = ws
    return ws
  }, [])

  useEffect(() => {
    // Don't connect if disconnected due to inactivity
    if (isDisconnected) return

    const ws = connectWebSocket()

    // Register with inactivity system
    registerConnection('rtai-websocket', {
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
      unregisterConnection('rtai-websocket')
      ws.close()
    }
  }, [isDisconnected, connectWebSocket, registerConnection, unregisterConnection])

  return (
    <div>
      <Card>
        <h2 className="text-lg font-semibold mb-2">Round Table AI Chat</h2>
        <div className="space-y-2 h-72 overflow-auto bg-cyan-800 p-3 rounded">
          {messages.map((m, i) => <div key={i} className="text-white">{m}</div>)}
        </div>
        <div className="mt-2">
          <button className="px-3 py-2 bg-gray-200 rounded" onClick={() => fetch('/api/rtai/clear', { method: 'POST' })}>Clear</button>
        </div>
      </Card>
    </div>
  )
}
