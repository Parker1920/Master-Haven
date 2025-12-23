"""
Discovery Data Extractor for NMS Save Files.
Extracts system, planet, and moon discovery data from parsed save files.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger('nms_watcher.extractor')


@dataclass
class MoonData:
    """Data for a discovered moon."""
    name: str
    biome: str
    sentinel_level: str = ""
    fauna_level: str = ""
    flora_level: str = ""
    resources: list[str] = field(default_factory=list)
    discovered_by: str = ""
    discovered_at: str = ""
    has_base: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BaseLocation:
    """Data for a base on a planet."""
    name: str
    latitude: float
    longitude: float

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        return f"{self.name} ({self.latitude:+.2f}, {self.longitude:+.2f})"


@dataclass
class PlanetData:
    """Data for a discovered planet."""
    name: str
    biome: str
    sentinel_level: str = ""
    fauna_level: str = ""
    flora_level: str = ""
    resources: list[str] = field(default_factory=list)
    discovered_by: str = ""
    discovered_at: str = ""
    has_base: bool = False
    base_locations: list[BaseLocation] = field(default_factory=list)
    moons: list[MoonData] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['base_locations'] = [b.to_dict() if isinstance(b, BaseLocation) else b for b in self.base_locations]
        d['moons'] = [m.to_dict() if isinstance(m, MoonData) else m for m in self.moons]
        return d


@dataclass
class SystemData:
    """Data for a discovered system."""
    name: str
    glyph_code: str
    galaxy: str
    galaxy_index: int
    star_type: str = ""
    economy_type: str = ""
    economy_level: str = ""
    conflict_level: str = ""
    discovered_by: str = ""
    discovered_at: str = ""
    planets: list[PlanetData] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['planets'] = [p.to_dict() if isinstance(p, PlanetData) else p for p in self.planets]
        return d


class LevelMapper:
    """Maps numeric level values to human-readable strings."""

    def __init__(self, levels_path: Optional[Path] = None):
        if levels_path is None:
            levels_path = Path(__file__).parent.parent / 'data' / 'levels.json'

        self.levels: dict = {}
        self._load_levels(levels_path)

    def _load_levels(self, path: Path):
        if not path.exists():
            logger.warning(f"Levels file not found: {path}")
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.levels = json.load(f)
            logger.debug(f"Loaded level mappings from {path}")
        except Exception as e:
            logger.error(f"Failed to load levels: {e}")

    def get_sentinel_level(self, value: Any) -> str:
        return self.levels.get('sentinel', {}).get(str(value), str(value))

    def get_fauna_level(self, value: Any) -> str:
        return self.levels.get('fauna', {}).get(str(value), str(value))

    def get_flora_level(self, value: Any) -> str:
        return self.levels.get('flora', {}).get(str(value), str(value))

    def get_economy_level(self, value: Any) -> str:
        return self.levels.get('economy', {}).get(str(value), str(value))

    def get_conflict_level(self, value: Any) -> str:
        return self.levels.get('conflict', {}).get(str(value), str(value))

    def get_biome(self, value: str) -> str:
        return self.levels.get('biome', {}).get(value, value)

    def get_star_type(self, value: str) -> str:
        return self.levels.get('star_type', {}).get(value, value)

    def get_economy_type(self, value: str) -> str:
        return self.levels.get('economy_type', {}).get(value, value)


class ResourceMapper:
    """Maps resource IDs to human-readable names."""

    def __init__(self, resources_path: Optional[Path] = None):
        if resources_path is None:
            resources_path = Path(__file__).parent.parent / 'data' / 'resources.json'

        self.resources: dict = {}
        self._load_resources(resources_path)

    def _load_resources(self, path: Path):
        if not path.exists():
            logger.warning(f"Resources file not found: {path}")
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.resources = json.load(f)
            logger.debug(f"Loaded {len(self.resources)} resource mappings")
        except Exception as e:
            logger.error(f"Failed to load resources: {e}")

    def get_name(self, resource_id: str) -> str:
        """Get human-readable name for a resource ID."""
        return self.resources.get(resource_id, resource_id)

    def map_resources(self, resource_ids: list[str]) -> list[str]:
        """Map a list of resource IDs to human-readable names."""
        return [self.get_name(rid) for rid in resource_ids if rid]


class GalaxyMapper:
    """Maps galaxy indices to names."""

    def __init__(self, galaxies_path: Optional[Path] = None):
        if galaxies_path is None:
            galaxies_path = Path(__file__).parent.parent / 'data' / 'galaxies.json'

        self.galaxies: dict = {}
        self._load_galaxies(galaxies_path)

    def _load_galaxies(self, path: Path):
        if not path.exists():
            logger.warning(f"Galaxies file not found: {path}")
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.galaxies = json.load(f)
            logger.debug(f"Loaded {len(self.galaxies)} galaxy mappings")
        except Exception as e:
            logger.error(f"Failed to load galaxies: {e}")

    def get_name(self, index: int) -> str:
        """Get galaxy name from index."""
        return self.galaxies.get(str(index), f"Galaxy {index}")


def coords_to_glyphs(x: int, y: int, z: int, system_index: int) -> str:
    """
    Convert galactic coordinates to portal glyph code.

    NMS uses a specific coordinate system:
    - X, Y, Z are region coordinates (-2047 to 2047 for X/Z, -127 to 127 for Y)
    - System index is 0-767 within a region

    Portal address format (12 hex digits):
    - P: Planet index (0 in glyph code, selected at portal)
    - SSS: System index (0-767)
    - YY: Y coordinate offset (Y + 128, so 0-255)
    - ZZZ: Z coordinate offset (Z + 2047, so 0-4095)
    - XXX: X coordinate offset (X + 2047, so 0-4095)

    Format: PSSS:YY:ZZZ:XXX (without colons = 12 hex chars)
    """
    # Offset coordinates to positive values
    x_offset = (x + 2047) & 0xFFF  # 12 bits
    y_offset = (y + 128) & 0xFF    # 8 bits
    z_offset = (z + 2047) & 0xFFF  # 12 bits
    sys_offset = system_index & 0xFFF  # 12 bits (but only 0-767 used)

    # Planet index is 0 in the glyph code (player selects at portal)
    planet = 0

    # Build the glyph code: PSSSYYZZZXXX
    glyph_value = (planet << 48) | (sys_offset << 36) | (y_offset << 28) | (z_offset << 16) | x_offset

    # Actually, simpler format - just 12 hex digits
    # Format: [P][SSS][YY][ZZZ][XXX]
    glyph_code = f"{planet:01X}{sys_offset:03X}{y_offset:02X}{z_offset:03X}{x_offset:03X}"

    return glyph_code


def galactic_address_to_glyphs(galactic_address: int) -> str:
    """
    Convert a GalacticAddress value directly to glyph code.

    The GalacticAddress is a packed integer containing:
    - Bits 0-11: Planet index
    - Bits 12-23: System index
    - Bits 24-31: Y coordinate (signed, -128 to 127)
    - Bits 32-43: Z coordinate (signed, -2048 to 2047)
    - Bits 44-55: X coordinate (signed, -2048 to 2047)

    Portal glyph format: PSSSYYZZZXXX (12 hex chars)
    """
    # Extract components from packed address
    planet_idx = galactic_address & 0xFFF
    system_idx = (galactic_address >> 12) & 0xFFF
    y_raw = (galactic_address >> 24) & 0xFF
    z_raw = (galactic_address >> 32) & 0xFFF
    x_raw = (galactic_address >> 44) & 0xFFF

    # For portal address, we use 0 for planet (selected at portal)
    # And keep other values as-is (they're already in the right format)
    glyph_code = f"0{system_idx:03X}{y_raw:02X}{z_raw:03X}{x_raw:03X}"

    return glyph_code


class DiscoveryExtractor:
    """Extracts discovery data from parsed NMS save files."""

    def __init__(self):
        self.level_mapper = LevelMapper()
        self.resource_mapper = ResourceMapper()
        self.galaxy_mapper = GalaxyMapper()

    def extract_discoveries(self, save_data: dict) -> list[SystemData]:
        """
        Extract all system discoveries from save data.

        Args:
            save_data: Parsed and deobfuscated save data

        Returns:
            List of SystemData objects
        """
        systems: list[SystemData] = []

        # Get the player state data
        # Structure varies between save versions, try multiple paths
        player_state = self._get_player_state(save_data)
        if not player_state:
            logger.warning("Could not find player state in save data")
            return systems

        # Get discovery manager data
        discovery_data = self._get_discovery_data(save_data)

        # Get current galaxy
        current_galaxy = player_state.get('CurrentGalaxy', 0)

        # Extract from DiscoveryManager store
        if discovery_data:
            systems.extend(self._extract_from_discovery_manager(discovery_data, current_galaxy))

        # Also check for current system data in player state
        current_system = self._extract_current_system(player_state, current_galaxy)
        if current_system:
            # Check if we already have this system
            existing = next((s for s in systems if s.glyph_code == current_system.glyph_code
                           and s.galaxy_index == current_system.galaxy_index), None)
            if not existing:
                systems.append(current_system)
            else:
                # Merge data if current has more info
                self._merge_system_data(existing, current_system)

        logger.info(f"Extracted {len(systems)} system discoveries")
        return systems

    def _get_player_state(self, save_data: dict) -> Optional[dict]:
        """Find player state data in save structure."""
        # Try direct path first
        if 'PlayerStateData' in save_data:
            return save_data['PlayerStateData']

        # Try under Version key (some save formats)
        if 'Version' in save_data and isinstance(save_data.get('PlayerStateData'), dict):
            return save_data['PlayerStateData']

        # Search recursively for PlayerStateData
        return self._find_key_recursive(save_data, 'PlayerStateData')

    def _get_discovery_data(self, save_data: dict) -> Optional[dict]:
        """Find discovery manager data in save structure."""
        # Try direct path
        if 'DiscoveryManagerData' in save_data:
            return save_data['DiscoveryManagerData']

        # Try under PlayerStateData
        player_state = self._get_player_state(save_data)
        if player_state and 'DiscoveryManagerData' in player_state:
            return player_state['DiscoveryManagerData']

        # Search recursively
        return self._find_key_recursive(save_data, 'DiscoveryManagerData')

    def _find_key_recursive(self, obj: Any, target_key: str) -> Optional[Any]:
        """Recursively search for a key in nested structure."""
        if isinstance(obj, dict):
            if target_key in obj:
                return obj[target_key]
            for value in obj.values():
                result = self._find_key_recursive(value, target_key)
                if result is not None:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_key_recursive(item, target_key)
                if result is not None:
                    return result
        return None

    def _extract_from_discovery_manager(self, discovery_data: dict, default_galaxy: int) -> list[SystemData]:
        """Extract systems from DiscoveryManagerData."""
        systems: list[SystemData] = []

        # Get the store of discoveries
        store = discovery_data.get('DiscoveryData-v1', {}).get('Store', {})
        if not store:
            store = discovery_data.get('Store', {})

        # Records are organized by type
        records = store.get('Record', [])
        if not records:
            return systems

        # Group discoveries by system (using galactic address)
        system_discoveries: dict[str, dict] = {}
        planet_discoveries: dict[str, list[dict]] = {}

        for record in records:
            discovery_type = record.get('DT', record.get('DiscoveryType', ''))

            # OT = OwnerType, DD = DiscoveryData
            owner_data = record.get('OWS', record.get('OwnerData', {}))
            discovery_info = record.get('DD', record.get('DiscoveryData', {}))

            # Get galactic address
            galactic_address = self._get_galactic_address(record)
            if not galactic_address:
                continue

            if discovery_type in ('SolarSystem', 'System'):
                system_discoveries[galactic_address] = record
            elif discovery_type in ('Planet', 'Moon'):
                if galactic_address not in planet_discoveries:
                    planet_discoveries[galactic_address] = []
                planet_discoveries[galactic_address].append(record)

        # Build system data objects
        for addr, system_record in system_discoveries.items():
            try:
                system = self._build_system_data(system_record, default_galaxy)
                if system:
                    # Add planets/moons
                    if addr in planet_discoveries:
                        for planet_record in planet_discoveries[addr]:
                            planet = self._build_planet_data(planet_record)
                            if planet:
                                # Check if it's a moon (has parent body)
                                if self._is_moon(planet_record):
                                    # Find parent planet and add moon to it
                                    # For now, add as planet (moon detection is complex)
                                    system.planets.append(planet)
                                else:
                                    system.planets.append(planet)
                    systems.append(system)
            except Exception as e:
                logger.error(f"Error building system data: {e}")

        return systems

    def _get_galactic_address(self, record: dict) -> Optional[str]:
        """Extract galactic address from a discovery record."""
        # Try various key names
        for key in ('GA', 'GalacticAddress', 'UniverseAddress'):
            if key in record:
                addr = record[key]
                if isinstance(addr, dict):
                    # Nested structure with VoxelX, VoxelY, VoxelZ, SolarSystemIndex
                    return self._build_address_from_voxels(addr)
                elif isinstance(addr, (int, str)):
                    return str(addr)

        # Check nested DiscoveryData
        dd = record.get('DD', record.get('DiscoveryData', {}))
        if isinstance(dd, dict):
            for key in ('GA', 'GalacticAddress', 'UniverseAddress'):
                if key in dd:
                    addr = dd[key]
                    if isinstance(addr, dict):
                        return self._build_address_from_voxels(addr)
                    elif isinstance(addr, (int, str)):
                        return str(addr)

        return None

    def _build_address_from_voxels(self, addr: dict) -> str:
        """Build address string from voxel coordinates."""
        x = addr.get('VoxelX', addr.get('RealityIndex', 0))
        y = addr.get('VoxelY', 0)
        z = addr.get('VoxelZ', 0)
        system_idx = addr.get('SolarSystemIndex', addr.get('SystemIndex', 0))

        # Return a unique identifier string
        return f"{x}:{y}:{z}:{system_idx}"

    def _build_system_data(self, record: dict, default_galaxy: int) -> Optional[SystemData]:
        """Build SystemData from a discovery record."""
        dd = record.get('DD', record.get('DiscoveryData', record))

        # Get name
        name = dd.get('N', dd.get('Name', ''))
        if not name:
            name = record.get('N', record.get('Name', 'Unknown System'))

        # Get galactic address for glyph code
        galactic_addr = self._get_galactic_address(record)
        if not galactic_addr:
            return None

        # Convert to glyph code
        glyph_code = self._address_to_glyphs(galactic_addr, record)

        # Get galaxy index
        galaxy_idx = self._get_galaxy_index(record, default_galaxy)

        # Get discoverer info
        discovered_by = self._get_discoverer(record)
        discovered_at = self._get_discovery_time(record)

        # Get system attributes
        star_type = self._extract_star_type(dd)
        economy_type = self._extract_economy_type(dd)
        economy_level = self._extract_economy_level(dd)
        conflict_level = self._extract_conflict_level(dd)

        return SystemData(
            name=name,
            glyph_code=glyph_code,
            galaxy=self.galaxy_mapper.get_name(galaxy_idx),
            galaxy_index=galaxy_idx,
            star_type=star_type,
            economy_type=economy_type,
            economy_level=economy_level,
            conflict_level=conflict_level,
            discovered_by=discovered_by,
            discovered_at=discovered_at,
            planets=[]
        )

    def _address_to_glyphs(self, addr_str: str, record: dict) -> str:
        """Convert address string or record to glyph code."""
        # Try to get raw GalacticAddress integer
        for key in ('GA', 'GalacticAddress'):
            val = record.get(key)
            if isinstance(val, int):
                return galactic_address_to_glyphs(val)
            if isinstance(val, dict):
                # Has components
                break

        # Parse from voxel string
        if ':' in addr_str:
            parts = addr_str.split(':')
            if len(parts) >= 4:
                try:
                    x = int(parts[0])
                    y = int(parts[1])
                    z = int(parts[2])
                    sys_idx = int(parts[3])
                    return coords_to_glyphs(x, y, z, sys_idx)
                except ValueError:
                    pass

        # Fallback - return address as-is
        return addr_str.replace(':', '')

    def _get_galaxy_index(self, record: dict, default: int) -> int:
        """Extract galaxy index from record."""
        # Try direct galaxy field
        for key in ('Galaxy', 'GalaxyIndex', 'RealityIndex'):
            if key in record:
                return int(record[key])

        # Try in nested data
        dd = record.get('DD', record.get('DiscoveryData', {}))
        if isinstance(dd, dict):
            for key in ('Galaxy', 'GalaxyIndex', 'RealityIndex'):
                if key in dd:
                    return int(dd[key])

        # Try in UniverseAddress
        ua = record.get('UA', record.get('UniverseAddress', {}))
        if isinstance(ua, dict):
            if 'RealityIndex' in ua:
                return int(ua['RealityIndex'])

        return default

    def _get_discoverer(self, record: dict) -> str:
        """Extract discoverer username from record."""
        # Try owner data
        owner = record.get('OWS', record.get('OwnerData', {}))
        if isinstance(owner, dict):
            for key in ('USN', 'Username', 'DiscovererName'):
                if key in owner and owner[key]:
                    return str(owner[key])

        # Try direct fields
        for key in ('USN', 'Username', 'DiscovererName', 'Discoverer'):
            if key in record and record[key]:
                return str(record[key])

        return ""

    def _get_discovery_time(self, record: dict) -> str:
        """Extract discovery timestamp from record."""
        for key in ('TS', 'Timestamp', 'DiscoveryTime', 'TimeStamp'):
            if key in record and record[key]:
                return str(record[key])
        return ""

    def _extract_star_type(self, dd: dict) -> str:
        """Extract star type from discovery data."""
        for key in ('StarType', 'ST', 'Star'):
            if key in dd:
                return self.level_mapper.get_star_type(str(dd[key]))
        return ""

    def _extract_economy_type(self, dd: dict) -> str:
        """Extract economy type from discovery data."""
        for key in ('EconomyType', 'ET', 'Economy'):
            if key in dd:
                return self.level_mapper.get_economy_type(str(dd[key]))
        return ""

    def _extract_economy_level(self, dd: dict) -> str:
        """Extract economy level/wealth from discovery data."""
        for key in ('Wealth', 'EconomyLevel', 'WL'):
            if key in dd:
                return self.level_mapper.get_economy_level(dd[key])
        return ""

    def _extract_conflict_level(self, dd: dict) -> str:
        """Extract conflict level from discovery data."""
        for key in ('Conflict', 'ConflictLevel', 'CL'):
            if key in dd:
                return self.level_mapper.get_conflict_level(dd[key])
        return ""

    def _build_planet_data(self, record: dict) -> Optional[PlanetData]:
        """Build PlanetData from a discovery record."""
        dd = record.get('DD', record.get('DiscoveryData', record))

        # Get name
        name = dd.get('N', dd.get('Name', ''))
        if not name:
            name = record.get('N', record.get('Name', 'Unknown Planet'))

        # Get biome
        biome = ""
        for key in ('Biome', 'B', 'BiomeType'):
            if key in dd:
                biome = self.level_mapper.get_biome(str(dd[key]))
                break

        # Get levels
        sentinel = ""
        fauna = ""
        flora = ""

        for key in ('Sentinels', 'SentinelLevel', 'SL'):
            if key in dd:
                sentinel = self.level_mapper.get_sentinel_level(dd[key])
                break

        for key in ('Fauna', 'FaunaLevel', 'FL'):
            if key in dd:
                fauna = self.level_mapper.get_fauna_level(dd[key])
                break

        for key in ('Flora', 'FloraLevel', 'FoL'):
            if key in dd:
                flora = self.level_mapper.get_flora_level(dd[key])
                break

        # Get resources
        resources = []
        for key in ('Resources', 'R', 'ResourceList'):
            if key in dd and isinstance(dd[key], list):
                resources = self.resource_mapper.map_resources(dd[key])
                break

        # Get discoverer
        discovered_by = self._get_discoverer(record)
        discovered_at = self._get_discovery_time(record)

        return PlanetData(
            name=name,
            biome=biome,
            sentinel_level=sentinel,
            fauna_level=fauna,
            flora_level=flora,
            resources=resources,
            discovered_by=discovered_by,
            discovered_at=discovered_at,
            has_base=False,
            moons=[]
        )

    def _is_moon(self, record: dict) -> bool:
        """Check if a body record is a moon."""
        dd = record.get('DD', record.get('DiscoveryData', record))

        # Check discovery type
        dtype = record.get('DT', record.get('DiscoveryType', ''))
        if dtype == 'Moon':
            return True

        # Check for moon indicator
        for key in ('IsMoon', 'Moon', 'ParentBody'):
            if key in dd and dd[key]:
                return True

        return False

    def _extract_current_system(self, player_state: dict, galaxy: int) -> Optional[SystemData]:
        """Extract the current system from player state."""
        # Try to find current system info
        current_pos = player_state.get('UniverseAddress', player_state.get('CurrentAddress', {}))
        if not current_pos:
            return None

        # Get coordinates
        if isinstance(current_pos, dict):
            x = current_pos.get('VoxelX', current_pos.get('GalacticAddress', {}).get('VoxelX', 0))
            y = current_pos.get('VoxelY', current_pos.get('GalacticAddress', {}).get('VoxelY', 0))
            z = current_pos.get('VoxelZ', current_pos.get('GalacticAddress', {}).get('VoxelZ', 0))
            sys_idx = current_pos.get('SolarSystemIndex',
                       current_pos.get('GalacticAddress', {}).get('SolarSystemIndex', 0))
            galaxy = current_pos.get('RealityIndex', galaxy)
        elif isinstance(current_pos, int):
            # Packed address
            glyph_code = galactic_address_to_glyphs(current_pos)
            # Can't easily get name from just coordinates
            return None
        else:
            return None

        glyph_code = coords_to_glyphs(x, y, z, sys_idx)

        # Try to get current system name
        system_name = player_state.get('CurrentSystemName', '')
        if not system_name:
            # Try other fields
            for key in ('LastSystemName', 'SystemName'):
                if key in player_state and player_state[key]:
                    system_name = player_state[key]
                    break

        if not system_name:
            system_name = f"System {glyph_code}"

        return SystemData(
            name=system_name,
            glyph_code=glyph_code,
            galaxy=self.galaxy_mapper.get_name(galaxy),
            galaxy_index=galaxy,
            planets=[]
        )

    def _merge_system_data(self, existing: SystemData, new: SystemData):
        """Merge new system data into existing, keeping non-empty values."""
        if new.name and not existing.name:
            existing.name = new.name
        if new.star_type and not existing.star_type:
            existing.star_type = new.star_type
        if new.economy_type and not existing.economy_type:
            existing.economy_type = new.economy_type
        if new.economy_level and not existing.economy_level:
            existing.economy_level = new.economy_level
        if new.conflict_level and not existing.conflict_level:
            existing.conflict_level = new.conflict_level
        if new.discovered_by and not existing.discovered_by:
            existing.discovered_by = new.discovered_by
        if new.discovered_at and not existing.discovered_at:
            existing.discovered_at = new.discovered_at

        # Merge planets
        existing_names = {p.name for p in existing.planets}
        for planet in new.planets:
            if planet.name not in existing_names:
                existing.planets.append(planet)


def extract_systems(save_data: dict) -> list[SystemData]:
    """Convenience function to extract system discoveries."""
    extractor = DiscoveryExtractor()
    return extractor.extract_discoveries(save_data)


def extract_bases(save_data: dict) -> list[dict]:
    """
    Extract base location data from save file.

    Returns list of bases with planet/system coordinates.
    """
    bases = []

    # Get player state
    player_state = save_data.get('PlayerStateData', {})

    # Bases are in PersistentPlayerBases
    persistent_bases = player_state.get('PersistentPlayerBases', [])

    for base in persistent_bases:
        base_info = {
            'name': base.get('Name', base.get('BaseName', 'Unnamed Base')),
            'type': base.get('BaseType', 'Unknown'),
        }

        # Get position
        position = base.get('Position', base.get('GalacticAddress', {}))
        if isinstance(position, dict):
            base_info['latitude'] = position.get('Lat', position.get('x', 0))
            base_info['longitude'] = position.get('Long', position.get('z', 0))

        # Get universe address for system identification
        universe_addr = base.get('UniverseAddress', base.get('GalacticAddress', {}))
        if isinstance(universe_addr, dict):
            base_info['galaxy_index'] = universe_addr.get('RealityIndex', 0)
            galactic = universe_addr.get('GalacticAddress', universe_addr)
            if isinstance(galactic, dict):
                base_info['voxel_x'] = galactic.get('VoxelX', 0)
                base_info['voxel_y'] = galactic.get('VoxelY', 0)
                base_info['voxel_z'] = galactic.get('VoxelZ', 0)
                base_info['system_index'] = galactic.get('SolarSystemIndex', 0)
                base_info['planet_index'] = galactic.get('PlanetIndex', 0)

        bases.append(base_info)

    return bases


class SystemComparator:
    """Compares system data for edit detection."""

    @staticmethod
    def compare(existing: dict, new: SystemData) -> dict:
        """
        Compare existing system data with new data to detect changes.

        Args:
            existing: Existing system data from database/API
            new: New SystemData from save file

        Returns:
            Dict with 'has_changes', 'changes' list, and 'is_significant'
        """
        changes = []

        # Compare system name
        if existing.get('name') != new.name and new.name:
            changes.append({
                'field': 'name',
                'old': existing.get('name'),
                'new': new.name
            })

        # Compare star type
        if existing.get('star_type') != new.star_type and new.star_type:
            changes.append({
                'field': 'star_type',
                'old': existing.get('star_type'),
                'new': new.star_type
            })

        # Compare economy
        if existing.get('economy_type') != new.economy_type and new.economy_type:
            changes.append({
                'field': 'economy_type',
                'old': existing.get('economy_type'),
                'new': new.economy_type
            })

        if existing.get('economy_level') != new.economy_level and new.economy_level:
            changes.append({
                'field': 'economy_level',
                'old': existing.get('economy_level'),
                'new': new.economy_level
            })

        # Compare conflict
        if existing.get('conflict_level') != new.conflict_level and new.conflict_level:
            changes.append({
                'field': 'conflict_level',
                'old': existing.get('conflict_level'),
                'new': new.conflict_level
            })

        # Check for new planets
        existing_planet_names = set()
        if 'planets' in existing and isinstance(existing['planets'], list):
            existing_planet_names = {p.get('name', '') for p in existing['planets']}

        new_planets = []
        for planet in new.planets:
            if planet.name not in existing_planet_names:
                new_planets.append(planet.name)

        if new_planets:
            changes.append({
                'field': 'new_planets',
                'old': None,
                'new': new_planets
            })

        # Determine if changes are significant enough to submit
        # Name changes and new planets are significant
        is_significant = any(
            c['field'] in ('name', 'new_planets')
            for c in changes
        )

        return {
            'has_changes': len(changes) > 0,
            'changes': changes,
            'is_significant': is_significant
        }

    @staticmethod
    def format_changes(comparison: dict) -> str:
        """Format comparison results as human-readable string."""
        if not comparison['has_changes']:
            return "No changes detected"

        lines = []
        for change in comparison['changes']:
            field = change['field']
            if field == 'new_planets':
                lines.append(f"New planets: {', '.join(change['new'])}")
            else:
                lines.append(f"{field}: '{change['old']}' → '{change['new']}'")

        return "; ".join(lines)
