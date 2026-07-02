"""Password-protected admin: review inquiries + payments.

Login sets an httpOnly session cookie; every data endpoint requires it.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..auth import (
    COOKIE_NAME,
    clear_session_cookie,
    create_session,
    destroy_session,
    require_admin,
    set_session_cookie,
    verify_password,
)
from ..db import get_db

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


class HandledRequest(BaseModel):
    handled: bool


@router.post("/admin/login")
def login(req: LoginRequest, response: Response):
    if not verify_password(req.password):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    set_session_cookie(response, create_session())
    return {"ok": True}


@router.post("/admin/logout")
def logout(request: Request, response: Response):
    destroy_session(request.cookies.get(COOKIE_NAME))
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/admin/me")
def me(_: None = Depends(require_admin)):
    return {"ok": True}


@router.get("/admin/inquiries")
def list_inquiries(_: None = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        """SELECT id, name, email, project_type, budget, message, created_at, handled
           FROM inquiries ORDER BY created_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


@router.patch("/admin/inquiries/{inquiry_id}")
def set_inquiry_handled(
    inquiry_id: int,
    req: HandledRequest,
    _: None = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
):
    cur = conn.execute(
        "UPDATE inquiries SET handled = ? WHERE id = ?",
        (1 if req.handled else 0, inquiry_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    return {"ok": True, "handled": req.handled}


@router.get("/admin/payments")
def list_payments(_: None = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        """SELECT id, reference, kind, amount_cents, currency, invoice_number, email,
                  status, provider, created_at, paid_at
           FROM payments ORDER BY created_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/admin/summary")
def summary(_: None = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    inq = conn.execute("SELECT COUNT(*) AS n FROM inquiries").fetchone()["n"]
    new_inq = conn.execute("SELECT COUNT(*) AS n FROM inquiries WHERE handled = 0").fetchone()["n"]
    paid = conn.execute("SELECT COUNT(*) AS n FROM payments WHERE status = 'paid'").fetchone()["n"]
    return {"inquiries": inq, "new_inquiries": new_inq, "payments_paid": paid}
