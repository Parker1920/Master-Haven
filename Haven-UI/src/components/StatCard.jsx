import React from 'react'
import Sparkline from './Sparkline'

export default function StatCard({title, value, subtitle, accent, children, className='', trend}){
  return (
    <div className={`p-4 rounded-xl shadow-md border ${className}`} style={{background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)', borderColor: 'rgba(255,255,255,0.04)'}}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-medium" style={{color: 'var(--app-accent-3)'}}>{title}</div>
          <div className="text-2xl font-bold mt-1" style={{color: 'var(--app-text)'}}>{value}</div>
          {subtitle && <div className="text-xs muted mt-1" style={{color: 'var(--app-accent-2)'}}>{subtitle}</div>}
        </div>
        <div className="flex items-center space-x-3">
          {trend && <div style={{width:120}}><Sparkline data={trend} /></div>}
          <div>
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}
