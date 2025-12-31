import React, { useEffect, useState } from 'react'
import Card from '../components/Card'
import Button from '../components/Button'
import DiscoverySubmitModal from '../components/DiscoverySubmitModal'

function Photo({ url, alt }){
  if(!url) return null
  return (
    <div className="mt-2">
      <img src={url} alt={alt||''} style={{maxWidth: '100%', borderRadius:8}} />
    </div>
  )
}

export default function Discoveries(){
  const [items, setItems] = useState([])
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState(null)
  const [showSubmitModal, setShowSubmitModal] = useState(false)

  useEffect(()=>{ fetch(`/api/discoveries`).then(r=>r.json()).then(j=>setItems(j.results||[])) }, [])

  useEffect(()=>{
    function onOpen(ev){
      const d = ev.detail
      if(d) openDetail(d)
    }
    window.addEventListener('openDetail', onOpen)
    return ()=> window.removeEventListener('openDetail', onOpen)
  }, [items])

  async function search(){
    const res = await fetch(`/api/discoveries?q=${encodeURIComponent(q)}`)
    const j = await res.json()
    setItems(j.results || [])
  }

  function photoUrlToStatic(url){
    if(!url) return null
    if(url.startsWith('http')) return url
    try{
      // Handle both forward slash and backslash paths like "photos/file.jpg" or "photos\file.jpg"
      const normalized = url.replace(/\\/g, '/')
      const idx = normalized.lastIndexOf('/')
      const name = idx !== -1 ? normalized.slice(idx+1) : normalized
      return `/haven-ui-photos/${encodeURIComponent(name)}`
    }catch(e){ return null }
  }

  async function openDetail(d){
    try{
      const res = await fetch(`/api/discoveries/${d.id}`)
      if(!res.ok) {
        setSelected(d)
        return
      }
      const full = await res.json()
      if(full.photo_url) full._photo_static = photoUrlToStatic(full.photo_url)
      // Handle both evidence_url (db column) and evidence_urls (legacy)
      const evidenceData = full.evidence_url || full.evidence_urls
      if(evidenceData && typeof evidenceData === 'string'){
        full._evidence = evidenceData.split(',').map(s=>s.trim()).filter(Boolean).map(u=>photoUrlToStatic(u) || u)
      } else if(Array.isArray(evidenceData)){
        full._evidence = evidenceData.map(u=>photoUrlToStatic(u) || u)
      } else {
        full._evidence = []
      }
      setSelected(full)
    }catch(e){
      console.error(e)
      setSelected(d)
    }
  }

  function closeDetail(){ setSelected(null) }

  return (
    <div>
      <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h2 className="text-2xl font-semibold">Discoveries</h2>
        <div className="flex items-center gap-2">
          <input className="p-2 rounded flex-1 sm:flex-initial" value={q} onChange={e=>setQ(e.target.value)} placeholder="search discoveries" />
          <Button onClick={search}>Search</Button>
          <Button onClick={() => setShowSubmitModal(true)}>Submit Discovery</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((d,i)=> (
          <Card key={i} className="cursor-pointer" onClick={() => open_detail_safe(d)}>
            <div className="font-semibold">{d.discovery_name || d.discovery_type || (d.description && d.description.slice(0, 80)) || ('Discovery #'+(d.id||i))}</div>
            <div className="muted text-sm mt-1">{d.system_id ? `System: ${d.system_id}` : ''} {d.planet_id ? ` • Planet: ${d.planet_id}` : ''}</div>
            <div className="mt-2 text-sm">{d.description || ''}</div>
            <div className="mt-3 text-sm muted">Discovered by: {d.discovered_by || d.discord_user_id || 'Unknown'}</div>
          </Card>
        ))}
      </div>

      {selected && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={closeDetail}>
          <div className="p-6 rounded" style={{width:'90%', maxWidth:900, backgroundColor:'var(--app-card)'}} onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">{selected.discovery_name || selected.discovery_type || `Discovery #${selected.id}`}</h3>
              <Button onClick={closeDetail} variant="ghost">Close</Button>
            </div>
            <div className="mt-2 text-sm muted">Submitted: {selected.submission_timestamp}</div>
            <div className="mt-4"><strong>Location:</strong> {selected.system_id ? `System: ${selected.system_id}` : ''} {selected.location_name ? ` • ${selected.location_name}` : ''}</div>
            <div className="mt-3 text-sm">{selected.description}</div>
            {selected._photo_static && <Photo url={selected._photo_static} alt={selected.discovery_name} />}
            {selected._evidence && selected._evidence.length>0 && (
              <div className="mt-3">
                <strong>Evidence:</strong>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {selected._evidence.map((u,idx)=> (
                    <div key={idx} className="p-1 rounded" style={{backgroundColor:'rgba(255,255,255,0.03)'}}>
                      {u.startsWith('/') ? <img src={u} style={{maxWidth:'100%'}} /> : <a href={u} target="_blank" rel="noreferrer">{u}</a>}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="mt-4 text-sm muted">Discovered by: {selected.discovered_by || selected.discord_user_id || 'Unknown'}</div>
          </div>
        </div>
      )}

      <DiscoverySubmitModal
        isOpen={showSubmitModal}
        onClose={() => setShowSubmitModal(false)}
        onSuccess={() => {
          setShowSubmitModal(false)
          fetch('/api/discoveries').then(r => r.json()).then(j => setItems(j.results || []))
        }}
      />
    </div>
  )
}

// helper to avoid passing event prop through Card
function open_detail_safe(d){
  // find and call openDetail from closure by dispatching a custom event
  const ev = new CustomEvent('openDetail', { detail: d })
  window.dispatchEvent(ev)
}

