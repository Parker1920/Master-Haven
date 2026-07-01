import { useEffect, useMemo, useState } from 'react';
import { api } from '../api.js';

const TYPES = ['role', 'role[]', 'channel', 'bool', 'string', 'number', 'select'];

export default function RegistryEditor() {
  const [original, setOriginal] = useState(null);
  const [reg, setReg] = useState(null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  function load() {
    setReg(null); setError(null); setMsg(null);
    api.adminGetRegistry().then((d) => { setReg(d.registry); setOriginal(JSON.stringify(d.registry)); }).catch((e) => setError(String(e.message || e)));
  }
  useEffect(load, []);

  const dirty = useMemo(() => reg && original !== null && JSON.stringify(reg) !== original, [reg, original]);

  if (error) return <p className="notice error">{error}</p>;
  if (!reg) return <p className="muted">Loading…</p>;

  const groups = reg.groups;
  const setGroups = (g) => { setReg({ ...reg, groups: g }); setMsg(null); };
  const updateGroup = (gi, patch) => setGroups(groups.map((g, i) => (i === gi ? { ...g, ...patch } : g)));
  const updateField = (gi, fi, patch) => updateGroup(gi, { fields: groups[gi].fields.map((f, i) => (i === fi ? { ...f, ...patch } : f)) });
  const move = (arr, i, dir) => { const a = [...arr]; const j = i + dir; if (j < 0 || j >= a.length) return a; [a[i], a[j]] = [a[j], a[i]]; return a; };

  async function save() {
    setSaving(true); setMsg(null);
    try {
      const d = await api.adminSaveRegistry(reg);
      setReg(d.registry); setOriginal(JSON.stringify(d.registry));
      setMsg({ kind: 'ok', text: "Saved ✓ — applies to every server's Settings tab." });
    } catch (e) { setMsg({ kind: 'err', text: 'Save failed: ' + e.message }); } finally { setSaving(false); }
  }

  return (
    <div>
      <p className="config-help" style={{ marginBottom: 14 }}>
        These are the options that render in each server's <b>Settings</b> tab. <b>Path</b> is where the value is stored in
        Viobot's config (e.g. <code>roles.newRoleId</code>, <code>features.myToggle</code>). Add fields as Viobot ships new config.
      </p>

      {groups.map((g, gi) => (
        <section key={gi} className="config-card">
          <div className="reg-group-head">
            <input className="cfg-input reg-group-label" placeholder="Group label" value={g.label} onChange={(e) => updateGroup(gi, { label: e.target.value })} />
            <input className="cfg-input mono reg-group-id" placeholder="id" value={g.id} onChange={(e) => updateGroup(gi, { id: e.target.value })} />
            <div className="reg-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => setGroups(move(groups, gi, -1))} disabled={gi === 0}>↑</button>
              <button className="btn btn-ghost btn-sm" onClick={() => setGroups(move(groups, gi, 1))} disabled={gi === groups.length - 1}>↓</button>
              <button className="btn btn-ghost btn-sm danger-text" onClick={() => setGroups(groups.filter((_, i) => i !== gi))}>Remove</button>
            </div>
          </div>

          <div className="reg-fields">
            {g.fields.map((f, fi) => (
              <div key={fi} className="reg-field">
                <input className="cfg-input" placeholder="Label" value={f.label || ''} onChange={(e) => updateField(gi, fi, { label: e.target.value })} />
                <input className="cfg-input mono" placeholder="path.to.value" value={f.path || ''} onChange={(e) => updateField(gi, fi, { path: e.target.value })} />
                <select className="cfg-select cfg-select-sm" value={f.type} onChange={(e) => updateField(gi, fi, { type: e.target.value })}>
                  {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <input className="cfg-input reg-help" placeholder="help (optional)" value={f.help || ''} onChange={(e) => updateField(gi, fi, { help: e.target.value })} />
                {f.type === 'select' && (
                  <input
                    className="cfg-input"
                    placeholder="options: a, b, c"
                    value={(f.options || []).map((o) => (o && typeof o === 'object' ? o.value : o)).join(', ')}
                    onChange={(e) => updateField(gi, fi, { options: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
                  />
                )}
                <label className="reg-testing" title="Only dashboard admins see this field — stage it before the public does">
                  <input type="checkbox" checked={Boolean(f.testing)} onChange={(e) => updateField(gi, fi, { testing: e.target.checked })} /> Testing
                </label>
                <div className="reg-actions">
                  <button className="btn btn-ghost btn-sm" onClick={() => updateGroup(gi, { fields: move(g.fields, fi, -1) })} disabled={fi === 0}>↑</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => updateGroup(gi, { fields: move(g.fields, fi, 1) })} disabled={fi === g.fields.length - 1}>↓</button>
                  <button className="chip-x" title="Remove field" onClick={() => updateGroup(gi, { fields: g.fields.filter((_, i) => i !== fi) })}>×</button>
                </div>
              </div>
            ))}
            <button className="btn btn-ghost btn-sm" onClick={() => updateGroup(gi, { fields: [...g.fields, { path: '', type: 'string', label: '', help: '' }] })}>+ Add field</button>
          </div>
        </section>
      ))}

      <button className="btn btn-ghost btn-sm" onClick={() => setGroups([...groups, { id: '', label: '', fields: [] }])}>+ Add group</button>
      {msg && <p className={`notice ${msg.kind === 'err' ? 'error' : 'ok'}`}>{msg.text}</p>}

      {dirty && (
        <div className="save-bar">
          <span className="save-bar-msg">Unsaved field changes</span>
          <div className="save-bar-actions">
            <button className="btn btn-ghost" disabled={saving} onClick={load}>Discard</button>
            <button className="btn btn-discord" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save fields'}</button>
          </div>
        </div>
      )}
    </div>
  );
}
