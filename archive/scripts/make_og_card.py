"""
Generate the static Open Graph / Twitter share card for the Haven
Archive (1200x630 PNG).

The card is STATIC — it doesn't change per request — so this is a
one-time tool, not a runtime endpoint. Run it once, commit the output
to frontend/public/og-card.png, done. Re-run only if the design or
copy changes.

    python scripts/make_og_card.py [output_path]

Defaults to writing frontend/public/og-card.png relative to the
archive root. Needs Pillow (already a project dependency) and a serif
TTF (DejaVu Serif — install fonts-dejavu-core if missing).

Design (matches the site masthead):
  - cosmic navy background #050324 with a faint starfield
  - teal->green "HA" tile (the navbar mark) + "Haven Archive"
    serif wordmark
  - dim tagline, wrapped
  - teal/violet/gold accent dots + the domain
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---- palette (from frontend/src/styles/global.css) -------------------
BG = (5, 3, 36)            # #050324  cosmic navy
TEXT = (246, 251, 252)     # #f6fbfc  near-white
DIM = (168, 181, 200)      # #a8b5c8  dim blue
FAINT = (138, 152, 176)    # #8a98b0
TEAL = (63, 130, 193)      # #3f82c1
TEAL2 = (29, 158, 117)     # #1D9E75  (navbar mark gradient end)
VIOLET = (83, 74, 183)     # #534AB7
GOLD = (250, 199, 117)     # #FAC775

W, H = 1200, 630

TAGLINE = ("Civilizations, diplomacy, and history across the No Man's Sky "
           "multiverse — chronicled by the travelers who live it.")
DOMAIN = "haven-archive.online"


# ---- font loading ----------------------------------------------------
# DejaVu first (the Pi build environment), then Windows (Georgia/Arial)
# and macOS fallbacks so the card can be regenerated on any dev machine.
SERIF_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "C:/Windows/Fonts/georgiab.ttf",
    "C:/Windows/Fonts/georgia.ttf",
    "/Library/Fonts/Georgia.ttf",
]
SERIF_REG_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "C:/Windows/Fonts/georgia.ttf",
    "/Library/Fonts/Georgia.ttf",
]
SANS_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/Library/Fonts/Arial.ttf",
]


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    raise RuntimeError(
        "No usable TTF found. Install fonts-dejavu-core "
        "(apt-get install -y fonts-dejavu-core) and retry. Tried: "
        + ", ".join(candidates)
    )


def _rounded_gradient_tile(size: int, radius: int) -> Image.Image:
    """Diagonal teal->green gradient square with rounded corners + 'TA'."""
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.new("RGB", (size, size), TEAL)
    px = grad.load()
    for y in range(size):
        for x in range(size):
            # 135deg diagonal: t goes 0..1 across the x+y diagonal
            t = (x + y) / (2 * (size - 1))
            r = int(TEAL[0] + (TEAL2[0] - TEAL[0]) * t)
            g = int(TEAL[1] + (TEAL2[1] - TEAL[1]) * t)
            b = int(TEAL[2] + (TEAL2[2] - TEAL[2]) * t)
            px[x, y] = (r, g, b)
    # rounded-corner mask
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    tile.paste(grad, (0, 0), mask)
    # "TA" centered
    d = ImageDraw.Draw(tile)
    f = _font(SANS_CANDIDATES, int(size * 0.42))
    tw = d.textbbox((0, 0), "HA", font=f)
    cx = (size - (tw[2] - tw[0])) / 2 - tw[0]
    cy = (size - (tw[3] - tw[1])) / 2 - tw[1]
    d.text((cx, cy), "HA", font=f, fill=(255, 255, 255))
    return tile


def _wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make(out_path: Path) -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # --- faint starfield ---
    rnd = random.Random(42)  # fixed seed so the card is reproducible
    for _ in range(140):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        r = rnd.choice([1, 1, 1, 2])
        a = rnd.randint(20, 90)
        d.ellipse([x, y, x + r, y + r], fill=(255, 255, 255, a) if False else
                  (min(255, BG[0] + a), min(255, BG[1] + a), min(255, BG[2] + a)))

    # --- soft radial glows (top-right teal, bottom-left violet) ---
    glow = Image.new("RGB", (W, H), BG)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W - 380, -180, W + 120, 320], fill=(12, 40, 70))
    gd.ellipse([-200, H - 260, 280, H + 200], fill=(28, 22, 64))
    img = Image.blend(img, glow, 0.45)
    d = ImageDraw.Draw(img)
    # re-scatter a few brighter stars on top
    for _ in range(40):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        d.ellipse([x, y, x + 1, y + 1], fill=(120, 140, 180))

    # --- layout ---
    margin = 96
    tile_size = 120
    tile_y = 232
    tile = _rounded_gradient_tile(tile_size, radius=22)
    img.paste(tile, (margin, tile_y), tile)

    text_x = margin + tile_size + 34

    # wordmark
    wf = _font(SERIF_CANDIDATES, 78)
    d.text((text_x, tile_y - 6), "Haven Archive", font=wf, fill=TEXT)

    # thin rule under wordmark
    rule_y = tile_y + 92
    d.line([(text_x, rule_y), (text_x + 360, rule_y)], fill=GOLD, width=3)

    # tagline (wrapped, dim)
    tf = _font(SERIF_REG_CANDIDATES, 30)
    lines = _wrap(d, TAGLINE, tf, max_w=W - text_x - margin)
    ty = rule_y + 26
    for ln in lines:
        d.text((text_x, ty), ln, font=tf, fill=DIM)
        ty += 42

    # --- bottom row: accent dots (left) + domain (right) ---
    by = H - 70
    dot_r = 9
    dots = [(TEAL, margin), (VIOLET, margin + 34), (GOLD, margin + 68)]
    for color, dx in dots:
        d.ellipse([dx, by, dx + dot_r * 2, by + dot_r * 2], fill=color)

    df = _font(SANS_CANDIDATES, 26)
    dom_w = d.textlength(DOMAIN, font=df)
    d.text((W - margin - dom_w, by - 2), DOMAIN, font=df, fill=FAINT)

    # eyebrow above the wordmark
    ef = _font(SANS_CANDIDATES, 22)
    d.text((text_x, tile_y - 44), "THE  ARCHIVE", font=ef, fill=FAINT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes, {W}x{H})")


if __name__ == "__main__":
    default_out = Path(__file__).resolve().parent.parent / "frontend" / "public" / "og-card.png"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default_out
    make(out)
