"""Service layer — cross-cutting logic that isn't a single route.

`haven_sync` is the live bridge to the main Haven control-room API: it
pulls per-community atlas figures and caches them locally so the archive
can show "live from the atlas" stats without coupling to Haven's DB.
"""
