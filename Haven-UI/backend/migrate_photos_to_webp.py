"""
One-time migration script: Convert all existing photos to WebP with thumbnails.

Processes:
  1. photos dir → planets.photo, moons.photo, discoveries.photo_url, discoveries.evidence_url
  2. war-media dir → war_media.filename, war_media.file_path, war_media.mime_type

For each non-WebP image:
  - Converts to WebP (max 1920px, quality 80)
  - Generates 300px thumbnail (_thumb.webp)
  - Deletes the original file
  - Updates all DB references

Usage:
  # Local (auto-detects paths):
  python Haven-UI/backend/migrate_photos_to_webp.py

  # Docker Pi (explicit paths):
  python Haven-UI/backend/migrate_photos_to_webp.py --db ~/haven-data/haven_ui.db --photos ~/haven-photos
"""

import argparse
import sqlite3
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from image_processor import process_image


def resolve_paths(args):
    """Resolve DB, photos, and war-media paths from CLI args or haven_paths defaults."""
    if args.db or args.photos:
        # Explicit paths provided (Docker / Pi usage)
        db = Path(args.db).expanduser() if args.db else None
        photos = Path(args.photos).expanduser() if args.photos else None
        war_media = Path(args.war_media).expanduser() if args.war_media else None
    else:
        # Auto-detect from haven_paths (local dev)
        from paths import haven_paths
        haven_ui = haven_paths.haven_ui_dir
        db = haven_paths.haven_db or (haven_ui / "data" / "haven_ui.db")
        photos = haven_ui / "photos"
        war_media = haven_ui / "public" / "war-media"

    return db, photos, war_media

# Image extensions to convert (skip .webp)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif"}


def backup_database(db_path):
    """Create a timestamped DB backup before migration."""
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"haven_ui_pre_webp_migration_{timestamp}.db"
    shutil.copy2(db_path, backup_path)
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


def migrate_photos_dir(conn, photos_dir):
    """Convert all images in photos dir and update DB references."""
    if not photos_dir or not photos_dir.exists():
        print("  photos/ directory not found, skipping.")
        return 0, 0, 0, 0

    # Collect all non-webp image files (skip thumbs)
    files = [
        f for f in photos_dir.iterdir()
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


def migrate_war_media(conn, war_media_dir):
    """Convert all images in war-media dir and update war_media table."""
    if not war_media_dir or not war_media_dir.exists():
        print("  war-media/ directory not found, skipping.")
        return 0, 0, 0, 0

    cursor = conn.cursor()
    cursor.execute("SELECT id, filename FROM war_media")
    rows = cursor.fetchall()

    # Filter to non-webp files that exist on disk
    to_convert = []
    for row_id, filename in rows:
        file_path = war_media_dir / filename
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


def repair_db_references(conn):
    """Fix any remaining non-WebP references in DB (handles comma-separated evidence_url, etc.)."""
    cursor = conn.cursor()
    fixed = 0
    ext_pattern = "|".join(ext.lstrip(".") for ext in IMAGE_EXTENSIONS)

    # Fix comma-separated evidence_url fields
    cursor.execute(
        "SELECT id, evidence_url FROM discoveries "
        "WHERE evidence_url IS NOT NULL AND evidence_url != ''"
    )
    for row_id, evidence_url in cursor.fetchall():
        parts = [p.strip() for p in evidence_url.split(",") if p.strip()]
        new_parts = []
        changed = False
        for part in parts:
            p = Path(part)
            if p.suffix.lower() in IMAGE_EXTENSIONS:
                new_parts.append(str(p.parent / (p.stem + ".webp")))
                changed = True
            else:
                new_parts.append(part)
        if changed:
            new_val = ",".join(new_parts)
            cursor.execute(
                "UPDATE discoveries SET evidence_url = ? WHERE id = ?",
                (new_val, row_id),
            )
            fixed += 1

    # Fix any single-value photo columns that still have old extensions
    for table, col in [
        ("planets", "photo"),
        ("moons", "photo"),
        ("discoveries", "photo_url"),
    ]:
        cursor.execute(
            f"SELECT id, {col} FROM {table} "
            f"WHERE {col} IS NOT NULL AND {col} != '' AND {col} NOT LIKE '%.webp'"
        )
        for row_id, val in cursor.fetchall():
            p = Path(val)
            if p.suffix.lower() in IMAGE_EXTENSIONS:
                new_val = str(p.parent / (p.stem + ".webp"))
                cursor.execute(
                    f"UPDATE {table} SET {col} = ? WHERE id = ?",
                    (new_val, row_id),
                )
                fixed += 1

    conn.commit()
    return fixed


def main():
    parser = argparse.ArgumentParser(description="Convert Haven photos to WebP with thumbnails")
    parser.add_argument("--db", help="Path to haven_ui.db (e.g. ~/haven-data/haven_ui.db)")
    parser.add_argument("--photos", help="Path to photos directory (e.g. ~/haven-photos)")
    parser.add_argument("--war-media", help="Path to war-media directory (optional)", default=None)
    args = parser.parse_args()

    db_path, photos_dir, war_media_dir = resolve_paths(args)

    print("=" * 60)
    print("  Haven Photo Migration: Convert to WebP + Thumbnails")
    print("=" * 60)
    print(f"  DB:        {db_path}")
    print(f"  Photos:    {photos_dir}")
    print(f"  War media: {war_media_dir}")
    print()

    if not db_path or not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        print("  Hint: use --db and --photos to specify paths on Docker/Pi")
        sys.exit(1)

    # Backup
    print("[1/4] Backing up database...")
    backup_database(db_path)
    print()

    conn = sqlite3.connect(str(db_path))

    # Migrate photos/
    print("[2/4] Converting photos/...")
    p_conv, p_fail, p_orig, p_comp = migrate_photos_dir(conn, photos_dir)
    print()

    # Migrate war-media/
    print("[3/4] Converting war-media/...")
    w_conv, w_fail, w_orig, w_comp = migrate_war_media(conn, war_media_dir)
    print()

    # Repair any missed DB references (comma-separated evidence_url, etc.)
    print("[4/4] Repairing DB references...")
    repaired = repair_db_references(conn)
    print(f"  Fixed {repaired} stale references")
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
