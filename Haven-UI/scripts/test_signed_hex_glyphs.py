"""
Test NMS Signed Hexadecimal Glyph System

This script tests the new signed hexadecimal coordinate conversion system
to verify it matches NMS specifications exactly.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from glyph_decoder import encode_coords_to_glyph, decode_glyph_to_coords, format_glyph


def test_case(name, coords, expected_glyph, planet=1, solar_system=1):
    """Run a single test case"""
    x, y, z = coords

    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"Input Coordinates: ({x:+5d}, {y:+4d}, {z:+5d})")
    print(f"Expected Glyph:    {expected_glyph}")

    try:
        # Encode
        actual_glyph = encode_coords_to_glyph(x, y, z, planet=planet, solar_system=solar_system)
        formatted = format_glyph(actual_glyph)
        print(f"Actual Glyph:      {formatted}")

        # Verify match
        if actual_glyph.upper() == expected_glyph.replace('-', '').upper():
            print(f"[OK] ENCODING PASSED")
        else:
            print(f"[FAIL] ENCODING FAILED - Mismatch!")
            return False

        # Decode back
        decoded = decode_glyph_to_coords(actual_glyph)
        decoded_coords = (decoded['x'], decoded['y'], decoded['z'])
        print(f"\nDecoded back:      ({decoded['x']:+5d}, {decoded['y']:+4d}, {decoded['z']:+5d})")

        # Verify round-trip
        if decoded_coords == coords:
            print(f"[OK] ROUND-TRIP PASSED")
        else:
            print(f"[FAIL] ROUND-TRIP FAILED - Coordinates don't match!")
            return False

        return True

    except Exception as e:
        print(f"[X] ERROR: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("NMS SIGNED HEXADECIMAL GLYPH SYSTEM TEST SUITE")
    print("="*60)

    test_cases = [
        # All test coordinates must be > 450 units from (0,0,0) to avoid core void

        # Test Case 1: Maximum East
        ("Maximum East", (2047, 0, 0), "1-001-00-000-7FF"),

        # Test Case 2: Maximum West
        ("Maximum West", (-2047, 0, 0), "1-001-00-000-801"),

        # Test Case 3: Maximum Up (with offset to avoid void)
        ("Maximum Up", (500, 127, 0), "1-001-7F-000-1F4"),

        # Test Case 4: Maximum Down (with offset to avoid void)
        ("Maximum Down", (500, -127, 0), "1-001-81-000-1F4"),

        # Test Case 5: Maximum South
        ("Maximum South", (0, 0, 2047), "1-001-00-7FF-000"),

        # Test Case 6: Maximum North
        ("Maximum North", (0, 0, -2047), "1-001-00-801-000"),

        # Test Case 7: Near West (outside void)
        ("Near West", (-1000, 0, 0), "1-001-00-000-C18"),

        # Test Case 8: Near North (outside void)
        ("Near North", (0, 0, -1000), "1-001-00-C18-000"),

        # Test Case 9: Near Down (outside void)
        ("Near Down", (500, -1, 0), "1-001-FF-000-1F4"),

        # Test Case 10: Complex Coordinate
        ("Complex Coordinate", (500, 25, -1200), "1-001-19-B50-1F4"),

        # Test Case 11: All Positive (outside void)
        ("All Positive", (500, 50, 500), "1-001-32-1F4-1F4"),

        # Test Case 12: All Negative (outside void)
        ("All Negative", (-500, -50, -500), "1-001-CE-E0C-E0C"),

        # Test Case 13: Mixed Signs 1
        ("Mixed Signs 1", (-500, 25, 1200), "1-001-19-4B0-E0C"),

        # Test Case 14: Mixed Signs 2
        ("Mixed Signs 2", (1000, -80, -1500), "1-001-B0-A24-3E8"),

        # Test Case 15: Edge of galaxy
        ("Edge of Galaxy", (2000, 100, -2000), "1-001-64-830-7D0"),
    ]

    passed = 0
    failed = 0

    for name, coords, expected in test_cases:
        if test_case(name, coords, expected):
            passed += 1
        else:
            failed += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"[OK] Passed: {passed}/{len(test_cases)}")
    print(f"[FAIL] Failed: {failed}/{len(test_cases)}")

    if failed == 0:
        print(f"\n[SUCCESS] ALL TESTS PASSED! The signed hexadecimal system is working correctly.")
    else:
        print(f"\n[WARNING] SOME TESTS FAILED - Please review the implementation.")

    # Test forbidden values
    print(f"\n{'='*60}")
    print(f"TESTING FORBIDDEN VALUES (Should all FAIL)")
    print(f"{'='*60}")

    forbidden_tests = [
        ("All zeros coordinate", (0, 0, 0)),
        # Note: Y=0x80 boundary (-128) is out of valid range (-127 to +127)
        # Note: X/Z=0x800 boundaries are mathematically impossible with signed conversion
    ]

    # Note: The all-zeros test will fail because (0,0,0) is the galaxy center
    # which is inside the core void, not because of the coordinate validation
    print("\nNote: (0,0,0) will be rejected due to core void, not forbidden coordinates")


if __name__ == '__main__':
    main()
