import fs from 'node:fs';
import Fastify from 'fastify';
import cookie from '@fastify/cookie';
import { env, oauthConfigured } from './env.js';
import { dbInfo } from './db.js';
import { getAppearance } from './dashboard/store.js';
import authRoutes from './routes/auth.js';
import guildRoutes from './routes/guilds.js';
import configRoutes from './routes/config.js';
import adminRoutes from './routes/admin.js';

export async function buildApp(opts = {}) {
  const app = Fastify({ logger: opts.logger ?? true });

  await app.register(cookie, { secret: env.session.secret });

  // CORS for the Vite dev server. In the container the SPA is served same-origin (static, below), so
  // this only matters for cross-origin dev; it only ever echoes the configured web origin.
  app.addHook('onRequest', async (req, reply) => {
    const origin = req.headers.origin;
    if (origin && origin === env.webOrigin) {
      reply.header('Access-Control-Allow-Origin', origin);
      reply.header('Access-Control-Allow-Credentials', 'true');
      reply.header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
      reply.header('Access-Control-Allow-Headers', 'Content-Type');
    }
    if (req.method === 'OPTIONS') return reply.code(204).send();
  });

  const serveStatic = Boolean(env.webDist && fs.existsSync(env.webDist));

  app.get('/api/health', async () => {
    let db;
    try {
      db = dbInfo();
    } catch (e) {
      db = { error: String(e.message) };
    }
    return {
      ok: true,
      phase: 1,
      oauthConfigured: oauthConfigured(),
      devLogin: env.devLogin,
      serveStatic,
      db,
    };
  });

  // Public: the dashboard's appearance (theme/brand/tabs) — needed to render before login.
  app.get('/api/appearance', async () => ({ appearance: getAppearance() }));

  await app.register(authRoutes);
  await app.register(guildRoutes);
  await app.register(configRoutes);
  await app.register(adminRoutes);

  // Serve the built SPA (production/container). SPA fallback for client-side routes; /api still 404s JSON.
  if (serveStatic) {
    const fstatic = (await import('@fastify/static')).default;
    await app.register(fstatic, { root: env.webDist, prefix: '/' });
    app.setNotFoundHandler((req, reply) => {
      if (req.method === 'GET' && !req.url.startsWith('/api')) {
        return reply.type('text/html').sendFile('index.html');
      }
      return reply.code(404).send({ error: 'not_found' });
    });
  }

  return app;
}
