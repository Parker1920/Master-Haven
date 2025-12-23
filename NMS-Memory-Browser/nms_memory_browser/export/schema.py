"""JSON schema definitions for memory snapshots.

Defines the structure of exported JSON files.
"""

# Schema version
SNAPSHOT_VERSION = "1.0.0"

# Full schema definition
SNAPSHOT_SCHEMA = {
    'version': SNAPSHOT_VERSION,
    'description': 'NMS Memory Browser snapshot format',

    'metadata': {
        'type': 'object',
        'properties': {
            'timestamp': {'type': 'string', 'format': 'date-time'},
            'game_version': {'type': 'string'},
            'extractor_version': {'type': 'string'},
            'galaxy_name': {'type': 'string'},
            'glyph_code': {'type': 'string'},
            'player_name': {'type': 'string'},
            'system_name': {'type': 'string'},
            'connected': {'type': 'boolean'},
        },
    },

    'known_structures': {
        'type': 'object',
        'properties': {
            'player': {'type': 'object'},
            'solar_system': {'type': 'object'},
            'multiplayer': {'type': 'object'},
            'simulation': {'type': 'object'},
        },
    },

    'struct_snapshot': {
        'type': 'object',
        'properties': {
            '__type__': {'type': 'string', 'description': 'Struct type name'},
            '__address__': {'type': 'string', 'description': 'Memory address (hex)'},
            '__size__': {'type': 'integer', 'description': 'Struct size in bytes'},
            'fields': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'object',
                    'properties': {
                        'offset': {'type': 'string'},
                        'size': {'type': 'integer'},
                        'type': {'type': 'string'},
                        'value': {'type': 'string'},
                        'raw': {'type': 'string'},
                    },
                },
            },
            'raw_hex': {'type': 'string', 'description': 'Full struct hex dump'},
            'valid': {'type': 'boolean'},
            'error': {'type': 'string'},
        },
    },

    'unknown_region': {
        'type': 'object',
        'properties': {
            'address': {'type': 'string', 'description': 'Memory address (hex)'},
            'size': {'type': 'integer', 'description': 'Region size in bytes'},
            'context': {'type': 'string', 'description': 'Location context'},
            'inferred_types': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'offset': {'type': 'integer'},
                        'type': {'type': 'string'},
                        'value': {},
                        'confidence': {'type': 'number'},
                        'size': {'type': 'integer'},
                    },
                },
            },
            'hex_dump': {'type': 'string'},
        },
    },

    'multiplayer': {
        'type': 'object',
        'properties': {
            'session_info': {
                'type': 'object',
                'properties': {
                    'multiplayer_active': {'type': 'boolean'},
                    'player_count': {'type': 'integer'},
                },
            },
            'other_players': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'index': {'type': 'integer'},
                        'name': {'type': 'string'},
                        'platform': {'type': 'string'},
                    },
                },
            },
            'player_bases': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'index': {'type': 'integer'},
                        'name': {'type': 'string'},
                        'base_type': {'type': 'integer'},
                        'position': {'type': 'object'},
                    },
                },
            },
            'settlements': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'index': {'type': 'integer'},
                        'name': {'type': 'string'},
                        'population': {'type': 'integer'},
                        'happiness': {'type': 'number'},
                        'productivity': {'type': 'number'},
                    },
                },
            },
            'comm_stations': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'index': {'type': 'integer'},
                        'message': {'type': 'string'},
                        'author': {'type': 'string'},
                    },
                },
            },
        },
    },
}


# Example output structure
EXAMPLE_SNAPSHOT = {
    'version': '1.0.0',
    'metadata': {
        'timestamp': '2025-12-22T12:00:00',
        'game_version': '4.13',
        'extractor_version': '1.0.0',
        'galaxy_name': 'Euclid',
        'glyph_code': '0123456789AB',
        'player_name': 'Traveller',
        'system_name': 'Example System',
        'connected': True,
    },
    'known_structures': {
        'player': {
            'player_state': {
                '__type__': 'cGcPlayerState',
                '__address__': '0x7FF123456000',
                '__size__': 50000,
                'fields': {
                    'miShield': {
                        'offset': '0x1B0',
                        'size': 4,
                        'type': 'int',
                        'value': '100',
                    },
                },
            },
        },
        'solar_system': {},
        'multiplayer': {
            'session_info': {'multiplayer_active': False},
            'other_players': [],
            'player_bases': [],
            'settlements': [],
            'comm_stations': [],
        },
    },
    'unknown_regions': [
        {
            'address': '0x7FF123456100',
            'size': 64,
            'context': 'Gap in cGcPlayerState after miHealth',
            'inferred_types': [
                {'offset': 0, 'type': 'float32', 'value': 1.5, 'confidence': 0.75},
            ],
            'hex_dump': '00 00 C0 3F 00 00 00 00...',
        },
    ],
    'stats': {
        'total_structs_read': 15,
        'total_bytes_read': 250000,
    },
}
