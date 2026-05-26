"""Public, read-only endpoints + the civ submission entry point's siblings."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..db import UPLOAD_DIR, get_db
from ..serialize import civ_public

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/civs")
def list_civs(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT * FROM civilizations WHERE approval_state = 'approved' "
        "ORDER BY display_order ASC, created_at ASC"
    ).fetchall()
    return [civ_public(r) for r in rows]


@router.get("/civs/{civ_id}")
def get_civ(civ_id: int, conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute(
        "SELECT * FROM civilizations WHERE id = ? AND approval_state = 'approved'",
        (civ_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Civilization not found.")
    return civ_public(row)


@router.get("/uploads/{filename}")
def get_upload(filename: str):
    # Reject anything that could escape the uploads directory.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="Not found.")
    upload_root = UPLOAD_DIR.resolve()
    path = (upload_root / filename).resolve()
    if path.parent != upload_root or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found.")
    return FileResponse(
        path,
        headers={"Cache-Control": "public, max-age=86400"},
    )
