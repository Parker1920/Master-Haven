import React from 'react'

export default function Button({children, onClick, className = '', type = 'button', variant='primary', ...rest}){
  const base = 'px-4 py-2 rounded inline-flex items-center justify-center'
  const variants = {
    primary: 'btn-primary',
    ghost: 'bg-transparent border border-white/10',
    neutral: 'bg-gray-700 text-white'
  }
  const vclass = variants[variant] || variants.primary
  return (
    <button type={type} onClick={onClick} className={`${base} ${vclass} ${className}`} {...rest}>{children}</button>
  )
}
