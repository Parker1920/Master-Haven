const TIMELINE = [
  ['The Grand Festival · in-game lore', 'Long before any traveler logged in, the in-game record tells of the Trade Lords gathering mid-year for the Grand Festival — an extravaganza of gambling, GekNip, and fireworks, preserved in a crashed Gek freighter’s distress beacon. It is the oldest gathering of its kind, and the namesake of this summer event.'],
  ['2017 · The first gathering', 'The United Federation of Travelers organizes the first community Unification Day, held December 30 in a single system in the Delta Quadrant. Modest in size but template-setting: an opening ceremony, a shared host world, and travelers proving they could find one another across the void.'],
  ['2018 – 2020 · The Jatriwil era', 'The Empire of Jatriwil takes the hosting baton and runs with it. Exocraft drag races, sculpting contests, and PvP arenas become signature traditions — several of which still anchor the schedule today — as attendance climbs year over year across the hubs.'],
  ['2021 – 2022 · Galactic Hub Eissentam', 'The format expands under Galactic Hub Eissentam. The Closing Ceremony rave at UD XXI becomes the stuff of legend, and cross-platform play opens the gathering to PC, PlayStation, Xbox, and Switch travelers alike.'],
  ['2023 – 2025 · Grand Unification Day', 'Galactic Hub Project assumes coordination and reimagines the event: no longer a single-system party but a multi-civilization tour across worlds and alliances. “Grand Unification Day” cements UD as the community’s flagship annual gathering.'],
]

export default function About() {
  return (
    <main className="page active">
      <section className="about-hero">
        <h1>About the Festival</h1>
        <p>
          From a distress beacon to a decade of gatherings — and now, every Trade Lord, traveler,
          and wandering alliance has two reasons to assemble.
        </p>
      </section>

      <section className="about-body">
        <div className="about-inner">
          <div className="lore-box">
            <div className="source">From a Crashed Ship's Distress Beacon</div>
            <blockquote>
              “Groups of similar minds, unable to meet but attempting to find one another, to claim
              worlds across time and space. Once a year their various alliances, federations, hubs,
              and empires united to remember all that they were, and could become in time…”
            </blockquote>
            <cite>— The original in-game log that started it all (writ. Greg Buchanan, Hello Games)</cite>
          </div>

          <div className="about-section">
            <h2>What is Unification Day?</h2>
            <p>
              Unification Day is the largest fan-run gathering in No Man's Sky. Every December since{' '}
              <strong>2017</strong>, civilizations across every galaxy converge in a single host
              system to celebrate what holds the community together — exploration, friendship, and
              the shared act of leaving footprints across infinite worlds.
            </p>
            <p>
              It started as a single party. It became a tradition. By 2023 it had evolved into a
              multi-civilization tour — a moving festival across the universe.{' '}
              <strong>2026 marks the 10th annual UD</strong>, alongside No Man's Sky's own 10-year
              anniversary year.
            </p>
          </div>

          <div className="about-section">
            <h2>Why summer?</h2>
            <p>
              For nine years UD has lived at the end of December — winter solstice, holiday season,
              an in-game new year. Beautiful, but <em>cold</em>. The community kept asking:{' '}
              <strong>why only once?</strong>
            </p>
            <p>
              The in-game record gives us the answer. Long before our first UD, the Trade Lords
              assembled mid-year for what they called <strong>the Grand Festival</strong> — an
              extravaganza of gambling, GekNip, and fireworks. We've been re-running half of the
              tradition. It's time we ran the other half.
            </p>
            <p>
              Summer Unification Day is that other half. The end-of-year UD remains the canonical
              “main” event. Summer UD is its warmer, looser, more festival-coded sibling — and it
              has lore on its side.
            </p>
          </div>

          <div className="about-section">
            <h2>Two events, one tradition</h2>
            <div className="compare-grid">
              <div className="compare-card summer">
                <h3>☀ Summer UD</h3>
                <ul>
                  <li><strong>When:</strong> Mid-year (target: July)</li>
                  <li><strong>Vibe:</strong> Grand Festival, open-air, celebratory</li>
                  <li><strong>Tone:</strong> Loose, playful, abundant</li>
                  <li><strong>Theme builds:</strong> Pavilions, gathering halls, festival grounds</li>
                  <li><strong>First held:</strong> 2026 (this one)</li>
                </ul>
              </div>
              <div className="compare-card winter">
                <h3>❄ Winter UD</h3>
                <ul>
                  <li><strong>When:</strong> Late December</li>
                  <li><strong>Vibe:</strong> Solemn, ceremonial, reflective</li>
                  <li><strong>Tone:</strong> The “official” annual gathering</li>
                  <li><strong>Theme builds:</strong> Monuments, halls, capital cities</li>
                  <li><strong>First held:</strong> 2017</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="about-section">
            <h2>A brief history</h2>
            <p>
              Unification Day has grown from a single December party into the largest fan-run
              tradition in No Man's Sky — passed hand to hand between civilizations, reinvented
              almost every year. Here's the throughline, and where the Summer Grand Festival fits in.
            </p>
            <div className="timeline">
              {TIMELINE.map(([year, what]) => (
                <div className="timeline-item" key={year}>
                  <div className="year">{year}</div>
                  <div className="what">{what}</div>
                </div>
              ))}
              <div className="timeline-item">
                <div className="year">2026 · Summer Grand Festival</div>
                <div className="what">
                  <strong>You are here.</strong> The first-ever mid-year gathering — reviving the
                  original Trade Lord Grand Festival under summer skies. Friday 19 – Sunday 21 June
                  2026, peaking on the Summer Solstice.
                </div>
              </div>
              <div className="timeline-item">
                <div className="year">2026 · Winter Unification Day</div>
                <div className="what">
                  The 10th annual end-of-year gathering. The big one — and the capstone of No Man's
                  Sky's own 10-year anniversary.
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
