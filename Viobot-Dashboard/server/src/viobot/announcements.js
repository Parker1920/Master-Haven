import crypto from 'node:crypto';
import { getDb, getWriteDb, backupDb } from '../db.js';

const MAX_MESSAGE = 2000;

/** Scheduled announcements for a guild. The bot polls send_at<=now, posts, and deletes them. */
export function readAnnouncements(guildId) {
  const db = getDb();
  return db
    .prepare('SELECT id, channel_id, created_by, message, send_at, created_at FROM scheduled_announcements WHERE guild_id = ? ORDER BY send_at ASC')
    .all(guildId)
    .map((r) => ({ id: r.id, channelId: r.channel_id, createdBy: r.created_by, message: r.message, sendAt: r.send_at, createdAt: r.created_at }));
}

export async function addAnnouncement(guildId, { channelId, message, sendAt }, actorId, validChannelIds) {
  const msg = String(message || '').trim().slice(0, MAX_MESSAGE);
  const cid = String(channelId || '');
  const when = Number(sendAt);
  if (!msg) { const e = new Error('message is required'); e.code = 'BAD'; throw e; }
  if (!cid || (validChannelIds && !validChannelIds.has(cid))) { const e = new Error('pick a valid channel'); e.code = 'BAD'; throw e; }
  if (!Number.isFinite(when) || when <= Date.now()) { const e = new Error('send time must be in the future'); e.code = 'BAD'; throw e; }

  const db = getWriteDb();
  await backupDb();
  const id = crypto.randomUUID();
  db.prepare(
    'INSERT INTO scheduled_announcements (id, guild_id, channel_id, created_by, message, send_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
  ).run(id, guildId, cid, actorId || null, msg, when, new Date().toISOString());
  return readAnnouncements(guildId);
}

export async function deleteAnnouncement(guildId, id) {
  const db = getWriteDb();
  await backupDb();
  const info = db.prepare('DELETE FROM scheduled_announcements WHERE id = ? AND guild_id = ?').run(String(id), guildId);
  if (info.changes === 0) { const e = new Error('not found'); e.code = 'NOTFOUND'; throw e; }
  return readAnnouncements(guildId);
}
