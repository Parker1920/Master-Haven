import Database from 'better-sqlite3';
import { env } from './env.js';

let _db = null;

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
