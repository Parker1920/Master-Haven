"""Grand Festival / Summer Unification Day — FastAPI entry point.

Serves the JSON API under /api and the built React SPA at /. A single
container runs both; Vite's dev server (port 5173) proxies /api here in dev.
"""

import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .routes import admin, public, schedule, submit

# Some platforms don't know .webp — register it so logos serve with the right type.
mimetypes.add_type("image/webp", ".webp")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Grand Festival API", version="1.0.0", lifespan=lifespan)


# ---- API ---------------------------------------------------------------------
app.include_router(public.router, prefix="/api", tags=["public"])
app.include_router(submit.router, prefix="/api", tags=["submit"])
app.include_router(schedule.router, prefix="/api", tags=["schedule"])
app.include_router(admin.router, prefix="/api", tags=["admin"])


# ---- Frontend SPA ------------------------------------------------------------
# Vite emits index.html + assets/ into frontend/dist. Mount the assets dir and
# fall back to index.html for any other path so client-side routes (/admin,
# /whos-going/submit, ...) survive a hard refresh.
if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not found.")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
