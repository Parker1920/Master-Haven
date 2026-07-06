"""Haven Ops — FastAPI entrypoint.

API routes are registered before the static mount, so /api/* (and the
auto docs at /docs) always win over the SPA bundle.

Startup runs migrate + seed: both are idempotent (migrations are tracked in
schema_version; seed only fills empty tables), so a clean `compose up` from
an empty data dir comes up fully migrated and seeded, and every later boot
is a no-op.
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from .auth import require_user
from .config import settings
from .migrate import run_migrations
from .routers import all_routers
from .seed import seed_if_empty


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_migrations()
    seed_if_empty()
    yield


app = FastAPI(title="Haven Ops", version="0.4.0", lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True}


# All data routes sit behind the auth seam (a Phase 1 no-op — the tailnet is
# the perimeter). When Discord-OAuth tiers land, require_user grows real
# checks and every router is already gated.
for router in all_routers:
    app.include_router(router, dependencies=[Depends(require_user)])


# Built frontend (Vite dist, copied to /app/static in the image). Guarded so
# the backend still boots in bare local dev before any frontend build exists.
if settings.static_dir.is_dir():
    app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")
