// Pure guild-scoping logic — the heart of Phase 1. No I/O, fully unit-testable.
// Reusable framework: works for any bot dashboard, not just Viobot.

export const ADMINISTRATOR = 0x8n; // Discord ADMINISTRATOR permission bit

/** A user administers a guild if they own it or hold the ADMINISTRATOR permission there. */
export function isAdminGuild(guild) {
  if (guild?.owner === true) return true;
  try {
    return (BigInt(guild?.permissions ?? '0') & ADMINISTRATOR) === ADMINISTRATOR;
  } catch {
    return false;
  }
}

/**
 * Accessible guilds = (user's admin guilds) ∩ (guilds where the bot is present).
 * @param userGuilds Discord partial guild objects from /users/@me/guilds
 * @param botGuilds  Map<guildId(string), guildName> of guilds the bot is in
 */
export function accessibleGuilds(userGuilds, botGuilds) {
  return (userGuilds ?? [])
    .filter(isAdminGuild)
    .filter((g) => botGuilds.has(String(g.id)))
    .map((g) => ({
      id: String(g.id),
      name: g.name ?? botGuilds.get(String(g.id)) ?? String(g.id),
      icon: g.icon ?? null,
      owner: Boolean(g.owner),
    }));
}

export function countAdmin(userGuilds) {
  return (userGuilds ?? []).filter(isAdminGuild).length;
}
