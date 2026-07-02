// Editable theme tokens (map to the CSS variables in styles.css) + the canonical per-server tabs.
// Defaults mirror the cosmic palette in styles.css :root. The panel/border tokens actually render as
// translucent rgba() (glass over the gradient); the hex here is an opaque approximation for the color picker.
export const THEME_TOKENS = [
  { key: 'accent', cssVar: '--accent', label: 'Accent', default: '#22d3ee' },
  { key: 'accent2', cssVar: '--accent-2', label: 'Accent 2 (Discord)', default: '#5865f2' },
  { key: 'bg', cssVar: '--bg', label: 'Background', default: '#050816' },
  { key: 'panel', cssVar: '--panel', label: 'Panel', default: '#0c1526' },
  { key: 'panel2', cssVar: '--panel-2', label: 'Panel (raised)', default: '#101d34' },
  { key: 'border', cssVar: '--border', label: 'Border', default: '#223349' },
  { key: 'text', cssVar: '--text', label: 'Text', default: '#edf7ff' },
  { key: 'muted', cssVar: '--muted', label: 'Muted text', default: '#94a9c7' },
];

export const DEFAULT_TABS = [
  { id: 'settings', label: 'Settings' },
  { id: 'tickets', label: 'Tickets' },
  { id: 'variables', label: 'Variables' },
  { id: 'aliases', label: 'Aliases' },
  { id: 'plus', label: 'Plus / Beta' },
];

export const DEFAULT_BRAND = 'Viobot Dashboard';
export const brandName = (a) => a?.brandName || DEFAULT_BRAND;

// Top-menu "Guides" item — embeds the docs site (served from its own origin so its assets resolve).
// URL/label are admin-editable via Appearance; a hidden toggle drops the nav item entirely.
export const DEFAULT_GUIDES_URL = '/setup-guide.html'; // same-origin Viobot server-setup guide (art3mis's ref docs stay at /docs/)
export const DEFAULT_GUIDES_LABEL = 'Guides';
export const guidesUrl = (a) => (typeof a?.guidesUrl === 'string' && a.guidesUrl.trim() ? a.guidesUrl.trim() : DEFAULT_GUIDES_URL);
export const guidesLabel = (a) => (typeof a?.guidesLabel === 'string' && a.guidesLabel.trim() ? a.guidesLabel.trim() : DEFAULT_GUIDES_LABEL);
export const guidesEnabled = (a) => a?.guidesEnabled !== false; // default: shown

// The Guides page is a selector between these docs. Picking one opens it same-origin in an iframe
// and pushes /guides/<slug> (deep-linkable, browser-back friendly). Order = display order.
export const GUIDES = [
  {
    slug: 'setup',
    title: 'Server Setup Guide',
    icon: '🛠️',
    tag: '~15 min',
    blurb: 'Step-by-step: the roles, channels, and permissions to create so mutes, tickets, and logging actually work.',
    url: '/setup-guide.html',
  },
  {
    slug: 'docs',
    title: 'Viobot Documentation',
    icon: '📖',
    tag: 'Reference',
    blurb: 'The full reference — every command, feature, workflow, and FAQ for the bot.',
    url: '/docs/',
  },
];
export const guideBySlug = (slug) => GUIDES.find((g) => g.slug === slug) || null;

// Apply theme variables to the live document.
export function applyAppearance(appearance) {
  const root = document.documentElement;
  const theme = appearance?.theme || {};
  for (const t of THEME_TOKENS) {
    const v = theme[t.key];
    if (typeof v === 'string' && /^(#|rgb|hsl)/i.test(v.trim())) root.style.setProperty(t.cssVar, v.trim());
    else root.style.removeProperty(t.cssVar);
  }
  document.getElementById('vbd-custom-css')?.remove(); // clean up any legacy injected style
}

// All tabs merged with defaults (so a newly-added canonical tab is never lost), labels + hidden applied.
export function mergedTabs(appearance) {
  const conf = Array.isArray(appearance?.tabs) ? appearance.tabs : [];
  const ids = new Set(conf.map((t) => t.id));
  const merged = conf.filter((t) => DEFAULT_TABS.some((d) => d.id === t.id)).map((t) => ({
    id: t.id,
    label: t.label || DEFAULT_TABS.find((d) => d.id === t.id)?.label || t.id,
    hidden: Boolean(t.hidden),
  }));
  for (const d of DEFAULT_TABS) if (!ids.has(d.id)) merged.push({ id: d.id, label: d.label, hidden: false });
  return merged;
}

// Visible tabs only, in order — what ConfigPage renders.
export const visibleTabs = (appearance) => mergedTabs(appearance).filter((t) => !t.hidden).map(({ id, label }) => ({ id, label }));
