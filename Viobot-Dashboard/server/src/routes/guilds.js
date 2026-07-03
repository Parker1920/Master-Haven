import { fetchUserGuilds } from '../framework/oauth.js';
import { accessibleGuilds, countAdmin } from '../framework/guildAccess.js';
import { readSession } from '../framework/requireAuth.js';
import { getBotGuildIds } from '../viobot/botGuilds.js';
import { isDashboardAdmin } from '../dashboard/store.js';
import { memberHoldsModeratorRole } from '../viobot/moderatorAccess.js';

export default async function guildRoutes(app) {
  // The servers the logged-in user may configure: admin ∩ Viobot-present.
  app.get('/api/guilds', async (req, reply) => {
    const { session } = readSession(req);
    if (!session?.user) return reply.code(401).send({ error: 'not_authenticated' });

    // Dev-login session: no Discord token, so treat every bot-present guild as accessible (testing only).
    if (session.dev) {
      const botGuilds = getBotGuildIds();
      const guilds = [...botGuilds].map(([id, name]) => ({ id, name: name ?? id, icon: null, owner: false }));
      return { dev: true, guilds, counts: { admin: guilds.length, botPresent: botGuilds.size, accessible: guilds.length } };
    }

    // Re-verify admin status against Discord when the access token is still valid (authoritative).
    // The browser's guild list is never trusted; the cached session list is only a fallback.
    let userGuilds = session.guilds ?? [];
    if (session.access_token && session.token_expires_at > Date.now()) {
      try {
        userGuilds = await fetchUserGuilds(session.access_token);
      } catch (e) {
        req.log.warn({ err: String(e) }, 'guild re-fetch failed; using cached session guilds');
      }
    }

    const botGuilds = getBotGuildIds();
    const adminGuilds = accessibleGuilds(userGuilds, botGuilds);

    // Only surface servers the user can actually configure: owner/operator, or holds the mod role
    // (matches resolveAccessibleGuild in routes/config.js — no mod role set ⇒ admin-only fallback).
    const isOperator = isDashboardAdmin(session.user.id);
    const checked = await Promise.all(
      adminGuilds.map(async (g) => {
        if (g.owner === true || isOperator) return g;
        const modCheck = await memberHoldsModeratorRole(g.id, session.user.id);
        return modCheck.ok ? g : null; // drop on !ok and on discord_unavailable (fail closed)
      }),
    );
    const guilds = checked.filter(Boolean);
    return {
      guilds,
      counts: { admin: countAdmin(userGuilds), botPresent: botGuilds.size, accessible: guilds.length },
    };
  });
}
