"""
Image processing utility for Haven API.

Compresses uploaded images to WebP format and generates thumbnails.
- Full images: max 1920px on longest side, WebP quality 80
- Thumbnails: 300px wide, WebP quality 75
"""

from pathlib import Path
from PIL import Image
import io
import logging

logger = logging.getLogger('control.room')

# Compression settings
MAX_DIMENSION = 1920
FULL_QUALITY = 80
THUMB_WIDTH = 300
THUMB_QUALITY = 75


def process_image(image_bytes: bytes, original_filename: str) -> dict:
    """
    Process an uploaded image: resize, compress to WebP, generate thumbnail.

    Args:
        image_bytes: Raw bytes of the uploaded image
        original_filename: Original filename (used for stem only)

    Returns:
        dict with keys:
            full_bytes: WebP bytes of the full-size image
            thumb_bytes: WebP bytes of the thumbnail
            full_filename: e.g. "photo_name.webp"
            thumb_filename: e.g. "photo_name_thumb.webp"
            width: final full image width
            height: final full image height
            original_size: size of raw upload in bytes
            compressed_size: size of full WebP in bytes
    """
    original_size = len(image_bytes)

    img = Image.open(io.BytesIO(image_bytes))

    # Convert to RGB (handles RGBA PNGs, palette images, etc.)
    if img.mode in ('RGBA', 'LA'):
        # Composite onto white background to avoid black areas
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Resize if larger than MAX_DIMENSION on longest side
    max_dim = max(img.size)
    if max_dim > MAX_DIMENSION:
        ratio = MAX_DIMENSION / max_dim
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Compress to WebP
    full_buf = io.BytesIO()
    img.save(full_buf, 'WEBP', quality=FULL_QUALITY)
    full_bytes = full_buf.getvalue()

    # Generate thumbnail
    thumb_ratio = THUMB_WIDTH / img.size[0]
    thumb_size = (THUMB_WIDTH, int(img.size[1] * thumb_ratio))
    thumb = img.resize(thumb_size, Image.LANCZOS)
    thumb_buf = io.BytesIO()
    thumb.save(thumb_buf, 'WEBP', quality=THUMB_QUALITY)
    thumb_bytes = thumb_buf.getvalue()

    # Build filenames from original stem
    stem = Path(original_filename).stem
    full_filename = f"{stem}.webp"
    thumb_filename = f"{stem}_thumb.webp"

    logger.info(
        f"Image processed: {original_filename} "
        f"({original_size/1024:.0f}KB → {len(full_bytes)/1024:.0f}KB full, "
        f"{len(thumb_bytes)/1024:.1f}KB thumb, "
        f"{img.size[0]}x{img.size[1]})"
    )

    return {
        'full_bytes': full_bytes,
        'thumb_bytes': thumb_bytes,
        'full_filename': full_filename,
        'thumb_filename': thumb_filename,
        'width': img.size[0],
        'height': img.size[1],
        'original_size': original_size,
        'compressed_size': len(full_bytes),
    }
