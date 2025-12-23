import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useInactivityAware } from '../hooks/useInactivityAware'

export default function TerminalViewer({ lines = 400 }) {
  const [rows, setRows] = useState([])
  const [paused, setPaused] = useState(false)
  const containerRef = useRef(null)
  const wsRef = useRef(null)
  const { isDisconnected, registerConnection, unregisterConnection } = useInactivityAware()

  const connectWebSocket = useCallback(() => {
    try {
      const proto = (location.protocol === 'https:') ? 'wss' : 'ws'
      const url = `${proto}://${location.host}/ws/logs`
      const ws = new WebSocket(url)
      wsRef.current = ws
      ws.onmessage = (ev) => {
        if (paused) return
        setRows(prev => {
          // Add new logs at the end (newest last)
          const next = [...prev, ev.data]
          // Trim from beginning to keep only the most recent logs
          if (next.length > lines) next.shift()
          return next
        })
      }
      ws.onopen = () => console.debug('TerminalViewer: ws open')
      ws.onclose = () => console.debug('TerminalViewer: ws closed')
      ws.onerror = (e) => console.debug('TerminalViewer: ws error', e)
      return ws
    } catch (err) {
      console.debug('TerminalViewer: websocket not available', err)
      return null
    }
  }, [lines, paused])

  useEffect(() => {
    // Don't connect if disconnected due to inactivity
    if (isDisconnected) return

    const ws = connectWebSocket()

    // Register with inactivity system
    registerConnection('terminal-viewer-websocket', {
      cleanup: () => {
        if (wsRef.current) {
          try {
            wsRef.current.close()
          } catch (_) {}
          wsRef.current = null
        }
      },
      restore: () => {
        connectWebSocket()
      }
    })

    return () => {
      unregisterConnection('terminal-viewer-websocket')
      if (ws) {
        try {
          ws.close()
        } catch (_) {}
      }
    }
  }, [isDisconnected, connectWebSocket, registerConnection, unregisterConnection])

  useEffect(() => {
    if (!paused && containerRef.current) {
      // Keep scroll at bottom to show newest logs
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [rows, paused])

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold">Live Logs</div>
        <div className="text-sm space-x-2">
          <button aria-pressed={paused} className="px-2 py-1 rounded bg-neutral-800 text-white focus:outline-none focus:ring-2 focus:ring-offset-1" onClick={() => { setPaused(p => !p) }}>{paused ? 'Resume' : 'Pause'}</button>
          <button className="px-2 py-1 rounded bg-neutral-800 text-white focus:outline-none focus:ring-2 focus:ring-offset-1" onClick={() => { setRows([]) }}>Clear</button>
        </div>
      </div>
      <div ref={containerRef} role="log" aria-live="polite" tabIndex={0} style={{ height: '360px', overflowY: 'auto', background: 'rgba(0,0,0,0.08)', padding: '10px', borderRadius: '8px', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, monospace', fontSize: '12px', color: 'var(--app-text)' }}>
        {rows.length === 0 ? <div className="text-sm muted">No logs available</div> : rows.map((r, i) => (<div key={i}><span style={{ opacity: 0.8 }}>{r}</span></div>))}
      </div>
    </div>
  )
}
