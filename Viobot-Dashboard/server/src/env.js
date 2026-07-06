import dotenv from 'dotenv';
dotenv.config();

const bool = (v, def) => (v === undefined ? def : String(v).toLowerCase() === 'true' || v === '1');

export const env = {
  port: Number(process.env.PORT ?? 8090),
  host: process.env.HOST ?? '0.0.0.0',
  nodeEnv: process.env.NODE_ENV ?? 'development',
  // Where the SPA lives. Empty in local dev (Vite serves it); set to the served dir in the container.
  webOrigin: process.env.WEB_ORIGIN ?? 'http://localhost:5173',
  webDist: process.env.WEB_DIST ?? '',
  // Canonical public origin — used to build absolute URLs for social/link embeds (og:image, og:url).
  publicOrigin: process.env.PUBLIC_ORIGIN ?? 'https://viobot.havenmap.online',

  discord: {
    clientId: process.env.DISCORD_CLIENT_ID ?? '',
    clientSecret: process.env.DISCORD_CLIENT_SECRET ?? '',
    redirectUri: process.env.DISCORD_REDIRECT_URI ?? 'http://localhost:5173/api/auth/callback',
    scopes: ['identify', 'guilds'],
  },

  // Dev-only login bypass for internal testing before a Discord OAuth app exists.
  // MUST be off in any real/public deployment. Treated as admin of every bot-present guild.
  devLogin: bool(process.env.DEV_LOGIN, false),
  devUser: {
    id: process.env.DEV_USER_ID ?? '0',
    name: process.env.DEV_USER_NAME ?? 'Dev Admin',
  },

  session: {
    cookieName: process.env.SESSION_COOKIE_NAME ?? 'vbd_sid',
    secret: process.env.SESSION_SECRET ?? 'dev-insecure-session-secret-change-me',
    ttlMs: Number(process.env.SESSION_TTL_MS ?? 1000 * 60 * 60 * 24),
    secure: bool(process.env.SESSION_SECURE, process.env.NODE_ENV === 'production'),
  },

  // Viobot's bot token — used server-side only, to read each guild's role/channel lists for the
  // config dropdowns (the bot is already in these guilds). Same token that runs the bot on the Pi.
  botToken: process.env.DISCORD_BOT_TOKEN ?? '',
  // Viobot Plus SKU id — to read each guild's premium entitlement status (read-only display).
  plusSkuId: process.env.VIOBOT_PLUS_SKU_ID ?? '',

  viobotDbPath: process.env.VIOBOT_DB_PATH ?? '',
  // Optional WRITE KILL-SWITCH (default OFF — the dashboard performs guarded writes by design:
  // backup-before-write + optimistic concurrency against the live Viobot DB). When VIOBOT_DB_READONLY=true,
  // the read connection is opened PRAGMA query_only=ON AND every Viobot-DB write endpoint refuses with
  // HTTP 403 (enforced in db.getWriteDb + routes/config.js). A safety switch, not the normal mode.
  dbReadonly: bool(process.env.VIOBOT_DB_READONLY, false),

  // Dashboard's own editable store (registry / admins / appearance) — separate from Viobot's DB.
  dataDir: process.env.DASHBOARD_DATA_DIR ?? '/app/dashboard-data',
  // The Viobot docs site's built files (the same dir the docs container serves + auto-syncs). Mounted
  // read-only so the dashboard can serve them same-origin at /docs — powers the Guides tab without a
  // separate subdomain. Empty/absent → /docs isn't served (Guides can point elsewhere via appearance).
  docsDir: process.env.DASHBOARD_DOCS_DIR ?? '/app/docs-content',
  // Bootstrap dashboard admins (Discord IDs). Default = Viobot's bot owner (art3mis).
  adminIds: (process.env.DASHBOARD_ADMIN_IDS ?? '1182179988150177812').split(',').map((s) => s.trim()).filter(Boolean),
};

export const oauthConfigured = () => Boolean(env.discord.clientId && env.discord.clientSecret);
export const redirectTo = (p = '/') => `${env.webOrigin || ''}${p}`;

// Startup safety guard: refuse to boot a PRODUCTION process with insecure defaults. Called from
// index.js (NOT at import) so tests/tooling can import this module freely; only the real server boot
// enforces it. In development it is a no-op.
export function assertProductionEnv() {
  if (env.nodeEnv !== 'production') return;
  const problems = [];
  if (!process.env.SESSION_SECRET || env.session.secret === 'dev-insecure-session-secret-change-me') {
    problems.push('SESSION_SECRET must be a strong random value (refusing to run with the committed default).');
  }
  if (env.devLogin) {
    problems.push('DEV_LOGIN must be OFF in production (it grants admin of every bot-present guild).');
  }
  if (!env.session.secure) {
    problems.push('SESSION_SECURE must be true in production (secure cookies over HTTPS).');
  }
  if (problems.length) {
    throw new Error('Refusing to start in production:\n  - ' + problems.join('\n  - '));
  }
}
