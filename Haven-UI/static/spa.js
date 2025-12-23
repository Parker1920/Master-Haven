// Minimal SPA for Haven-UI web control
// Hash-based routing

let isAdmin = false;
async function checkAdmin(){
  try {
    const r = await fetch('/api/admin/status');
    if (!r.ok) { isAdmin = false; return false; }
    const j = await r.json(); isAdmin = Boolean(j.logged_in); return isAdmin;
  } catch(e){ isAdmin = false; return false }
}

async function loginAdmin(password){
  const r = await fetch('/api/admin/login', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({password})});
  if (!r.ok) { const t = await r.text(); throw new Error(t) }
  await checkAdmin();
}

async function logoutAdmin(){
  await fetch('/api/admin/logout', { method: 'POST', credentials:'include' });
  await checkAdmin();
}

const routes = {
  '#/': renderDashboard,
  '': renderDashboard,
  '#/systems': renderSystems,
  '#/wizard': renderWizard,
  '#/tests': renderTests,
  '#/logs': renderLogs,
  '#/rtai': renderRTAI,
  '#/settings': renderSettings,
};

function navigate(hash) {
  window.location.hash = hash;
}

async function fetchJson(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || r.statusText);
  }
  return r.json();
}

function renderHeader() {
  const testsLink = isAdmin ? `<a href="#/tests" onclick="navigate('#/tests')">Test Manager</a> |` : '';
  const settingsLink = isAdmin ? `<a href="#/settings" onclick="navigate('#/settings')">Settings</a> |` : '';
  const rtaiLink = isAdmin ? `<a href="#/rtai" onclick="navigate('#/rtai')">AI Chat Monitor</a>` : '';
  const authButton = isAdmin ? `<button id='btnAdminAction' class='btn'>Logout</button>` : `<button id='btnAdminAction' class='btn'>Unlock</button>`;
  return `
    <header>
      <h1>Haven Control Room (Web)</h1>
      <nav>
        <a href="#/" onclick="navigate('#/')">Dashboard</a> |
        <a href="#/systems" onclick="navigate('#/systems')">Systems</a> |
        <a href="#/wizard" onclick="navigate('#/wizard')">Create System</a> |
        ${testsLink}
        <a href="#/logs" onclick="navigate('#/logs')">Logs</a> |
        ${settingsLink}
        ${rtaiLink}
        | ${authButton}
      </nav>
    </header>
  `;
}

async function renderDashboard() {
  const stats = await fetchJson('/api/stats');
  const resp = await fetch('/api/systems');
  const j = await resp.json();
  const list = j.systems || [];
  const html = `
    ${renderHeader()}
    <main>
      <section>
        <h2>Quick Actions</h2>
        <button id="btnReload">Reload Systems</button>
        <button id="btnGenerate">Generate Map</button>
        <button id="btnOpenMap">Open Latest Map</button>
      </section>

      <section>
        <h2>Recent Systems</h2>
        <div id="systems"></div>
      </section>
      <section>
        <h2>Stats</h2>
        <div id="status">OK</div>
        <div id="stats">Total systems: ${stats.total} - Regions: ${stats.regions.join(', ')}</div>
      </section>
    </main>
  `;
  document.querySelector('.app').innerHTML = html;
  let explicitSubmit = false;
  document.getElementById('btnReload').addEventListener('click', () => renderDashboard());
  document.getElementById('btnGenerate').addEventListener('click', async () => {
    await fetch('/api/generate_map', { method: 'POST' });
    alert('Map generation queued.');
  });
  document.getElementById('btnOpenMap').addEventListener('click', () => window.open('/map/latest', '_blank'));
  const el = document.getElementById('systems');
  el.innerHTML = '';
  list.slice(0, 20).forEach(s => {
    const d = document.createElement('div'); d.textContent = `${s.name} — ${s.region || ''}`;
    el.appendChild(d);
  })
}

async function renderSystems(){
  const html = `${renderHeader()}<main><h2>Systems</h2><input id="search" placeholder="Search systems" /><div id="systemsList"></div></main>`;
  document.querySelector('.app').innerHTML = html;
  document.getElementById('search').addEventListener('input', async (ev) => {
    const q = ev.target.value.trim();
    if (!q) return renderSystems();
    try{
      const j = await fetchJson(`/api/systems/search?q=${encodeURIComponent(q)}`);
      renderSystemsList(j.results || []);
    }catch(e){ console.error(e); alert('Search failed: ' + e.message) }
  });
  const r = await fetch('/api/systems');
  const j = await r.json();
  renderSystemsList(j.systems || []);
}

