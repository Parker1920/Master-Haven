import { getGuildMember } from './discord.js';
import { readGuildConfig } from './configRead.js';

/**
 * Layered authorization on top of "Discord admin ∩ bot-present" (already enforced by accessibleGuilds):
 * a non-owner, non-operator must ALSO hold the guild's configured Viobot moderator role to view/edit
 * that server's dashboard config.
 *
 * Safeguards:
 *  - If no moderator role is configured yet, fall back to Administrator-only so a fresh install isn't
 *    locked out of its own first-time setup.
 *  - Owners and dashboard operators are exempt (handled by the callers, not here).
 *
 * Note: a Discord ADMINISTRATOR can already self-assign this role, so this is a least-privilege
 * guardrail (aligning dashboard access with the people who actually moderate), not a hard security
 * boundary against admins.
 *
 * @returns {Promise<{ok:true}|{ok:false}|{error:'discord_unavailable'}>}
 */
export async function memberHoldsModeratorRole(guildId, userId) {
  const modRoleId = readGuildConfig(guildId)?.config?.roles?.moderatorRoleId || null;
  if (!modRoleId) return { ok: true }; // not configured yet → Administrator-only fallback

  try {
    const member = await getGuildMember(guildId, userId);
    const roleIds = new Set((member?.roles ?? []).map(String));
    return { ok: roleIds.has(String(modRoleId)) };
  } catch {
    // Can't verify (Discord blip / rate limit) → fail closed; caller surfaces a retryable 502.
    return { error: 'discord_unavailable' };
  }
}
