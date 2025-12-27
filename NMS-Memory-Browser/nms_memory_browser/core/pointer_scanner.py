"""Pointer scanner for finding root game object addresses.

Uses NMS.py's gameData to access known root pointers and provides
utilities for discovering additional game objects in memory.
"""

import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RootPointer:
    """Information about a root game object pointer."""
    name: str
    path: str  # Access path from gameData
    struct_type: str
    description: str
    address: int = 0
    valid: bool = False


class PointerScanner:
    """Scanner for locating root game object pointers.

    Uses nmspy.common.gameData to access known game structures
    and provides a unified interface for the memory browser.
    """

    # Known root pointer paths from NMS.py
    ROOT_POINTERS = {
        'player_state': {
            'path': 'player_state',
            'struct_type': 'cGcPlayerState',
            'description': 'Player state including inventory, location, stats',
        },
        'simulation': {
            'path': 'simulation',
            'struct_type': 'cGcSimulation',
            'description': 'Main simulation containing environment, player, solar system',
        },
        'game_state': {
            'path': 'game_state',
            'struct_type': 'cGcGameState',
            'description': 'Overall game state with player ownership data',
        },
        'environment': {
            'path': 'environment',
            'struct_type': 'cGcEnvironment',
            'description': 'Environment and weather systems',
        },
        'player': {
            'path': 'player',
            'struct_type': 'cGcPlayer',
            'description': 'Player entity with character state',
        },
        'player_environment': {
            'path': 'simulation.mEnvironment.mPlayerEnvironment',
            'struct_type': 'cGcPlayerEnvironment',
            'description': 'Player environment (location type, distance from planet)',
        },
        'solar_system': {
            'path': 'simulation.mpSolarSystem',
            'struct_type': 'cGcSolarSystem',
            'description': 'Current solar system data',
        },
        'gc_application': {
            'path': 'GcApplication',
            'struct_type': 'cGcApplication',
            'description': 'Main application object',
        },
        'ship_ownership': {
            'path': 'game_state.mPlayerShipOwnership',
            'struct_type': 'cGcPlayerShipOwnership',
            'description': 'Player ship fleet (12 ships)',
        },
        'hud_manager': {
            'path': 'GcApplication.mData.mHUDManager',
            'struct_type': 'cGcHUDManager',
            'description': 'HUD manager with player/ship HUD',
        },
    }

    def __init__(self):
        """Initialize the pointer scanner."""
        self._cached_pointers: Dict[str, RootPointer] = {}
        self._game_data = None
        self._connected = False

    def connect(self) -> bool:
        """Establish connection to game data.

        Returns:
            True if connected successfully
        """
        try:
            from nmspy.common import gameData
            self._game_data = gameData
            self._connected = True
            logger.info("Connected to NMS gameData")

            # Debug: Log what gameData looks like
            logger.info(f"gameData type: {type(gameData)}")
            logger.info(f"gameData id: {id(gameData)}")

            # Check what's available
            if hasattr(gameData, '__dict__'):
                attrs = list(gameData.__dict__.keys())
                logger.info(f"gameData attrs: {attrs}")
            else:
                # Try dir() instead
                attrs = [a for a in dir(gameData) if not a.startswith('_')][:20]
                logger.info(f"gameData dir (first 20): {attrs}")

            # Try accessing player_state directly
            try:
                ps = getattr(gameData, 'player_state', None)
                logger.info(f"Direct access - player_state: {type(ps) if ps else 'None'}")
            except Exception as e:
                logger.warning(f"Direct access - player_state failed: {e}")

            return True
        except ImportError as e:
            logger.error(f"Failed to import nmspy: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to gameData: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    @property
    def is_connected(self) -> bool:
        """Check if connected to game data."""
        return self._connected and self._game_data is not None

    def scan_root_pointers(self) -> Dict[str, RootPointer]:
        """Scan all known root pointers and get their addresses.

        Returns:
            Dictionary of root pointer info
        """
        if not self.is_connected:
            logger.warning("Not connected to game data")
            return {}

        results = {}

        for name, info in self.ROOT_POINTERS.items():
            pointer = RootPointer(
                name=name,
                path=info['path'],
                struct_type=info['struct_type'],
                description=info['description'],
            )

            try:
                addr = self._resolve_path(info['path'])
                if addr and addr != 0:
                    pointer.address = addr
                    pointer.valid = True
                    logger.debug(f"Found {name} at 0x{addr:X}")
            except Exception as e:
                logger.debug(f"Could not resolve {name}: {e}")

            results[name] = pointer

        self._cached_pointers = results
        return results

    def _resolve_path(self, path: str) -> Optional[int]:
        """Resolve a dot-separated path to an address.

        Args:
            path: Path like 'simulation.mpSolarSystem'

        Returns:
            Memory address or None
        """
        try:
            from pymhf.core.memutils import get_addressof

            parts = path.split('.')
            obj = self._game_data

            for part in parts:
                if obj is None:
                    return None
                obj = getattr(obj, part, None)

            if obj is not None:
                return get_addressof(obj)

        except Exception as e:
            logger.debug(f"Failed to resolve path '{path}': {e}")

        return None

    def get_pointer(self, name: str) -> Optional[RootPointer]:
        """Get a specific root pointer.

        Args:
            name: Pointer name (e.g., 'player_state')

        Returns:
            RootPointer info or None
        """
        if name in self._cached_pointers:
            return self._cached_pointers[name]

        if not self.is_connected:
            return None

        if name in self.ROOT_POINTERS:
            info = self.ROOT_POINTERS[name]
            pointer = RootPointer(
                name=name,
                path=info['path'],
                struct_type=info['struct_type'],
                description=info['description'],
            )

            try:
                addr = self._resolve_path(info['path'])
                if addr and addr != 0:
                    pointer.address = addr
                    pointer.valid = True
            except:
                pass

            self._cached_pointers[name] = pointer
            return pointer

        return None

    def get_game_object(self, name: str) -> Optional[Any]:
        """Get a game object directly from gameData.

        Args:
            name: Object name (e.g., 'player_state')

        Returns:
            The game object or None
        """
        if not self.is_connected:
            logger.warning(f"get_game_object('{name}'): Not connected")
            return None

        if name not in self.ROOT_POINTERS:
            logger.warning(f"get_game_object('{name}'): Unknown root pointer")
            return None

        path = self.ROOT_POINTERS[name]['path']
        logger.debug(f"get_game_object('{name}'): Resolving path '{path}'")

        try:
            parts = path.split('.')
            obj = self._game_data
            logger.debug(f"get_game_object('{name}'): gameData = {type(obj)}, id={id(obj) if obj else 'None'}")

            for i, part in enumerate(parts):
                if obj is None:
                    logger.warning(f"get_game_object('{name}'): obj is None at part {i} ('{part}')")
                    return None

                # Check what attributes are available
                if hasattr(obj, '__dict__'):
                    avail_attrs = list(obj.__dict__.keys())[:10]  # First 10 attrs
                    logger.debug(f"get_game_object: obj has attrs: {avail_attrs}...")

                prev_obj = obj
                obj = getattr(obj, part, None)
                logger.debug(f"get_game_object('{name}'): {part} -> {type(obj) if obj else 'None'}")

                if obj is None:
                    logger.warning(f"get_game_object('{name}'): getattr({type(prev_obj).__name__}, '{part}') returned None")

            if obj is not None:
                logger.info(f"get_game_object('{name}'): SUCCESS - got {type(obj)}")
            return obj
        except Exception as e:
            logger.error(f"Failed to get game object '{name}': {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def refresh(self) -> Dict[str, RootPointer]:
        """Refresh all cached pointers.

        Returns:
            Updated pointer dictionary
        """
        self._cached_pointers.clear()
        return self.scan_root_pointers()

    # =========================================================================
    # Derived Pointers (computed from root pointers)
    # =========================================================================

    def get_solar_system_data_address(self) -> Optional[int]:
        """Get address of current solar system data struct."""
        try:
            solar_system = self.get_game_object('solar_system')
            if solar_system is not None:
                from pymhf.core.memutils import get_addressof
                # cGcSolarSystemData is at offset 0 in cGcSolarSystem
                return get_addressof(solar_system)
        except:
            pass
        return None

    def get_planets_array_address(self) -> Optional[int]:
        """Get address of planets array in current system."""
        try:
            solar_system = self.get_game_object('solar_system')
            if solar_system is not None:
                # maPlanets is typically at a known offset
                from pymhf.core.memutils import get_addressof
                base = get_addressof(solar_system)
                # Offset for maPlanets array (needs verification)
                return base + 0x2630 if base else None
        except:
            pass
        return None

    def get_player_location(self) -> Optional[Dict[str, Any]]:
        """Get player's current location data."""
        try:
            player_state = self.get_game_object('player_state')
            if player_state is not None and hasattr(player_state, 'mLocation'):
                location = player_state.mLocation
                if hasattr(location, 'GalacticAddress'):
                    ga = location.GalacticAddress
                    return {
                        'voxel_x': getattr(ga, 'VoxelX', 0),
                        'voxel_y': getattr(ga, 'VoxelY', 0),
                        'voxel_z': getattr(ga, 'VoxelZ', 0),
                        'system_index': getattr(ga, 'SolarSystemIndex', 0),
                        'planet_index': getattr(ga, 'PlanetIndex', 0),
                        'galaxy_index': getattr(location, 'RealityIndex', 0),
                    }
        except Exception as e:
            logger.debug(f"Failed to get player location: {e}")
        return None

    # =========================================================================
    # Status Methods
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get scanner status information."""
        return {
            'connected': self.is_connected,
            'cached_pointers': len(self._cached_pointers),
            'valid_pointers': sum(1 for p in self._cached_pointers.values() if p.valid),
            'pointers': {
                name: {
                    'address': f"0x{p.address:X}" if p.address else "NULL",
                    'valid': p.valid,
                    'struct': p.struct_type,
                }
                for name, p in self._cached_pointers.items()
            }
        }
