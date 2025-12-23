import React from 'react'

export default function FormField({label, children, hint, className=''}){
  return (
    <div className={`mb-4 ${className}`}>
      {label && <label className="block text-sm font-medium mb-1">{label}</label>}
      <div>{children}</div>
      {hint && <div className="text-xs muted mt-1">{hint}</div>}
    </div>
  )
}
