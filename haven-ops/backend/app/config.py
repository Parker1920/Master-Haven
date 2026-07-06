"""Central configuration — every path derives from DATA_DIR.

DATA_DIR is /data inside the container (docker-compose sets it); for bare
local dev it defaults to ~/docker/haven-ops-data, mirroring the Pi layout.
The data dir holds the DB (+WAL sidecars), generated documents, the
e-signature image, and the real .env — none of which ever enter the repo.

Env overrides (case-insensitive): DATA_DIR, DB_PATH, UPLOAD_DIR,
SIGNATURE_PATH, STATIC_DIR, PORT.
"""
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Path.home() / "docker" / "haven-ops-data"
    port: int = 8090

    # Shared secret for machine-to-machine hooks (/api/hooks/*) from the
    # voyagershaven.online backend. Empty = hooks disabled (503). Set via
    # OPS_SERVICE_TOKEN env; the site sets the same value in HAVEN_OPS_TOKEN.
    ops_service_token: str = ""

    # Derived from data_dir unless explicitly overridden via env.
    db_path: Path | None = None
    upload_dir: Path | None = None
    signature_path: Path | None = None

    # The built frontend. /app/static in the Docker image.
    static_dir: Path = Path(__file__).resolve().parent.parent / "static"

    @model_validator(mode="after")
    def _derive_paths(self) -> "Settings":
        if self.db_path is None:
            self.db_path = self.data_dir / "haven-ops.db"
        if self.upload_dir is None:
            self.upload_dir = self.data_dir / "uploads" / "generated"
        if self.signature_path is None:
            self.signature_path = self.data_dir / "signature.png"
        return self


settings = Settings()
