import React from 'react'
import Button from './Button'
import { ChartBarIcon, GlobeAltIcon } from '@heroicons/react/24/outline'

export default function QuickActions(){
  return (
    <div className="space-x-3">
      <Button className="btn-primary inline-flex items-center" onClick={()=>{ fetch('/api/generate_map',{method: 'POST'}) }}><ChartBarIcon className="w-4 h-4 mr-2"/>Generate Map</Button>
      <a className="px-4 py-2 bg-neutral-200 text-gray-800 rounded hover:bg-neutral-300 inline-flex items-center" href="/map/latest" target="_blank" rel="noreferrer"><GlobeAltIcon className="w-4 h-4 mr-2"/>Open Latest Map</a>
    </div>
  )
}
