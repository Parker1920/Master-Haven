export async function apiGet(path){
  const res = await fetch(path, {method: 'GET', credentials: 'same-origin'})
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

export async function apiPost(path, body, { adminToken } = {}){
  const headers = { 'Content-Type': 'application/json' }
  if(adminToken) headers['X-HAVEN-ADMIN'] = adminToken
  const res = await fetch(path, { method: 'POST', credentials: 'same-origin', headers, body: JSON.stringify(body) })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

export async function adminLogin(password){
  const res = await fetch('/api/admin/login', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

export async function adminLogout(){
  const res = await fetch('/api/admin/logout', { method: 'POST', credentials: 'same-origin' })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

export async function adminStatus(){
  const res = await fetch('/api/admin/status', { method: 'GET', credentials: 'same-origin' })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}

export async function uploadPhoto(file){
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch('/api/photos', { method: 'POST', credentials: 'same-origin', body: formData })
  if(!res.ok) throw new Error(await res.text())
  return await res.json()
}
