"""Multiplayer data collector.

Collects multiplayer-related data including other players,
player bases, settlements, and communication stations.
"""

import logging
from typing import Optional, Dict, Any, List

from ..core.memory_reader import MemoryReader
from ..core.struct_mapper import StructMapper, MappedStruct
from ..core.pointer_scanner import PointerScanner
from ..data.tree_node import (
    TreeNode, NodeType, create_struct_node, create_field_node,
    create_category_node, create_array_node
)
from ..data.snapshot import StructSnapshot

logger = logging.getLogger(__name__)


class MultiplayerCollector:
    """Collects multiplayer-related game data.

    This collector focuses on:
    - Other players in the session
    - Player bases (yours and others)
    - Settlements
    - Communication stations/message modules
    """

    # Known multiplayer-related struct types
    MP_STRUCTS = {
        'bases': 'cGcPersistentBaseEntry',
        'settlement': 'cGcSettlementState',
        'settlement_local': 'cGcSettlementLocalSaveData',
        'base_building': 'cGcBaseBuildingEntry',
        'network_player': 'cGcNetworkPlayer',
    }

    def __init__(
        self,
        reader: MemoryReader,
        mapper: StructMapper,
        scanner: PointerScanner
    ):
        """Initialize the multiplayer collector.

        Args:
            reader: Memory reader instance
            mapper: Struct mapper instance
            scanner: Pointer scanner instance
        """
        self.reader = reader
        self.mapper = mapper
        self.scanner = scanner

    def collect(self) -> Dict[str, Any]:
        """Collect all multiplayer data.

        Returns:
            Dictionary of multiplayer data organized by type
        """
        result = {
            'session_info': {},
            'other_players': [],
            'player_bases': [],
            'settlements': [],
            'comm_stations': [],
            'structs': {},
        }

        # Check if multiplayer is active
        result['session_info'] = self._get_session_info()

        # Collect player bases
        result['player_bases'] = self._collect_bases()

        # Collect settlements
        result['settlements'] = self._collect_settlements()

        # Collect other players (if in MP session)
        if result['session_info'].get('multiplayer_active', False):
            result['other_players'] = self._collect_other_players()

        # Collect comm stations
        result['comm_stations'] = self._collect_comm_stations()

        return result

    def _get_session_info(self) -> Dict[str, Any]:
        """Get multiplayer session information."""
        info = {
            'multiplayer_active': False,
            'player_count': 0,
        }

        try:
            # Try to access cGcApplication to check MP status
            # cGcApplication.mbMultiplayerActive is typically at offset 0xB508
            gc_app = self.scanner.get_game_object('gc_application')
            if gc_app is not None:
                if hasattr(gc_app, 'mbMultiplayerActive'):
                    info['multiplayer_active'] = bool(gc_app.mbMultiplayerActive)

                # Get player count if available
                if hasattr(gc_app, 'mpData'):
                    app_data = gc_app.mpData
                    # Look for network manager or player count
                    # This varies by game version
        except Exception as e:
            logger.debug(f"Error getting session info: {e}")

        return info

    def _collect_bases(self) -> List[Dict[str, Any]]:
        """Collect player base data."""
        bases = []

        try:
            # Bases are typically stored in cGcGameState.mPersistentBaseStorage
            # or accessible via cGcBaseBuildingManager
            game_state = self.scanner.get_game_object('game_state')
            if game_state is None:
                return bases

            # Try different access paths based on what's available
            # Path 1: mPersistentBaseStorage
            if hasattr(game_state, 'mPersistentBaseStorage'):
                storage = game_state.mPersistentBaseStorage
                if hasattr(storage, 'maEntries'):
                    entries = storage.maEntries
                    # Iterate through base entries
                    for i, entry in enumerate(entries):
                        if i >= 20:  # Limit to prevent excessive iteration
                            break
                        base_data = self._extract_base_entry(entry, i)
                        if base_data:
                            bases.append(base_data)

        except Exception as e:
            logger.debug(f"Error collecting bases: {e}")

        return bases

    def _extract_base_entry(self, entry: Any, index: int) -> Optional[Dict[str, Any]]:
        """Extract data from a base entry."""
        try:
            data = {'index': index}

            if hasattr(entry, 'mName'):
                name = entry.mName
                if hasattr(name, 'value'):
                    data['name'] = name.value
                else:
                    data['name'] = str(name)

            if hasattr(entry, 'mPosition'):
                pos = entry.mPosition
                if hasattr(pos, 'x'):
                    data['position'] = {
                        'x': pos.x,
                        'y': pos.y,
                        'z': pos.z,
                    }

            if hasattr(entry, 'mBaseType'):
                data['base_type'] = int(entry.mBaseType)

            if hasattr(entry, 'mOwnerUA'):
                # Owner's universal address
                ua = entry.mOwnerUA
                if hasattr(ua, 'VoxelX'):
                    data['owner_location'] = {
                        'voxel_x': ua.VoxelX,
                        'voxel_y': ua.VoxelY,
                        'voxel_z': ua.VoxelZ,
                    }

            return data if len(data) > 1 else None

        except Exception as e:
            logger.debug(f"Error extracting base entry {index}: {e}")
            return None

    def _collect_settlements(self) -> List[Dict[str, Any]]:
        """Collect settlement data."""
        settlements = []

        try:
            # Settlements are in cGcGameState or player state
            game_state = self.scanner.get_game_object('game_state')
            player_state = self.scanner.get_game_object('player_state')

            # Try player state settlement data
            if player_state and hasattr(player_state, 'mSettlementState'):
                settlement = player_state.mSettlementState
                settlement_data = self._extract_settlement(settlement, 0)
                if settlement_data:
                    settlements.append(settlement_data)

        except Exception as e:
            logger.debug(f"Error collecting settlements: {e}")

        return settlements

    def _extract_settlement(self, settlement: Any, index: int) -> Optional[Dict[str, Any]]:
        """Extract settlement data."""
        try:
            data = {'index': index}

            if hasattr(settlement, 'mName'):
                data['name'] = str(settlement.mName)

            if hasattr(settlement, 'mPopulation'):
                data['population'] = int(settlement.mPopulation)

            if hasattr(settlement, 'mHappiness'):
                data['happiness'] = float(settlement.mHappiness)

            if hasattr(settlement, 'mProductivity'):
                data['productivity'] = float(settlement.mProductivity)

            if hasattr(settlement, 'mSentinelLevel'):
                data['sentinel_level'] = int(settlement.mSentinelLevel)

            return data if len(data) > 1 else None

        except Exception as e:
            logger.debug(f"Error extracting settlement {index}: {e}")
            return None

    def _collect_other_players(self) -> List[Dict[str, Any]]:
        """Collect data about other players in the session."""
        players = []

        try:
            # Network players are typically in cGcNetworkManager or similar
            # This requires the multiplayer session to be active
            pass  # Implementation depends on specific NMS.py struct availability

        except Exception as e:
            logger.debug(f"Error collecting other players: {e}")

        return players

    def _collect_comm_stations(self) -> List[Dict[str, Any]]:
        """Collect communication station/message data."""
        stations = []

        try:
            # Comm stations are usually part of scan events or marker system
            # Implementation depends on game version and struct availability
            pass

        except Exception as e:
            logger.debug(f"Error collecting comm stations: {e}")

        return stations

    # =========================================================================
    # Tree Node Generation
    # =========================================================================

    def build_tree_nodes(self) -> TreeNode:
        """Build tree nodes for multiplayer data.

        Returns:
            Multiplayer category node with children
        """
        category = create_category_node('Multiplayer', 'Multiplayer Data')

        # Collect data
        data = self.collect()

        # Add Session Info
        session_node = TreeNode(
            name='Session Info',
            node_type=NodeType.STRUCT,
            display_text='Session Status',
            icon='network',
        )

        for key, value in data['session_info'].items():
            session_node.add_child(create_field_node(
                name=key,
                value=value,
                formatted_value=str(value),
                offset=0,
                size=4,
            ))

        category.add_child(session_node)

        # Add Other Players
        players_node = create_array_node(
            name='Other Players',
            element_type='NetworkPlayer',
            address=0,
            count=len(data['other_players']),
        )

        for player in data['other_players']:
            player_node = TreeNode(
                name=player.get('name', f"Player {player.get('index', '?')}"),
                node_type=NodeType.ARRAY_ELEMENT,
                display_text=player.get('name', 'Unknown Player'),
                icon='person',
            )

            for key, value in player.items():
                player_node.add_child(create_field_node(
                    name=key,
                    value=value,
                    formatted_value=str(value),
                    offset=0,
                    size=4,
                ))

            players_node.add_child(player_node)

        category.add_child(players_node)

        # Add Player Bases
        bases_node = create_array_node(
            name='Player Bases',
            element_type='cGcPersistentBaseEntry',
            address=0,
            count=len(data['player_bases']),
        )

        for base in data['player_bases']:
            base_node = TreeNode(
                name=base.get('name', f"Base {base.get('index', '?')}"),
                node_type=NodeType.ARRAY_ELEMENT,
                display_text=base.get('name', 'Unnamed Base'),
                icon='home',
            )

            for key, value in base.items():
                if isinstance(value, dict):
                    sub_node = TreeNode(
                        name=key,
                        node_type=NodeType.STRUCT,
                        display_text=key,
                    )
                    for sub_key, sub_value in value.items():
                        sub_node.add_child(create_field_node(
                            name=sub_key,
                            value=sub_value,
                            formatted_value=str(sub_value),
                            offset=0,
                            size=4,
                        ))
                    base_node.add_child(sub_node)
                else:
                    base_node.add_child(create_field_node(
                        name=key,
                        value=value,
                        formatted_value=str(value),
                        offset=0,
                        size=4,
                    ))

            bases_node.add_child(base_node)

        category.add_child(bases_node)

        # Add Settlements
        settlements_node = create_array_node(
            name='Settlements',
            element_type='cGcSettlementState',
            address=0,
            count=len(data['settlements']),
        )

        for settlement in data['settlements']:
            settlement_node = TreeNode(
                name=settlement.get('name', f"Settlement {settlement.get('index', '?')}"),
                node_type=NodeType.ARRAY_ELEMENT,
                display_text=settlement.get('name', 'Unknown Settlement'),
                icon='settlement',
            )

            for key, value in settlement.items():
                settlement_node.add_child(create_field_node(
                    name=key,
                    value=value,
                    formatted_value=str(value),
                    offset=0,
                    size=4,
                ))

            settlements_node.add_child(settlement_node)

        category.add_child(settlements_node)

        # Add Comm Stations
        comms_node = create_array_node(
            name='Comm Stations',
            element_type='MessageModule',
            address=0,
            count=len(data['comm_stations']),
        )

        for station in data['comm_stations']:
            station_node = TreeNode(
                name=f"Message {station.get('index', '?')}",
                node_type=NodeType.ARRAY_ELEMENT,
                display_text=station.get('message', 'Message')[:50],
                icon='message',
            )

            for key, value in station.items():
                station_node.add_child(create_field_node(
                    name=key,
                    value=value,
                    formatted_value=str(value),
                    offset=0,
                    size=4,
                ))

            comms_node.add_child(station_node)

        category.add_child(comms_node)

        return category
