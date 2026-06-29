import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api.js';

const VAR_NAME_RE = /^[a-z0-9_.-]{1,64}$/;

// Self-sizing value field — grows to fit its content so nothing is clipped, no inner scrollbar.
function AutoTextarea({ value, onChange, ...props }) {
  const ref = useRef(null);
  const fit = () => { const el = ref.current; if (el) { el.style.height = 'auto'; el.style.height = `${el.scrollHeight}px`; } };
  useEffect(fit, [value]);
  return <textarea ref={ref} rows={1} value={value} onChange={(e) => { onChange(e); fit(); }} {...props} />;
}

export default function VariablesEditor({ guildId }) {
  const [original, setOriginal] = useState(null);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  function load() {
    setRows(null);
    setError(null);
    setMsg(null);
    api
      .getVariables(guildId)
      .then((d) => {
        const list = (d.variables || []).map((v) => ({ name: v.name, value: v.value }));
        setRows(list);
        setOriginal(JSON.stringify(list));
      })
      .catch((e) => setError(String(e.message || e)));
  }
  useEffect(load, [guildId]);

  const dirty = useMemo(() => rows && original !== null && JSON.stringify(rows) !== original, [rows, original]);

  const nameError = (name, i) => {
    const n = (name || '').trim().toLowerCase();
    if (!n) return 'required';
    if (!VAR_NAME_RE.test(n)) return 'use a-z 0-9 . _ -';
    if (rows.some((r, j) => j !== i && (r.name || '').trim().toLowerCase() === n)) return 'duplicate';
    return null;
  };
  const anyInvalid = rows ? rows.some((r, i) => nameError(r.name, i)) : false;

  const setRow = (i, patch) => { setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r))); setMsg(null); };
  const addRow = () => { setRows((rs) => [...rs, { name: '', value: '' }]); setMsg(null); };
  const removeRow = (i) => { setRows((rs) => rs.filter((_, j) => j !== i)); setMsg(null); };

  async function save() {
    setSaving(true);
    setMsg(null);
    try {
      const payload = rows.map((r) => ({ name: (r.name || '').trim().toLowerCase(), value: r.value })).filter((r) => r.name);
      const res = await api.saveVariables(guildId, payload);
      const list = (res.variables || []).map((v) => ({ name: v.name, value: v.value }));
      setRows(list);
      setOriginal(JSON.stringify(list));
      setMsg({ kind: 'ok', text: 'Variables saved ✓' });
    } catch (e) {
      setMsg({ kind: 'err', text: `Save failed: ${e.message}` });
    } finally {
      setSaving(false);
    }
  }

  if (error) return <p className="notice error">Couldn't load variables: {error}</p>;
  if (rows === null) return <p className="muted">Loading variables…</p>;

  return (
    <section className="config-card">
      <div className="vars-head">
        <h3 className="config-group-title">Server variables</h3>
        <button className="btn btn-ghost btn-sm" onClick={addRow} disabled={rows.length >= 200}>+ Add variable</button>
      </div>
      <p className="config-help" style={{ padding: '0 0 8px' }}>
        Reusable text snippets, used in aliases as <code>$var(name)</code>. Also editable in Discord with <code>!var</code>.
      </p>

      {rows.length === 0 && <p className="val-empty" style={{ padding: '8px 0' }}>No variables yet.</p>}

      <div className="var-rows">
        {rows.length > 0 && (
          <div className="var-head"><span>Name</span><span>Value</span><span /></div>
        )}
        {rows.map((r, i) => {
          const err = nameError(r.name, i);
          return (
            <div key={i} className="var-row">
              <div className="var-name">
                <input
                  className={`cfg-input ${err ? 'cfg-input-err' : ''}`}
                  placeholder="name"
                  value={r.name}
                  onChange={(e) => setRow(i, { name: e.target.value })}
                />
                {err && <span className="var-err">{err}</span>}
              </div>
              <AutoTextarea className="cfg-input var-val" placeholder="value" value={r.value} onChange={(e) => setRow(i, { value: e.target.value })} />
              <button className="chip-x var-del" title="Remove variable" onClick={() => removeRow(i)}>×</button>
            </div>
          );
        })}
      </div>

      {msg && <p className={`notice ${msg.kind === 'err' ? 'error' : 'ok'}`}>{msg.text}</p>}

      {dirty && (
        <div className="vars-save">
          <button className="btn btn-ghost" disabled={saving} onClick={load}>Discard</button>
          <button className="btn btn-discord" disabled={saving || anyInvalid} onClick={save}>{saving ? 'Saving…' : 'Save variables'}</button>
        </div>
      )}
    </section>
  );
}
