import React, { useEffect, useState } from 'react'

export default function Tests(){
  const [tests, setTests] = useState([])
  const [running, setRunning] = useState(false)
  useEffect(()=>{ fetch('/api/tests').then(r=>r.json()).then(j=>setTests(j.tests||[])) }, [])
  async function runTest(path){
    setRunning(true)
    const res = await fetch('/api/tests/run', { method:'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ test_path: path }) })
    const j = await res.json()
    alert('Return: '+j.returncode+'\n'+j.stdout+'\n'+j.stderr)
    setRunning(false)
  }
  return (
    <div>
      <h2 className="text-xl font-semibold mb-2">Tests</h2>
      <div className="space-y-2">
        {tests.map((t,i) => (
          <div key={i} className="p-2 bg-white/5 rounded flex justify-between items-center">
            <div>{t}</div>
            <button className="px-3 py-1 bg-sky-600 text-white rounded" onClick={()=>runTest(t)} disabled={running}>Run</button>
          </div>
        ))}
      </div>
    </div>
  )
}
