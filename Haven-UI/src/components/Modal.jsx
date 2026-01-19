import React from 'react'

export default function Modal({title, children, onClose, isOpen = true}){
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-40 p-2 sm:p-4 overflow-y-auto">
      <div className="p-4 sm:p-6 rounded shadow w-full max-w-[95vw] sm:max-w-xl md:max-w-2xl lg:max-w-3xl my-2 sm:my-4 max-h-[95vh] sm:max-h-[90vh] flex flex-col" style={{backgroundColor:'var(--app-card)'}}>
        <div className="flex items-center justify-between mb-3 flex-shrink-0 gap-2">
          <div className="font-semibold text-base sm:text-lg flex-1 min-w-0 truncate">{title}</div>
          <button onClick={onClose} className="px-3 py-1.5 sm:px-2 sm:py-1 rounded text-sm flex-shrink-0" style={{backgroundColor:'var(--app-accent-3)', color:'#fff'}}>Close</button>
        </div>
        <div className="overflow-y-auto flex-1 -mx-4 px-4 sm:-mx-6 sm:px-6">
          {children}
        </div>
      </div>
    </div>
  )
}
