// Site footer. The product (the Viobot-specific dashboard) is the Client's; Voyager's Haven LLC built it.
// This is part of the Client-owned visual layer — easy to restyle/relabel at handoff.
export default function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="site-footer">
      <span className="foot-copy">© {year} Viobot. All rights reserved.</span>
      <span className="foot-build">
        Built by <strong>Voyager&rsquo;s Haven LLC</strong>
      </span>
    </footer>
  );
}
