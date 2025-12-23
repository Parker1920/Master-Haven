"""
No Man's Sky Portal Glyph Decoder/Encoder

Handles conversion between NMS portal glyphs and galaxy coordinates.

Glyph Format: P-SSS-YY-ZZZ-XXX (12 hexadecimal digits)
- P: Planet/Body index (1 hex digit, 0-F, typically 0-6 for planets)
- SSS: Solar System index (3 hex digits, 001-FFF, cannot be 000)
- YY: Y-axis vertical coordinate (2 hex digits, 00-7F or 81-FF, cannot be 80)
- ZZZ: Z-axis north-south coordinate (3 hex digits, 000-7FF or 801-FFF, cannot be 800)
- XXX: X-axis east-west coordinate (3 hex digits, 000-7FF or 801-FFF, cannot be 800)

Galaxy Dimensions:
- X: 4096 units (-2048 to +2047, centered at 0)
- Y: 256 units (-128 to +127, centered at 0)
- Z: 4096 units (-2048 to +2047, centered at 0)
- Solar Systems: 767 per coordinate (1-767)

Regions:
- 4096 x 4096 x 256 region grid
- Each region = 128 x 128 x 128 coordinates
- Region coordinate = floor(galaxy_coord / 128)
"""

import re
import hashlib
from typing import Dict, Tuple, Optional

# Glyph image mapping (standard NMS community order)
GLYPH_TO_HEX = {
    'sunset': '0',    # IMG_9202.jpg - Water/waves with arch
    'bird': '1',      # IMG_9203.jpg - Flying bird
    'face': '2',      # IMG_9204.jpg - Face/mask
    'diplo': '3',     # IMG_9205.jpg - Dinosaur
    'eclipse': '4',   # IMG_9206.jpg - Crescent
    'balloon': '5',   # IMG_9207.jpg - Teardrop
    'boat': '6',      # IMG_9208.png - Platform
    'bug': '7',       # IMG_9209.jpg - Insect
    'dragonfly': '8', # IMG_9210.jpg - Dragonfly
    'galaxy': '9',    # IMG_9211.jpg - Spiral
    'voxel': 'A',     # IMG_9212.jpg - Hexagon
    'fish': 'B',      # IMG_9213.jpg - Fish
    'tent': 'C',      # IMG_9214.jpg - Tent/tipi
    'rocket': 'D',    # IMG_9215.jpg - Rocket
    'tree': 'E',      # IMG_9216.jpg - Tree
    'atlas': 'F',     # IMG_9217.jpg - Triangles
}

HEX_TO_GLYPH = {v: k for k, v in GLYPH_TO_HEX.items()}

# Glyph photo filenames
GLYPH_IMAGES = {
    '0': 'IMG_9202.jpg',
    '1': 'IMG_9203.jpg',
    '2': 'IMG_9204.jpg',
    '3': 'IMG_9205.jpg',
    '4': 'IMG_9206.jpg',
    '5': 'IMG_9207.jpg',
    '6': 'IMG_9208.png',
    '7': 'IMG_9209.jpg',
    '8': 'IMG_9210.jpg',
    '9': 'IMG_9211.jpg',
    'A': 'IMG_9212.jpg',
    'B': 'IMG_9213.jpg',
    'C': 'IMG_9214.jpg',
    'D': 'IMG_9215.jpg',
    'E': 'IMG_9216.jpg',
    'F': 'IMG_9217.jpg',
}

# Coordinate ranges (NMS full in-game range)
COORD_RANGES = {
    'planet': (0, 15),          # 0x0 to 0xF (typically 0-6 for planets)
    'solar_system': (1, 4095),  # 0x001 to 0xFFF (cannot be 000)
    'x': (-2047, 2047),         # 0x801-0xFFF (-2047 to -1), 0x000-0x7FF (0 to +2047)
    'y': (-127, 127),           # 0x81-0xFF (-127 to -1), 0x00-0x7F (0 to +127)
    'z': (-2047, 2047),         # 0x801-0xFFF (-2047 to -1), 0x000-0x7FF (0 to +2047)
}

