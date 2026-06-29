import http from 'node:http';

// Streams a container's Docker logs over the host socket. Read-only; never touches the bot process.
// Allow-listed in code (same posture as dockerControl).
const SOCKET = '/var/run/docker.sock';
const ALLOWED = new Set(['viobot', 'viobot-dashboard']);

export function isLogContainerAllowed(name) { return ALLOWED.has(name); }

function inspectTty(name) {
  return new Promise((resolve) => {
    const req = http.request({ socketPath: SOCKET, method: 'GET', path: `/containers/${encodeURIComponent(name)}/json` }, (res) => {
      let b = '';
      res.on('data', (d) => { b += d; });
      res.on('end', () => { try { resolve(Boolean(JSON.parse(b)?.Config?.Tty)); } catch { resolve(false); } });
    });
    req.on('error', () => resolve(false));
    req.setTimeout(5000, () => { req.destroy(); resolve(false); });
    req.end();
  });
}

// Docker multiplexes non-TTY streams: each frame = [type(1) 0 0 0 size(4 BE)] + size bytes of payload.
// Frames span socket chunks arbitrarily, so this is a stateful de-framer that yields decoded text.
function makeDemuxer(onText) {
  let buf = Buffer.alloc(0);
  return (chunk) => {
    buf = buf.length ? Buffer.concat([buf, chunk]) : chunk;
    while (buf.length >= 8) {
      const size = buf.readUInt32BE(4);
      if (buf.length < 8 + size) break;
      onText(buf.subarray(8, 8 + size).toString('utf8'));
      buf = buf.subarray(8 + size);
    }
  };
}

/**
 * Follow a container's logs, surviving restarts. Reconnect is keyed on the container NAME and uses
 * `since=<last timestamp>`, so a `docker restart` (same id) streams straight through, and a recreate
 * (new id) is picked up on the next reconnect with no gap. Returns a stop() function.
 */
export function streamContainerLogs(name, { tail = 200, handlers }) {
  if (!ALLOWED.has(name)) throw new Error('container not allowed');
  let stopped = false;
  let activeReq = null;
  let lastTs = null;

  function connectOnce() {
    return new Promise((resolve) => {
      inspectTty(name).then((tty) => {
        if (stopped) return resolve();
        const qs = new URLSearchParams({ stdout: '1', stderr: '1', follow: '1', timestamps: '1' });
        if (lastTs) qs.set('since', lastTs); else qs.set('tail', String(tail));
        const req = http.request({ socketPath: SOCKET, method: 'GET', path: `/containers/${encodeURIComponent(name)}/logs?${qs}` }, (res) => {
          if (res.statusCode !== 200) { res.resume(); return resolve(); }
          let lineBuf = '';
          const handleText = (text) => {
            lineBuf += text;
            let i;
            while ((i = lineBuf.indexOf('\n')) >= 0) {
              emitLine(lineBuf.slice(0, i).replace(/\r$/, ''));
              lineBuf = lineBuf.slice(i + 1);
            }
          };
          const feed = tty ? (c) => handleText(c.toString('utf8')) : makeDemuxer(handleText);
          res.on('data', (c) => feed(c));
          res.on('end', resolve);
          res.on('error', resolve);
        });
        req.on('error', resolve);
        req.end();
        activeReq = req;
      });
    });
  }

  function emitLine(raw) {
    if (!raw) return;
    const sp = raw.indexOf(' ');
    const ts = sp > 0 ? raw.slice(0, sp) : '';
    if (/^\d{4}-\d\d-\d\dT/.test(ts)) lastTs = ts;
    handlers.line(raw);
  }

  (async () => {
    let first = true;
    while (!stopped) {
      if (!first) handlers.notice?.('reconnecting…');
      first = false;
      await connectOnce();
      if (stopped) break;
      await new Promise((r) => setTimeout(r, 1000)); // container is mid-restart; back off then resume via `since`
    }
  })();

  return function stop() { stopped = true; try { activeReq?.destroy(); } catch { /* ignore */ } };
}
