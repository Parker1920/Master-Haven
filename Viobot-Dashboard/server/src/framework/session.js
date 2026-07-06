import crypto from 'node:crypto';
import { env } from '../env.js';

/**
 * Minimal server-side session store keyed by a signed session-id cookie.
 *
 * In-memory (single instance) — fine for the Pi's single dashboard container and for dev.
 * OPERATIONAL NOTE: sessions live only in this process, so every restart / redeploy / reimage clears
 * them and all users must log in again. Acceptable on one container; move to a persistent store
 * (e.g. a SQLite sessions table) before any multi-instance / zero-downtime-deploy setup.
 * Reusable framework; not Viobot-specific.
 */
const store = new Map(); // sid -> { data, expiresAt }

export function createSession(data) {
  const sid = crypto.randomBytes(24).toString('base64url');
  store.set(sid, { data, expiresAt: Date.now() + env.session.ttlMs });
  return sid;
}

export function getSession(sid) {
  if (!sid) return null;
  const s = store.get(sid);
  if (!s) return null;
  if (s.expiresAt < Date.now()) {
    store.delete(sid);
    return null;
  }
  return s.data;
}

export function destroySession(sid) {
  if (sid) store.delete(sid);
}

// Periodic cleanup of expired sessions.
setInterval(() => {
  const now = Date.now();
  for (const [sid, s] of store) if (s.expiresAt < now) store.delete(sid);
}, 60_000).unref();
