import React, { useEffect, useRef } from 'react'

// Wizard v1 help panel (mockup .v11-help-panel 10263-10298, expanded May 2026).
//
// Slide-in drawer from the right. Each FAQ item has a stable `anchor` so the
// inline `(?)` HelpChips and the mobile HelpFab can deep-link to a specific
// entry. When opened with an anchor, the panel scrolls that item into view
// and auto-expands its <details>.
//
// FAQ items are organized into groups for scannability. The original 7
// items from the mockup are preserved verbatim under their natural groups;
// 10 new items added per Parker's May 2026 expansion.
//
// Props:
//   open: bool
//   onClose()
//   initialAnchor?: string — anchor of the FAQ item to scroll to + open
const FAQ_GROUPS = [
  {
    title: 'Getting Started',
    items: [
      {
        anchor: 'glyphs',
        q: 'What are Glyphs / Portal Coordinates?',
        a: `Each NMS system has a 12-character hexadecimal portal address. The first character is the planet index, the next 3 are the solar system index within the region, and the remaining 8 are the region's X/Y/Z voxel coordinates.

To find them: stand at any portal (the big stone arches), or open photo mode anywhere in the system to see the address overlay. You can also read them from a save file. The wizard's Glyph Picker lets you click each glyph icon — no typing needed.`,
      },
      {
        anchor: 'easy-vs-advanced',
        q: "What's the Easy vs Advanced wizard?",
        a: `Easy ("First Charting") is a 4-step linear flow for getting a system into Haven fast: glyphs → community → name & star → planets. Skips the optional fields. Best for your first submission or if you're in a hurry.

Advanced ("Full Logbook") is a single-page form with a sticky sidebar covering 7 sections: Portal, System Attributes, Planets & Moons, Space Station, Discoveries, Identity, Submit. Use this when you've fully scanned the system and want to log every detail.

You can switch between flows at the top toolbar at any time without losing data.`,
      },
      {
        anchor: 'submit-flow',
        q: 'What happens after I submit?',
        a: `Public submissions go into the approval queue. The community partner that owns your selected Discord community reviews them — typically within a day or two depending on how active the partner is. Approved systems land in the live database and show up on the map and in browse views.

Partners and Haven super-admins can save systems directly without going through the queue. You'll see the system live immediately in that case.

If your submission needs corrections, the approver may edit the system data before approving, or reject with a reason you can act on.`,
      },
      {
        anchor: 'edit-system',
        q: 'Can I edit a system after submitting?',
        a: `Yes. Open any system page and click "Edit" — that takes you to the wizard with ?edit=<id> in the URL. The wizard loads the existing data and shows an "✎ Edit Mode" badge.

Fields you change get an amber border so you (and the approver) can see what's different at a glance. The same approval queue applies — your edit goes through review unless you're the original submitter or have approval permissions.

If two people are editing the same system at once, the conflict resolution modal at submit lets you pick "yours" vs "what's already in Haven" per field.`,
      },
    ],
  },
  {
    title: 'System Attributes',
    items: [
      {
        anchor: 'spectral-class',
        q: 'Spectral Class — what do the letters mean?',
        a: `Spectral class is a real astronomy classification scheme NMS uses for star types. The first letter is the temperature class:
O/B = blue, F/G = yellow, K/M = red, E = green, X/Y = purple. The number (0-9) is sub-class.
Suffixes (p, f, etc.) are optional decorators. Example: G2pf is a yellow main-sequence star.`,
      },
      {
        anchor: 'wealth-tier',
        q: 'Wealth Tier (T1/T2/T3/T4) — what does it mean?',
        a: `T1 = Low (★), T2 = Medium (★★), T3 = High (★★★), T4 = Pirate (☠).
Wealth determines what trade goods are sold at the station — pick the tier shown next to your station's economy text in-game.`,
      },
      {
        anchor: 'conflict-level',
        q: 'Conflict Level — what does each option mean?',
        a: `Low = peaceful, Medium = some pirate activity, High = active conflict zone, Pirate = pirate-controlled.
None = abandoned/uninhabited (only valid when economy = None or Abandoned).`,
      },
      {
        anchor: 'lifeform',
        q: "What's the difference between None and Abandoned for Dominant Lifeform?",
        a: `These look similar but mean different things and we track them separately:

• None — the system has no dominant lifeform and never did. No buildings, no race, just stars and planets. Common for sentinel-only systems and Atlas systems.

• Abandoned — the system used to be inhabited. There are buildings, outposts, maybe a station, but nobody's home now. The race left.

The Gek/Vy'keen/Korvax options are for inhabited systems with that race in charge.`,
      },
    ],
  },
  {
    title: 'Planets & Discoveries',
    items: [
      {
        anchor: 'planet-attrs',
        q: 'Planet Attributes — what are the special flags?',
        a: `These are rare planet conditions: Has Rings, Dissonant System, Infested, Extreme Weather, Water World,
Vile Brood, Bubble Planet, Floating Islands, Gas Giant, Ancient Bones, Salvageable Scrap, Storm Crystals, Gravitino Balls.
Tick the ones that apply — they affect the system's completeness grade.`,
      },
      {
        anchor: 'exotic-trophy',
        q: 'Exotic Trophy — when do I fill that in?',
        a: `Only when the planet is an Exotic biome and has a unique surface collectible (e.g. Storm Crystals on Storm planets).
Pick from the dropdown; leave blank if the planet has no exotic trophy.`,
      },
      {
        anchor: 'discoveries',
        q: 'What counts as a Discovery?',
        a: `Anything notable enough to log alongside the system. Haven has 12 discovery types:

🦗 Fauna · 🌿 Flora · 💎 Mineral · 🏛️ Ancient (ruins/structures) · 📜 History · 🦴 Bones · 👽 Alien (encounters) · 🚀 Starship · ⚙️ Multi-tool · 📖 Lore · 🏠 Custom Base · 🆕 Other

Add discoveries inline in the Advanced wizard's Discoveries section. Each type has its own metadata fields (ship class, fauna height, etc.). Discoveries get attached to the system when it's saved.`,
      },
      {
        anchor: 'records',
        q: '★ Submit for record — what is this?',
        a: `Some discoveries (largest fauna, S-class starships, rarest mineral deposits) are eligible for Haven's "Wonders of Haven" leaderboard.
Tick this if you think your find is among the best in its category. The wizard auto-flags it when your numbers beat the current record.`,
      },
      {
        anchor: 'photos',
        q: 'How do I upload photos?',
        a: `Click the photo dropzone, drag images onto it, or paste with Ctrl/Cmd+V. The first photo becomes the main image — drag tiles to reorder, or click the ☆ icon on any tile to make it the main photo. The × on a tile removes it.

Photos are auto-compressed to WebP (~80% smaller) with a thumbnail. Up to 10 photos per discovery.`,
      },
      {
        anchor: 'region-naming',
        q: 'Why is region naming required?',
        a: `Regions are how the community groups thousands of systems into named areas. If a region is unnamed when you submit,
you propose a name; admins approve it; subsequent submissions inherit it. This keeps the galactic map navigable.`,
      },
    ],
  },
  {
    title: 'Submitting & Identity',
    items: [
      {
        anchor: 'grading',
        q: 'How does the grading system work?',
        a: `Every system gets a completeness grade: S (85+), A (65–84), B (40–64), C (<40). The score is weighted across 6 categories:

• System Core (35) — star, economy, conflict, lifeform
• System Extra (10) — glyphs, spectral class
• Planet Coverage (10) — at least one planet
• Planet Environment (25) — biome, weather, sentinel (per planet)
• Planet Life (15) — fauna, flora, resources (biome-aware)
• Space Station (5)

X ("fully charted") is a bonus tier on top of S: the system scores S AND has a discovery on every planet & moon, wonder notes on at least one planet or moon, a documented base (base lat/long on any body, or a base discovery), and a recorded space station (abandoned / no-station systems are exempt from the station requirement).

Hover the grade letter in the sidebar to see your category breakdown and how many points to the next grade. The "Boost your grade" panel below shows the top 4 fields you could fill to climb fastest.`,
      },
      {
        anchor: 'coauthors',
        q: 'How do Co-Authors work?',
        a: `Add a co-author for anyone who helped scan the system but isn't the primary submitter. Type their Discord username in the chip input and press Enter.

Each co-author gets credit on a SEPARATE leaderboard column from primary submissions — so co-authoring never inflates your "systems submitted" count, but does count toward "co-authored systems". Up to 10 per system.`,
      },
      {
        anchor: 'expeditions',
        q: 'What are Expeditions?',
        a: `Expeditions are community-scoped charting campaigns — a named effort to map a region, run a sweep, or hunt for something specific. The whole community can see expeditions for their Discord, and any logged-in member can pick or create one.

Tag your submission with an active expedition and it counts toward that campaign's totals. Once you've picked an expedition, the wizard remembers it for follow-on submissions ("Submit Another" preserves the active expedition).

To create a new one: open the Expedition picker on the Identity section and click "+ Create new". Anonymous (not logged in) submissions can't tag expeditions.`,
      },
    ],
  },
]

