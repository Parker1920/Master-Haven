import crypto from 'node:crypto';
import { env, oauthConfigured, redirectTo } from '../env.js';
import { buildAuthUrl, exchangeCode, fetchUser, fetchUserGuilds } from '../framework/oauth.js';
import { createSession, destroySession } from '../framework/session.js';
import { readSession } from '../framework/requireAuth.js';

const STATE_COOKIE = 'vbd_oauth_state';

function setSessionCookie(reply, sid) {
  reply.setCookie(env.session.cookieName, sid, {
    httpOnly: true, sameSite: 'lax', secure: env.session.secure, signed: true, path: '/',
    maxAge: Math.floor(env.session.ttlMs / 1000),
  });
}

export default async function authRoutes(app) {
  // DEV-ONLY login bypass for internal testing before an OAuth app exists. Never enable in production.
  // Creates a session flagged `dev` → treated as admin of every bot-present guild (see routes/guilds.js).
  if (env.devLogin) {
    app.get('/api/auth/dev-login', async (req, reply) => {
      const sid = createSession({
        user: { id: env.devUser.id, username: env.devUser.name, global_name: env.devUser.name, avatar: null },
        dev: true,
      });
      setSessionCookie(reply, sid);
      return reply.redirect(redirectTo('/'));
    });
  }
  // Begin OAuth: set a signed state cookie (CSRF), redirect to Discord.
  app.get('/api/auth/login', async (req, reply) => {
    if (!oauthConfigured()) {
      return reply.code(503).send({
        error: 'oauth_not_configured',
        message: 'Discord OAuth credentials are not set. Add DISCORD_CLIENT_ID / DISCORD_CLIENT_SECRET (from art3mis) to server/.env.',
      });
    }
    const state = crypto.randomBytes(16).toString('base64url');
    reply.setCookie(STATE_COOKIE, state, {
      httpOnly: true, sameSite: 'lax', secure: env.session.secure, signed: true, path: '/', maxAge: 600,
    });
    return reply.redirect(buildAuthUrl(state));
  });

  // OAuth callback: verify state, exchange code, build session, redirect to the web app.
  app.get('/api/auth/callback', async (req, reply) => {
    const { code, state } = req.query ?? {};
    const stateCookie = req.cookies?.[STATE_COOKIE];
    const unsigned = stateCookie ? req.unsignCookie(stateCookie) : { valid: false };
    if (!code || !state || !unsigned.valid || unsigned.value !== state) {
      return reply.code(400).send({ error: 'invalid_oauth_state' });
    }
    reply.clearCookie(STATE_COOKIE, { path: '/' });

    try {
      const token = await exchangeCode(code);
      const [user, guilds] = await Promise.all([
        fetchUser(token.access_token),
        fetchUserGuilds(token.access_token),
      ]);
      const sid = createSession({
        user: {
          id: user.id,
          username: user.username,
          global_name: user.global_name ?? null,
          avatar: user.avatar ?? null,
        },
        access_token: token.access_token,
        token_expires_at: Date.now() + (token.expires_in ?? 0) * 1000,
        guilds, // cached; /api/guilds re-verifies against Discord when the token is still valid
      });
      setSessionCookie(reply, sid);
      return reply.redirect(redirectTo('/'));
    } catch (e) {
      req.log.error({ err: String(e) }, 'oauth callback failed');
      return reply.code(502).send({ error: 'oauth_failed' });
    }
  });

  app.get('/api/auth/me', async (req, reply) => {
    const { session } = readSession(req);
    if (!session?.user) return reply.code(401).send({ error: 'not_authenticated' });
    return { user: session.user };
  });

  app.post('/api/auth/logout', async (req, reply) => {
    const { sid } = readSession(req);
    destroySession(sid);
    reply.clearCookie(env.session.cookieName, { path: '/' });
    return { ok: true };
  });
}
