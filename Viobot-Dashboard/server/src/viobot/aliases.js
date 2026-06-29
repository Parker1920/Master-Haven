import { getDb, getWriteDb, backupDb } from '../db.js';

const norm = (n) => String(n || '').trim().toLowerCase().replace(/^!/, '');

/** Public (server-wide) aliases + a count of per-member private aliases. */
export function readAliases(guildId) {
  const db = getDb();
  const aliases = db
    .prepare(
      `SELECT alias_name, help_text, raw_body, allow_members, created_by, updated_at
       FROM aliases WHERE guild_id = ? AND scope = 'public' AND owner_id = 'public'
       ORDER BY alias_name ASC`,
    )
    .all(guildId)
    .map((r) => ({
      name: r.alias_name,
      helpText: r.help_text || '',
      rawBody: r.raw_body || '',
      allowMembers: Boolean(r.allow_members),
      createdBy: r.created_by,
      updatedAt: r.updated_at,
    }));
  const privateCount = db
    .prepare("SELECT COUNT(*) AS n FROM aliases WHERE guild_id = ? AND scope = 'private'")
    .get(guildId).n;
  return { aliases, privateCount };
}

/** Update a public alias's help text + member-access only (body authoring stays in the generator). */
export async function updateAliasMeta(guildId, name, { helpText, allowMembers }, actorId) {
  const n = norm(name);
  if (!n) { const e = new Error('alias name required'); e.code = 'BAD'; throw e; }
  const db = getWriteDb();
  await backupDb();
  const info = db
    .prepare(
      `UPDATE aliases SET help_text = ?, allow_members = ?, updated_by = ?, updated_at = ?
       WHERE guild_id = ? AND scope = 'public' AND owner_id = 'public' AND alias_name = ?`,
    )
    .run(String(helpText || '').slice(0, 500), allowMembers ? 1 : 0, actorId || null, new Date().toISOString(), guildId, n);
  if (info.changes === 0) { const e = new Error('alias not found'); e.code = 'NOTFOUND'; throw e; }
  return readAliases(guildId);
}

export async function deleteAlias(guildId, name) {
  const n = norm(name);
  const db = getWriteDb();
  await backupDb();
  const info = db
    .prepare("DELETE FROM aliases WHERE guild_id = ? AND scope = 'public' AND owner_id = 'public' AND alias_name = ?")
    .run(guildId, n);
  if (info.changes === 0) { const e = new Error('alias not found'); e.code = 'NOTFOUND'; throw e; }
  return readAliases(guildId);
}
