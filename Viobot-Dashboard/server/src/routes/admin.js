import { env } from '../env.js';
import { readSession } from '../framework/requireAuth.js';
import { getRegistry, setRegistry, getStoredAdmins, setStoredAdmins, isDashboardAdmin, getAppearance, setAppearance } from '../dashboard/store.js';
import { getContainerStatus, restartContainer, stopContainer, startContainer, requestReimage } from '../dashboard/dockerControl.js';
import { streamContainerLogs, isLogContainerAllowed } from '../dashboard/dockerLogs.js';

function requireAdmin(req, reply) {
  const { session } = readSession(req);
  if (!session?.user) { reply.code(401).send({ error: 'not_authenticated' }); return null; }
  if (!isDashboardAdmin(session.user.id)) { reply.code(403).send({ error: 'forbidden' }); return null; }
  return session;
}

export default async function adminRoutes(app) {
  // Config registry — what fields render in each server's tabs (the "modular config system").
  app.get('/api/admin/registry', async (req, reply) => {
    if (!requireAdmin(req, reply)) return;
    return { registry: getRegistry() };
  });

  app.put('/api/admin/registry', async (req, reply) => {
    if (!requireAdmin(req, reply)) return;
    try {
      return { ok: true, registry: setRegistry((req.body || {}).registry) };
    } catch (e) {
      return reply.code(400).send({ error: 'invalid', message: String(e.message) });
    }
  });

  // Dashboard admin allow-list. Env admins are the immovable bootstrap; stored admins are editable here.
  app.get('/api/admin/admins', async (req, reply) => {
    if (!requireAdmin(req, reply)) return;
    return { envAdmins: env.adminIds, storedAdmins: getStoredAdmins() };
  });

  app.put('/api/admin/admins', async (req, reply) => {
    if (!requireAdmin(req, reply)) return;
    return { ok: true, envAdmins: env.adminIds, storedAdmins: setStoredAdmins((req.body || {}).admins) };
  });

  // Appearance (theme / brand / logo / tabs / custom CSS). Larger body limit for a logo data URI.
  app.put('/api/admin/appearance', { bodyLimit: 4 * 1024 * 1024 }, async (req, reply) => {
    if (!requireAdmin(req, reply)) return;
    return { ok: true, appearance: setAppearance((req.body || {}).appearance) };
  });

  // Viobot container control (restart to apply config). Restricted to the viobot container in code.
  app.get('/api/admin/bot-status', async (req, reply) => {
    if (!requireAdmin(req, reply)) return;
    try { return await getContainerStatus('viobot'); }
    catch (e) { return reply.code(502).send({ error: 'docker_unavailable', message: String(e.message) }); }
  });

  app.post('/api/admin/restart-bot', async (req, reply) => {
    if (!requireAdmin(req, reply)) return;
    try { await restartContainer('viobot'); return { ok: true }; }
    catch (e) {
      if (e.code === 'NOTFOUND') return reply.code(404).send({ error: 'not_found' });
      return reply.code(502).send({ error: 'docker_unavailable', message: String(e.message) });
    }
  });

  app.post('/api/admin/bot/stop', async (req, reply) => {
    if (!requireAdmin(req, reply)) return;
    try { return await stopContainer('viobot'); }
    catch (e) {
      if (e.code === 'NOTFOUND') return reply.code(404).send({ error: 'not_found' });
      return reply.code(502).send({ error: 'docker_unavailable', message: String(e.message) });
    }
  });

  app.post('/api/admin/bot/start', async (req, reply) => {
    if (!requireAdmin(req, reply)) return;
    try { return await startContainer('viobot'); }
    catch (e) {
      if (e.code === 'NOTFOUND') return reply.code(404).send({ error: 'not_found' });
      return reply.code(502).send({ error: 'docker_unavailable', message: String(e.message) });
    }
  });

  // Reimage = drop a flag file for the host cron to rebuild + recreate viobot (see viobot-rebuild-watch.sh).
  app.post('/api/admin/bot/reimage', async (req, reply) => {
    if (!requireAdmin(req, reply)) return;
    try { return requestReimage(); }
    catch (e) { return reply.code(500).send({ error: 'reimage_failed', message: String(e.message) }); }
  });

  // Live log feed (SSE). Survives container restarts; reads the Docker socket only — the bot is untouched.
  app.get('/api/admin/bot-logs/stream', async (req, reply) => {
    if (!requireAdmin(req, reply)) return;
    const name = String(req.query.container || 'viobot');
    if (!isLogContainerAllowed(name)) return reply.code(400).send({ error: 'container_not_allowed' });
    const tail = Math.min(Math.max(parseInt(req.query.tail, 10) || 200, 0), 2000);

    reply.hijack();
    const raw = reply.raw;
    raw.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no', // tell NPM/nginx not to buffer the stream
    });
    raw.write(': connected\n\n');

    const sse = (event, data) => { try { raw.write((event ? `event: ${event}\n` : '') + `data: ${data}\n\n`); } catch { /* closed */ } };
    let stop = () => {};
    try {
      stop = streamContainerLogs(name, {
        tail,
        handlers: { line: (t) => sse(null, t), notice: (t) => sse('notice', t) },
      });
    } catch (e) {
      sse('fatal', String(e.message));
      return raw.end();
    }

    const hb = setInterval(() => { try { raw.write(': ping\n\n'); } catch { /* closed */ } }, 15000);
    const cleanup = () => { clearInterval(hb); try { stop(); } catch { /* ignore */ } try { raw.end(); } catch { /* ignore */ } };
    req.raw.on('close', cleanup);
    req.raw.on('error', cleanup);
  });
}
