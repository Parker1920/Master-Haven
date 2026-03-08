"""
One-time migration script: Convert all existing photos to WebP with thumbnails.

Processes:
  1. Haven-UI/photos/ → planets.photo, moons.photo, discoveries.photo_url, discoveries.evidence_url
  2. Haven-UI/public/war-media/ → war_media.filename, war_media.file_path, war_media.mime_type

For each non-WebP image:
  - Converts to WebP (max 1920px, quality 80)
  - Generates 300px thumbnail (_thumb.webp)
  - Deletes the original file
  - Updates all DB references

Usage:
  cd Master-Haven
  python Haven-UI/backend/migrate_photos_to_webp.py
"""

import sqlite3
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from image_processor import process_image
from paths import haven_paths

# Use centralized path config (respects HAVEN_UI_DIR / HAVEN_DB_PATH env overrides on Pi)
HAVEN_UI_DIR = haven_paths.haven_ui_dir
PHOTOS_DIR = HAVEN_UI_DIR / "photos"
WAR_MEDIA_DIR = HAVEN_UI_DIR / "public" / "war-media"
DB_PATH = haven_paths.haven_db or (HAVEN_UI_DIR / "data" / "haven_ui.db")
BACKUP_DIR = HAVEN_UI_DIR / "data" / "backups"

# Image extensions to convert (skip .webp)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif"}