export default function HelpPanel({ open, onClose, initialAnchor }) {
  const itemRefs = useRef({})

  useEffect(() => {
    if (!open) return
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  // When opened with an initialAnchor, scroll that item into the panel's
  // viewport and auto-expand its <details>.
  useEffect(() => {
    if (!open || !initialAnchor) return
    // Small delay so the panel's slide-in transform completes before we
    // scroll-to (otherwise the scroll target hasn't laid out yet).
    const t = setTimeout(() => {
      const el = itemRefs.current[initialAnchor]
      if (!el) return
      el.open = true
      el.scrollIntoView({ block: 'start' })
    }, 60)
    return () => clearTimeout(t)
  }, [open, initialAnchor])

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40"
        onClick={onClose}
      />
      {/* Slide-in panel */}
      <aside
        className="fixed right-0 top-0 bottom-0 z-50 w-full sm:w-[460px] flex flex-col shadow-2xl"
        style={{ backgroundColor: 'var(--app-card)', borderLeft: '1px solid var(--app-accent-3)' }}
      >
        <div
          className="flex items-center justify-between px-4 py-3 border-b"
          style={{ borderColor: 'var(--app-accent-3)' }}
        >
          <h2 className="font-semibold">Cartographer Help</h2>
          <button
            type="button"
            onClick={onClose}
            className="px-2 py-1 rounded text-sm"
            style={{ backgroundColor: 'var(--app-accent-3)' }}
            aria-label="Close help"
          >
            Close
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-6 text-sm">
          {FAQ_GROUPS.map((group) => (
            <section key={group.title}>
              <h3
                className="text-xs font-semibold uppercase tracking-wider opacity-70 mb-2 pb-1 border-b"
                style={{ borderColor: 'var(--app-accent-3)' }}
              >
                {group.title}
              </h3>
              <div className="space-y-2">
                {group.items.map((item) => (
                  <details
                    key={item.anchor}
                    ref={(el) => { if (el) itemRefs.current[item.anchor] = el }}
                    className="rounded p-3 scroll-mt-2"
                    style={{ backgroundColor: 'var(--app-bg)' }}
                  >
                    <summary className="cursor-pointer font-semibold">{item.q}</summary>
                    <p className="mt-2 opacity-85 whitespace-pre-line">{item.a.trim()}</p>
                  </details>
                ))}
              </div>
            </section>
          ))}
        </div>
      </aside>
    </>
  )
}
