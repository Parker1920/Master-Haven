// Thin API client. Same-origin in dev via the Vite /api proxy.
const opts = { credentials: 'include' };

async function getJson(url) {
  const res = await fetch(url, opts);
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`${url} → ${res.status}`);
  return res.json();
}

export const api = {
  loginUrl: '/api/auth/login',
  devLoginUrl: '/api/auth/dev-login',
  health: () => getJson('/api/health'),
  me: () => getJson('/api/auth/me'),
  guilds: () => getJson('/api/guilds'),
  getGuildConfig: (id) => getJson(`/api/guilds/${id}/config`),
  saveGuildConfig: (id, config, updatedAt) =>
    fetch(`/api/guilds/${id}/config`, {
      method: 'PUT',
      ...opts,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config, updatedAt }),
    }).then(async (r) => {
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        const e = new Error(d.message || d.error || `save failed (${r.status})`);
        e.status = r.status;
        e.code = d.error;
        throw e;
      }
      return d;
    }),
  getVariables: (id) => getJson(`/api/guilds/${id}/variables`),
  saveVariables: (id, variables) =>
    fetch(`/api/guilds/${id}/variables`, {
      method: 'PUT',
      ...opts,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ variables }),
    }).then(async (r) => {
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        const e = new Error(d.message || d.error || `save failed (${r.status})`);
        e.status = r.status;
        throw e;
      }
      return d;
    }),
  getAliases: (id) => getJson(`/api/guilds/${id}/aliases`),
  updateAlias: (id, name, body) =>
    fetch(`/api/guilds/${id}/aliases/${encodeURIComponent(name)}`, {
      method: 'PUT', ...opts, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }).then(async (r) => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.error || `failed (${r.status})`); return d; }),
  deleteAlias: (id, name) =>
    fetch(`/api/guilds/${id}/aliases/${encodeURIComponent(name)}`, { method: 'DELETE', ...opts })
      .then(async (r) => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.error || `failed (${r.status})`); return d; }),
  getPremium: (id) => getJson(`/api/guilds/${id}/premium`),
  getAnnouncements: (id) => getJson(`/api/guilds/${id}/announcements`),
  createAnnouncement: (id, body) =>
    fetch(`/api/guilds/${id}/announcements`, {
      method: 'POST', ...opts, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }).then(async (r) => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.message || d.error || `failed (${r.status})`); return d; }),
  deleteAnnouncement: (id, annId) =>
    fetch(`/api/guilds/${id}/announcements/${encodeURIComponent(annId)}`, { method: 'DELETE', ...opts })
      .then(async (r) => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.error || `failed (${r.status})`); return d; }),
  getAvatar: (id) => getJson(`/api/guilds/${id}/avatar`),
  setAvatar: (id, dataUri) =>
    fetch(`/api/guilds/${id}/avatar`, {
      method: 'PUT', ...opts, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ dataUri }),
    }).then(async (r) => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.message || d.error || `failed (${r.status})`); return d; }),
  resetAvatar: (id) =>
    fetch(`/api/guilds/${id}/avatar`, { method: 'DELETE', ...opts })
      .then(async (r) => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.message || d.error || `failed (${r.status})`); return d; }),
  getAppearance: () => getJson('/api/appearance'),
  adminSaveAppearance: (appearance) =>
    fetch('/api/admin/appearance', { method: 'PUT', ...opts, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ appearance }) })
      .then(async (r) => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.message || d.error || `failed (${r.status})`); return d; }),
  adminGetRegistry: () => getJson('/api/admin/registry'),
  adminSaveRegistry: (registry) =>
    fetch('/api/admin/registry', { method: 'PUT', ...opts, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ registry }) })
      .then(async (r) => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.message || d.error || `failed (${r.status})`); return d; }),
  adminBotStatus: () => getJson('/api/admin/bot-status'),
  // Maps each control action to its server route (see server/src/routes/admin.js):
  // restart → POST /api/admin/restart-bot ; start/stop/reimage → POST /api/admin/bot/<action>.
  adminBotAction: (action) => {
    const routes = { restart: 'restart-bot', start: 'bot/start', stop: 'bot/stop', reimage: 'bot/reimage' };
    const path = routes[action];
    if (!path) return Promise.reject(new Error(`unknown bot action: ${action}`));
    return fetch(`/api/admin/${path}`, { method: 'POST', ...opts })
      .then(async (r) => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.message || d.error || `failed (${r.status})`); return d; });
  },
  adminRestartBot: () => api.adminBotAction('restart'),
  adminGetAdmins: () => getJson('/api/admin/admins'),
  adminSaveAdmins: (admins) =>
    fetch('/api/admin/admins', { method: 'PUT', ...opts, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ admins }) })
      .then(async (r) => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.error || `failed (${r.status})`); return d; }),
  logout: () => fetch('/api/auth/logout', { method: 'POST', ...opts }).then((r) => r.json()),
};
