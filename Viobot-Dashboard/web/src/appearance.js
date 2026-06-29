// Editable theme tokens (map to the CSS variables in styles.css) + the canonical per-server tabs.
export const THEME_TOKENS = [
  { key: 'accent', cssVar: '--accent', label: 'Accent', default: '#14b8a6' },
  { key: 'accent2', cssVar: '--accent-2', label: 'Accent 2 (Discord)', default: '#5865f2' },
  { key: 'bg', cssVar: '--bg', label: 'Background', default: '#0e1016' },
  { key: 'panel', cssVar: '--panel', label: 'Panel', default: '#171a23' },
  { key: 'panel2', cssVar: '--panel-2', label: 'Panel (raised)', default: '#1e222e' },
  { key: 'border', cssVar: '--border', label: 'Border', default: '#272c3a' },
  { key: 'text', cssVar: '--text', label: 'Text', default: '#e7e9f0' },
  { key: 'muted', cssVar: '--muted', label: 'Muted text', default: '#9aa3b6' },
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
