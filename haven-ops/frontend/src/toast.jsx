import { createContext, useCallback, useContext, useRef, useState } from 'react'

const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }) {
  const [msg, setMsg] = useState(null)
  const timer = useRef()
  const show = useCallback((m) => {
    setMsg(m)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setMsg(null), 1900)
  }, [])
  return (
    <ToastCtx.Provider value={show}>
      {children}
      <div className={`toast${msg ? ' show' : ''}`}>{msg}</div>
    </ToastCtx.Provider>
  )
}
