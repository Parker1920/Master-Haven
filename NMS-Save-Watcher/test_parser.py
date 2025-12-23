#!/usr/bin/env python3
"""
Test script for NMS Save Watcher parsing functionality.
Run this to test save file parsing without the full watcher.
"""

import sys
import json
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import find_nms_save_path, get_save_file_path, load_config, SAVE_SLOTS
from src.parser import SaveParser, KeyMapper
from src.extractor import DiscoveryExtractor, extract_bases, SystemComparator

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_parser')


def test_save_path_detection():
    """Test auto-detection of NMS save path."""
    print("\n" + "=" * 60)
    print("Testing Save Path Detection")
    print("=" * 60)

    save_path = find_nms_save_path()
    if save_path:
        print(f"[OK] Found NMS save folder: {save_path}")

        # List save files
        for slot, filename in SAVE_SLOTS.items():
            save_file = save_path / filename
            if save_file.exists():
                size = save_file.stat().st_size
                print(f"    Slot {slot}: {filename} ({size:,} bytes)")
            else:
                print(f"    Slot {slot}: {filename} (not found)")

        return save_path
    else:
        print("[FAIL] Could not find NMS save folder")
        print("       Expected at: %APPDATA%\\HelloGames\\NMS\\st_*\\")
        return None


def test_key_mapper():
    """Test key mapping functionality."""
    print("\n" + "=" * 60)
    print("Testing Key Mapper")
    print("=" * 60)

    mapper = KeyMapper()

    print(f"[OK] Loaded {len(mapper.mappings)} key mappings")

    # Test a few known mappings
    test_keys = ['F2P', '8pG', 'osr', 'yhJ', 'dZj']
    for key in test_keys:
        mapped = mapper.mappings.get(key, '[NOT FOUND]')
        print(f"    {key} -> {mapped}")

    # Test deobfuscation
    test_obj = {
        'F2P': {
            '8pG': {
                'osr': 0,
                'yhJ': {'dZj': 100, 'IyE': 50, 'uXE': -200}
            }
        }
    }

    deobfuscated = mapper.deobfuscate(test_obj)
    print(f"\n    Sample deobfuscation:")
    print(f"    Input:  {test_obj}")
    print(f"    Output: {deobfuscated}")

    return mapper


