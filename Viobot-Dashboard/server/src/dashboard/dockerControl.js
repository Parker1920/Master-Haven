import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { env } from '../env.js';

// Talks to the Docker Engine API over the host socket. HARD-restricted to the containers below —
// the dashboard can never touch anything else, even though the socket itself is privileged.
const SOCKET = '/var/run/docker.sock';
const ALLOWED = new Set(['viobot']);

function dockerRequest(method, urlPath) {
  return new Promise((resolve, reject) => {
    const req = http.request({ socketPath: SOCKET, method, path: urlPath }, (res) => {
      let body = '';
      res.on('data', (d) => { body += d; });
      res.on('end', () => resolve({ status: res.statusCode, body }));
    });
    req.on('error', reject);
    req.setTimeout(90000, () => req.destroy(new Error('docker request timed out')));
    req.end();
  });
}

export async function getContainerStatus(name) {
  if (!ALLOWED.has(name)) { const e = new Error('container not allowed'); e.code = 'FORBIDDEN'; throw e; }
  const res = await dockerRequest('GET', `/containers/${encodeURIComponent(name)}/json`);
  if (res.status === 404) return { exists: false };
  if (res.status !== 200) { const e = new Error(`docker ${res.status}`); e.code = 'DOCKER'; throw e; }
  const data = JSON.parse(res.body);
  return { exists: true, status: data.State?.Status ?? 'unknown', startedAt: data.State?.StartedAt ?? null };
}

export async function restartContainer(name) {
  if (!ALLOWED.has(name)) { const e = new Error('container not allowed'); e.code = 'FORBIDDEN'; throw e; }
  const res = await dockerRequest('POST', `/containers/${encodeURIComponent(name)}/restart?t=10`);
  if (res.status === 204) return { ok: true };
  if (res.status === 404) { const e = new Error('container not found'); e.code = 'NOTFOUND'; throw e; }
  const e = new Error(`restart failed: ${res.status} ${res.body.slice(0, 160)}`);
  e.code = 'DOCKER';
  throw e;
}

export async function stopContainer(name) {
  if (!ALLOWED.has(name)) { const e = new Error('container not allowed'); e.code = 'FORBIDDEN'; throw e; }
  const res = await dockerRequest('POST', `/containers/${encodeURIComponent(name)}/stop?t=10`);
  if (res.status === 204 || res.status === 304) return { ok: true, already: res.status === 304 };
  if (res.status === 404) { const e = new Error('container not found'); e.code = 'NOTFOUND'; throw e; }
  const e = new Error(`stop failed: ${res.status} ${res.body.slice(0, 160)}`); e.code = 'DOCKER'; throw e;
}

export async function startContainer(name) {
  if (!ALLOWED.has(name)) { const e = new Error('container not allowed'); e.code = 'FORBIDDEN'; throw e; }
  const res = await dockerRequest('POST', `/containers/${encodeURIComponent(name)}/start`);
  if (res.status === 204 || res.status === 304) return { ok: true, already: res.status === 304 };
  if (res.status === 404) { const e = new Error('container not found'); e.code = 'NOTFOUND'; throw e; }
  const e = new Error(`start failed: ${res.status} ${res.body.slice(0, 160)}`); e.code = 'DOCKER'; throw e;
}

// Reimage = rebuild the viobot image + recreate. The socket API can't build, so drop a flag file that
// the host-side cron (viobot-rebuild-watch.sh) picks up and runs `docker compose up -d --build viobot`.
export function requestReimage() {
  const dir = path.join(env.dataDir, 'actions');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'rebuild-viobot'), new Date().toISOString());
  return { ok: true, queued: true };
}
