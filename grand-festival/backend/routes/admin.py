"""Auth-gated admin endpoints: login/logout, review queue, edit, delete, audit."""

import hashlib
import sqlite3

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile

from ..auth import (
    COOKIE_NAME,
    clear_session_cookie,
    create_session,
    destroy_session,
    require_admin,
    set_session_cookie,
    verify_password,
)
from ..db import UPLOAD_DIR, get_db
from ..images import ImageError, process_logo, slugify
from ..models import AdminLogin, CivPatch, RejectBody
from ..serialize import civ_admin

router = APIRouter()

ALLOWED_STATUS = {"host", "confirmed", "tentative"}
ALLOWED_APPROVAL = {"pending", "approved", "rejected"}


def _log(conn: sqlite3.Connection, action: str, target_id: int | None, notes: str | None = None) -> None:
    conn.execute(
        "INSERT INTO admin_log (action, target_id, target_type, notes) "
        "VALUES (?, ?, 'civilization', ?)",
        (action, target_id, notes),
    )


def _get_civ_or_404(conn: sqlite3.Connection, civ_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM civilizations WHERE id = ?", (civ_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Civilization not found.")
    return row


# ---- Auth --------------------------------------------------------------------

@router.post("/admin/login")
def login(body: AdminLogin, response: Response):
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    token = create_session()
    set_session_cookie(response, token)
    return {"ok": True}


@router.post("/admin/logout")
def logout(request: Request, response: Response):
    destroy_session(request.cookies.get(COOKIE_NAME))
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/admin/me", dependencies=[Depends(require_admin)])
def me():
    return {"authenticated": True}


# ---- Review queue ------------------------------------------------------------

@router.get("/admin/civs", dependencies=[Depends(require_admin)])
def admin_list(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT * FROM civilizations "
        "ORDER BY (approval_state = 'pending') DESC, display_order ASC, created_at DESC"
    ).fetchall()
    pending_count = conn.execute(
        "SELECT COUNT(*) AS c FROM civilizations WHERE approval_state = 'pending'"
    ).fetchone()["c"]
    return {"civs": [civ_admin(r) for r in rows], "pending_count": pending_count}


@router.get("/admin/civs/pending", dependencies=[Depends(require_admin)])
def admin_pending(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT * FROM civilizations WHERE approval_state = 'pending' "
        "ORDER BY created_at ASC"
    ).fetchall()
    return {"civs": [civ_admin(r) for r in rows]}


@router.post("/admin/civs/{civ_id}/approve", dependencies=[Depends(require_admin)])
def approve(civ_id: int, conn: sqlite3.Connection = Depends(get_db)):
    _get_civ_or_404(conn, civ_id)
    conn.execute(
        "UPDATE civilizations SET approval_state = 'approved', approved_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (civ_id,),
    )
    _log(conn, "approved", civ_id)
    return {"ok": True}


@router.post("/admin/civs/{civ_id}/reject", dependencies=[Depends(require_admin)])
def reject(civ_id: int, body: RejectBody | None = None, conn: sqlite3.Connection = Depends(get_db)):
    _get_civ_or_404(conn, civ_id)
    notes = (body.notes if body else None) or None
    conn.execute(
        "UPDATE civilizations SET approval_state = 'rejected' WHERE id = ?",
        (civ_id,),
    )
    _log(conn, "rejected", civ_id, notes)
    return {"ok": True}


@router.patch("/admin/civs/{civ_id}", dependencies=[Depends(require_admin)])
def edit(civ_id: int, body: CivPatch, conn: sqlite3.Connection = Depends(get_db)):
    _get_civ_or_404(conn, civ_id)

    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    if "status" in fields and fields["status"] not in ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail="Invalid status.")
    if "approval_state" in fields and fields["approval_state"] not in ALLOWED_APPROVAL:
        raise HTTPException(status_code=400, detail="Invalid approval state.")

    columns = ["name", "role", "description", "status", "display_order", "approval_state"]
    sets = [f"{c} = ?" for c in columns if c in fields]
    values = [fields[c] for c in columns if c in fields]
    if not sets:
        raise HTTPException(status_code=400, detail="No editable fields to update.")
    # Keep approved_at in sync when an edit flips approval to approved.
    if fields.get("approval_state") == "approved":
        sets.append("approved_at = CURRENT_TIMESTAMP")

    values.append(civ_id)
    conn.execute(f"UPDATE civilizations SET {', '.join(sets)} WHERE id = ?", values)
    _log(conn, "edited", civ_id, ", ".join(f"{c}={fields[c]!r}" for c in columns if c in fields))

    row = _get_civ_or_404(conn, civ_id)
    return civ_admin(row)


@router.delete("/admin/civs/{civ_id}", dependencies=[Depends(require_admin)])
def delete(civ_id: int, conn: sqlite3.Connection = Depends(get_db)):
    row = _get_civ_or_404(conn, civ_id)
    logo = row["logo_filename"]
    conn.execute("DELETE FROM civilizations WHERE id = ?", (civ_id,))
    if logo:
        try:
            (UPLOAD_DIR / logo).unlink(missing_ok=True)
        except OSError:
            pass
    _log(conn, "deleted", civ_id, f"name={row['name']!r}")
    return {"ok": True}


# ---- Emblem / logo -----------------------------------------------------------

@router.post("/admin/civs/{civ_id}/logo", dependencies=[Depends(require_admin)])
async def set_logo(
    civ_id: int,
    logo: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
):
    row = _get_civ_or_404(conn, civ_id)
    raw = await logo.read()
    try:
        processed = process_logo(raw, logo.content_type)
    except ImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Content-hashed filename so a replacement gets a fresh URL (no stale cache).
    digest = hashlib.sha1(processed).hexdigest()[:8]
    filename = f"{civ_id}-{slugify(row['name'])}-{digest}.webp"
    (UPLOAD_DIR / filename).write_bytes(processed)

    old = row["logo_filename"]
    if old and old != filename:
        try:
            (UPLOAD_DIR / old).unlink(missing_ok=True)
        except OSError:
            pass

    conn.execute("UPDATE civilizations SET logo_filename = ? WHERE id = ?", (filename, civ_id))
    _log(conn, "edited", civ_id, "emblem updated")
    return civ_admin(_get_civ_or_404(conn, civ_id))


@router.delete("/admin/civs/{civ_id}/logo", dependencies=[Depends(require_admin)])
def clear_logo(civ_id: int, conn: sqlite3.Connection = Depends(get_db)):
    row = _get_civ_or_404(conn, civ_id)
    old = row["logo_filename"]
    conn.execute("UPDATE civilizations SET logo_filename = NULL WHERE id = ?", (civ_id,))
    if old:
        try:
            (UPLOAD_DIR / old).unlink(missing_ok=True)
        except OSError:
            pass
    _log(conn, "edited", civ_id, "emblem removed")
    return {"ok": True}


# ---- Audit -------------------------------------------------------------------

@router.get("/admin/log", dependencies=[Depends(require_admin)])
def admin_log(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT id, action, target_id, target_type, notes, created_at "
        "FROM admin_log ORDER BY created_at DESC, id DESC LIMIT 100"
    ).fetchall()
    return {"log": [dict(r) for r in rows]}
