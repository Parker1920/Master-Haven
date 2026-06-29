import { env } from '../env.js';
import { getDb } from '../db.js';

// Mirrors the bot's feature keys (src/utils/featureAccess.js). Access = premium entitlement OR beta.
// (The bot-owner override is intentionally excluded — this is the per-server access view.)
export const FEATURE_LIST = [
  { key: 'custom_contact_categories', label: 'Custom contact categories' },
  { key: 'announce_command', label: 'Scheduled announcements (!announce)' },
  { key: 'activity_reports', label: 'Activity reports' },
  { key: 'custom_avatar', label: 'Custom server avatar' },
  { key: 'alias_limits', label: 'Higher alias limits' },
];

const cache = new Map();
const TTL_MS = 60_000;

export function readBeta(guildId) {
  const db = getDb();
  const bg = db.prepare('SELECT enabled FROM beta_guilds WHERE guild_id = ?').get(guildId);
  const feats = db
    .prepare('SELECT feature_key FROM beta_guild_features WHERE guild_id = ? AND enabled = 1')
    .all(guildId)
    .map((r) => r.feature_key);
  return { isBetaGuild: Boolean(bg?.enabled), betaFeatures: new Set(feats) };
}

async function checkPremium(guildId) {
  if (!env.botToken || !env.discord.clientId || !env.plusSkuId) return { available: false, plus: false };
  const key = `plus:${guildId}`;
  const hit = cache.get(key);
  if (hit && hit.exp > Date.now()) return hit.data;
  let data = { available: false, plus: false };
  try {
    const url =
      `https://discord.com/api/v10/applications/${env.discord.clientId}/entitlements` +
      `?guild_id=${guildId}&sku_ids=${env.plusSkuId}&exclude_ended=true`;
    const res = await fetch(url, { headers: { Authorization: `Bot ${env.botToken}` } });
    if (res.ok) {
      const arr = await res.json();
      data = { available: true, plus: Array.isArray(arr) && arr.length > 0 };
    }
  } catch {
    data = { available: false, plus: false };
  }
  cache.set(key, { data, exp: Date.now() + TTL_MS });
  return data;
}

// A guild has a feature if it has the exact beta key, the 'all' beta wildcard, or an active Plus entitlement.
export async function hasFeature(guildId, key) {
  const beta = readBeta(guildId);
  if (beta.betaFeatures.has(key) || beta.betaFeatures.has('all')) return true;
  const premium = await checkPremium(guildId);
  return premium.plus;
}

export async function getFeatureAccess(guildId) {
  const beta = readBeta(guildId);
  const premium = await checkPremium(guildId);
  const features = FEATURE_LIST.map((f) => {
    const hasBeta = beta.betaFeatures.has(f.key) || beta.betaFeatures.has('all'); // 'all' = every feature (free Plus)
    const sources = [];
    if (premium.plus) sources.push('premium');
    if (hasBeta) sources.push('beta');
    return { key: f.key, label: f.label, allowed: sources.length > 0, premium: premium.plus, beta: hasBeta, source: sources.join(' + ') || 'none' };
  });
  return {
    plus: premium.plus,
    plusAvailable: premium.available,
    isBetaGuild: beta.isBetaGuild,
    betaFeatureCount: beta.betaFeatures.size,
    features,
  };
}