function renderSystemsList(list){
  const el = document.getElementById('systemsList');
  el.innerHTML = '';
  list.forEach(s => {
    const entry = document.createElement('div');
    entry.className = 'card';
    const photo = s.photo ? `<img src="/haven-ui-photos/${s.photo.split('/').pop()}" alt="${s.name}" style="max-width:120px; display:block; margin-bottom:6px"/>` : '';
    entry.innerHTML = `${photo}<strong>${s.name}</strong> <small>${s.region || ''}</small><div>${s.description || ''}</div><button data-name="${s.name}" aria-label="Edit ${s.name}">Edit</button>`;
    entry.querySelector('button').addEventListener('click', () => { openEditWizard(s); });
    el.appendChild(entry);
  });
}

function openEditWizard(system){
  window.location.hash = '#/wizard';
  setTimeout(() => populateWizard(system), 100);
}

function populateWizard(system){
  document.getElementById('name').value = system.name || '';
  document.getElementById('region').value = system.region || '';
  document.getElementById('x').value = system.x || '';
  document.getElementById('y').value = system.y || '';
  document.getElementById('z').value = system.z || '';
  document.getElementById('desc').value = system.description || '';
  document.getElementById('id').value = system.id || '';
}

async function renderWizard(){
  const html = `${renderHeader()}<main><h2>System Wizard</h2>
    <form id="systemForm" class="card">
      <input id="id" type="hidden" />
      <label>Name <input id="name" required /></label>
      <label>Region <input id="region" /></label>
      <label>X <input id="x" type="number" /></label>
      <label>Y <input id="y" type="number" /></label>
      <label>Z <input id="z" type="number" /></label>
      <label>Description <textarea id="desc"></textarea></label>
        <label>Photo <input id="photo" type="file" accept="image/*" /></label>
      <button type="submit">Save</button>
    </form>
  </main>`;
  document.querySelector('.app').innerHTML = html;
  document.getElementById('systemForm').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if(!explicitSubmit){
      explicitSubmit = false;
      return;
    }
    explicitSubmit = false;
    let photoPath = '';
    const fileInput = document.getElementById('photo');
    if (fileInput && fileInput.files && fileInput.files[0]){
      const fd = new FormData();
      fd.append('file', fileInput.files[0]);
      const upload = await fetch('/api/photos', { method: 'POST', body: fd });
      if (upload.ok){ const jup = await upload.json(); photoPath = jup.path; }
    }
    const body = {
      id: document.getElementById('id').value,
      name: document.getElementById('name').value,
      region: document.getElementById('region').value,
      x: parseFloat(document.getElementById('x').value || 0),
      y: parseFloat(document.getElementById('y').value || 0),
      z: parseFloat(document.getElementById('z').value || 0),
      description: document.getElementById('desc').value
      , photo: photoPath
    };
    try{
      const r = await fetch('/api/save_system', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)});
      if (!r.ok){ const t = await r.text(); throw new Error(t) }
      const j = await r.json();
      alert('Saved: ' + JSON.stringify(j));
      window.location.hash = '#/systems';
    }catch(e){ console.error(e); alert('Save failed: ' + e.message) }
  });

  // Flag explicit submit when Save button is clicked
  const saveBtn = document.querySelector('#systemForm button[type="submit"]');
  if (saveBtn) {
    saveBtn.addEventListener('click', () => { explicitSubmit = true });
  }

  // Prevent pressing Enter in text inputs from submitting the form accidentally
  document.getElementById('systemForm').addEventListener('keydown', (ev) => {
    if(ev.key === 'Enter'){
      const tag = ev.target && ev.target.nodeName ? ev.target.nodeName.toUpperCase() : '';
      const type = ev.target && ev.target.type ? String(ev.target.type).toLowerCase() : '';
      if(tag === 'TEXTAREA') return; // allow newline in textareas
      if(type === 'submit' || tag === 'BUTTON') return; // allow when on submit button
      ev.preventDefault();
    }
  });
}

async function renderTests(){
  if (!isAdmin){ navigate('#/'); return }
  const html = `${renderHeader()}<main><h2>Test Manager</h2><div id="testsList"></div></main>`;
  document.querySelector('.app').innerHTML = html;
  try{
    const r = await fetchJson('/api/tests');
    const list = r.tests || [];
    const el = document.getElementById('testsList');
    el.innerHTML = '';
    list.forEach(t => {
      const row = document.createElement('div');
      row.textContent = t;
      const run = document.createElement('button'); run.textContent = 'Run';
      run.addEventListener('click', async () => {
        const rr = await fetchJson('/api/tests/run', { method: 'POST', headers: { 'Content-Type': 'application/json'}, body: JSON.stringify({test_path: t}) });
        alert('Return: ' + rr.returncode + '\n' + rr.stdout);
      });
      row.appendChild(run);
      el.appendChild(row);
    })
  } catch(e){ console.error(e); alert('Failed to list tests: ' + e.message) }
}

