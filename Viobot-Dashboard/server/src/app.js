import fs from 'node:fs';
import path from 'node:path';
import Fastify from 'fastify';
import cookie from '@fastify/cookie';
import { env, oauthConfigured } from './env.js';
import { dbInfo } from './db.js';
import { getAppearance } from './dashboard/store.js';
import authRoutes from './routes/auth.js';
import guildRoutes from './routes/guilds.js';
import configRoutes from './routes/config.js';
import adminRoutes from './routes/admin.js';

// Per-route social/link-embed (Open Graph) metadata. The SPA serves the same index.html for every
// route, so scrapers (Discord/Twitter/etc.) would otherwise see one generic card — this gives `/`
// and `/guides` their own. og:image is the Viobot logo already served at /images/viobot_icon.png.
const OG_ROUTES = {
  '/': {
    title: 'Viobot Dashboard',
    description: 'Configure Viobot for your Discord server.',
    themeColor: '#22d3ee',
  },
  '/guides': {
    title: 'Viobot Guides',
    description: 'Commands and setup guides for Viobot.',
    themeColor: '#a78bfa',
  },
};

const htmlEscape = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function injectOg(indexHtml, route, path, origin) {
  const image = `${origin}/images/viobot_icon.png`;
  const url = `${origin}${path}`;
  const tags = [
    `<meta name="description" content="${htmlEscape(route.description)}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="Viobot" />`,
    `<meta property="og:title" content="${htmlEscape(route.title)}" />`,
    `<meta property="og:description" content="${htmlEscape(route.description)}" />`,
    `<meta property="og:url" content="${htmlEscape(url)}" />`,
    `<meta property="og:image" content="${htmlEscape(image)}" />`,
    `<meta name="twitter:card" content="summary" />`,
    `<meta name="twitter:title" content="${htmlEscape(route.title)}" />`,
    `<meta name="twitter:description" content="${htmlEscape(route.description)}" />`,
    `<meta name="twitter:image" content="${htmlEscape(image)}" />`,
    `<meta name="theme-color" content="${route.themeColor}" />`,
  ].join('\n    ');
  return indexHtml
    .replace(/<title>.*?<\/title>/i, `<title>${htmlEscape(route.title)}</title>`)
    .replace('</head>', `    ${tags}\n  </head>`);
}

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
      reply.header('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS');
      reply.header('Access-Control-Allow-Headers', 'Content-Type');
    }
    if (req.method === 'OPTIONS') return reply.code(204).send();
  });

  const serveStatic = Boolean(env.webDist && fs.existsSync(env.webDist));

  // Public, unauthenticated — keep it minimal. Only what the login screen needs (OAuth readiness, dev
  // login visibility, and a live DB connection check). Do NOT expose the DB path / table list / journal
  // mode here; that detail is available to admins via dbInfo() behind the admin routes.
  app.get('/api/health', async () => {
    let db;
    try {
      db = { registeredGuilds: dbInfo().registeredGuilds };
    } catch (e) {
      db = { error: String(e.message) };
    }
    return {
      ok: true,
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

    // Inject per-route link-embed (OG) meta into index.html for `/` and `/guides`. Runs before the
    // static handler; browsers ignore the extra tags, scrapers read them. Read once at startup.
    let indexHtml = null;
    try { indexHtml = fs.readFileSync(path.join(env.webDist, 'index.html'), 'utf8'); } catch { /* fall through */ }
    if (indexHtml) {
      app.addHook('onRequest', async (req, reply) => {
        if (req.method !== 'GET') return;
        const p = req.url.split('?')[0];
        const route = OG_ROUTES[p];
        if (route) reply.type('text/html').send(injectOg(indexHtml, route, p, env.publicOrigin));
      });
    }

    // Docs (Guides) served same-origin from the auto-synced docs files, so the Guides tab embeds
    // viobot.havenmap.online/docs/ — no separate subdomain. decorateReply:false so only the SPA
    // registration below owns reply.sendFile (used by the SPA fallback). Registered first = more
    // specific /docs/* and /images/* routes win over the SPA catch-all.
    const docsDir = env.docsDir;
    if (docsDir && fs.existsSync(docsDir)) {
      await app.register(fstatic, { root: docsDir, prefix: '/docs/', redirect: true, decorateReply: false });
      // The docs' only root-absolute asset is the logo at /images/*.
      const imagesDir = path.join(docsDir, 'images');
      if (fs.existsSync(imagesDir)) {
        await app.register(fstatic, { root: imagesDir, prefix: '/images/', decorateReply: false });
      }
    }

    await app.register(fstatic, { root: env.webDist, prefix: '/' });
    app.setNotFoundHandler((req, reply) => {
      if (req.method === 'GET' && !req.url.startsWith('/api')) {
        // Bare /docs → /docs/ so art3mis's reference docs load with or without the trailing slash
        // (the static docs route only matches the /docs/ prefix; without this it falls to the SPA).
        if (req.url.replace(/\?.*$/, '') === '/docs') return reply.redirect('/docs/');
        return reply.type('text/html').sendFile('index.html');
      }
      return reply.code(404).send({ error: 'not_found' });
    });
  }

  return app;
}
