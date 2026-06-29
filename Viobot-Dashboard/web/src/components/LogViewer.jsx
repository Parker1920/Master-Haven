import { useEffect, useRef, useState } from 'react';

const CONTAINERS = [
  { id: 'viobot', label: 'Viobot' },
  { id: 'viobot-dashboard', label: 'Dashboard' },
];
const MAX_LINES = 2000;

// Logs come in as "2026-...Z message" (timestamps=1). Split the ISO stamp into a dim HH:MM:SS.
function parseLine(text) {
  const sp = text.indexOf(' ');
  const ts = sp > 0 ? text.slice(0, sp) : '';
  if (/^\d{4}-\d\d-\d\dT/.test(ts)) {
    const d = new Date(ts);
    const time = Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString([], { hour12: false });
    return { time, msg: text.slice(sp + 1) };
  }
  return { time: '', msg: text };
}

export default function LogViewer() {
  const [container, setContainer] = useState('viobot');
  const [status, setStatus] = useState('connecting');
  const [lines, setLines] = useState([]);
  const [autoscroll, setAutoscroll] = useState(true);
  const boxRef = useRef(null);
  const autoRef = useRef(true);
  autoRef.current = autoscroll;

  useEffect(() => {
    setLines([]); setStatus('connecting');
    const es = new EventSource(`/api/admin/bot-logs/stream?container=${encodeURIComponent(container)}&tail=400`);
    es.onopen = () => setStatus('live');
    es.onmessage = (e) => setLines((prev) => {
      const next = prev.concat({ k: 'log', t: e.data });
      return next.length > MAX_LINES ? next.slice(-MAX_LINES) : next;
    });
    es.addEventListener('notice', (e) => { setStatus('reconnecting'); setLines((prev) => prev.concat({ k: 'notice', t: e.data })); });
    es.addEventListener('fatal', (e) => { setStatus('error'); setLines((prev) => prev.concat({ k: 'notice', t: e.data })); });
    es.onerror = () => setStatus((s) => (s === 'live' ? 'reconnecting' : s)); // EventSource auto-reconnects
    return () => es.close();
  }, [container]);

  useEffect(() => {
    if (autoRef.current && boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight;
  }, [lines]);

  function onScroll(e) {
    const el = e.currentTarget;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    if (atBottom !== autoRef.current) setAutoscroll(atBottom);
  }

  const statusClass = status === 'live' ? 'pill-on' : status === 'error' ? 'pill-off' : 'pill-warn';

  return (
    <section className="config-card">
      <p className="config-help" style={{ padding: '0 0 12px' }}>
        Live <code>docker logs</code> — streams straight through a Restart (you'll see it shut down and boot back up). Read-only; the bot isn't touched.
      </p>
      <div className="logs-head">
        <div className="logs-controls">
          <select className="cfg-select cfg-select-sm" value={container} onChange={(e) => setContainer(e.target.value)}>
            {CONTAINERS.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
          <span className={`pill ${statusClass}`}>{status}</span>
        </div>
        <div className="logs-controls">
          <label className="logs-check"><input type="checkbox" checked={autoscroll} onChange={(e) => setAutoscroll(e.target.checked)} /> Auto-scroll</label>
          <button className="btn btn-ghost btn-sm" onClick={() => setLines([])}>Clear</button>
        </div>
      </div>
      <pre className="logs-box" ref={boxRef} onScroll={onScroll}>
        {lines.length === 0
          ? <span className="muted">Waiting for logs…</span>
          : lines.map((l, i) => (
              l.k === 'notice'
                ? <div key={i} className="log-notice">── {l.t} ──</div>
                : <LogLine key={i} text={l.t} />
            ))}
      </pre>
    </section>
  );
}

function LogLine({ text }) {
  const { time, msg } = parseLine(text);
  return <div className="log-line">{time && <span className="log-time">{time}</span>}{msg}</div>;
}
