"""Public civ submission — multipart form with an optional logo.

New submissions land as `pending` and never appear on the public site until an
admin approves them.
"""

import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..db import UPLOAD_DIR, get_db
from ..images import ImageError, process_logo, slugify

router = APIRouter()

ALLOWED_STATUS = {"host", "confirmed", "tentative"}
MAX_NAME = 120
MAX_ROLE = 120
MAX_DESC = 2000
MAX_DISCORD = 100
MAX_NOTES = 2000


@router.post("/civs/submit")
async def submit_civ(
    name: str = Form(...),
    role: str = Form(...),
    description: str = Form(...),
    status: str = Form("tentative"),
    submitter_discord: str | None = Form(None),
    submitter_notes: str | None = Form(None),
    logo: UploadFile | None = File(None),
    conn: sqlite3.Connection = Depends(get_db),
):
    name = (name or "").strip()
    role = (role or "").strip()
    description = (description or "").strip()
    status = (status or "tentative").strip().lower()
    submitter_discord = ((submitter_discord or "").strip()) or None
    submitter_notes = ((submitter_notes or "").strip()) or None

    if not name or not role or not description:
        raise HTTPException(status_code=400, detail="Name, role, and description are required.")
    if status not in ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail="Invalid status.")
    if len(name) > MAX_NAME or len(role) > MAX_ROLE or len(description) > MAX_DESC:
        raise HTTPException(status_code=400, detail="One or more fields exceed the maximum length.")
    if submitter_discord and len(submitter_discord) > MAX_DISCORD:
        raise HTTPException(status_code=400, detail="Discord handle is too long.")
    if submitter_notes and len(submitter_notes) > MAX_NOTES:
        raise HTTPException(status_code=400, detail="Notes are too long.")

    # Validate + normalize the image BEFORE inserting, so a rejected upload
    # never leaves an orphan pending row behind.
    processed_logo: bytes | None = None
    if logo is not None and (logo.filename or "").strip():
        raw = await logo.read()
        try:
            processed_logo = process_logo(raw, logo.content_type)
        except ImageError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    cur = conn.execute(
        "INSERT INTO civilizations "
        "(name, role, description, status, submitter_discord, submitter_notes, approval_state) "
        "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
        (name, role, description, status, submitter_discord, submitter_notes),
    )
    civ_id = cur.lastrowid

    if processed_logo is not None:
        filename = f"{civ_id}-{slugify(name)}.webp"
        (UPLOAD_DIR / filename).write_bytes(processed_logo)
        conn.execute(
            "UPDATE civilizations SET logo_filename = ? WHERE id = ?",
            (filename, civ_id),
        )

    return {
        "ok": True,
        "id": civ_id,
        "message": "Submission received — it will appear once an organizer approves it.",
    }
