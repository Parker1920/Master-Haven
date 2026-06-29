// Shared Discord CDN + display helpers.
export function initials(name) {
  return (name || '?')
    .trim()
    .split(/\s+/)
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

export function guildIconUrl(g, size = 128) {
  if (!g?.icon) return null;
  const ext = g.icon.startsWith('a_') ? 'gif' : 'png';
  return `https://cdn.discordapp.com/icons/${g.id}/${g.icon}.${ext}?size=${size}`;
}

export function userAvatarUrl(u, size = 64) {
  if (!u?.avatar) return null;
  const ext = u.avatar.startsWith('a_') ? 'gif' : 'png';
  return `https://cdn.discordapp.com/avatars/${u.id}/${u.avatar}.${ext}?size=${size}`;
}

// Deterministic gradient for icon-less servers so each stays visually distinct.
export function hueFromName(name) {
  let h = 0;
  const s = name || '?';
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
  return h;
}

export function fallbackGradient(name) {
  const hue = hueFromName(name);
  return `linear-gradient(135deg, hsl(${hue} 52% 34%), hsl(${(hue + 40) % 360} 52% 24%))`;
}
