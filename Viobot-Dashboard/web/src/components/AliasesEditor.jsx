import { useEffect, useState } from 'react';
import { api } from '../api.js';

function AliasRow({ guildId, alias, open, onToggle, onChanged }) {
  const [help, setHelp] = useState(alias.helpText);
  const [allow, setAllow] = useState(alias.allowMembers);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => { setHelp(alias.helpText); setAllow(alias.allowMembers); }, [alias.helpText, alias.allowMembers]);
  const dirty = help !== alias.helpText || allow !== alias.allowMembers;

  async function save() {
    setBusy(true); setMsg(null);
    try { onChanged(await api.updateAlias(guildId, alias.name, { helpText: help, allowMembers: allow })); setMsg('Saved ✓'); }
    catch (e) { setMsg('Error: ' + e.message); } finally { setBusy(false); }
  }
  async function del() {
    if (!window.confirm(`Delete public alias !${alias.name}? This can't be undone.`)) return;
    setBusy(true); setMsg(null);
    try { onChanged(await api.deleteAlias(guildId, alias.name)); }
    catch (e) { setMsg('Error: ' + e.message); setBusy(false); }
  }

  return (
    <div className="alias-item">
      <button className="alias-summary" onClick={onToggle}>
        <span className="mono alias-name">!{alias.name}</span>
        <span className={`role-badge ${allow ? 'role-admin' : 'role-owner'}`}>{allow ? 'Public' : 'Mod only'}</span>
        <span className="alias-help muted">{alias.helpText || '—'}</span>
        <span className="guild-go">{open ? '▾' : '›'}</span>
      </button>
      {open && (
        <div className="alias-detail">
          <span className="config-help">Alias body (author with the Alias Generator)</span>
          <pre className="alias-body">{alias.rawBody || '(empty)'}</pre>
          <div className="alias-edit">
            <input className="cfg-input" placeholder="Help text" value={help} onChange={(e) => setHelp(e.target.value)} />
            <button type="button" className={`switch switch-sm ${allow ? 'switch-on' : ''}`} title="Members can use" onClick={() => setAllow(!allow)}><span className="switch-knob" /></button>
            <span className="muted small">Members can use</span>
          </div>
          <div className="alias-actions">
            <button className="btn btn-ghost btn-sm danger-text" onClick={del} disabled={busy}>Delete</button>
            {dirty && <button className="btn btn-discord btn-sm" onClick={save} disabled={busy}>{busy ? '…' : 'Save'}</button>}
            {msg && <span className="muted small">{msg}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AliasesEditor({ guildId }) {
  const [data, setData] = useState(undefined);
  const [error, setError] = useState(null);
  const [openName, setOpenName] = useState(null);

  useEffect(() => {
    setData(undefined); setError(null);
    api.getAliases(guildId).then(setData).catch((e) => setError(String(e.message || e)));
  }, [guildId]);

  if (error) return <p className="notice error">Couldn't load aliases: {error}</p>;
  if (data === undefined) return <p className="muted">Loading aliases…</p>;

  return (
    <section className="config-card">
      <div className="vars-head">
        <h3 className="config-group-title">Public aliases</h3>
        <span className="muted small">{data.aliases.length} public · {data.privateCount} private (per-member)</span>
      </div>
      <p className="config-help" style={{ padding: '0 0 8px' }}>
        Server-wide command shortcuts. Author new ones with the Alias Generator; manage access &amp; remove them here.
      </p>
      {data.aliases.length === 0 && <p className="val-empty" style={{ padding: '8px 0' }}>No public aliases.</p>}
      <div className="alias-list">
        {data.aliases.map((a) => (
          <AliasRow
            key={a.name}
            guildId={guildId}
            alias={a}
            open={openName === a.name}
            onToggle={() => setOpenName(openName === a.name ? null : a.name)}
            onChanged={setData}
          />
        ))}
      </div>
    </section>
  );
}
