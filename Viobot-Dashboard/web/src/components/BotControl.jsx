import { useEffect, useState } from 'react';
import { api } from '../api.js';

export default function BotControl() {
  const [status, setStatus] = useState(undefined);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  function load() {
    setStatus(undefined);
    api.adminBotStatus().then(setStatus).catch(() => setStatus({ error: true }));
  }
  useEffect(load, []);

  async function restart() {
    if (!window.confirm('Restart Viobot now?\n\nThe bot briefly goes offline (~10s) in ALL servers while it reloads. Settings/category changes take effect after this.')) return;
    setBusy(true);
    setMsg(null);
    try {
      await api.adminRestartBot();
      setMsg({ kind: 'ok', text: 'Restarting Viobot… give it ~10–20s, then it’s back with the latest config.' });
      setTimeout(load, 14000);
    } catch (e) {
      setMsg({ kind: 'err', text: 'Failed: ' + e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="config-card">
      <h3 className="config-group-title">Viobot</h3>
      <p className="config-help" style={{ padding: '0 0 14px' }}>
        Restart the bot to apply <b>Settings</b> / <b>category</b> changes — the bot caches each server's config until it reloads.
        This briefly drops Viobot in <b>all</b> servers (~10s). Variables, aliases, announcements, and avatars don't need this.
      </p>
      <div className="bot-control">
        <div className="bot-status">
          <span className="config-label"><span>Status</span></span>
          {status === undefined ? (
            <span className="muted">checking…</span>
          ) : status.error ? (
            <span className="pill pill-off">unavailable</span>
          ) : (
            <span className={`pill ${status.status === 'running' ? 'pill-on' : 'pill-off'}`}>{status.status || '?'}</span>
          )}
          {status?.startedAt && <span className="muted small">up since {new Date(status.startedAt).toLocaleString()}</span>}
        </div>
        <button className="btn btn-discord btn-sm" onClick={restart} disabled={busy}>{busy ? '…' : 'Restart Viobot'}</button>
      </div>
      {msg && <p className={`notice ${msg.kind === 'err' ? 'error' : 'ok'}`}>{msg.text}</p>}
    </section>
  );
}