def backup_database():
    """Create a timestamped DB backup before migration."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"haven_ui_pre_webp_migration_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    print(f"  Database backed up to: {backup_path}")
    return backup_path


def convert_file(file_path: Path) -> dict | None:
    """Convert a single image file to WebP + thumbnail. Returns filenames or None on failure."""
    try:
        image_bytes = file_path.read_bytes()
        result = process_image(image_bytes, file_path.name)

        output_dir = file_path.parent

        # Write full WebP
        full_path = output_dir / result["full_filename"]
        full_path.write_bytes(result["full_bytes"])

        # Write thumbnail
        thumb_path = output_dir / result["thumb_filename"]
        thumb_path.write_bytes(result["thumb_bytes"])

        original_size = result["original_size"]
        compressed_size = result["compressed_size"]
        thumb_size = len(result["thumb_bytes"])

        # Delete original
        file_path.unlink()

        return {
            "full_filename": result["full_filename"],
            "thumb_filename": result["thumb_filename"],
            "original_size": original_size,
            "compressed_size": compressed_size + thumb_size,
        }
    except Exception as e:
        print(f"  ERROR converting {file_path.name}: {e}")
        return None


def migrate_photos_dir(conn):
    """Convert all images in Haven-UI/photos/ and update DB references."""
    if not PHOTOS_DIR.exists():
        print("  photos/ directory not found, skipping.")
        return 0, 0, 0, 0

    # Collect all non-webp image files (skip thumbs)
    files = [
        f for f in PHOTOS_DIR.iterdir()
        if f.is_file()
        and f.suffix.lower() in IMAGE_EXTENSIONS
        and not f.stem.endswith("_thumb")
    ]

    if not files:
        print("  No non-WebP images found in photos/.")
        return 0, 0, 0, 0

    print(f"  Found {len(files)} images to convert in photos/")
    cursor = conn.cursor()
    converted = 0
    failed = 0
    total_original = 0
    total_compressed = 0

    for i, file_path in enumerate(files, 1):
        old_name = file_path.name
        result = convert_file(file_path)

        if result is None:
            failed += 1
            continue

        new_name = result["full_filename"]
        total_original += result["original_size"]
        total_compressed += result["compressed_size"]

        # Update DB references: planets.photo stores "photos\filename"
        old_db_ref = f"photos\\{old_name}"
        new_db_ref = f"photos\\{new_name}"

        # Also handle forward-slash variants
        old_db_ref_fwd = f"photos/{old_name}"
        new_db_ref_fwd = f"photos/{new_name}"

        # Update planets.photo
        cursor.execute(
            "UPDATE planets SET photo = ? WHERE photo = ? OR photo = ?",
            (new_db_ref, old_db_ref, old_db_ref_fwd),
        )

        # Update moons.photo
        cursor.execute(
            "UPDATE moons SET photo = ? WHERE photo = ? OR photo = ?",
            (new_db_ref, old_db_ref, old_db_ref_fwd),
        )

        # Update discoveries.photo_url
        cursor.execute(
            "UPDATE discoveries SET photo_url = ? WHERE photo_url = ? OR photo_url = ?",
            (new_db_ref, old_db_ref, old_db_ref_fwd),
        )

        # Update discoveries.evidence_url
        cursor.execute(
            "UPDATE discoveries SET evidence_url = ? WHERE evidence_url = ? OR evidence_url = ?",
            (new_db_ref, old_db_ref, old_db_ref_fwd),
        )

        converted += 1
        if i % 25 == 0 or i == len(files):
            print(f"    [{i}/{len(files)}] converted...")

    conn.commit()
    return converted, failed, total_original, total_compressed


def migrate_war_media(conn):
    """Convert all images in Haven-UI/public/war-media/ and update war_media table."""
    if not WAR_MEDIA_DIR.exists():
        print("  war-media/ directory not found, skipping.")
        return 0, 0, 0, 0

    cursor = conn.cursor()
    cursor.execute("SELECT id, filename FROM war_media")
    rows = cursor.fetchall()

    # Filter to non-webp files that exist on disk
    to_convert = []
    for row_id, filename in rows:
        file_path = WAR_MEDIA_DIR / filename
        if file_path.exists() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
            to_convert.append((row_id, filename, file_path))

    if not to_convert:
        print("  No non-WebP war media images found.")
        return 0, 0, 0, 0

    print(f"  Found {len(to_convert)} war media images to convert")
    converted = 0
    failed = 0
    total_original = 0
    total_compressed = 0

    for row_id, old_filename, file_path in to_convert:
        result = convert_file(file_path)

        if result is None:
            failed += 1
            continue

        new_filename = result["full_filename"]
        total_original += result["original_size"]
        total_compressed += result["compressed_size"]

        # Update war_media row
        cursor.execute(
            "UPDATE war_media SET filename = ?, file_path = ?, mime_type = ? WHERE id = ?",
            (new_filename, f"/war-media/{new_filename}", "image/webp", row_id),
        )

        converted += 1

    conn.commit()
    return converted, failed, total_original, total_compressed


def main():
    print("=" * 60)
    print("  Haven Photo Migration: Convert to WebP + Thumbnails")
    print("=" * 60)
    print()

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    # Backup
    print("[1/3] Backing up database...")
    backup_database()
    print()

    conn = sqlite3.connect(str(DB_PATH))

    # Migrate photos/
    print("[2/3] Converting photos/...")
    p_conv, p_fail, p_orig, p_comp = migrate_photos_dir(conn)
    print()

    # Migrate war-media/
    print("[3/3] Converting war-media/...")
    w_conv, w_fail, w_orig, w_comp = migrate_war_media(conn)
    print()

    conn.close()

    # Summary
    total_conv = p_conv + w_conv
    total_fail = p_fail + w_fail
    total_orig = p_orig + w_orig
    total_comp = p_comp + w_comp

    print("=" * 60)
    print("  Migration Complete")
    print("=" * 60)
    print(f"  Photos converted:    {p_conv} ({p_fail} failed)")
    print(f"  War media converted: {w_conv} ({w_fail} failed)")
    print(f"  Total converted:     {total_conv}")
    if total_orig > 0:
        savings = total_orig - total_comp
        pct = (savings / total_orig) * 100
        print(f"  Original size:       {total_orig / (1024*1024):.1f} MB")
        print(f"  Compressed size:     {total_comp / (1024*1024):.1f} MB")
        print(f"  Space saved:         {savings / (1024*1024):.1f} MB ({pct:.0f}%)")
    if total_fail > 0:
        print(f"\n  WARNING: {total_fail} files failed to convert (originals kept).")
    print()


if __name__ == "__main__":
    main()
