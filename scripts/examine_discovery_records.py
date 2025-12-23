import sys
import json
sys.path.insert(0, r'c:\Master-Haven\NMS-Save-Watcher\src')

from parser import parse_save

def examine_discovery_records():
    save_path = r'C:\Users\parke\Desktop\No Man\'s Sky\st_76561198061737478\save4.hg'

    print("Parsing save file with deobfuscation...")
    save_data = parse_save(save_path, deobfuscate=True)

    print("\nNavigating to DiscoveryManagerData...")

    # Navigate to the discovery records
    discovery_manager = save_data.get('6f=', {}).get('F2P', {}).get('DiscoveryManagerData', {})
    discovery_data = discovery_manager.get('DiscoveryData-v1', {})
    store = discovery_data.get('Store', {})
    records = store.get('Record', [])

    print(f"\nTotal records found: {len(records)}")

    # Find Planet records
    planet_records = []
    solar_system_records = []

    for record in records:
        dt = record.get('DT', {}).get('DiscoveryType', '')
        if dt == 'Planet':
            planet_records.append(record)
        elif dt == 'SolarSystem':
            solar_system_records.append(record)

    print(f"Planet records found: {len(planet_records)}")
    print(f"SolarSystem records found: {len(solar_system_records)}")

    # Print 2-3 Planet records with COMPLETE structure
    print("\n" + "="*80)
    print("PLANET RECORDS - COMPLETE STRUCTURE")
    print("="*80)

    for i, record in enumerate(planet_records[:3], 1):
        print(f"\n{'='*80}")
        print(f"PLANET RECORD #{i}")
        print(f"{'='*80}")
        print(json.dumps(record, indent=2, default=str))

    # Print 1-2 SolarSystem records for comparison
    print("\n" + "="*80)
    print("SOLAR SYSTEM RECORDS - COMPLETE STRUCTURE")
    print("="*80)

    for i, record in enumerate(solar_system_records[:2], 1):
        print(f"\n{'='*80}")
        print(f"SOLAR SYSTEM RECORD #{i}")
        print(f"{'='*80}")
        print(json.dumps(record, indent=2, default=str))

    # Print a summary of ALL unique keys found across all Planet records
    print("\n" + "="*80)
    print("SUMMARY: ALL UNIQUE KEYS IN PLANET RECORDS")
    print("="*80)
    all_planet_keys = set()
    for record in planet_records:
        def get_all_keys(d, prefix=''):
            keys = set()
            if isinstance(d, dict):
                for k, v in d.items():
                    key_path = f"{prefix}.{k}" if prefix else k
                    keys.add(key_path)
                    keys.update(get_all_keys(v, key_path))
            elif isinstance(d, list):
                for item in d:
                    keys.update(get_all_keys(item, prefix))
            return keys

        all_planet_keys.update(get_all_keys(record))

    print("\nAll unique key paths found in Planet records:")
    for key in sorted(all_planet_keys):
        print(f"  - {key}")

    # Same for SolarSystem records
    print("\n" + "="*80)
    print("SUMMARY: ALL UNIQUE KEYS IN SOLAR SYSTEM RECORDS")
    print("="*80)
    all_ss_keys = set()
    for record in solar_system_records:
        def get_all_keys(d, prefix=''):
            keys = set()
            if isinstance(d, dict):
                for k, v in d.items():
                    key_path = f"{prefix}.{k}" if prefix else k
                    keys.add(key_path)
                    keys.update(get_all_keys(v, key_path))
            elif isinstance(d, list):
                for item in d:
                    keys.update(get_all_keys(item, prefix))
            return keys

        all_ss_keys.update(get_all_keys(record))

    print("\nAll unique key paths found in SolarSystem records:")
    for key in sorted(all_ss_keys):
        print(f"  - {key}")

if __name__ == "__main__":
    examine_discovery_records()
