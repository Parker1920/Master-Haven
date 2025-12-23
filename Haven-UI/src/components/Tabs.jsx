import React, { useState } from 'react'

export default function Tabs({tabs = [], initial = 0, onChange}){
  const [active, setActive] = useState(initial)
  return (
    <div>
      <div role="tablist" className="flex space-x-2 mb-3">
        {tabs.map((t, i) => (
          <button key={i} role="tab" aria-selected={i===active} tabIndex={0} className={`px-3 py-1 rounded ${i===active? 'bg-[rgba(255,255,255,0.06)]': 'bg-transparent'}`} onClick={()=>{ setActive(i); onChange && onChange(i) }}>
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {tabs[active] && tabs[active].content}
      </div>
    </div>
  )
}
