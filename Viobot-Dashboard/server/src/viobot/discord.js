import { env } from '../env.js';

// Bot-token reads of a guild's roles + channels, for the config dropdowns. Cached briefly since a
// server's roles/channels rarely change and the config page may be opened repeatedly.
const API = 'https://discord.com/api/v10';
const TTL_MS = 60_000;
const cache = new Map(); // key -> { data, exp }

async function botGet(path) {
  if (!env.botToken) throw new Error('DISCORD_BOT_TOKEN not set');
  const res = await fetch(`${API}${path}`, { headers: { Authorization: `Bot ${env.botToken}` } });
  if (!res.ok) throw new Error(`Discord ${path} → ${res.status} ${await res.text().catch(() => '')}`);
  return res.json();
}

async function cached(key, fn) {
  const hit = cache.get(key);
  if (hit && hit.exp > Date.now()) return hit.data;
  const data = await fn();
  cache.set(key, { data, exp: Date.now() + TTL_MS });
  return data;
}

function colorHex(c) {
  return c ? `#${c.toString(16).padStart(6, '0')}` : null;
}

export async function getGuildRoles(guildId) {
  return cached(`roles:${guildId}`, async () => {
    const roles = await botGet(`/guilds/${guildId}/roles`);
    return roles
      .filter((r) => r.id !== guildId) // drop @everyone
      .sort((a, b) => b.position - a.position)
      .map((r) => ({ id: r.id, name: r.name, color: colorHex(r.color), managed: Boolean(r.managed) }));
  });
}

export async function getGuildChannels(guildId) {
  return cached(`channels:${guildId}`, async () => {
    const ch = await botGet(`/guilds/${guildId}/channels`);
    return ch
      .map((c) => ({ id: c.id, name: c.name, type: c.type, parentId: c.parent_id ?? null, position: c.position ?? 0 }))
      .sort((a, b) => a.position - b.position);
  });
}

// A single guild member (bot-token REST; no privileged intent needed for a by-id fetch). Returns
// `{ roles: [] }` when the user isn't in the guild (404). Cached briefly like roles/channels — so a
// role change can take up to ~1 min to reflect in dashboard access (acceptable: the caller is already
// a Discord admin, so this is a guardrail, not an escalation boundary).
export async function getGuildMember(guildId, userId) {
  return cached(`member:${guildId}:${userId}`, async () => {
    if (!env.botToken) throw new Error('DISCORD_BOT_TOKEN not set');
    const res = await fetch(`${API}/guilds/${guildId}/members/${userId}`, {
      headers: { Authorization: `Bot ${env.botToken}` },
    });
    if (res.status === 404) return { roles: [] }; // not a member of this guild
    if (!res.ok) throw new Error(`Discord member ${guildId}/${userId} → ${res.status} ${await res.text().catch(() => '')}`);
    return res.json();
  });
}
