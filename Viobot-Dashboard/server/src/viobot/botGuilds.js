import { getDb } from '../db.js';

/**
 * Viobot-specific source of "is the bot present in this guild?".
 *
 * A guild is registered/bot-present iff it has a row in guild_configs (Viobot writes this row when
 * the server is registered). Because the dashboard is co-located with Viobot and reads the same DB,
 * this is authoritative — no separate bot guild-list API call is required.
 *
 * @returns Map<guildId(string), guildName|null>
 */
export function getBotGuildIds() {
  const db = getDb();
  const rows = db.prepare('SELECT guild_id, guild_name FROM guild_configs').all();
  return new Map(rows.map((r) => [String(r.guild_id), r.guild_name ?? null]));
}
