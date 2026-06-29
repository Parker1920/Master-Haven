import { useEffect, useState } from 'react';
import { api } from '../api.js';

const fmt = (ms) => { try { return new Date(ms).toLocaleString(); } catch { return String(ms); } };
const toLocalInput = () => { const d = new Date(Date.now() + 3600_000); const off = d.getTimezoneOffset(); return new Date(d.getTime() - off * 60000).toISOString().slice(0, 16); };
const fromLocalInput = (v) => (v ? new Date(v).getTime() : NaN);

export default function AnnouncementsEditor({ guildId }) {
  const [data, setData] = useState(undefined);
  const [error, setError] = useState(null);
  const [channelId, setChannelId] = useState('');
  const [message, setMessage] = useState('');
  const [when, setWhen] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    setData(undefined); setError(null);
    api.getAnnouncements(guildId).then(setData).catch((e) => setError(String(e.message || e)));
  }, [guildId]);

  if (error) return null;
  if (data === undefined) {
    return <section className="config-card"><h3 className="config-group-title">Scheduled announcements</h3><p className="muted">Loading…</p></section>;
  }
  if (!data.allowed) {
    return (
      <section className="config-card">
        <h3 className="config-group-title">Scheduled announcements</h3>
        <p className="muted small" style={{ padding: '8px 0' }}>Requires <b>Plus</b> or <b>Beta</b> access for this server.</p>
      </section>
    );
  }

  const textChannels = (data.channels || []).filter((c) => [0, 5].includes(c.type));
  const canCreate = channelId && message.trim() && when && fromLocalInput(when) > Date.now();

  async function create() {
    setBusy(true); setMsg(null);
    try {
      const res = await api.createAnnouncement(guildId, { channelId, message, sendAt: fromLocalInput(when) });
      setData(res); setMessage(''); setWhen(''); setChannelId(''); setMsg({ kind: 'ok', text: 'Scheduled ✓' });
    } catch (e) { setMsg({ kind: 'err', text: e.message }); } finally { setBusy(false); }
  }
  async function cancel(id) {
    if (!window.confirm('Cancel this scheduled announcement?')) return;
    try { setData(await api.deleteAnnouncement(guildId, id)); } catch (e) { setMsg({ kind: 'err', text: e.message }); }
  }

  return (
    <section className="config-card">
      <h3 className="config-group-title">Scheduled announcements</h3>
      {data.announcements.length === 0 && <p className="val-empty" style={{ padding: '8px 0' }}>None scheduled.</p>}
      <div className="ann-list">
        {data.announcements.map((a) => {
          const ch = textChannels.find((c) => c.id === a.channelId);
          return (
            <div key={a.id} className="ann-row">
              <div className="ann-info">
                <div className="ann-meta"><span className="mono"># {ch?.name || a.channelId}</span><span className="muted small">{fmt(a.sendAt)}</span></div>
                <span className="ann-msg">{a.message}</span>
              </div>
              <button className="btn btn-ghost btn-sm danger-text" onClick={() => cancel(a.id)}>Cancel</button>
            </div>
          );
        })}
      </div>

      <div className="ann-form">
        <div className="ann-form-top">
          <select className="cfg-select" value={channelId} onChange={(e) => setChannelId(e.target.value)}>
            <option value="">Channel…</option>
            {textChannels.map((c) => <option key={c.id} value={c.id}># {c.name}</option>)}
          </select>
          <input className="cfg-input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} placeholder={toLocalInput()} />
        </div>
        <textarea className="cfg-input" placeholder="Announcement message…" value={message} maxLength={2000} onChange={(e) => setMessage(e.target.value)} />
        <div className="ann-form-actions">
          {msg && <span className={msg.kind === 'err' ? 'var-err' : 'muted small'}>{msg.text}</span>}
          <button className="btn btn-discord btn-sm" disabled={busy || !canCreate} onClick={create}>{busy ? '…' : 'Schedule'}</button>
        </div>
      </div>
    </section>
  );
}
