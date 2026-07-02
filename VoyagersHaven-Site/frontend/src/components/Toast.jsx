import { createContext, useCallback, useContext, useRef, useState } from 'react'

const ToastCtx = createContext(() => {})

export function useToast() {
  return useContext(ToastCtx)
}

export function ToastProvider({ children }) {
  const [state, setState] = useState({ msg: '', kind: 'ok', show: false })
  const timer = useRef(null)

  const toast = useCallback((msg, kind = 'ok') => {
    setState({ msg, kind, show: true })
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setState((s) => ({ ...s, show: false })), 2800)
  }, [])

  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div className={`toast${state.show ? ' show' : ''}`}>
        <span className={`dot${state.kind === 'err' ? ' err' : ''}`} />
        <span>{state.msg}</span>
      </div>
    </ToastCtx.Provider>
  )
}