# Display scale factor (configurable)
DISPLAY_SCALE = 0.2  # 1:5 scale

# Core void zone (galactic center exclusion)
# NMS lore: The galactic core is a bright center of light used for galaxy travel
# The core is devoid of stars for ~3,000 light years in all directions
# Each voxel/region = ~400 light years, so void = ~7.5 voxels radius
# Reference: https://nomanssky.fandom.com/wiki/Galaxy_Centre
CORE_VOID_RADIUS_XZ = 8  # Coordinate units from center in X/Z plane (~3,200 ly)
CORE_VOID_RADIUS_Y = 1  # Coordinate units from center in Y axis (scaled: 8 * 256/4096 ≈ 0.5, rounded up)
CORE_VOID_ENABLED = True  # Can be disabled for testing

# Phantom star detection
# Each region has 4,096 possible star systems (SSS 001-FFF)
# Only ~600 are accessible on the Galactic Map; the rest are phantom stars
# Reference: https://nomanssky.fandom.com/wiki/Phantom_Star
PHANTOM_SSS_THRESHOLD = 0x258  # 600 decimal - SSS >= this are typically phantom
PHANTOM_SSS_EXCEPTION = 0x3E8  # 1000 decimal - bug allows this to appear on map
PHANTOM_SSS_ZERO = True  # SSS = 0x000 also produces phantom stars in some regions

# Region size in coordinate units (NMS uses 128-unit regions)
REGION_SIZE = 128


def calculate_star_position_in_region(region_x: int, region_y: int, region_z: int,
                                       solar_system_index: int) -> Tuple[float, float, float]:
    """
    Generate a unique 3D position within a region based on the solar system index.

    In NMS, multiple star systems exist within the same region (same XYZ glyph coordinates).
    The SolarSystemIndex (SSS) uniquely identifies which star within that region.
    This function uses deterministic hashing to generate consistent positions.

    Args:
        region_x: Region X coordinate (0-4095 from glyph XXX)
        region_y: Region Y coordinate (0-255 from glyph YY)
        region_z: Region Z coordinate (0-4095 from glyph ZZZ)
        solar_system_index: Solar system index within the region (1-4095)

    Returns:
        Tuple of (star_x, star_y, star_z) - actual star position in galaxy coordinates
    """
    # Create a deterministic seed from region coords + SSS
    # This ensures the same glyph always produces the same star position
    seed_string = f"NMS:{region_x}:{region_y}:{region_z}:{solar_system_index}"
    hash_bytes = hashlib.sha256(seed_string.encode()).digest()

    # Extract 3 values for x, y, z offsets (-0.5 to +0.5 range)
    # Using different byte ranges for each axis to ensure independence
    offset_x = (int.from_bytes(hash_bytes[0:4], 'big') / 0xFFFFFFFF) - 0.5
    offset_y = (int.from_bytes(hash_bytes[4:8], 'big') / 0xFFFFFFFF) - 0.5
    offset_z = (int.from_bytes(hash_bytes[8:12], 'big') / 0xFFFFFFFF) - 0.5

    # Scale offsets to spread stars within a reasonable range (±64 units)
    # This keeps stars spread out but still clearly within their region
    spread = 64
    offset_x *= spread
    offset_y *= spread
    offset_z *= spread

    # Convert region coordinates to signed galaxy coordinates
    # region_x: 0x000-0x7FF = positive (0 to +2047), 0x801-0xFFF = negative (-2047 to -1)
    if region_x <= 0x7FF:
        base_x = region_x
    else:
        base_x = region_x - 0x1000

    if region_y <= 0x7F:
        base_y = region_y
    else:
        base_y = region_y - 0x100

    if region_z <= 0x7FF:
        base_z = region_z
    else:
        base_z = region_z - 0x1000

    # Add offset to base position
    star_x = base_x + offset_x
    star_y = base_y + offset_y
    star_z = base_z + offset_z

    return (star_x, star_y, star_z)


