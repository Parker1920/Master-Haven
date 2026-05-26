"""Logo image validation + WebP normalization (Pillow).

Submitted logos are validated and re-encoded to a small WebP before they ever
touch disk: accept only real PNG/JPEG/WebP, cap at 2 MB, resize to fit 512x512
preserving aspect ratio.
"""

import io
import re

from PIL import Image

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB before resize
MAX_DIMENSION = 512
WEBP_QUALITY = 82


class ImageError(ValueError):
    """Raised for any rejected upload; the route turns this into a 400."""


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or "civ"


def process_logo(raw: bytes, content_type: str | None) -> bytes:
    """Validate and normalize an uploaded image to WebP bytes.

    Raises ImageError on anything not an acceptable, openable image.
    """
    if content_type and content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise ImageError("Unsupported image type. Use PNG, JPEG, or WebP.")
    if not raw:
        raise ImageError("Empty file.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ImageError("Image is larger than 2 MB.")

    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()  # detects truncated / non-image data
        img = Image.open(io.BytesIO(raw))  # reopen — verify() leaves the file unusable
    except Exception as exc:  # noqa: BLE001 - any decode failure is a bad upload
        raise ImageError("File is not a readable image.") from exc

    if img.format not in ("PNG", "JPEG", "WEBP"):
        raise ImageError("Unsupported image format. Use PNG, JPEG, or WebP.")

    # Flatten transparency onto nothing special — keep alpha for WebP.
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.mode else "RGB")

    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="WEBP", quality=WEBP_QUALITY, method=6)
    return out.getvalue()
