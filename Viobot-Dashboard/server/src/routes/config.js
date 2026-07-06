import { fetchUserGuilds } from '../framework/oauth.js';
import { accessibleGuilds } from '../framework/guildAccess.js';
import { readSession } from '../framework/requireAuth.js';
import { getBotGuildIds } from '../viobot/botGuilds.js';
import { getGuildRoles, getGuildChannels } from '../viobot/discord.js';
import { readGuildConfig } from '../viobot/configRead.js';
import { writeGuildConfig } from '../viobot/configWrite.js';
import { readVariables, writeVariables } from '../viobot/variables.js';
import { readAliases, updateAliasMeta, deleteAlias } from '../viobot/aliases.js';
import { getFeatureAccess, hasFeature } from '../viobot/premium.js';
import { readAnnouncements, addAnnouncement, deleteAnnouncement } from '../viobot/announcements.js';
import { readAvatar, setAvatar, resetAvatar } from '../viobot/avatar.js';
import { registryForViewer, isDashboardAdmin } from '../dashboard/store.js';
import { memberHoldsModeratorRole } from '../viobot/moderatorAccess.js';
import { env } from '../env.js';

/**
 * Resolve the requested guild ONLY if the caller may configure it:
 * the bot must be present (guild_configs row) AND the user must administer it.
 * Returns { guild } or { error: <httpStatus> }.
 */
async function resolveAccessibleGuild(req, guildId) {
  const { session } = readSession(req);
  if (!session?.user) return { error: 401 };
  const isAdmin = isDashboardAdmin(session.user.id);

  const botGuilds = getBotGuildIds();
  if (!botGuilds.has(guildId)) return { error: 404 }; // bot not in this guild

  // Dev session: no Discord identity, so allow any bot-present guild (testing only).
  if (session.dev) {
    return { guild: { id: guildId, name: botGuilds.get(guildId) ?? guildId, owner: false }, isAdmin };
  }

  let userGuilds = session.guilds ?? [];
  if (session.access_token && session.token_expires_at > Date.now()) {
    try {
      userGuilds = await fetchUserGuilds(session.access_token);
    } catch {
      /* fall back to cached session guilds */
    }
  }
  const guild = accessibleGuilds(userGuilds, botGuilds).find((g) => g.id === guildId);
  if (!guild) return { error: 403 }; // not an admin of this guild

  // Beyond Administrator, a non-owner / non-operator must also hold the guild's configured Viobot
  // moderator role (falls back to admin-only when no mod role is set — see moderatorAccess.js).
  if (guild.owner !== true && !isAdmin) {
    const modCheck = await memberHoldsModeratorRole(guildId, session.user.id);
    if (modCheck.error) return { error: 502 }; // couldn't verify — retryable
    if (!modCheck.ok) return { error: 403 };
  }
  return { guild, isAdmin };
}

