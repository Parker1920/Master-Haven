import React, { useEffect, useState } from 'react'

export default function Toast({ message, show, onClose }){
  const [visible, setVisible] = useState(show)
  useEffect(()=>{ setVisible(show) }, [show])
  useEffect(()=>{ if(visible){ const t = setTimeout(()=>{ setVisible(false); onClose?.() }, 3500); return () => clearTimeout(t) } }, [visible])
  if(!visible) return null
  return (
    <div className="fixed right-4 bottom-6 btn-primary px-4 py-2 rounded shadow">{message}</div>
  )
}
