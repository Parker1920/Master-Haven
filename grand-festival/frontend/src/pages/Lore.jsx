export default function Lore() {
  return (
    <main className="page active">
      <section className="lore-hero">
        <h1>archive : grand_festival</h1>
        <p>
          Salvaged log fragments and recovered records pertaining to the mid-year gathering known to
          traveler-kind as the Grand Festival.
        </p>
      </section>

      <section className="lore-body">
        <div className="lore-inner">
          <article className="log-entry">
            <div className="log-meta">
              <div className="log-id">TRA_CRA_RES_B_18 <span className="blink">_</span></div>
              <div className="log-source">resolution log · recovered</div>
              <div className="log-status">verified</div>
            </div>
            <div className="log-body">
              I access the ship's systems, extracting a quantity of <em>Nanite Clusters</em>. Nothing
              else is salvageable, the pilot's ship already in poor repair before the crash. The log
              shows these Gek were on their way to the <em>Grand Festival</em>, an assembly of Trade
              Lords and their employees from across the stars.
            </div>
            <div className="log-footer">
              <span>SOURCE :: crashed_ship.log</span>
              <span>SIGNAL :: stable</span>
            </div>
          </article>

          <article className="log-entry">
            <div className="log-meta">
              <div className="log-id">TRA_CRA_DESC_19 <span className="blink">_</span></div>
              <div className="log-source">descriptive log · recovered</div>
              <div className="log-status">verified</div>
            </div>
            <div className="log-body">
              There they prayed to the Atlas and divine luck, their worship manifesting in an
              extravaganza of <em>gambling</em>, <em>GekNip</em>, and <em>fireworks</em>. They started
              the celebrations too early. They never saw the asteroid field…
            </div>
            <div className="log-footer">
              <span>SOURCE :: crashed_ship.log</span>
              <span>SIGNAL :: stable</span>
            </div>
          </article>

          <p className="lore-disclaimer">end of recovered fragments · archive continues</p>
        </div>
      </section>
    </main>
  )
}
