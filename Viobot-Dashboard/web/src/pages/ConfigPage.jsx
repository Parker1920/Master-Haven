import { useEffect, useMemo, useState } from 'react';
import { api } from '../api.js';
import Footer from '../components/Footer.jsx';
import VariablesEditor from '../components/VariablesEditor.jsx';
import AliasesEditor from '../components/AliasesEditor.jsx';
import PlusBetaView from '../components/PlusBetaView.jsx';
import TopBar from '../components/TopBar.jsx';
import { initials, guildIconUrl, fallbackGradient } from '../util.js';
import { visibleTabs } from '../appearance.js';

const TEXTISH = new Set([0, 5]); // text + announcement channels
const CONFIG_TABS = new Set(['settings', 'tickets']); // tabs that edit config_json (shared save bar)
const RESERVED_CAT = new Set(['report-user', 'other']);
const DEFAULT_CATS = [
  { id: 'report-user', label: 'Report a user' },
  { id: 'other', label: 'Other' },
];
const slugify = (s) => String(s || '').toLowerCase().trim().replace(/['"]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80);

const getPath = (o, p) => p.split('.').reduce((x, k) => (x == null ? undefined : x[k]), o);
function setPath(obj, p, v) {
  const ks = p.split('.');
  const root = structuredClone(obj);
  let c = root;
  for (let i = 0; i < ks.length - 1; i++) {
    if (c[ks[i]] == null || typeof c[ks[i]] !== 'object') c[ks[i]] = {};
    c = c[ks[i]];
  }
  c[ks[ks.length - 1]] = v;
  return root;
}

function RoleSelect({ value, roles, onChange }) {
  const missing = value && !roles.some((r) => r.id === value);
  return (
    <select className="cfg-select" value={value || ''} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">— None —</option>
      {missing && <option value={value}>Unknown role ({value})</option>}
      {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
    </select>
  );
}
function ChannelSelect({ value, channels, onChange }) {
  const opts = channels.filter((c) => TEXTISH.has(c.type));
  const missing = value && !opts.some((c) => c.id === value);
  return (
    <select className="cfg-select" value={value || ''} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">— None —</option>
      {missing && <option value={value}>Unknown channel ({value})</option>}
      {opts.map((c) => <option key={c.id} value={c.id}># {c.name}</option>)}
    </select>
  );
}
function Toggle({ on, onChange, sm }) {
  return (
    <button type="button" className={`switch ${sm ? 'switch-sm' : ''} ${on ? 'switch-on' : ''}`} onClick={() => onChange(!on)} aria-pressed={on}>
      <span className="switch-knob" />
    </button>
  );
}
function RoleMulti({ values, roles, onChange }) {
  const arr = Array.isArray(values) ? values : [];
  const available = roles.filter((r) => !arr.includes(r.id));
  return (
    <div className="role-multi">
      <div className="chips">
        {arr.length === 0 && <span className="val-empty">None</span>}
        {arr.map((id) => {
          const r = roles.find((x) => x.id === id);
          return (
            <span key={id} className="chip">
              <span className="tag-dot" style={{ background: r?.color || 'var(--faint)' }} />
              {r?.name ?? id}
              <button type="button" className="chip-x" onClick={() => onChange(arr.filter((v) => v !== id))}>×</button>
            </span>
          );
        })}
      </div>
      {available.length > 0 && (
        <select className="cfg-select cfg-select-sm" value="" onChange={(e) => { if (e.target.value) onChange([...arr, e.target.value]); }}>
          <option value="">+ Add role…</option>
          {available.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
      )}
    </div>
  );
}

function PlainSelect({ value, options, onChange }) {
  const opts = (options || []).map((o) => (o && typeof o === 'object' ? o : { value: o, label: String(o) }));
  return (
    <select className="cfg-select" value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">— None —</option>
      {opts.map((o) => <option key={o.value} value={o.value}>{o.label ?? o.value}</option>)}
    </select>
  );
}

function FieldEditor({ field, value, roles, channels, onChange }) {
  switch (field.type) {
    case 'role': return <RoleSelect value={value} roles={roles} onChange={onChange} />;
    case 'channel': return <ChannelSelect value={value} channels={channels} onChange={onChange} />;
    case 'bool': return <Toggle on={Boolean(value)} onChange={onChange} />;
    case 'role[]': return <RoleMulti values={value} roles={roles} onChange={onChange} />;
    case 'string':
      return <input className="cfg-select" style={{ cursor: 'text' }} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />;
    case 'number':
      return <input className="cfg-select" style={{ cursor: 'text' }} type="number" value={value ?? ''} onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} />;
    case 'select':
      return <PlainSelect value={value} options={field.options} onChange={onChange} />;
    default: return null;
  }
}

function CategoryEditor({ categories, onChange }) {
  const cats = Array.isArray(categories) ? categories : [];
  const setCat = (i, patch) => onChange(cats.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  return (
    <section className="config-card">
      <div className="vars-head">
        <h3 className="config-group-title">Custom Contact-Us categories</h3>
        <button className="btn btn-ghost btn-sm" onClick={() => onChange([...cats, { label: '', description: '', enabled: true }])} disabled={cats.length >= 10}>
          + Add category
        </button>
      </div>
      <p className="config-help" style={{ padding: '0 0 8px' }}>
        Extra options in the Contact Us menu (max 10). The ticket system itself is toggled in <b>Settings</b>. These two defaults always exist:
      </p>
      <div className="cat-defaults">
        {DEFAULT_CATS.map((d) => (
          <span key={d.id} className="chip"><span className="tag-dot" style={{ background: 'var(--faint)' }} />{d.label} <span className="mono muted" style={{ fontSize: 11 }}>{d.id}</span></span>
        ))}
      </div>

      {cats.length === 0 && <p className="val-empty" style={{ padding: '10px 0' }}>No custom categories yet.</p>}

      <div className="cat-rows">
        {cats.map((c, i) => {
          const id = c.id || slugify(c.label);
          const bad = id && RESERVED_CAT.has(id);
          return (
            <div key={i} className="cat-row">
              <div className="cat-fields">
                <input className="cfg-input" placeholder="Label (e.g. Event Help)" value={c.label || ''} onChange={(e) => setCat(i, { label: e.target.value })} />
                <input className="cfg-input" placeholder="Description (optional)" value={c.description || ''} onChange={(e) => setCat(i, { description: e.target.value })} />
              </div>
              <div className="cat-meta">
                <span className={`mono cat-id ${bad ? 'cat-id-bad' : ''}`}>{id || '—'}{bad ? ' · reserved' : ''}</span>
                <Toggle sm on={c.enabled !== false} onChange={(v) => setCat(i, { enabled: v })} />
                <button className="chip-x" title="Remove" onClick={() => onChange(cats.filter((_, j) => j !== i))}>×</button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function ConfigPage({ user, guild, appearance, isAdmin, onBack, onGuides, onLogout }) {
  const tabs = visibleTabs(appearance);
  const [data, setData] = useState(undefined);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState(null);
  const [tab, setTab] = useState(() => tabs[0]?.id || 'settings');

  function load() {
    setData(undefined);
    setDraft(null);
    setError(null);
    setSaveMsg(null);
    api
      .getGuildConfig(guild.id)
      .then((d) => { setData(d); setDraft(structuredClone(d.config)); })
      .catch((e) => setError(String(e.message || e)));
  }
  useEffect(load, [guild.id]);

  const dirty = useMemo(() => data && draft && JSON.stringify(draft) !== JSON.stringify(data.config), [data, draft]);
  const update = (path, v) => { setDraft((d) => setPath(d, path, v)); setSaveMsg(null); };

  async function save() {
    setSaving(true);
    setSaveMsg(null);
    try {
      const res = await api.saveGuildConfig(guild.id, draft, data.updatedAt);
      setData((d) => ({ ...d, config: res.config, updatedAt: res.updatedAt }));
      setDraft(structuredClone(res.config));
      setSaveMsg({ kind: 'ok', text: 'Saved ✓ — Viobot applies config on its next reload (restart the bot to see it live now).' });
    } catch (e) {
      if (e.status === 409) {
        setSaveMsg({ kind: 'err', text: 'Someone changed this config while you were editing — reloading the latest…' });
        setTimeout(load, 1000);
      } else {
        setSaveMsg({ kind: 'err', text: `Save failed: ${e.message}` });
      }
    } finally {
      setSaving(false);
    }
  }

  const gIcon = guildIconUrl(guild);

  return (
    <div className="page">
      <TopBar
        appearance={appearance}
        user={user}
        isAdmin={isAdmin}
        back={{ label: '‹ Servers', onClick: onBack }}
        onGuides={onGuides}
        onLogout={onLogout}
      />

      <main className="container">
        <div className="config-head">
          {gIcon ? (
            <img className="config-icon" src={gIcon} alt="" />
          ) : (
            <span className="config-icon config-icon--fallback" style={{ background: fallbackGradient(guild.name) }}>
              {initials(guild.name)}
            </span>
          )}
          <div>
            <h2>{guild.name}</h2>
            <p className="muted small">Viobot configuration</p>
          </div>
        </div>

        {error && <p className="notice error">Couldn't load config: {error}</p>}
        {data === undefined && !error && <p className="muted">Loading configuration…</p>}

        {data && draft && (
          <>
            <div className="config-tabs">
              {tabs.map((t) => (
                <button key={t.id} className={`config-tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>{t.label}</button>
              ))}
            </div>

            {data.lookupError && tab === 'settings' && (
              <p className="notice">Couldn't load role/channel names ({data.lookupError}); pickers may be limited.</p>
            )}

            {tab === 'settings' &&
              data.registry.groups.map((group) => (
                <section key={group.id} className="config-card">
                  <h3 className="config-group-title">{group.label}</h3>
                  <div className="config-fields">
                    {group.fields.map((field) => (
                      <div key={field.path} className="config-row">
                        <div className="config-label">
                          <span>{field.label}{field.testing && <span className="pill pill-warn testing-tag">testing</span>}</span>
                          {field.help && <span className="config-help">{field.help}</span>}
                        </div>
                        <div className="config-value">
                          <FieldEditor
                            field={field}
                            value={getPath(draft, field.path)}
                            roles={data.roles}
                            channels={data.channels}
                            onChange={(v) => update(field.path, v)}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              ))}

            {tab === 'tickets' && (
              <CategoryEditor
                categories={getPath(draft, 'tickets.customContactCategories')}
                onChange={(next) => update('tickets.customContactCategories', next)}
              />
            )}

            {tab === 'variables' && <VariablesEditor guildId={guild.id} />}
            {tab === 'aliases' && <AliasesEditor guildId={guild.id} />}
            {tab === 'plus' && <PlusBetaView guildId={guild.id} />}

            {saveMsg && CONFIG_TABS.has(tab) && (
              <p className={`notice ${saveMsg.kind === 'err' ? 'error' : 'ok'}`}>{saveMsg.text}</p>
            )}
          </>
        )}
      </main>

      {dirty && CONFIG_TABS.has(tab) && (
        <div className="save-bar">
          <span className="save-bar-msg">You have unsaved changes</span>
          <div className="save-bar-actions">
            <button className="btn btn-ghost" disabled={saving} onClick={() => setDraft(structuredClone(data.config))}>Discard</button>
            <button className="btn btn-discord" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save changes'}</button>
          </div>
        </div>
      )}
      <Footer />
    </div>
  );
}
