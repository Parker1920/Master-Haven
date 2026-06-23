"""
Config loaded from environment variables.

Why a tiny dataclass instead of pydantic-settings:
- Keeps the dependency surface small for Phase 1.
- All values are strings or simple booleans — no validation gymnastics.
- The Pi-side .env is loaded by Docker, not Python. We just read
  os.environ.

Edit-friendly notes for a junior dev:
- Add a new setting: add a field to `Settings`, set its default in
  `_load()`, expose it via env var in docker-compose.yml + .env.example.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    # 'dev' or 'production'
    env: str

    # Absolute path to the SQLite DB file
    database_path: str

    # Absolute path to the media folder (uploaded images, etc.)
    media_path: str

    # Signed-cookie secret. Generated random in dev if not provided so
    # local devs aren't forced to set it.
    session_secret: str

    # Public hostname (without scheme) — e.g. "archive.havenmap.online".
    # When set, the session cookie's Domain is constrained to this host;
    # when empty (dev), the cookie is host-only.
    public_host: str

    # -- Discord OAuth (Phase 7) --------------------------------------
    discord_client_id: str
    discord_client_secret: str
    discord_redirect_uri: str
    discord_bot_token: str
    discord_vh_guild_id: str
    discord_archivist_guild_id: str

    # Username that is allowed to be auto-promoted to admin on first
    # claim (closes the public race condition in auth_claim).
    admin_username: str

    # -- Haven atlas sync ---------------------------------------------
    # Base URL of the main Haven control-room API. On the Pi the archive
    # container shares the docker_default network with Haven, so the
    # internal service name resolves: http://haven:8005. For local dev
    # against prod data, set HAVEN_API_BASE=https://havenmap.online.
    haven_api_base: str
    # Master switch for the background sync job + scheduler.
    haven_sync_enabled: bool
    # How often (minutes) the scheduler pulls fresh atlas figures.
    haven_sync_interval_min: int

    @property
    def is_dev(self) -> bool:
        return self.env.lower() == "dev"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


def _load() -> Settings:
    env = os.environ.get("ENV", "dev")

    session_secret = os.environ.get("SESSION_SECRET", "").strip()
    if not session_secret:
        if env.lower() == "production":
            raise RuntimeError(
                "SESSION_SECRET must be set in production. Add it to .env."
            )
        # Random per-process secret — fine for dev. Sessions invalidate
        # on each container restart, which is expected in dev.
        session_secret = secrets.token_urlsafe(32)

    return Settings(
        env=env,
        database_path=os.environ.get("DATABASE_PATH", "/data/archive.db"),
        media_path=os.environ.get("MEDIA_PATH", "/data/media"),
        session_secret=session_secret,
        public_host=os.environ.get("PUBLIC_HOST", "").strip(),
        discord_client_id=os.environ.get("DISCORD_CLIENT_ID", ""),
        discord_client_secret=os.environ.get("DISCORD_CLIENT_SECRET", ""),
        discord_redirect_uri=os.environ.get("DISCORD_REDIRECT_URI", ""),
        discord_bot_token=os.environ.get("DISCORD_BOT_TOKEN", ""),
        discord_vh_guild_id=os.environ.get("DISCORD_VH_GUILD_ID", ""),
        discord_archivist_guild_id=os.environ.get("DISCORD_ARCHIVIST_GUILD_ID", ""),
        admin_username=os.environ.get("ADMIN_USERNAME", "ekimo").strip().lower(),
        haven_api_base=os.environ.get("HAVEN_API_BASE", "http://haven:8005").strip().rstrip("/"),
        haven_sync_enabled=os.environ.get("HAVEN_SYNC_ENABLED", "1").strip().lower()
        in ("1", "true", "yes", "on"),
        haven_sync_interval_min=int(os.environ.get("HAVEN_SYNC_INTERVAL_MIN", "30") or "30"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached accessor — call from anywhere in the app to get the same
    Settings instance. lru_cache makes this effectively a singleton.
    """
    return _load()
