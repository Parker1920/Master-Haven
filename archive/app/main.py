"""
Travelers Archive — FastAPI entrypoint.

Phase 1 surface:
- GET /health — liveness probe, returns version + env
- Every route module from app/routes/ is mounted, but most are empty
  stubs in Phase 1. They get fleshed out in Phases 2-4.

Edit-friendly notes:
- To add a new resource (e.g. "tags"), create app/routes/tags.py with
  a `router = APIRouter(prefix="/api/v1/tags", tags=["tags"])` and
  add `app.include_router(routes.tags.router)` below.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__, auth_claim, auth_dev
from .config import get_settings
from .routes import (
    admin,
    auth,
    civilizations,
    comments,
    drafts,
    events,
    inquisitions,
    media,
    notifications,
    people,
    places,
    search,
    stories,
    timeline,
    watchlist,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("archive")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Travelers Archive",
        version=__version__,
        description=(
            "A No Man's Sky community archive: news room, civilizations "
            "encyclopedia, inquisitions, and collaborative drafting."
        ),
        # Auto-docs are nice for dev; we'll consider gating in prod later.
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    # ---- health ------------------------------------------------------
    @app.get("/health", tags=["meta"])
    def health() -> JSONResponse:
        """Liveness probe. Returns 200 once the app object is up."""
        return JSONResponse(
            {
                "status": "ok",
                "version": __version__,
                "env": settings.env,
            }
        )

    # ---- routes ------------------------------------------------------
    # Each module exposes a `router` (APIRouter).
    for module in (
        auth,
        admin,
        civilizations,
        comments,
        drafts,
        events,
        inquisitions,
        media,
        notifications,
        people,
        places,
        search,
        stories,
        timeline,
        watchlist,
    ):
        app.include_router(module.router)

    # Dev-only fake login. The endpoints inside this router self-gate
    # via _ensure_dev_mode() so attempting to hit them in production
    # returns 404. We still mount the router in prod so the OpenAPI
    # doc is consistent across environments.
    app.include_router(auth_dev.router)

    # Claim-based login (v0.6+). Works in both dev and production.
    app.include_router(auth_claim.router)

    # ---- frontend SPA (Phase 5) -------------------------------------
    # The built Vite frontend lives at /app/frontend_dist (per the
    # Dockerfile). We mount it AFTER all /api routes so the API wins.
    # The fallback handler below serves index.html for any non-/api,
    # non-asset path so the hash router (#/civs, #/draft/3, ...) works
    # on direct browser hits even though we don't use path-based
    # routing.
    dist_dir = Path("/app/frontend_dist")
    if dist_dir.exists():
        # /assets/* are versioned files emitted by `vite build`
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        index_html = dist_dir / "index.html"

        @app.get("/", include_in_schema=False)
        def spa_root() -> Response:
            return FileResponse(str(index_html))

        @app.get("/{path:path}", include_in_schema=False)
        def spa_fallback(request: Request, path: str) -> Response:
            """
            Catch-all: serve index.html for non-API routes so the hash
            router can do its thing. API + assets are already matched
            by earlier routes, so this only fires for things like
            /favicon.ico or random typed paths.
            """
            # First, try a literal file in dist (favicon, manifest, etc.)
            candidate = dist_dir / path
            if candidate.is_file():
                return FileResponse(str(candidate))
            # Fallback: serve the SPA shell
            return FileResponse(str(index_html))
        log.info("serving SPA from %s", dist_dir)
    else:
        log.warning("frontend dist not found at %s — backend only", dist_dir)

    log.info(
        "archive %s up — env=%s db=%s media=%s",
        __version__,
        settings.env,
        settings.database_path,
        settings.media_path,
    )

    return app


app = create_app()
