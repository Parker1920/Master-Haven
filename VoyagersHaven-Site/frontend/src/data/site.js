// All editable site content in one place — copy, portfolio, hosting, infra,
// tiers, footer. Attribution is deliberate: `built` = VH designed & built,
// `client` = built under contract, `hosted` = we keep it online (maker named),
// `internal` = our own R&D.

export const CONTACT_EMAIL = 'ekimo.vhav@gmail.com'

export const CAPABILITIES = [
  { k: 'Model', v: 'Self-hosted, end to end' },
  { k: 'Stack', v: 'FastAPI · React · SQLite' },
  { k: 'Also', v: 'Local AI · Discord bots' },
  { k: 'Based in', v: 'Mechanicsburg, PA' },
]

export const SERVICES = [
  {
    icon: 'app',
    title: 'Web applications',
    body: 'Full-stack apps and internal tools — from the data model up to a UI people actually want to use.',
  },
  {
    icon: 'chart',
    title: 'Dashboards & admin',
    body: 'Control panels that turn messy data into something you can read, filter, and act on at a glance.',
  },
  {
    icon: 'ai',
    title: 'Local AI',
    body: 'Private assistants and retrieval over your own knowledge, on your box. Nothing leaves the machine.',
  },
  {
    icon: 'server',
    title: 'Self-hosted deploys',
    body: 'We stand the product up on hardware we run and keep it online — no cloud markup for the life of the project.',
  },
]

// --------------------------------------------------------------------------
// PORTFOLIO
// role: built | client | community | hosted | internal
// status: 'live' | 'dev'
// maker: credit line for work we host but didn't author
// --------------------------------------------------------------------------

// The Haven ecosystem — the No Man's Sky community platform we built.
export const ECOSYSTEM = [
  {
    name: 'Haven Control Room',
    domain: 'havenmap.online',
    role: 'built',
    status: 'live',
    body: "A 3D galaxy atlas for the No Man's Sky community — an interactive map of 13,700+ catalogued star systems with search, region naming, contributor tools, and a full admin approval pipeline.",
    tags: ['FastAPI', 'React', 'Three.js', 'SQLite'],
  },
  {
    name: 'Travelers Archive',
    domain: 'haven-archive.online',
    role: 'built',
    status: 'live',
    body: 'A community newsroom and encyclopedia — contributors file briefs and features on civilizations, places, people, and events that cross-link into a living reference.',
    tags: ['FastAPI', 'React', 'SQLite'],
  },
  {
    name: 'Travelers Exchange',
    domain: 'travelers-exchange.online',
    role: 'built',
    status: 'live',
    body: 'A full virtual economy for the community — Travelers Coin, nation treasuries, a blockchain ledger, a marketplace, and a live stock exchange, with banks, loans, and minting.',
    tags: ['FastAPI', 'SQLite', 'Jinja'],
  },
  {
    name: 'Haven Extractor',
    domain: 'desktop tool',
    role: 'built',
    status: 'live',
    body: "An in-game extraction mod that reads live No Man's Sky data and uploads catalogued systems straight into the atlas — with procedural naming and a self-updating installer for a growing user base.",
    tags: ['Python', 'PyMHF', 'NMS.py'],
  },
  {
    name: 'Planet Atlas',
    domain: 'internal tool',
    role: 'built',
    status: 'live',
    body: 'Interactive 3D planetary cartography — renders individual worlds and points of interest from catalogued data.',
    tags: ['Python', 'Dash', 'Plotly'],
  },
]

// Sites we built for community events.
export const COMMUNITY = [
  {
    name: 'Grand Festival',
    domain: 'grandfestival.online',
    role: 'built',
    status: 'live',
    body: 'A community festival site for Summer Unification Day — signups, a live schedule, and a civilizations showcase.',
    tags: ['FastAPI', 'React', 'SQLite'],
  },
  {
    name: 'NMS10',
    domain: 'nms10.online',
    role: 'built',
    status: 'live',
    body: "A community celebration site we built and host for No Man's Sky's 10th anniversary — a landmark for the players who've charted the galaxy with us.",
    tags: ['FastAPI', 'React', 'SQLite'],
  },
  {
    name: 'Skyscraper Tracker',
    domain: 'skyscraper.havenmap.online',
    role: 'built',
    status: 'live',
    body: 'A live tracker for the Project Skyscraper No Man’s Sky ARG — documents the mystery and surfaces new clues the moment they drop.',
    tags: ['HTML', 'CSS', 'JS'],
  },
  {
    name: 'Skyscraper Watcher',
    domain: 'automation',
    role: 'built',
    status: 'live',
    body: "A change-notifier that watches the ARG's site, sitemaps, and socials every two minutes and pushes each update to Discord and the community forums — and triggers an external archive re-crawl.",
    tags: ['Python', 'Discord', 'cron'],
  },
]