def test_save_parsing(save_path: Path):
    """Test parsing a save file."""
    print("\n" + "=" * 60)
    print("Testing Save File Parsing")
    print("=" * 60)

    # Use slot 1 (save.hg)
    save_file = save_path / 'save.hg'

    if not save_file.exists():
        print(f"[SKIP] Save file not found: {save_file}")
        return None

    print(f"[INFO] Parsing: {save_file}")
    print(f"       Size: {save_file.stat().st_size:,} bytes")

    try:
        parser = SaveParser()

        # Test decompression
        decompressed = parser.decompress_save(save_file)
        print(f"[OK] Decompressed: {len(decompressed):,} bytes")

        # Test full parsing
        data = parser.parse_save(save_file, deobfuscate=True)
        print(f"[OK] Parsed JSON with {len(data)} top-level keys")

        # Show top-level structure
        print("\n    Top-level keys:")
        for key in list(data.keys())[:10]:
            value = data[key]
            if isinstance(value, dict):
                print(f"      {key}: dict ({len(value)} keys)")
            elif isinstance(value, list):
                print(f"      {key}: list ({len(value)} items)")
            else:
                print(f"      {key}: {type(value).__name__}")

        # Check for unknown keys
        unknown = parser.get_unknown_keys()
        if unknown:
            print(f"\n[WARN] Found {len(unknown)} unknown obfuscated keys:")
            for key in list(unknown)[:10]:
                print(f"       {key}")
            if len(unknown) > 10:
                print(f"       ... and {len(unknown) - 10} more")

        return data

    except Exception as e:
        print(f"[FAIL] Parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_discovery_extraction(save_data: dict):
    """Test discovery data extraction."""
    print("\n" + "=" * 60)
    print("Testing Discovery Extraction")
    print("=" * 60)

    if not save_data:
        print("[SKIP] No save data to extract from")
        return

    try:
        extractor = DiscoveryExtractor()
        systems = extractor.extract_discoveries(save_data)

        print(f"[OK] Extracted {len(systems)} system(s)")

        if systems:
            # Show first few systems
            print("\n    Discovered Systems:")
            for i, system in enumerate(systems[:5]):
                print(f"\n    [{i+1}] {system.name}")
                print(f"        Glyph: {system.glyph_code}")
                print(f"        Galaxy: {system.galaxy} (index {system.galaxy_index})")
                print(f"        Star: {system.star_type or 'Unknown'}")
                print(f"        Economy: {system.economy_type or 'Unknown'} ({system.economy_level or '?'})")
                print(f"        Conflict: {system.conflict_level or 'Unknown'}")
                print(f"        Discovered by: {system.discovered_by or 'Unknown'}")
                print(f"        Planets: {len(system.planets)}")

                for planet in system.planets[:3]:
                    print(f"          - {planet.name} ({planet.biome or 'Unknown biome'})")
                    if planet.resources:
                        print(f"            Resources: {', '.join(planet.resources[:5])}")

            if len(systems) > 5:
                print(f"\n    ... and {len(systems) - 5} more systems")

        # Test base extraction
        print("\n    Extracting bases...")
        bases = extract_bases(save_data)
        print(f"[OK] Found {len(bases)} base(s)")

        if bases:
            for base in bases[:3]:
                print(f"      - {base.get('name', 'Unnamed')}")
                if 'latitude' in base and 'longitude' in base:
                    print(f"        Location: ({base['latitude']:.2f}, {base['longitude']:.2f})")

        return systems

    except Exception as e:
        print(f"[FAIL] Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_comparator():
    """Test system comparison for edit detection."""
    print("\n" + "=" * 60)
    print("Testing System Comparator")
    print("=" * 60)

    from src.extractor import SystemData, PlanetData

    # Create mock existing data
    existing = {
        'name': 'Old System Name',
        'star_type': 'Yellow',
        'economy_type': 'Trading',
        'economy_level': 'High',
        'conflict_level': 'Low',
        'planets': [
            {'name': 'Planet A'},
            {'name': 'Planet B'}
        ]
    }

    # Create new data with changes
    new_system = SystemData(
        name='New System Name',  # Changed
        glyph_code='012345678901',
        galaxy='Euclid',
        galaxy_index=0,
        star_type='Yellow',
        economy_type='Trading',
        economy_level='High',
        conflict_level='Medium',  # Changed
        planets=[
            PlanetData(name='Planet A', biome='Lush'),
            PlanetData(name='Planet B', biome='Toxic'),
            PlanetData(name='Planet C', biome='Frozen')  # New planet
        ]
    )

    comparison = SystemComparator.compare(existing, new_system)

    print(f"[OK] Comparison complete")
    print(f"    Has changes: {comparison['has_changes']}")
    print(f"    Is significant: {comparison['is_significant']}")
    print(f"    Changes: {SystemComparator.format_changes(comparison)}")


def test_api_connection():
    """Test connection to Voyagers Haven API."""
    print("\n" + "=" * 60)
    print("Testing API Connection")
    print("=" * 60)

    config = load_config()
    api_url = config.get('api', {}).get('base_url', 'http://localhost:8005')
    api_key = config.get('api', {}).get('key', '')

    print(f"    API URL: {api_url}")
    print(f"    API Key: {'[configured]' if api_key else '[not configured]'}")

    if not api_key:
        print("[SKIP] No API key configured")
        return

    from src.api_client import APIClient

    try:
        client = APIClient(api_url, api_key)
        success, message = client.test_connection()

        if success:
            print(f"[OK] Connection successful: {message}")
        else:
            print(f"[FAIL] Connection failed: {message}")

    except Exception as e:
        print(f"[FAIL] Connection error: {e}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("  NMS Save Watcher - Parser Test Suite")
    print("=" * 60)

    # Test save path detection
    save_path = test_save_path_detection()

    # Test key mapper
    test_key_mapper()

    # Test save parsing
    save_data = None
    if save_path:
        save_data = test_save_parsing(save_path)

    # Test discovery extraction
    if save_data:
        test_discovery_extraction(save_data)

    # Test comparator
    test_comparator()

    # Test API connection
    test_api_connection()

    print("\n" + "=" * 60)
    print("  Tests Complete")
    print("=" * 60)


if __name__ == '__main__':
    main()
