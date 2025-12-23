import React from 'react'

export default function Sparkline({data = [], width=120, height=28, stroke='var(--app-primary)'}){
  if(!data || data.length === 0) return <svg width={width} height={height} />
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const points = data.map((d,i)=>{
    const x = (i/(data.length-1))*(width-2) + 1
    const y = height - ((d - min)/range)*(height-4) - 2
    return `${x},${y}`
  }).join(' ')
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <polyline fill="none" stroke={stroke} strokeWidth="2" points={points} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
