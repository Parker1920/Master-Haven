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
  logout: () => fetch('/api/auth/logout', { method: 'POST', ...opts }).then((r) => r.json()),
};
