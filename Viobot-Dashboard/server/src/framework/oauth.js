import { env } from '../env.js';

// Generic Discord OAuth2 client. Knows nothing about Viobot — part of the reusable framework.
const DISCORD_API = 'https://discord.com/api';

export function buildAuthUrl(state) {
  const p = new URLSearchParams({
    client_id: env.discord.clientId,
    redirect_uri: env.discord.redirectUri,
    response_type: 'code',
    scope: env.discord.scopes.join(' '),
    state,
    prompt: 'none',
  });
  return `${DISCORD_API}/oauth2/authorize?${p.toString()}`;
}

export async function exchangeCode(code) {
  const body = new URLSearchParams({
    client_id: env.discord.clientId,
    client_secret: env.discord.clientSecret,
    grant_type: 'authorization_code',
    code,
    redirect_uri: env.discord.redirectUri,
  });
  const res = await fetch(`${DISCORD_API}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  if (!res.ok) throw new Error(`Token exchange failed: ${res.status} ${await res.text()}`);
  return res.json(); // { access_token, token_type, expires_in, refresh_token, scope }
}

export async function fetchUser(accessToken) {
  const res = await fetch(`${DISCORD_API}/users/@me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`fetchUser failed: ${res.status}`);
  return res.json();
}

export async function fetchUserGuilds(accessToken) {
  const res = await fetch(`${DISCORD_API}/users/@me/guilds`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`fetchUserGuilds failed: ${res.status}`);
  return res.json(); // partial guild objects incl. `permissions` (string bitfield) and `owner`
}
