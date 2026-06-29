import { getDb } from '../db.js';

// Mirrors Viobot's ConfigManager DEFAULTS (src/lib/ConfigManager.js) — used when a guild has no row yet.
export const DEFAULTS = {
  version: 1,
  roles: {
    moderatorRoleId: null,
    muteRoleId: null,
    voiceMuteRoleId: null,
    verificationRequiredRoleId: null,
    staffRoleIds: [],
  },
  channels: {
    loggingChannelId: null,
    contactMemberChannelId: null,
    contactMutedChannelId: null,
    papertrailChannelId: null,
    violationsChannelId: null,
  },
  features: {
    tickets: false,
    logger: false,
    autoSusmuteNewAccounts: false,
  },
  tickets: {
    customContactCategories: [],
  },
};

/** Read a guild's stored config_json (read-only connection). Falls back to DEFAULTS if absent/corrupt. */
export function readGuildConfig(guildId) {
  const db = getDb();
  const row = db
    .prepare('SELECT config_json, guild_name, updated_at FROM guild_configs WHERE guild_id = ?')
    .get(guildId);

  let config = null;
  if (row?.config_json) {
    try {
      config = JSON.parse(row.config_json);
    } catch {
      config = null;
    }
  }

  return {
    config: config ?? structuredClone(DEFAULTS),
    guildName: row?.guild_name ?? null,
    updatedAt: row?.updated_at ?? null,
    exists: Boolean(row),
  };
}
