import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

const MAX_BYTES = 5 * 1024 * 1024;
const OK_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];

export default function AvatarEditor({ guildId }) {
  const [data, setData] = useState(undefined); // { avatar, allowed }
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(null); // { dataUri, name }
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    setData(undefined); setError(null); setPending(null); setMsg(null);
    api.getAvatar(guildId).then(setData).catch((e) => setError(String(e.message || e)));
  }, [guildId]);

  if (error) {
    return <section className="config-card"><h3 className="config-group-title">Server avatar</h3><p className="notice error">Couldn't load avatar: {error}</p></section>;
  }
  if (data === undefined) {
    return <section className="config-card"><h3 className="config-group-title">Server avatar</h3><p className="muted">Loading…</p></section>;
  }
  if (!data.allowed) {
    return (
      <section className="config-card">
        <h3 className="config-group-title">Server avatar</h3>
        <p className="muted small" style={{ padding: '8px 0' }}>Requires <b>Plus</b> or <b>Beta</b> access for this server.</p>
      </section>
    );
  }

  function pick(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setMsg(null);
    if (!OK_TYPES.includes(f.type)) { setMsg({ kind: 'err', text: 'Use PNG, JPG, GIF, or WEBP.' }); return; }
    if (f.size > MAX_BYTES) { setMsg({ kind: 'err', text: 'Max 5MB.' }); return; }
    const reader = new FileReader();
    reader.onload = () => setPending({ dataUri: reader.result, name: f.name });
    reader.readAsDataURL(f);
  }
  async function upload() {
    if (!pending) return;
    setBusy(true); setMsg(null);
    try {
      const res = await api.setAvatar(guildId, pending.dataUri);
      setData((d) => ({ ...d, avatar: res.avatar }));
      setPending(null);
      if (fileRef.current) fileRef.current.value = '';
      setMsg({ kind: 'ok', text: 'Avatar updated ✓' });
    } catch (e) { setMsg({ kind: 'err', text: e.message }); } finally { setBusy(false); }
  }
  async function reset() {
    if (!window.confirm('Remove the custom server avatar (revert to default)?')) return;
    setBusy(true); setMsg(null);
    try {
      await api.resetAvatar(guildId);
      setData((d) => ({ ...d, avatar: null }));
      setPending(null);
      if (fileRef.current) fileRef.current.value = '';
      setMsg({ kind: 'ok', text: 'Reset to default ✓' });
    } catch (e) { setMsg({ kind: 'err', text: e.message }); } finally { setBusy(false); }
  }

  const preview = pending?.dataUri || data.avatar?.dataUri || null;

  return (
    <section className="config-card">
      <h3 className="config-group-title">Server avatar</h3>
      <p className="config-help" style={{ padding: '0 0 12px' }}>
        Viobot's avatar just for this server. PNG / JPG / GIF / WEBP, square works best, up to 5MB.
      </p>
      <div className="avatar-edit">
        <div className="avatar-box">{preview ? <img src={preview} alt="" /> : <span className="mono muted">none</span>}</div>
        <div className="avatar-side">
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/gif,image/webp" onChange={pick} className="avatar-file" />
          <div className="avatar-buttons">
            {pending && <button className="btn btn-discord btn-sm" disabled={busy} onClick={upload}>{busy ? '…' : 'Upload'}</button>}
            {data.avatar && !pending && <button className="btn btn-ghost btn-sm danger-text" disabled={busy} onClick={reset}>Reset to default</button>}
          </div>
          {msg && <span className={msg.kind === 'err' ? 'var-err' : 'muted small'}>{msg.text}</span>}
          {!msg && data.avatar?.updatedAt && !pending && <span className="muted small">Set {new Date(data.avatar.updatedAt).toLocaleDateString()}</span>}
        </div>
      </div>
    </section>
  );
}
