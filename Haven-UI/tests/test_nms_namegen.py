"""
Smoke tests for vendored nms_namegen package.

Verifies that the vendored NMS procedural name generation library
(from https://github.com/stuart/nms_namegen) imports correctly and
produces known-good outputs matching the game's actual names.

Run from the vendored package directory:
    cd NMS-Haven-Extractor/dist/HavenExtractor/mod
    python -m pytest ../../../../Haven-UI/tests/test_nms_namegen.py -v

Or from project root with PYTHONPATH:
    PYTHONPATH=NMS-Haven-Extractor/dist/HavenExtractor/mod python -m pytest Haven-UI/tests/test_nms_namegen.py -v
"""
import sys
import os
import unittest

# Add the mod directory to sys.path so nms_namegen can be imported
MOD_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'NMS-Haven-Extractor',
    'dist', 'HavenExtractor', 'mod'
)
MOD_DIR = os.path.abspath(MOD_DIR)
if MOD_DIR not in sys.path:
    sys.path.insert(0, MOD_DIR)


class TestNmsNamegenImport(unittest.TestCase):
    """Verify all vendored modules import without error."""

    def test_import_prng(self):
        from nms_namegen.prng import PRNG
        self.assertIsNotNone(PRNG)

    def test_import_iprng(self):
        from nms_namegen.iprng import indexPrimedPRNG
        self.assertIsNotNone(indexPrimedPRNG)

    def test_import_roman(self):
        from nms_namegen.roman import toRoman
        self.assertEqual(toRoman(1), "I")
        self.assertEqual(toRoman(19), "XIX")

    def test_import_generator(self):
        from nms_namegen.generator import generateName
        self.assertIsNotNone(generateName)

    def test_import_region(self):
        from nms_namegen.region import regionName
        self.assertIsNotNone(regionName)

    def test_import_system(self):
        from nms_namegen.system import systemName
        self.assertIsNotNone(systemName)

    def test_import_planet(self):
        from nms_namegen.planet import planetName
        self.assertIsNotNone(planetName)


class TestKnownGoodOutputs(unittest.TestCase):
    """Verify known-good examples from the nms_namegen README."""

    def test_region_name(self):
        from nms_namegen.region import regionName
        result = regionName(0x03E9F3545C3E, 0)
        self.assertEqual(result, "Yihelli Quadrant")

    def test_system_name(self):
        from nms_namegen.system import systemName
        result = systemName(0x03E9F3545C3E, 0)
        self.assertEqual(result, "Abarof-Dulin")

    def test_planet_name_from_seed(self):
        from nms_namegen.planet import planetName
        result = planetName(0xC911CCCD7395E842)
        self.assertEqual(result, "Nutsvill Sigma")

    def test_planet_name_from_portal_code(self):
        from nms_namegen.planet import planetName
        result = planetName(0x1001ff218345, 4)
        self.assertEqual(result, "Edershar K25")


class TestDeterminism(unittest.TestCase):
    """Verify name generation is deterministic (same input = same output)."""

    def test_region_deterministic(self):
        from nms_namegen.region import regionName
        r1 = regionName(0x03E9F3545C3E, 0)
        r2 = regionName(0x03E9F3545C3E, 0)
        self.assertEqual(r1, r2)

    def test_system_deterministic(self):
        from nms_namegen.system import systemName
        s1 = systemName(0x03E9F3545C3E, 0)
        s2 = systemName(0x03E9F3545C3E, 0)
        self.assertEqual(s1, s2)

    def test_planet_deterministic(self):
        from nms_namegen.planet import planetName
        p1 = planetName(0xC911CCCD7395E842)
        p2 = planetName(0xC911CCCD7395E842)
        self.assertEqual(p1, p2)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases that the extractor might encounter."""

    def test_galaxy_zero(self):
        from nms_namegen.region import regionName
        result = regionName(0x03E9F3545C3E, 0)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_galaxy_255(self):
        from nms_namegen.region import regionName
        result = regionName(0x03E9F3545C3E, 255)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_different_galaxies_different_names(self):
        from nms_namegen.system import systemName
        name_euclid = systemName(0x03E9F3545C3E, 0)
        name_hilbert = systemName(0x03E9F3545C3E, 1)
        # Different galaxies should produce different system names
        self.assertNotEqual(name_euclid, name_hilbert)

    def test_portal_code_zero(self):
        from nms_namegen.system import systemName
        # Portal code 0 is technically valid (galactic origin)
        result = systemName(0, 0)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_planet_seed_zero_raises_or_returns(self):
        from nms_namegen.planet import planetName
        # Seed 0 should either raise or return a name, but not crash
        try:
            result = planetName(0)
            self.assertIsInstance(result, str)
        except (ZeroDivisionError, IndexError, ValueError):
            pass  # acceptable failure modes for seed 0

    def test_system_name_returns_string(self):
        from nms_namegen.system import systemName
        # Various portal codes
        for code in [0x000000000001, 0xFFFFFFFFFFFF, 0x094F3545C3E]:
            result = systemName(code, 0)
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)

    def test_region_name_returns_string(self):
        from nms_namegen.region import regionName
        for code in [0x000000000001, 0xFFFFFFFFFFFF, 0x094F3545C3E]:
            result = regionName(code, 0)
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)


if __name__ == '__main__':
    unittest.main()
