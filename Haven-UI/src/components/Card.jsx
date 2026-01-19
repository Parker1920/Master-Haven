import React from 'react'

export default function Card({children, className='', thin=false, ...rest}){
  const base = 'p-4 sm:p-6 rounded-lg shadow-sm border border-gray-100'
  const bg = 'bg-card'
  return (
    <div {...rest} className={`${bg} ${base} ${className}`} style={{backgroundColor:'var(--app-card)'}}>{children}</div>
  )
}
