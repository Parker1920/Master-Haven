import { getDb, getWriteDb, backupDb } from '../db.js';

// Matches the bot's !var rules (src/MessageCommands/var.js).
const VAR_NAME_RE = /^[a-z0-9_.-]{1,64}$/;
const MAX_VARS = 200;
const MAX_VALUE = 4000;

/** All server variables for a guild (read-only connection). */
export function readVariables(guildId) {
  const db = getDb();
  return db
    .prepare('SELECT var_name, var_value, updated_at FROM guild_variables WHERE guild_id = ? ORDER BY var_name ASC')
    .all(guildId)
    .map((r) => ({ name: r.var_name, value: r.var_value ?? '', updatedAt: r.updated_at }));
}

/**
 * Replace a guild's variable set with `list` (upsert present, delete removed) in one transaction,
 * after a backup. Rejects names that don't match the bot's allowed pattern.
 */
export async function writeVariables(guildId, list) {
  const wanted = new Map();
  const invalid = [];
  for (const v of Array.isArray(list) ? list : []) {
    const name = String(v?.name ?? '').trim().toLowerCase();
    if (!name) continue;
    if (!VAR_NAME_RE.test(name)) { invalid.push(name); continue; }
    wanted.set(name, String(v?.value ?? '').slice(0, MAX_VALUE)); // last write wins on dup
    if (wanted.size >= MAX_VARS) break;
  }
  if (invalid.length) {
    const e = new Error(`invalid variable name(s): ${invalid.slice(0, 5).join(', ')}`);
    e.code = 'INVALID';
    throw e;
  }

  const db = getWriteDb();
  await backupDb();
  const now = new Date().toISOString();
  const run = db.transaction(() => {
    const existing = db.prepare('SELECT var_name FROM guild_variables WHERE guild_id = ?').all(guildId).map((r) => r.var_name);
    const del = db.prepare('DELETE FROM guild_variables WHERE guild_id = ? AND var_name = ?');
    for (const name of existing) if (!wanted.has(name)) del.run(guildId, name);
    const up = db.prepare(
      `INSERT INTO guild_variables (guild_id, var_name, var_value, updated_at) VALUES (?, ?, ?, ?)
       ON CONFLICT(guild_id, var_name) DO UPDATE SET var_value = excluded.var_value, updated_at = excluded.updated_at`,
    );
    for (const [name, value] of wanted) up.run(guildId, name, value, now);
  });
  run();
  return readVariables(guildId);
}