async function renderLogs(){
  const html = `${renderHeader()}<main><h2>Logs</h2><div id="logStream" class="card" style="height:300px; overflow:auto"></div></main>`;
  document.querySelector('.app').innerHTML = html;
  const el = document.getElementById('logStream');
  // Fetch last logs once
  const r = await fetch('/api/logs');
  const j = await r.json();
  j.lines.forEach(l => { const d = document.createElement('div'); d.textContent = l; el.appendChild(d); });
  // WebSocket for live tail
  try{
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/logs`);
    ws.onmessage = (ev) => {
      const d = document.createElement('div'); d.textContent = ev.data; el.appendChild(d); el.scrollTop = el.scrollHeight;
    }
  }catch(e){ console.error('WS failed', e) }
}

async function renderRTAI(){
  if (!isAdmin){ navigate('#/'); return }
  const html = `${renderHeader()}<main><h2>RT AI</h2><div id="chat" class="card" style="height:300px; overflow:auto"></div><button id="clear">Clear</button></main>`;
  document.querySelector('.app').innerHTML = html;
  const el = document.getElementById('chat');
  const r = await fetch('/api/rtai/history');
  const j = await r.json();
  j.messages.forEach(m => { const d = document.createElement('div'); d.textContent = m; el.appendChild(d); });
  const clearBtn = document.getElementById('clear');
  clearBtn.addEventListener('click', async () => {
    await fetch('/api/rtai/clear', { method: 'POST' });
    el.innerHTML = '';
  });
  try{
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/rtai`);
    ws.onmessage = (ev) => { const d = document.createElement('div'); d.textContent = ev.data; el.appendChild(d); el.scrollTop = el.scrollHeight; };
  }catch(e){ console.error('WS failed', e); }
}

async function renderSettings(){
  if (!isAdmin){ navigate('#/'); return }
  const html = `${renderHeader()}<main><h2>Settings</h2><div id="settings"></div></main>`;
  document.querySelector('.app').innerHTML = html;
  const el = document.getElementById('settings');
  try{
    const r = await fetch('/api/stats');
    const sd = await r.json();
    el.innerHTML = `<div>Total systems: ${sd.total}</div><button id="dep">Update deps</button>`;
    document.getElementById('dep').addEventListener('click', async () => {
      const r = await fetch('/api/update_deps', { method: 'POST' });
      const j = await r.json();
      alert('Deps updated: ' + j.returncode);
    });
  }catch(e){ el.innerHTML = 'Failed to load settings'; }
}

function onHashChange(){
  const route = window.location.hash || '#/';
  const fn = routes[route] || renderDashboard;
  checkAdmin().then(()=>fn());
}

window.onhashchange = onHashChange;
window.onload = () => {
  onHashChange();
  document.addEventListener('click', (e) => {
      if (e.target && e.target.id === 'btnAdminAction'){
        if (!isAdmin){
          // Show modal login for improved UX instead of prompt()
          showAdminModal();
        } else {
          logoutAdmin().then(()=>{ alert('Logged out'); onHashChange(); });
        }
      }
  })
};

  function showAdminModal(){
    if (document.getElementById('admin-login-modal')) return;
    const modal = document.createElement('div');
    modal.id = 'admin-login-modal';
    modal.style = 'position:fixed; inset:0; display:flex; align-items:center; justify-content:center; background:rgba(0,0,0,0.5); z-index:9999;';
    modal.innerHTML = `
      <div style='background:#fff; padding:16px; border-radius:8px; min-width:320px;'>
        <h3>Admin Login</h3>
        <input id='admin-password' type='password' placeholder='Admin password' style='width:100%; padding:8px; margin-top:8px;'/>
        <div style='margin-top:8px; display:flex; gap:8px; justify-content:flex-end;'>
          <button id='admin-login-submit' class='btn'>Unlock</button>
          <button id='admin-login-cancel' class='btn'>Cancel</button>
        </div>
        <div id='admin-login-error' style='color:#f00; margin-top:8px; display:none;'></div>
      </div>`;
    document.body.appendChild(modal);
    document.getElementById('admin-login-cancel').addEventListener('click', () => { modal.remove(); });
    document.getElementById('admin-login-submit').addEventListener('click', async () => {
      const p = document.getElementById('admin-password').value;
      try{
        await loginAdmin(p);
        modal.remove();
        alert('Admin unlocked');
        onHashChange();
      }catch(e){
        const errEl = document.getElementById('admin-login-error'); errEl.style.display = 'block'; errEl.textContent = e.message || 'Login failed';
      }
    });
  }
