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

  async function act(action, confirmMsg, okMsg, reloadDelay = 12000) {
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    setBusy(true);
    setMsg(null);
    try {
      await api.adminBotAction(action);
      setMsg({ kind: 'ok', text: okMsg });
      if (reloadDelay) setTimeout(load, reloadDelay);
    } catch (e) {
      setMsg({ kind: 'err', text: `Failed: ${e.message}` });
    } finally {
      setBusy(false);
    }
  }

  const running = status && !status.error && status.status === 'running';

  return (
    <section className="config-card">
      <h3 className="config-group-title">Viobot</h3>
      <p className="config-help" style={{ padding: '0 0 14px' }}>
        <b>Restart</b> applies Settings/category changes (~10s). <b>Reimage</b> pulls the latest code and rebuilds.
        <b> Off/On</b> is a hard stop/start. All of these affect the bot in <b>every</b> server.
      </p>
      <div className="bot-status">
        <span className="config-label"><span>Status</span></span>
        {status === undefined ? (
          <span className="muted">checking…</span>
        ) : status.error ? (
          <span className="pill pill-off">unavailable</span>
        ) : (
          <span className={`pill ${running ? 'pill-on' : 'pill-off'}`}>{status.status || '?'}</span>
        )}
        {status?.startedAt && running && <span className="muted small">up since {new Date(status.startedAt).toLocaleString()}</span>}
      </div>
      <div className="bot-actions">
        <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => act('start', null, 'Starting Viobot…', 4000)}>Turn on</button>
        <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => act('stop', 'Turn OFF Viobot?\n\nIt goes offline in ALL servers until you turn it back on.', 'Stopping Viobot…', 4000)}>Turn off</button>
        <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => act('restart', 'Restart Viobot?\n\n~10s offline in ALL servers while it reloads. Applies Settings/category changes.', 'Restarting Viobot… ~10–20s.', 12000)}>Restart</button>
        <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => act('reimage', 'Reimage Viobot?\n\nPulls the latest code and rebuilds the container — brief downtime during the recreate (~1 min). Watch the Logs tab.', 'Reimage queued — watch the Logs tab (~1 min).', 30000)}>Reimage</button>
      </div>
      {msg && <p className={`notice ${msg.kind === 'err' ? 'error' : 'ok'}`}>{msg.text}</p>}
    </section>
  );
}
