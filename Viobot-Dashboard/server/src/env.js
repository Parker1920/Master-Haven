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

  viobotDbPath: process.env.VIOBOT_DB_PATH ?? '',
  // Phase 1 reads only. The connection is opened read-write (so WAL shared-memory works against the
  // LIVE db) but PRAGMA query_only=ON guarantees no data writes. Flip to false only in Phase 2.
  dbReadonly: bool(process.env.VIOBOT_DB_READONLY, true),
};

export const oauthConfigured = () => Boolean(env.discord.clientId && env.discord.clientSecret);
export const redirectTo = (p = '/') => `${env.webOrigin || ''}${p}`;
