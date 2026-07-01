import { getWriteDb, backupDb } from '../db.js';
import { getRegistry, isDashboardAdmin } from '../dashboard/store.js';
import { DEFAULTS } from './configRead.js';

const getPath = (o, p) => p.split('.').reduce((x, k) => (x == null ? undefined : x[k]), o);
function setPath(o, p, v) {
  const ks = p.split('.');
  let c = o;
  for (let i = 0; i < ks.length - 1; i++) {
    if (c[ks[i]] == null || typeof c[ks[i]] !== 'object') c[ks[i]] = {};
    c = c[ks[i]];
  }
  c[ks[ks.length - 1]] = v;
}

/**
 * Apply ONLY registry-managed fields from `incoming` onto `base`, coercing/validating each:
 * role/channel IDs must exist in the guild (else nulled/dropped), bools coerced, role arrays deduped.
 * Unmanaged fields on `base` (meta, version, tickets.customContactCategories) are preserved untouched.
 */
// ── Custom contact categories (tickets.customContactCategories) ──────────────
// Mirrors the bot's src/utils/contactCategories.js exactly so a dashboard save can't break tickets.
const MAX_CATEGORIES = 10;
const RESERVED_CATEGORY_IDS = new Set(['report-user', 'other']);
const slugifyCategoryId = (input) =>
  String(input || '').toLowerCase().trim().replace(/['"]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80);
const sanitizeCategoryText = (input, max = 100) =>
  String(input || '').replace(/@everyone/gi, '').replace(/@here/gi, '').replace(/[<>]/g, '').trim().slice(0, max);

function sanitizeCategories(incoming, actorId, existing) {
  const now = new Date().toISOString();
  const prev = new Map((Array.isArray(existing) ? existing : []).map((c) => [c.id, c]));
  const out = [];
  const seen = new Set();
  for (const c of Array.isArray(incoming) ? incoming : []) {
    const label = sanitizeCategoryText(c?.label, 100);
    const id = slugifyCategoryId(c?.id || label);
    if (!id || !label || RESERVED_CATEGORY_IDS.has(id) || seen.has(id)) continue;
    seen.add(id);
    const old = prev.get(id);
    out.push({
      id,
      label,
      description: sanitizeCategoryText(c?.description || 'Contact staff about this topic.', 100),
      enabled: c?.enabled !== false,
      createdAt: old?.createdAt || c?.createdAt || now,
      createdBy: old?.createdBy || c?.createdBy || actorId || null,
      updatedAt: now,
      updatedBy: actorId || null,
      isDefault: false,
    });
    if (out.length >= MAX_CATEGORIES) break;
  }
  return out;
}

function applyManaged(base, incoming, roles, channels, actorIsAdmin) {
  const roleIds = new Set(roles.map((r) => r.id));
  const chanIds = new Set(channels.map((c) => c.id));
  for (const group of getRegistry().groups) {
    for (const f of group.fields) {
      if (f.testing && !actorIsAdmin) continue; // testing fields are admin-only; ignore non-admin writes
      const v = getPath(incoming, f.path);
      if (v === undefined) continue; // field not submitted → leave base value
      if (f.type === 'role') setPath(base, f.path, typeof v === 'string' && roleIds.has(v) ? v : null);
      else if (f.type === 'channel') setPath(base, f.path, typeof v === 'string' && chanIds.has(v) ? v : null);
      else if (f.type === 'bool') setPath(base, f.path, Boolean(v));
      else if (f.type === 'role[]') {
        const arr = (Array.isArray(v) ? v : []).filter((x) => typeof x === 'string' && roleIds.has(x));
        setPath(base, f.path, [...new Set(arr)]);
      } else if (f.type === 'string') {
        setPath(base, f.path, v == null ? null : String(v).slice(0, f.maxLength || 1000));
      } else if (f.type === 'number') {
        const n = Number(v);
        setPath(base, f.path, Number.isFinite(n) ? n : (f.default ?? null));
      } else if (f.type === 'select') {
        const allowed = new Set((f.options || []).map((o) => (o && typeof o === 'object' ? o.value : o)));
        setPath(base, f.path, allowed.has(v) ? v : (f.default ?? null));
      }
    }
  }
  return base;
}

/**
 * Write a guild's config. Backs up first, then in a single transaction: re-reads the freshest row,
 * enforces optimistic concurrency against `expectedUpdatedAt`, merges the validated managed fields
 * onto the DB's current config, and persists. Throws {code:'CONFLICT'} on a concurrent change.
 */
export async function writeGuildConfig(guildId, incoming, expectedUpdatedAt, roles, channels, actorId = null) {
  const db = getWriteDb();
  await backupDb();
  const now = new Date().toISOString();

  const run = db.transaction(() => {
    const row = db
      .prepare('SELECT config_json, created_at, updated_at FROM guild_configs WHERE guild_id = ?')
      .get(guildId);

    if (row && expectedUpdatedAt && row.updated_at !== expectedUpdatedAt) {
      const e = new Error('config changed since it was loaded');
      e.code = 'CONFLICT';
      throw e;
    }

    let base;
    if (row?.config_json) {
      try { base = JSON.parse(row.config_json); } catch { base = structuredClone(DEFAULTS); }
    } else {
      base = structuredClone(DEFAULTS);
    }

    base = applyManaged(base, incoming, roles, channels, isDashboardAdmin(actorId));

    // Structured field (not a simple registry entry): custom contact categories.
    if (incoming?.tickets && Array.isArray(incoming.tickets.customContactCategories)) {
      base.tickets = base.tickets && typeof base.tickets === 'object' ? base.tickets : {};
      base.tickets.customContactCategories = sanitizeCategories(
        incoming.tickets.customContactCategories,
        actorId,
        Array.isArray(base.tickets.customContactCategories) ? base.tickets.customContactCategories : [],
      );
    }
    base.version = base.version || DEFAULTS.version;
    base.meta = base.meta && typeof base.meta === 'object' ? base.meta : {};
    base.meta.guildId = guildId;
    base.meta.createdAt = base.meta.createdAt || row?.created_at || now;
    base.meta.updatedAt = now;

    const json = JSON.stringify(base);
    if (row) {
      db.prepare('UPDATE guild_configs SET config_json = ?, updated_at = ? WHERE guild_id = ?').run(json, now, guildId);
    } else {
      db.prepare(
        'INSERT INTO guild_configs (guild_id, guild_name, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
      ).run(guildId, null, json, now, now);
    }
    return { config: base, updatedAt: now };
  });

  return run();
}
