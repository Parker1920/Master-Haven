"""
test_resolver.py
================
Accuracy self-check for haven_glyph_resolver.

Pulls real catalogued systems, hides their glyphs, resolves each one by
name (+ galaxy), and compares the result to the true stored glyph. Prints
a pass rate so you can trust the tool on your own data.

    python test_resolver.py            # default 40 systems
    python test_resolver.py 100        # check 100 systems

Hits havenmap.online read-only. Every resolve() is one HTTP search, so
keep the sample modest unless you want to wait.
"""
import sys
import haven_glyph_resolver as r

def main(n=40):
    data = r._get("/api/systems", {"limit": n})
    systems = [s for s in (data or {}).get("systems", [])
               if s.get("glyph_code") and len(s["glyph_code"]) == 12]
    if not systems:
        print("no systems pulled"); return 1

    exact = found = missed = 0
    misses = []
    for s in systems:
        truth = s["glyph_code"].upper()
        res = r.resolve(s["name"], galaxy=s.get("galaxy"))
        glyphs = {c.glyph_code.upper() for c in res.candidates}
        if glyphs == {truth}:
            exact += 1                      # unique, correct
        elif truth in glyphs:
            found += 1                      # correct, but among collisions
        else:
            missed += 1
            misses.append((s["name"], s.get("galaxy"), truth, res.confidence.value))

    total = len(systems)
    print(f"\n  checked        : {total} systems")
    print(f"  exact + unique : {exact}  ({exact/total*100:.0f}%)")
    print(f"  correct (amb.) : {found}  (true glyph present, multiple share the name)")
    print(f"  missed         : {missed}")
    for nm, g, t, c in misses[:10]:
        print(f"     MISS: {nm!r} [{g}] expected {t} (conf {c})")
    print()
    return 0

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    sys.exit(main(n))