// Built under contract for a client.
export const CLIENT = [
  {
    name: 'Viobot Dashboard',
    domain: 'viobot.havenmap.online',
    role: 'client',
    status: 'live',
    maker: 'Built for the Viobot team',
    body: 'A standalone configuration dashboard for the Viobot Discord bot. Real Discord login, an admin-scoped server picker, and per-server controls the bot enforces live — fully isolated from every other system we run.',
    tags: ['Node', 'React', 'SQLite', 'Docker'],
  },
]

// Our own R&D — shown as capability, not a product for sale.
export const INTERNAL = [
  {
    name: 'Haven Brain',
    domain: 'internal',
    role: 'internal',
    status: 'live',
    body: 'A private local-AI assistant that answers over our own knowledge base and runs entirely on owned hardware. Retrieval-augmented and fully offline — nothing leaves the machine.',
    tags: ['Ollama', 'ChromaDB', 'RAG'],
  },
  {
    name: 'Haven Trade Engine',
    domain: 'R&D',
    role: 'internal',
    status: 'dev',
    body: 'In-house quantitative trading research — market-neutral strategy work and reinforcement-learning experiments. Private by design; here only as proof of our AI + quant range.',
    tags: ['Python', 'RL', 'Backtesting'],
  },
]

// Projects by others that we keep online (credited to their makers). Shown as
// cards on the Hosting page alongside the full fleet list below.
export const HOSTED = [
  {
    name: 'The Keeper',
    domain: 'Discord',
    role: 'hosted',
    status: 'live',
    maker: 'Bot by Stars — we keep it online',
    body: 'The community Discord bot for the Haven server — XP, glyph tools, and community features. Maintained by Stars; hosted on our infrastructure.',
    tags: ['Python', 'discord.py'],
  },
  {
    name: 'Viobot Docs',
    domain: 'viobot.havenmap.online/docs',
    role: 'hosted',
    status: 'live',
    maker: 'Docs by art3mis — synced & served',
    body: "The Viobot documentation, synced from the maintainer's repo and served alongside the dashboard.",
    tags: ['Static', 'Nginx'],
  },
]

// Everything running on the one box — the "what we host" fleet (Hosting page).
// role: built | client | hosted | internal.  maker = credit when we didn't build it.
export const FLEET = [
  { name: 'Haven Control Room', domain: 'havenmap.online', role: 'built' },
  { name: 'Travelers Archive', domain: 'haven-archive.online', role: 'built' },
  { name: 'Travelers Exchange', domain: 'travelers-exchange.online', role: 'built' },
  { name: 'Grand Festival', domain: 'grandfestival.online', role: 'built' },
  { name: 'NMS10', domain: 'nms10.online', role: 'built' },
  { name: 'Skyscraper Tracker', domain: 'skyscraper.havenmap.online', role: 'built' },
  { name: 'Skyscraper Watcher', domain: 'monitor · Pi cron', role: 'built' },
  { name: "Voyager's Haven", domain: 'voyagershaven.online', role: 'built' },
  { name: 'Viobot Dashboard', domain: 'viobot.havenmap.online', role: 'client' },
  { name: 'Viobot Docs', domain: 'viobot.havenmap.online/docs', role: 'hosted', maker: 'by art3mis' },
  { name: 'The Keeper', domain: 'Discord bot', role: 'hosted', maker: 'by Stars' },
  { name: 'Haven Brain', domain: 'internal', role: 'internal' },
]

// The self-hosting story for the Hosting page.
export const STACK = [
  { k: 'Hardware', v: 'Raspberry Pi 5 — owned, on-prem' },
  { k: 'Runtime', v: 'Docker · one compose stack' },
  { k: 'Routing', v: 'Nginx Proxy Manager · TLS' },
  { k: 'Data', v: 'SQLite · host-mounted & backed up' },
  { k: 'Local AI', v: 'Ollama · models on the box' },
  { k: 'Delivery', v: 'Git-driven auto-deploy' },
]

export const STATS = [
  { n: '12', l: 'Services online' },
  { n: '8', l: 'Live domains' },
  { n: '1', l: 'Box, self-hosted' },
  { n: '2026', l: 'PA LLC formed' },
]

export const PRINCIPLES = [
  {
    title: 'Own the whole stack',
    body: 'Data model, interface, and the server it runs on — one team, no gaps between them.',
  },
  {
    title: 'No handoffs',
    body: "We don't ship a repo and disappear. We build it, deploy it, and keep it running.",
  },
  {
    title: 'No cloud margin',
    body: 'Self-hosted on hardware we own, so hosting cost stays flat for the life of the project.',
  },
]

export const TIERS = [
  { amount: 5, name: 'Supporter' },
  { amount: 15, name: 'Navigator' },
  { amount: 40, name: 'Cartographer' },
]

export const PROJECT_TYPES = [
  'Web application',
  'Dashboard / admin tool',
  'Local AI / assistant',
  'Discord bot',
  'Something else',
]

export const BUDGETS = ['Under $1k', '$1k – $5k', '$5k – $15k', '$15k+', 'Not sure yet']
