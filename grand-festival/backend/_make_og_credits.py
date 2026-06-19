"""One-off: composite a team-credits bar onto the OG link-preview image.

Reads frontend/public/og-image.jpg, draws a translucent bar across the bottom
crediting the festival team — line 1 is the team (equal billing, no single
"host"), line 2 is the secondary website credit — and writes
og-image-credits.jpg beside it. The new filename (vs. overwriting og-image.jpg)
forces Discord/Twitter to re-fetch the preview instead of serving a cached one.

Run from the grand-festival dir:
    backend/.venv/Scripts/python.exe backend/_make_og_credits.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "public" / "og-image.jpg"
OUT = ROOT / "frontend" / "public" / "og-image-credits.jpg"

# Equal-billing team line, then the (secondary) website credit beneath it.
LINE1 = "MCs: Jenness & Agent Spike    ·    Mods: Art3mis (Viobot), Santa & Bread Pirate    ·    Sponsor: Mjstral (Service Bot)"
LINE2 = "Website by Ekimo"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\seguisb.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(size: int):
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fit_font(draw, text, max_w, start, floor=12):
    """Largest font (<= start) whose rendered text fits within max_w."""
    size = start
    font = load_font(size)
    while size > floor and draw.textlength(text, font=font) > max_w:
        size -= 1
        font = load_font(size)
    return font


def main() -> None:
    img = Image.open(SRC).convert("RGBA")
    W, H = img.size

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    bar_h = max(104, int(H * 0.17))
    bar_top = H - bar_h
    d.rectangle([0, bar_top, W, H], fill=(5, 18, 38, 198))                # navy bar
    d.rectangle([0, bar_top, W, bar_top + 3], fill=(255, 224, 121, 235))  # gold top edge

    margin = 56
    max_w = W - 2 * margin

    f1 = fit_font(d, LINE1, max_w, 25)
    f2 = fit_font(d, LINE2, max_w, 19)

    h1 = sum(f1.getmetrics())
    h2 = sum(f2.getmetrics())
    gap = 8
    block_h = h1 + gap + h2
    y1 = bar_top + (bar_h - block_h) / 2
    y2 = y1 + h1 + gap

    w1 = d.textlength(LINE1, font=f1)
    w2 = d.textlength(LINE2, font=f2)
    x1 = (W - w1) / 2
    x2 = (W - w2) / 2

    # Line 1 — the team, white (primary, equal billing).
    d.text((x1 + 1, y1 + 2), LINE1, font=f1, fill=(0, 0, 0, 170))
    d.text((x1, y1), LINE1, font=f1, fill=(255, 255, 255, 255))
    # Line 2 — the website credit, soft sky-blue (secondary).
    d.text((x2 + 1, y2 + 1), LINE2, font=f2, fill=(0, 0, 0, 150))
    d.text((x2, y2), LINE2, font=f2, fill=(168, 220, 255, 255))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(OUT, "JPEG", quality=88)
    print(f"wrote {OUT}  ({W}x{H}, bar {bar_h}px, L1 {f1.size}px/{int(w1)}px, L2 {f2.size}px/{int(w2)}px)")


if __name__ == "__main__":
    main()
