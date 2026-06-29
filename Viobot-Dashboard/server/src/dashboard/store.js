import fs from 'node:fs';
import path from 'node:path';
import { env } from '../env.js';
import { configRegistry as DEFAULT_REGISTRY } from '../viobot/configRegistry.js';

// Single JSON file holding the editable dashboard config: { registry, admins, appearance }.
// Missing/invalid → falls back to the built-in defaults, so the dashboard can never break from a bad file.
const FILE = path.join(env.dataDir, 'dashboard.json');
const FIELD_TYPES = new Set(['role', 'role[]', 'channel', 'bool', 'string', 'number', 'select']);

let _cache = null;

export function validateRegistry(reg) {
  if (!reg || !Array.isArray(reg.groups)) throw new Error('registry.groups must be an array');
  const seenPaths = new Set();
  for (const g of reg.groups) {
    if (!g || typeof g.id !== 'string' || !g.id.trim()) throw new Error('each group needs an id');
    if (typeof g.label !== 'string' || !g.label.trim()) throw new Error(`group ${g.id} needs a label`);
    if (!Array.isArray(g.fields)) throw new Error(`group ${g.id} fields must be an array`);
    for (const f of g.fields) {
      if (!f || typeof f.path !== 'string' || !/^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*$/.test(f.path)) {
        throw new Error(`invalid field path: ${JSON.stringify(f?.path)}`);
      }
      if (!FIELD_TYPES.has(f.type)) throw new Error(`field ${f.path}: invalid type ${f.type}`);
      if (typeof f.label !== 'string' || !f.label.trim()) throw new Error(`field ${f.path} needs a label`);
      if (f.type === 'select' && !Array.isArray(f.options)) throw new Error(`select field ${f.path} needs options`);
      if (seenPaths.has(f.path)) throw new Error(`duplicate field path: ${f.path}`);
      seenPaths.add(f.path);
    }
  }
  return true;
}

function load() {
  if (_cache) return _cache;
  let data = {};
  try { data = JSON.parse(fs.readFileSync(FILE, 'utf8')); } catch { data = {}; }
  let registry = structuredClone(DEFAULT_REGISTRY);
  if (data.registry) {
    try { validateRegistry(data.registry); registry = data.registry; } catch { /* keep default */ }
  }
  _cache = {
    registry,
    admins: Array.isArray(data.admins) ? data.admins.map(String) : [],
    appearance: data.appearance && typeof data.appearance === 'object' ? data.appearance : {},
  };
  return _cache;
}

function persist() {
  fs.mkdirSync(path.dirname(FILE), { recursive: true });
  fs.writeFileSync(FILE, JSON.stringify(_cache, null, 2));
}

export function getRegistry() { return load().registry; }
export function setRegistry(reg) {
  validateRegistry(reg);
  load().registry = reg;
  persist();
  return reg;
}

export function getStoredAdmins() { return load().admins; }
export function setStoredAdmins(ids) {
  load().admins = [...new Set((Array.isArray(ids) ? ids : []).map(String).map((s) => s.trim()).filter(Boolean))];
  persist();
  return load().admins;
}

export function isDashboardAdmin(userId) {
  if (!userId) return false;
  const id = String(userId);
  return env.adminIds.includes(id) || getStoredAdmins().includes(id);
}

export function sanitizeAppearance(a) {
  if (!a || typeof a !== 'object') return {};
  const out = {};
  if (typeof a.brandName === 'string') out.brandName = a.brandName.slice(0, 60);
  if (a.logo === null) out.logo = null;
  else if (typeof a.logo === 'string') out.logo = a.logo.slice(0, 2_000_000);
  if (a.theme && typeof a.theme === 'object') {
    out.theme = {};
    for (const [k, v] of Object.entries(a.theme)) if (typeof v === 'string' && v) out.theme[k] = v.slice(0, 40);
  }
  if (Array.isArray(a.tabs)) {
    out.tabs = a.tabs.filter((t) => t && typeof t.id === 'string')
      .map((t) => ({ id: t.id, label: typeof t.label === 'string' ? t.label.slice(0, 40) : t.id, hidden: Boolean(t.hidden) }));
  }
  return out;
}

export function getAppearance() { return load().appearance; }
export function setAppearance(a) { load().appearance = sanitizeAppearance(a); persist(); return load().appearance; }