def validate_glyph_code(glyph: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a 12-character hexadecimal glyph code.

    Args:
        glyph: 12-digit hex string

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not glyph:
        return False, "Glyph code cannot be empty"

    glyph = glyph.strip().upper().replace('-', '').replace(' ', '')

    if len(glyph) != 12:
        return False, f"Glyph must be 12 hex digits (got {len(glyph)})"

    if not re.match(r'^[0-9A-F]{12}$', glyph):
        return False, "Glyph must contain only hex digits (0-9, A-F)"

    # Parse components for range validation
    try:
        planet = int(glyph[0], 16)
        solar_system = int(glyph[1:4], 16)
        y = int(glyph[4:6], 16)
        z = int(glyph[6:9], 16)
        x = int(glyph[9:12], 16)

        warnings = []

        # Check ranges - only warn on truly invalid values
        # Full in-game range: SSS (001-FFF), YY (00-FF except 80), ZZZ/XXX (000-FFF except 800)
        if solar_system == 0:
            warnings.append(f"Solar system cannot be 000")

        if y == 0x80:
            warnings.append(f"Y coordinate 80 is forbidden (use 00-7F or 81-FF)")

        if z == 0x800:
            warnings.append(f"Z coordinate 800 is forbidden (use 000-7FF or 801-FFF)")

        if x == 0x800:
            warnings.append(f"X coordinate 800 is forbidden (use 000-7FF or 801-FFF)")

        if warnings:
            return True, "Valid but unusual: " + "; ".join(warnings)

        return True, None

    except ValueError as e:
        return False, f"Invalid hex format: {e}"


def decode_glyph_to_coords(glyph: str, apply_scale: bool = False) -> Dict:
    """
    Decode NMS portal glyph to galaxy coordinates.

    Args:
        glyph: 12-digit hex string (e.g., "10A4F3E7B2C1")
        apply_scale: If True, apply display scaling factor

    Returns:
        Dictionary with:
            - x, y, z: Region coordinates (centered, -2048 to +2047) - identifies the REGION
            - star_x, star_y, star_z: Actual star position within the region (for 3D map plotting)
            - planet: Planet index (0-15)
            - solar_system: Solar system index (1-4095)
            - region_x, region_y, region_z: Region grid coordinates
            - glyph: Original glyph code
            - display_x, display_y, display_z: Scaled region coordinates (if apply_scale=True)
            - display_star_x, display_star_y, display_star_z: Scaled star coordinates (if apply_scale=True)
            - warnings: List of validation warnings
    """
    glyph = glyph.strip().upper().replace('-', '').replace(' ', '')

    is_valid, error = validate_glyph_code(glyph)
    if not is_valid:
        raise ValueError(error)

    # Parse glyph components
    planet = int(glyph[0], 16)
    solar_system = int(glyph[1:4], 16)
    y_hex = int(glyph[4:6], 16)
    z_hex = int(glyph[6:9], 16)
    x_hex = int(glyph[9:12], 16)

    # Convert signed hexadecimal to centered coordinates
    # X-Axis (West ← 0 → East): 801-FFF (West negative), 000-7FF (East positive)
    if x_hex <= 0x7FF:
        x = x_hex  # Positive (East): 000 → 0, 7FF → +2047
    else:
        x = x_hex - 0x1000  # Negative (West): 801 → -2047, FFF → -1

    # Y-Axis (Down ← 0 → Up): 81-FF (Down negative), 00-7F (Up positive)
    if y_hex <= 0x7F:
        y = y_hex  # Positive (Up): 00 → 0, 7F → +127
    else:
        y = y_hex - 0x100  # Negative (Down): 81 → -127, FF → -1

    # Z-Axis (South ← 0 → North): 000-7FF (South positive), 801-FFF (North negative)
    if z_hex <= 0x7FF:
        z = z_hex  # Positive (South): 000 → 0, 7FF → +2047
    else:
        z = z_hex - 0x1000  # Negative (North): 801 → -2047, FFF → -1

    # Region coordinates come DIRECTLY from the glyph hex values
    # Galaxy is 4096 x 256 x 4096 regions
    # XXX (0x000-0xFFF) = region_x (0-4095)
    # YY (0x00-0xFF) = region_y (0-255)
    # ZZZ (0x000-0xFFF) = region_z (0-4095)
    region_x = x_hex
    region_y = y_hex
    region_z = z_hex

    # Calculate actual star position within the region using deterministic hash
    # This ensures stars in the same region don't overlap on the 3D map
    star_x, star_y, star_z = calculate_star_position_in_region(
        region_x, region_y, region_z, solar_system
    )

    # Get system classification (phantom star and core void status)
    classification = get_system_classification(x, y, z, solar_system)

    # Build warnings list
    all_warnings = []
    if error and "unusual" in error.lower():
        all_warnings.append(error)

    # Add phantom star warning
    if classification['is_phantom']:
        all_warnings.append(
            f"PHANTOM STAR: Solar system index {solar_system} (0x{solar_system:03X}) indicates a phantom star. "
            f"These systems are not normally accessible via the Galactic Map."
        )

    # Add core void warning
    if classification['is_in_core']:
        all_warnings.append(
            f"CORE VOID: Coordinates ({x}, {y}, {z}) are within the galactic core void "
            f"(~3,000 light years from center). Only phantom stars exist in this region."
        )

    result = {
        # Region coordinates (from glyph YY-ZZZ-XXX) - identifies which region
        'x': x,
        'y': y,
        'z': z,
        # Actual star position (calculated from region + SSS) - for 3D map plotting
        'star_x': star_x,
        'star_y': star_y,
        'star_z': star_z,
        # Other glyph components
        'planet': planet,
        'solar_system': solar_system,
        'region_x': region_x,
        'region_y': region_y,
        'region_z': region_z,
        'glyph': glyph,
        'glyph_formatted': format_glyph(glyph),
        # Classification flags
        'is_phantom': classification['is_phantom'],
        'is_in_core': classification['is_in_core'],
        'is_accessible': classification['is_accessible'],
        'classification': classification['classification'],
        'warnings': '; '.join(all_warnings) if all_warnings else None
    }

    # Apply display scaling if requested
    if apply_scale:
        # Scaled region coordinates (backward compatible)
        result['display_x'] = x * DISPLAY_SCALE
        result['display_y'] = y * DISPLAY_SCALE
        result['display_z'] = z * DISPLAY_SCALE
        # Scaled star coordinates (for 3D map)
        result['display_star_x'] = star_x * DISPLAY_SCALE
        result['display_star_y'] = star_y * DISPLAY_SCALE
        result['display_star_z'] = star_z * DISPLAY_SCALE

    return result


def encode_coords_to_glyph(x: int, y: int, z: int,
                           planet: int = 0,
                           solar_system: int = 1) -> str:
    """
    Encode galaxy coordinates to NMS portal glyph using signed hexadecimal.

    NMS Coordinate System (Signed Hexadecimal):
    - X-Axis (West ← 0 → East): 801-FFF (West -2047 to -1), 000-7FF (East 0 to +2047)
    - Y-Axis (Down ← 0 → Up): 81-FF (Down -127 to -1), 00-7F (Up 0 to +127)
    - Z-Axis (South ← 0 → North): 000-7FF (South 0 to +2047), 801-FFF (North -2047 to -1)

    Args:
        x: X coordinate (-2047 to +2047, West to East)
        y: Y coordinate (-127 to +127, Down to Up)
        z: Z coordinate (-2047 to +2047, South to North) [Note: inverted, South is positive]
        planet: Planet index (0-6, default 0 for space station)
        solar_system: Solar system index (1-767, default 1)

    Returns:
        12-digit hex glyph code
    """
    # Validate input ranges (full in-game range)
    if not (-2047 <= x <= 2047):
        raise ValueError(f"X coordinate {x} out of range (-2047 to +2047)")
    if not (-127 <= y <= 127):
        raise ValueError(f"Y coordinate {y} out of range (-127 to +127)")
    if not (-2047 <= z <= 2047):
        raise ValueError(f"Z coordinate {z} out of range (-2047 to +2047)")
    if not (0 <= planet <= 15):
        raise ValueError(f"Planet index {planet} out of range (0-15)")
    if not (1 <= solar_system <= 4095):
        raise ValueError(f"Solar system index {solar_system} out of range (1-4095)")

    # Check if coordinates are in galactic core void (hard block)
    if is_in_core_void(x, y, z):
        raise ValueError(
            f"Coordinates ({x}, {y}, {z}) are within the galactic core void "
            f"(X/Z radius: {CORE_VOID_RADIUS_XZ}, Y radius: {CORE_VOID_RADIUS_Y}). "
            f"This region is not suitable for star systems."
        )

    # Convert centered coordinates to signed hexadecimal
    # X-Axis: East (positive) = 000-7FF, West (negative) = 801-FFF
    if x >= 0:
        x_hex = x  # Positive (East): 0 → 000, +2047 → 7FF
    else:
        x_hex = 0x1000 + x  # Negative (West): -1 → FFF, -2047 → 801

    # Y-Axis: Up (positive) = 00-7F, Down (negative) = 81-FF
    if y >= 0:
        y_hex = y  # Positive (Up): 0 → 00, +127 → 7F
    else:
        y_hex = 0x100 + y  # Negative (Down): -1 → FF, -127 → 81

    # Z-Axis: South (positive) = 000-7FF, North (negative) = 801-FFF
    if z >= 0:
        z_hex = z  # Positive (South): 0 → 000, +2047 → 7FF
    else:
        z_hex = 0x1000 + z  # Negative (North): -1 → FFF, -2047 → 801

    # Validate that we didn't hit forbidden values
    if y_hex == 0x80:
        raise ValueError(f"Y coordinate {y} maps to forbidden hex value 0x80")
    if x_hex == 0x800:
        raise ValueError(f"X coordinate {x} maps to forbidden hex value 0x800")
    if z_hex == 0x800:
        raise ValueError(f"Z coordinate {z} maps to forbidden hex value 0x800")
    if x_hex == 0 and y_hex == 0 and z_hex == 0:
        raise ValueError("All coordinates cannot be zero (forbidden by NMS)")

    # Build glyph string
    glyph = (
        f"{planet:X}"           # 1 hex digit (0-6)
        f"{solar_system:03X}"   # 3 hex digits (001-2FF)
        f"{y_hex:02X}"          # 2 hex digits (00-7F, 81-FF)
        f"{z_hex:03X}"          # 3 hex digits (000-7FF, 801-FFF)
        f"{x_hex:03X}"          # 3 hex digits (000-7FF, 801-FFF)
    )

    return glyph.upper()


def format_glyph(glyph: str) -> str:
    """
    Format glyph code with separators for readability.

    Args:
        glyph: 12-digit hex string

    Returns:
        Formatted string: P-SSS-YY-ZZZ-XXX
    """
    glyph = glyph.strip().upper().replace('-', '').replace(' ', '')
    if len(glyph) != 12:
        return glyph

    return f"{glyph[0]}-{glyph[1:4]}-{glyph[4:6]}-{glyph[6:9]}-{glyph[9:12]}"


def is_in_core_void(x: int, y: int, z: int) -> bool:
    """
    Check if coordinates are within the galactic core void.

    The galactic core is a restricted zone where star systems cannot exist.
    In NMS lore, this is the bright center of light used for galaxy travel.

    Uses an ellipsoidal boundary that respects the galaxy's flattened shape:
    - X/Z dimensions: 4096 units each (-2048 to +2047)
    - Y dimension: 256 units (-128 to +127)

    The void is an ellipsoid scaled proportionally to the galaxy dimensions,
    preventing the void from extending through the entire Y axis.

    Args:
        x: X coordinate (centered, -2048 to +2047)
        y: Y coordinate (centered, -128 to +127)
        z: Z coordinate (centered, -2048 to +2047)

    Returns:
        True if within core void (unsafe zone), False otherwise
    """
    if not CORE_VOID_ENABLED:
        return False

    # Calculate normalized ellipsoidal distance from galactic center (0,0,0)
    # Each axis is normalized by its respective void radius
    # Point is inside ellipsoid if: (x/a)² + (y/b)² + (z/c)² < 1
    normalized_distance_sq = (
        (x / CORE_VOID_RADIUS_XZ) ** 2 +
        (y / CORE_VOID_RADIUS_Y) ** 2 +
        (z / CORE_VOID_RADIUS_XZ) ** 2
    )
    return normalized_distance_sq < 1.0


def is_phantom_star(solar_system_index: int) -> bool:
    """
    Check if a solar system index indicates a phantom star.

    Phantom stars are star systems that exist in the game data but are not
    normally accessible via the Galactic Map. Each region has 4,096 possible
    systems (SSS 001-FFF), but only ~600 appear on the map.

    Reference: https://nomanssky.fandom.com/wiki/Phantom_Star

    Args:
        solar_system_index: Solar system index (0-4095)

    Returns:
        True if this is a phantom star, False if accessible
    """
    # SSS = 0 produces phantom stars in some regions
    if PHANTOM_SSS_ZERO and solar_system_index == 0:
        return True

    # SSS = 0x3E8 (1000) is a special exception - appears on map due to bug
    if solar_system_index == PHANTOM_SSS_EXCEPTION:
        return False

    # SSS >= 600 (0x258) are typically phantom stars
    return solar_system_index >= PHANTOM_SSS_THRESHOLD


def get_system_classification(x: int, y: int, z: int, solar_system_index: int) -> dict:
    """
    Get full classification of a star system including phantom and core void status.

    Args:
        x: X coordinate (centered, -2048 to +2047)
        y: Y coordinate (centered, -128 to +127)
        z: Z coordinate (centered, -2048 to +2047)
        solar_system_index: Solar system index (0-4095)

    Returns:
        Dictionary with classification flags:
            - is_phantom: True if phantom star (SSS-based)
            - is_in_core: True if in core void (coordinate-based)
            - is_accessible: True if normal accessible system
            - classification: String description
    """
    phantom = is_phantom_star(solar_system_index)
    in_core = is_in_core_void(x, y, z)

    # Determine classification
    if in_core and phantom:
        classification = "core_phantom"
    elif in_core:
        # Note: Normal systems shouldn't exist in core, but check anyway
        classification = "core_anomaly"
    elif phantom:
        classification = "phantom"
    else:
        classification = "accessible"

    return {
        'is_phantom': phantom,
        'is_in_core': in_core,
        'is_accessible': not phantom and not in_core,
        'classification': classification
    }


def calculate_region_name(region_x: int, region_y: int, region_z: int) -> str:
    """
    Generate a region name based on region coordinates.

    Args:
        region_x: Region X coordinate (0-31)
        region_y: Region Y coordinate (0-1)
        region_z: Region Z coordinate (0-31)

    Returns:
        Region name string
    """
    # Simple naming scheme - can be customized
    # Format: "Region [RX:RY:RZ]"
    return f"Region [{region_x:02X}:{region_y:X}:{region_z:02X}]"


def get_glyph_image_path(hex_digit: str) -> str:
    """
    Get the image filename for a hex digit.

    Args:
        hex_digit: Single hex character (0-9, A-F)

    Returns:
        Image filename
    """
    return GLYPH_IMAGES.get(hex_digit.upper(), '')


def parse_glyph_sequence(glyph_names: list) -> str:
    """
    Convert a sequence of glyph names to hex code.

    Args:
        glyph_names: List of 12 glyph names (e.g., ['sunset', 'bird', ...])

    Returns:
        12-digit hex string
    """
    if len(glyph_names) != 12:
        raise ValueError(f"Expected 12 glyphs, got {len(glyph_names)}")

    hex_digits = []
    for name in glyph_names:
        name_lower = name.lower()
        if name_lower not in GLYPH_TO_HEX:
            raise ValueError(f"Unknown glyph name: {name}")
        hex_digits.append(GLYPH_TO_HEX[name_lower])

    return ''.join(hex_digits)


# Example usage and testing
if __name__ == '__main__':
    # Test encoding
    print("=== Testing Coordinate Encoding ===")
    test_coords = [
        (500, 50, 500),       # Safe region (outside core void)
        (100, 50, -500),      # Random coordinate (outside core void)
        (-1000, -100, 1500),  # Far coordinate
    ]

    for x, y, z in test_coords:
        glyph = encode_coords_to_glyph(x, y, z, planet=0, solar_system=1)
        print(f"Coords ({x:5d}, {y:4d}, {z:5d}) -> Glyph: {format_glyph(glyph)}")

    print("\n=== Testing Glyph Decoding ===")
    test_glyphs = [
        "1001807FF800",  # Galaxy center (approximately)
        "00010000007FF",  # Corner coordinate
        "10A4F3E7B2C1",  # Random valid glyph
    ]

    for glyph in test_glyphs:
        try:
            result = decode_glyph_to_coords(glyph, apply_scale=True)
            print(f"Glyph: {result['glyph_formatted']}")
            print(f"  Region Coords: ({result['x']}, {result['y']}, {result['z']})")
            print(f"  Star Position: ({result['star_x']:.2f}, {result['star_y']:.2f}, {result['star_z']:.2f})")
            print(f"  Display Region: ({result['display_x']:.1f}, {result['display_y']:.1f}, {result['display_z']:.1f})")
            print(f"  Display Star: ({result['display_star_x']:.2f}, {result['display_star_y']:.2f}, {result['display_star_z']:.2f})")
            print(f"  Region Grid: [{result['region_x']}, {result['region_y']}, {result['region_z']}]")
            print(f"  Planet: {result['planet']}, System: {result['solar_system']}")
            if result['warnings']:
                print(f"  WARNING: {result['warnings']}")
        except ValueError as e:
            print(f"Error decoding {glyph}: {e}")
        print()

    print("=== Testing Star Position Uniqueness (Same Region, Different SSS) ===")
    # Test that different solar system indices produce different star positions
    # These glyphs have the same region coords but different SSS values
    same_region_glyphs = [
        "100100000000",  # SSS=001
        "100200000000",  # SSS=002
        "100300000000",  # SSS=003
        "107900000000",  # SSS=079 (Black Hole in every region)
        "107A00000000",  # SSS=07A (Atlas Interface in every region)
    ]
    print("All glyphs below have the same region coordinates but different Solar System Index:")
    for glyph in same_region_glyphs:
        result = decode_glyph_to_coords(glyph)
        print(f"  {format_glyph(glyph)} (SSS={result['solar_system']:03X}): "
              f"Star at ({result['star_x']:.2f}, {result['star_y']:.2f}, {result['star_z']:.2f})")
    print()

    print("=== Testing Round-trip ===")
    original_x, original_y, original_z = 500, -50, -1200
    glyph = encode_coords_to_glyph(original_x, original_y, original_z)
    decoded = decode_glyph_to_coords(glyph)
    print(f"Original: ({original_x}, {original_y}, {original_z})")
    print(f"Glyph: {format_glyph(glyph)}")
    print(f"Decoded: ({decoded['x']}, {decoded['y']}, {decoded['z']})")
    print(f"Match: {original_x == decoded['x'] and original_y == decoded['y'] and original_z == decoded['z']}")
