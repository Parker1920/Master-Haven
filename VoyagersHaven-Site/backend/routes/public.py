"""Public, read-only endpoints: health, status, and browser-safe config."""

from fastapi import APIRouter

from ..config import APP_NAME, APP_VERSION, public_config

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/status")
def status():
    # Mirrors the Haven convention of a name+version status probe.
    return {"name": APP_NAME, "version": APP_VERSION}


@router.get("/config")
def config():
    return public_config()