export default async function configRoutes(app) {
  // Write kill-switch: when VIOBOT_DB_READONLY is set, refuse every Viobot-DB mutation on this plugin's
  // routes (config/variables/aliases/announcements/avatar) with a clean 403. GET reads still work; the
  // dashboard-store admin writes (appearance/registry/admins) live in a separate plugin and are unaffected.
  app.addHook('preHandler', async (req, reply) => {
    if (env.dbReadonly && (req.method === 'PUT' || req.method === 'POST' || req.method === 'DELETE')) {
      return reply.code(403).send({
        error: 'read_only',
        message: 'The dashboard is in read-only mode (VIOBOT_DB_READONLY=true). Set it to false to enable edits.',
      });
    }
  });

  // Live config for one server + the role/channel lists the dropdowns render from.
  app.get('/api/guilds/:id/config', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) {
      const msg = { 401: 'not_authenticated', 403: 'forbidden', 404: 'not_found', 502: 'discord_unavailable' }[r.error];
      return reply.code(r.error).send({ error: msg });
    }

    let config, updatedAt;
    try {
      ({ config, updatedAt } = readGuildConfig(guildId));
    } catch (e) {
      req.log.error({ err: String(e.message || e) }, 'config read failed');
      return reply.code(500).send({ error: 'read_failed' });
    }

    let roles = [];
    let channels = [];
    let lookupError = null;
    try {
      [roles, channels] = await Promise.all([getGuildRoles(guildId), getGuildChannels(guildId)]);
    } catch (e) {
      lookupError = String(e.message || e);
      req.log.warn({ err: lookupError }, 'roles/channels fetch failed');
    }

    // Config-embedded gated features (so the editor can lock the right controls). Currently just custom
    // contact categories (Plus/Beta). Fails closed (locked) if the entitlement check can't complete.
    let features = { custom_contact_categories: false };
    try {
      features = { custom_contact_categories: await hasFeature(guildId, 'custom_contact_categories') };
    } catch (e) {
      req.log.warn({ err: String(e.message || e) }, 'feature access check failed');
    }

    return { guild: r.guild, config, updatedAt, registry: registryForViewer(r.isAdmin), roles, channels, lookupError, features };
  });

  // Save a server's config (validated, optimistic-concurrency, backup-before-write).
  app.put('/api/guilds/:id/config', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) {
      const msg = { 401: 'not_authenticated', 403: 'forbidden', 404: 'not_found', 502: 'discord_unavailable' }[r.error];
      return reply.code(r.error).send({ error: msg });
    }

    const body = req.body || {};
    if (!body.config || typeof body.config !== 'object') {
      return reply.code(400).send({ error: 'invalid_body' });
    }

    // Custom contact categories are a Plus/Beta feature — strip them from a non-entitled guild's write
    // so a crafted request can't set inert categories (the bot ignores them regardless). Preserves the
    // stored value: writeGuildConfig only overwrites customContactCategories when it's present here.
    if (body.config.tickets && Array.isArray(body.config.tickets.customContactCategories)) {
      let allowed = false;
      try { allowed = await hasFeature(guildId, 'custom_contact_categories'); } catch { allowed = false; }
      if (!allowed) delete body.config.tickets.customContactCategories;
    }

    let roles = [];
    let channels = [];
    try {
      [roles, channels] = await Promise.all([getGuildRoles(guildId), getGuildChannels(guildId)]);
    } catch (e) {
      return reply.code(502).send({ error: 'discord_unavailable', detail: String(e.message || e) });
    }

    const { session } = readSession(req);
    const actorId = session?.user?.id ?? null;
    try {
      const result = await writeGuildConfig(guildId, body.config, body.updatedAt ?? null, roles, channels, actorId);
      return { ok: true, config: result.config, updatedAt: result.updatedAt };
    } catch (e) {
      if (e.code === 'CONFLICT') {
        return reply.code(409).send({ error: 'conflict', message: 'This server’s config changed since you loaded it. Reload and try again.' });
      }
      req.log.error({ err: String(e.message || e) }, 'config write failed');
      return reply.code(500).send({ error: 'write_failed', detail: String(e.message || e) });
    }
  });

  // Server variables ($var) — read.
  app.get('/api/guilds/:id/variables', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) {
      const msg = { 401: 'not_authenticated', 403: 'forbidden', 404: 'not_found', 502: 'discord_unavailable' }[r.error];
      return reply.code(r.error).send({ error: msg });
    }
    return { variables: readVariables(guildId) };
  });

  // Server variables — replace the set (validated, backup-before-write).
  app.put('/api/guilds/:id/variables', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) {
      const msg = { 401: 'not_authenticated', 403: 'forbidden', 404: 'not_found', 502: 'discord_unavailable' }[r.error];
      return reply.code(r.error).send({ error: msg });
    }
    const body = req.body || {};
    if (!Array.isArray(body.variables)) return reply.code(400).send({ error: 'invalid_body' });
    try {
      const variables = await writeVariables(guildId, body.variables);
      return { ok: true, variables };
    } catch (e) {
      if (e.code === 'INVALID') return reply.code(400).send({ error: 'invalid', message: String(e.message) });
      req.log.error({ err: String(e.message || e) }, 'variables write failed');
      return reply.code(500).send({ error: 'write_failed', detail: String(e.message || e) });
    }
  });

  const denied = (reply, code) =>
    reply.code(code).send({ error: { 401: 'not_authenticated', 403: 'forbidden', 404: 'not_found', 502: 'discord_unavailable' }[code] });

  // Public aliases — list.
  app.get('/api/guilds/:id/aliases', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) return denied(reply, r.error);
    return readAliases(guildId);
  });

  // Public alias — update help/access.
  app.put('/api/guilds/:id/aliases/:name', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) return denied(reply, r.error);
    const { session } = readSession(req);
    const body = req.body || {};
    try {
      const data = await updateAliasMeta(guildId, req.params.name, { helpText: body.helpText, allowMembers: !!body.allowMembers }, session?.user?.id ?? null);
      return { ok: true, ...data };
    } catch (e) {
      if (e.code === 'NOTFOUND') return reply.code(404).send({ error: 'not_found' });
      if (e.code === 'BAD') return reply.code(400).send({ error: 'invalid' });
      req.log.error({ err: String(e.message || e) }, 'alias update failed');
      return reply.code(500).send({ error: 'write_failed' });
    }
  });

  // Public alias — delete.
  app.delete('/api/guilds/:id/aliases/:name', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) return denied(reply, r.error);
    try {
      const data = await deleteAlias(guildId, req.params.name);
      return { ok: true, ...data };
    } catch (e) {
      if (e.code === 'NOTFOUND') return reply.code(404).send({ error: 'not_found' });
      req.log.error({ err: String(e.message || e) }, 'alias delete failed');
      return reply.code(500).send({ error: 'write_failed' });
    }
  });

  // Plus / Beta access (read-only).
  app.get('/api/guilds/:id/premium', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) return denied(reply, r.error);
    try {
      return await getFeatureAccess(guildId);
    } catch (e) {
      req.log.error({ err: String(e.message || e) }, 'premium read failed');
      return reply.code(500).send({ error: 'read_failed' });
    }
  });

  // Scheduled announcements (Plus / Beta feature). Bot polls send_at and auto-posts.
  const announcementsPayload = async (guildId) => {
    let channels = [];
    try { channels = await getGuildChannels(guildId); } catch { /* names just unavailable */ }
    const allowed = await hasFeature(guildId, 'announce_command');
    return { announcements: readAnnouncements(guildId), channels, allowed };
  };

  app.get('/api/guilds/:id/announcements', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) return denied(reply, r.error);
    return announcementsPayload(guildId);
  });

  app.post('/api/guilds/:id/announcements', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) return denied(reply, r.error);
    if (!(await hasFeature(guildId, 'announce_command'))) {
      return reply.code(403).send({ error: 'feature_locked', message: 'Scheduled announcements require Plus or Beta.' });
    }
    const { session } = readSession(req);
    let channels = [];
    try { channels = await getGuildChannels(guildId); } catch { /* */ }
    const body = req.body || {};
    try {
      await addAnnouncement(guildId, body, session?.user?.id ?? null, new Set(channels.map((c) => c.id)));
      return { ok: true, ...(await announcementsPayload(guildId)) };
    } catch (e) {
      if (e.code === 'BAD') return reply.code(400).send({ error: 'invalid', message: String(e.message) });
      req.log.error({ err: String(e.message || e) }, 'announcement add failed');
      return reply.code(500).send({ error: 'write_failed' });
    }
  });

  app.delete('/api/guilds/:id/announcements/:annId', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) return denied(reply, r.error);
    if (!(await hasFeature(guildId, 'announce_command'))) return reply.code(403).send({ error: 'feature_locked' });
    try {
      await deleteAnnouncement(guildId, req.params.annId);
      return { ok: true, ...(await announcementsPayload(guildId)) };
    } catch (e) {
      if (e.code === 'NOTFOUND') return reply.code(404).send({ error: 'not_found' });
      req.log.error({ err: String(e.message || e) }, 'announcement delete failed');
      return reply.code(500).send({ error: 'write_failed' });
    }
  });

  // Custom server avatar (Plus / Beta feature). Applies to Discord (PATCH member @me) + persists.
  app.get('/api/guilds/:id/avatar', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) return denied(reply, r.error);
    return { avatar: readAvatar(guildId), allowed: await hasFeature(guildId, 'custom_avatar') };
  });

  // Larger body limit — the upload is a base64 data URI.
  app.put('/api/guilds/:id/avatar', { bodyLimit: 12 * 1024 * 1024 }, async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) return denied(reply, r.error);
    if (!(await hasFeature(guildId, 'custom_avatar'))) {
      return reply.code(403).send({ error: 'feature_locked', message: 'Custom server avatar requires Plus or Beta.' });
    }
    const { session } = readSession(req);
    try {
      const avatar = await setAvatar(guildId, (req.body || {}).dataUri, session?.user?.id ?? null);
      return { ok: true, avatar };
    } catch (e) {
      if (e.code === 'BAD') return reply.code(400).send({ error: 'invalid', message: String(e.message) });
      if (e.code === 'DISCORD') return reply.code(502).send({ error: 'discord_rejected', message: String(e.message) });
      req.log.error({ err: String(e.message || e) }, 'avatar set failed');
      return reply.code(500).send({ error: 'write_failed' });
    }
  });

  app.delete('/api/guilds/:id/avatar', async (req, reply) => {
    const guildId = String(req.params.id);
    const r = await resolveAccessibleGuild(req, guildId);
    if (r.error) return denied(reply, r.error);
    if (!(await hasFeature(guildId, 'custom_avatar'))) return reply.code(403).send({ error: 'feature_locked' });
    try {
      await resetAvatar(guildId);
      return { ok: true, avatar: null };
    } catch (e) {
      if (e.code === 'DISCORD') return reply.code(502).send({ error: 'discord_rejected', message: String(e.message) });
      req.log.error({ err: String(e.message || e) }, 'avatar reset failed');
      return reply.code(500).send({ error: 'write_failed' });
    }
  });
}
