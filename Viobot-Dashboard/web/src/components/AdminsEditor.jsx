import { useEffect, useState } from 'react';
import { api } from '../api.js';

export default function AdminsEditor() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [newId, setNewId] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  function load() { api.adminGetAdmins().then(setData).catch((e) => setError(String(e.message || e))); }
  useEffect(load, []);

  if (error) return <p className="notice error">{error}</p>;
  if (!data) return <p className="muted">Loading…</p>;

  async function save(ids) {
    setBusy(true); setMsg(null);
    try { const d = await api.adminSaveAdmins(ids); setData((s) => ({ ...s, storedAdmins: d.storedAdmins })); setMsg('Saved ✓'); }
    catch (e) { setMsg('Error: ' + e.message); } finally { setBusy(false); }
  }
  function add() {
    const id = newId.trim();
    if (!/^\d{15,25}$/.test(id)) { setMsg('Enter a numeric Discord user ID'); return; }
    if (data.storedAdmins.includes(id) || data.envAdmins.includes(id)) { setMsg('Already an admin'); return; }
    save([...data.storedAdmins, id]); setNewId('');
  }

  return (
    <section className="config-card">
      <h3 className="config-group-title">Dashboard admins</h3>
      <p className="config-help" style={{ padding: '0 0 10px' }}>
        Discord user IDs who can access this admin area. Built-in admins are set on the server and can't be removed here.
      </p>
      <div className="admin-list">
        {data.envAdmins.map((id) => (
          <div key={id} className="admin-row"><span className="mono">{id}</span><span className="role-badge role-owner">built-in</span></div>
        ))}
        {data.storedAdmins.map((id) => (
          <div key={id} className="admin-row"><span className="mono">{id}</span><button className="chip-x" title="Remove" onClick={() => save(data.storedAdmins.filter((x) => x !== id))} disabled={busy}>×</button></div>
        ))}
        {data.storedAdmins.length === 0 && <span className="val-empty">No added admins.</span>}
      </div>
      <div className="admin-add">
        <input className="cfg-input" placeholder="Discord user ID" value={newId} onChange={(e) => setNewId(e.target.value)} />
        <button className="btn btn-ghost btn-sm" onClick={add} disabled={busy}>Add admin</button>
        {msg && <span className="muted small">{msg}</span>}
      </div>
    </section>
  );
}
