import React from 'react'

export default function Modal({title, children, onClose, isOpen = true}){
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-40 p-4 overflow-y-auto">
      <div className="p-6 rounded shadow max-w-3xl w-full my-4 max-h-[90vh] flex flex-col" style={{backgroundColor:'var(--app-card)'}}>
        <div className="flex items-center justify-between mb-3 flex-shrink-0">
          <div className="font-semibold text-lg">{title}</div>
          <button onClick={onClose} className="px-2 py-1 rounded" style={{backgroundColor:'var(--app-accent-3)', color:'#fff'}}>Close</button>
        </div>
        <div className="overflow-y-auto flex-1">
          {children}
        </div>
      </div>
    </div>
  )
}
