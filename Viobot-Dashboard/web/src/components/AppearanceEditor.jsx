import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api.js';
import { THEME_TOKENS, DEFAULT_TABS, DEFAULT_GUIDES_LABEL, applyAppearance } from '../appearance.js';

export default function AppearanceEditor({ appearance, onChange }) {
  const [draft, setDraft] = useState(() => structuredClone(appearance || {}));
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  const savedRef = useRef(appearance || {});
  savedRef.current = appearance || {};
  // On leave, drop any unsaved live preview by re-applying the saved appearance.
  useEffect(() => () => applyAppearance(savedRef.current), []);

  const original = useMemo(() => JSON.stringify(appearance || {}), [appearance]);
  const dirty = JSON.stringify(draft) !== original;

  // Every change previews live on the whole document.
  const set = (patch) => { const next = { ...draft, ...patch }; setDraft(next); applyAppearance(next); setMsg(null); };
  const setTheme = (key, v) => set({ theme: { ...(draft.theme || {}), [key]: v } });
  const clearTheme = (key) => { const t = { ...(draft.theme || {}) }; delete t[key]; set({ theme: t }); };

  // tabs merged with the canonical set so nothing is ever lost
  const tabs = useMemo(() => {
    const conf = Array.isArray(draft.tabs) ? draft.tabs : [];
    const ids = new Set(conf.map((t) => t.id));
    const merged = conf.filter((t) => DEFAULT_TABS.some((d) => d.id === t.id))
      .map((t) => ({ id: t.id, label: t.label || DEFAULT_TABS.find((d) => d.id === t.id)?.label || t.id, hidden: Boolean(t.hidden) }));
    for (const d of DEFAULT_TABS) if (!ids.has(d.id)) merged.push({ id: d.id, label: d.label, hidden: false });
    return merged;
  }, [draft.tabs]);
  const setTabs = (t) => set({ tabs: t });
  const updateTab = (i, patch) => setTabs(tabs.map((t, j) => (j === i ? { ...t, ...patch } : t)));
  const moveTab = (i, dir) => { const a = [...tabs]; const j = i + dir; if (j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; setTabs(a); };

  function pickLogo(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!/^image\//.test(f.type)) { setMsg({ kind: 'err', text: 'Logo must be an image.' }); return; }
    if (f.size > 1024 * 1024) { setMsg({ kind: 'err', text: 'Logo must be ≤ 1MB.' }); return; }
    const r = new FileReader();
    r.onload = () => set({ logo: r.result });
    r.readAsDataURL(f);
  }

  async function save() {
    setSaving(true); setMsg(null);
    try {
      const d = await api.adminSaveAppearance(draft);
      const next = d.appearance || draft;
      setDraft(structuredClone(next));
      onChange?.(next);
      setMsg({ kind: 'ok', text: 'Appearance saved ✓ — live for everyone.' });
    } catch (e) { setMsg({ kind: 'err', text: 'Save failed: ' + e.message }); } finally { setSaving(false); }
  }
  function discard() { setDraft(structuredClone(appearance || {})); applyAppearance(appearance || {}); setMsg(null); }
  function resetAll() {
    if (!window.confirm('Reset all appearance to defaults? (Saves immediately.)')) return;
    setDraft({}); applyAppearance({});
    api.adminSaveAppearance({}).then((d) => { onChange?.(d.appearance || {}); setMsg({ kind: 'ok', text: 'Reset to defaults ✓' }); }).catch((e) => setMsg({ kind: 'err', text: e.message }));
  }

  return (
    <div>
      <section className="config-card">
        <h3 className="config-group-title">Branding</h3>
        <div className="config-fields">
          <div className="config-row">
            <div className="config-label"><span>Dashboard name</span></div>
            <div className="config-value">
              <input className="cfg-input" value={draft.brandName ?? ''} placeholder="Viobot Dashboard" onChange={(e) => set({ brandName: e.target.value })} />
            </div>
          </div>
          <div className="config-row">
            <div className="config-label"><span>Logo</span><span className="config-help">PNG/SVG, ≤1MB — replaces the corner mark</span></div>
            <div className="config-value brand-logo-row">
              {draft.logo && <img className="brand-logo-preview" src={draft.logo} alt="" />}
              <label className="btn btn-ghost btn-sm">{draft.logo ? 'Replace' : 'Upload'}<input type="file" accept="image/*" hidden onChange={pickLogo} /></label>
              {draft.logo && <button className="chip-x" title="Remove logo" onClick={() => set({ logo: null })}>×</button>}
            </div>
          </div>
        </div>
      </section>

      <section className="config-card">
        <h3 className="config-group-title">Theme colors</h3>
        <p className="config-help" style={{ padding: '0 0 8px' }}>Changes preview live as you edit. Leave blank to use the default.</p>
        <div className="config-fields">
          {THEME_TOKENS.map((t) => (
            <div key={t.key} className="config-row">
              <div className="config-label"><span>{t.label}</span><span className="config-help mono">{t.cssVar}</span></div>
              <div className="config-value theme-color">
                <input type="color" className="theme-swatch" value={(draft.theme?.[t.key] || t.default).slice(0, 7)} onChange={(e) => setTheme(t.key, e.target.value)} />
                <input className="cfg-input mono theme-hex" value={draft.theme?.[t.key] ?? ''} placeholder={t.default} onChange={(e) => setTheme(t.key, e.target.value)} />
                {draft.theme?.[t.key] && <button className="chip-x" title="Reset to default" onClick={() => clearTheme(t.key)}>×</button>}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="config-card">
        <h3 className="config-group-title">Server tabs</h3>
        <p className="config-help" style={{ padding: '0 0 10px' }}>Show / hide, reorder, and rename the tabs on every server's config page.</p>
        <div className="reg-fields">
          {tabs.map((t, i) => (
            <div key={t.id} className="reg-field tab-row">
              <span className="mono muted tab-id">{t.id}</span>
              <input className="cfg-input" value={t.label} onChange={(e) => updateTab(i, { label: e.target.value })} />
              <button type="button" className={`switch switch-sm ${!t.hidden ? 'switch-on' : ''}`} title={t.hidden ? 'Hidden' : 'Visible'} onClick={() => updateTab(i, { hidden: !t.hidden })}><span className="switch-knob" /></button>
              <div className="reg-actions">
                <button className="btn btn-ghost btn-sm" onClick={() => moveTab(i, -1)} disabled={i === 0}>↑</button>
                <button className="btn btn-ghost btn-sm" onClick={() => moveTab(i, 1)} disabled={i === tabs.length - 1}>↓</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="config-card">
        <h3 className="config-group-title">Guides (docs)</h3>
        <p className="config-help" style={{ padding: '0 0 8px' }}>The “Guides” item in the top menu opens a selector between the Server Setup Guide and the full Viobot Documentation. Turn it off to hide the item.</p>
        <div className="config-fields">
          <div className="config-row">
            <div className="config-label"><span>Show Guides</span></div>
            <div className="config-value">
              <button type="button" className={`switch ${draft.guidesEnabled !== false ? 'switch-on' : ''}`} title={draft.guidesEnabled === false ? 'Hidden' : 'Visible'} onClick={() => set({ guidesEnabled: draft.guidesEnabled === false })}><span className="switch-knob" /></button>
            </div>
          </div>
          <div className="config-row">
            <div className="config-label"><span>Menu label</span></div>
            <div className="config-value">
              <input className="cfg-input" value={draft.guidesLabel ?? ''} placeholder={DEFAULT_GUIDES_LABEL} onChange={(e) => set({ guidesLabel: e.target.value })} />
            </div>
          </div>
        </div>
      </section>

      <div className="appearance-foot">
        <button className="btn btn-ghost btn-sm danger-text" onClick={resetAll} disabled={saving}>Reset all to defaults</button>
      </div>

      {msg && <p className={`notice ${msg.kind === 'err' ? 'error' : 'ok'}`}>{msg.text}</p>}

      {dirty && (
        <div className="save-bar">
          <span className="save-bar-msg">Unsaved appearance — previewing live</span>
          <div className="save-bar-actions">
            <button className="btn btn-ghost" disabled={saving} onClick={discard}>Discard</button>
            <button className="btn btn-discord" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save appearance'}</button>
          </div>
        </div>
      )}
    </div>
  );
}
