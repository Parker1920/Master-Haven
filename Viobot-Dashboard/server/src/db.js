import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';
import { env } from './env.js';

let _db = null;
let _writeDb = null;

/**
 * Open the Viobot SQLite DB.
 *
 * The LIVE db is in WAL mode. A WAL *reader* must be able to write the -shm lock slots, so a read-only
 * filesystem mount breaks reads. We therefore open read-write (so shm works) and enforce read-only at
 * the SQL layer with PRAGMA query_only=ON — any write attempt is rejected by SQLite. WAL also allows
 * many concurrent readers alongside the bot's single writer, so this is safe against the running bot.
 *
 * Phase 2 will set VIOBOT_DB_READONLY=false to enable config writes (with backup-before-write).
 */
export function getDb() {
  if (_db) return _db;
  if (!env.viobotDbPath) {
    throw new Error(
      'VIOBOT_DB_PATH is not set. Point it at the Viobot SQLite DB (a local copy in dev; the mounted live file on the Pi).',
    );
  }
  _db = new Database(env.viobotDbPath, { fileMustExist: true });
  _db.pragma('busy_timeout = 5000');
  if (env.dbReadonly) {
    _db.pragma('query_only = ON'); // hard guarantee: no data writes in read-only phase
  }
  return _db;
}

/**
 * Write-capable connection (separate from the read-only one). Used only by the config write path.
 * WAL allows this alongside the bot's own writer; busy_timeout serializes contention.
 */
export function getWriteDb() {
  if (_writeDb) return _writeDb;
  if (!env.viobotDbPath) throw new Error('VIOBOT_DB_PATH is not set.');
  _writeDb = new Database(env.viobotDbPath, { fileMustExist: true });
  _writeDb.pragma('busy_timeout = 8000');
  return _writeDb;
}

/** Backup-before-write (SOW safe-transfer). Online-safe SQLite backup; keeps the most recent 15. */
export async function backupDb() {
  const dir = path.join(path.dirname(env.viobotDbPath), 'dashboard-backups');
  fs.mkdirSync(dir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const dest = path.join(dir, `viobot-${stamp}.db`);
  await getWriteDb().backup(dest);
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.db')).sort();
  for (const f of files.slice(0, Math.max(0, files.length - 15))) {
    try { fs.unlinkSync(path.join(dir, f)); } catch { /* ignore */ }
  }
  return dest;
}

export function dbInfo() {
  const db = getDb();
  const tables = db
    .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    .all()
    .map((r) => r.name);
  const guildCount = db.prepare('SELECT COUNT(*) AS n FROM guild_configs').get().n;
  return {
    path: env.viobotDbPath,
    readOnly: env.dbReadonly,
    queryOnly: db.pragma('query_only', { simple: true }) === 1,
    journalMode: db.pragma('journal_mode', { simple: true }),
    tables,
    registeredGuilds: guildCount,
  };
}
