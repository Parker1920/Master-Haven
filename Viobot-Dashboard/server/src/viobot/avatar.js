import { getDb, getWriteDb, backupDb } from '../db.js';
import { env } from '../env.js';

const ALLOWED_MIME = new Set(['image/png', 'image/jpeg', 'image/gif', 'image/webp']);
const MAX_DATAURI = 8 * 1024 * 1024; // generous; Discord enforces its own limit too

export function readAvatar(guildId) {
  const db = getDb();
  const row = db
    .prepare('SELECT data_uri, mime_type, updated_by, updated_at FROM guild_server_avatars WHERE guild_id = ?')
    .get(guildId);
  if (!row) return null;
  return { dataUri: row.data_uri, mimeType: row.mime_type, updatedBy: row.updated_by, updatedAt: row.updated_at };
}

function parseDataUri(dataUri) {
  const m = /^data:([a-z0-9.+-]+\/[a-z0-9.+-]+);base64,/i.exec(String(dataUri || ''));
  return m ? { mime: m[1].toLowerCase() } : null;
}

// Same call the bot makes: PATCH the bot's own per-guild member avatar.
async function discordSetAvatar(guildId, avatar) {
  if (!env.botToken) { const e = new Error('bot token unavailable'); e.code = 'DISCORD'; throw e; }
  const res = await fetch(`https://discord.com/api/v10/guilds/${guildId}/members/@me`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bot ${env.botToken}`,
      'Content-Type': 'application/json',
      'X-Audit-Log-Reason': 'Viobot dashboard server avatar',
    },
    body: JSON.stringify({ avatar }),
  });
  if (!res.ok) {
    const t = await res.text().catch(() => '');
    const e = new Error(`Discord rejected the avatar (${res.status})${t ? ': ' + t.slice(0, 180) : ''}`);
    e.code = 'DISCORD';
    throw e;
  }
  return res.json().catch(() => null);
}

export async function setAvatar(guildId, dataUri, actorId) {
  const parsed = parseDataUri(dataUri);
  if (!parsed) { const e = new Error('image must be a base64 data URI'); e.code = 'BAD'; throw e; }
  if (!ALLOWED_MIME.has(parsed.mime)) { const e = new Error('use PNG, JPG, GIF, or WEBP'); e.code = 'BAD'; throw e; }
  if (String(dataUri).length > MAX_DATAURI) { const e = new Error('image is too large'); e.code = 'BAD'; throw e; }

  // Apply to Discord first — only persist what Discord accepts (so the bot's re-sync stays valid).
  await discordSetAvatar(guildId, dataUri);

  const db = getWriteDb();
  await backupDb();
  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO guild_server_avatars (guild_id, data_uri, mime_type, updated_by, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?)
     ON CONFLICT(guild_id) DO UPDATE SET
       data_uri = excluded.data_uri, mime_type = excluded.mime_type,
       updated_by = excluded.updated_by, updated_at = excluded.updated_at`,
  ).run(guildId, dataUri, parsed.mime, actorId || null, now, now);
  return readAvatar(guildId);
}

export async function resetAvatar(guildId) {
  await discordSetAvatar(guildId, null);
  const db = getWriteDb();
  await backupDb();
  db.prepare('DELETE FROM guild_server_avatars WHERE guild_id = ?').run(guildId);
  return null;
}
