"""Password-protected admin: review inquiries + payments.

Login sets an httpOnly session cookie; every data endpoint requires it.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import config
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
from ..services.invoices import create_invoice, record_paid_invoice

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


class HandledRequest(BaseModel):
    handled: bool


class ProductRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    price: float = Field(..., ge=0)          # dollars from the admin form
    image_url: str | None = Field(default=None, max_length=500)
    active: bool = True
    requires_shipping: bool = True
    sort_order: int = 0


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
    inquiries = [dict(r) for r in rows]

    # Attach the invoice(s) each inquiry produced, and derive a pipeline stage so
    # the admin can read one lead end to end: New -> Invoiced -> Paid.
    inv_rows = conn.execute(
        """SELECT id, inquiry_id, number, amount_cents, currency, description, status,
                  provider, hosted_invoice_url, receipt_url, pdf_url, paid_at, created_at
           FROM invoices WHERE inquiry_id IS NOT NULL ORDER BY created_at ASC"""
    ).fetchall()
    by_inq: dict[int, list] = {}
    for iv in inv_rows:
        by_inq.setdefault(iv["inquiry_id"], []).append(dict(iv))

    for q in inquiries:
        linked = by_inq.get(q["id"], [])
        q["invoices"] = linked
        if any(x["status"] == "paid" for x in linked):
            q["stage"] = "paid"
        elif any(x["status"] == "open" for x in linked):
            q["stage"] = "invoiced"
        else:
            q["stage"] = "new"
    return inquiries


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
    products = conn.execute("SELECT COUNT(*) AS n FROM products WHERE active = 1").fetchone()["n"]
    orders = conn.execute("SELECT COUNT(*) AS n FROM orders WHERE fulfilled = 0").fetchone()["n"]
    open_inv = conn.execute("SELECT COUNT(*) AS n FROM invoices WHERE status = 'open'").fetchone()["n"]
    return {"inquiries": inq, "new_inquiries": new_inq, "payments_paid": paid,
            "active_products": products, "unfulfilled_orders": orders, "open_invoices": open_inv}


# --------------------------------------------------------------------------- #
# Products / merch (admin-managed)
# --------------------------------------------------------------------------- #
@router.get("/admin/products")
def list_admin_products(_: None = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM products ORDER BY sort_order, id").fetchall()
    return [dict(r) for r in rows]


@router.post("/admin/products")
def create_product(
    req: ProductRequest,
    _: None = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
):
    cur = conn.execute(
        """INSERT INTO products (name, description, price_cents, image_url, active, requires_shipping, sort_order)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (req.name, req.description, int(round(req.price * 100)), req.image_url,
         1 if req.active else 0, 1 if req.requires_shipping else 0, req.sort_order),
    )
    return {"ok": True, "id": cur.lastrowid}


@router.put("/admin/products/{product_id}")
def update_product(
    product_id: int,
    req: ProductRequest,
    _: None = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
):
    cur = conn.execute(
        """UPDATE products SET name = ?, description = ?, price_cents = ?, image_url = ?,
                  active = ?, requires_shipping = ?, sort_order = ? WHERE id = ?""",
        (req.name, req.description, int(round(req.price * 100)), req.image_url,
         1 if req.active else 0, 1 if req.requires_shipping else 0, req.sort_order, product_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Product not found.")
    return {"ok": True}


@router.delete("/admin/products/{product_id}")
def delete_product(
    product_id: int,
    _: None = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
):
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Orders (merch fulfillment)
# --------------------------------------------------------------------------- #
class FulfilledRequest(BaseModel):
    fulfilled: bool


@router.get("/admin/orders")
def list_orders(_: None = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


@router.patch("/admin/orders/{order_id}")
def set_order_fulfilled(
    order_id: int, req: FulfilledRequest,
    _: None = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db),
):
    cur = conn.execute("UPDATE orders SET fulfilled = ? WHERE id = ?", (1 if req.fulfilled else 0, order_id))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Order not found.")
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Invoices (Option C — Stripe Invoicing in live mode)
# --------------------------------------------------------------------------- #
class InvoiceRequest(BaseModel):
    customer_name: str | None = Field(default=None, max_length=140)
    customer_email: str = Field(..., min_length=3, max_length=254)
    description: str | None = Field(default=None, max_length=1000)
    amount: float = Field(..., gt=0)
    inquiry_id: int | None = None          # link this invoice to the lead it came from


class RecordPaidRequest(BaseModel):
    customer_name: str | None = Field(default=None, max_length=140)
    customer_email: str = Field(..., min_length=3, max_length=254)
    description: str | None = Field(default=None, max_length=1000)
    amount: float = Field(..., gt=0)
    inquiry_id: int | None = None
    receipt_url: str | None = Field(default=None, max_length=500)
    paid_at: str | None = None             # ISO datetime; defaults to now


@router.get("/admin/invoices")
def list_invoices(_: None = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        """SELECT i.*, q.name AS inquiry_name, q.email AS inquiry_email
           FROM invoices i LEFT JOIN inquiries q ON q.id = i.inquiry_id
           ORDER BY i.created_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/admin/invoices")
def create_invoice_endpoint(
    req: InvoiceRequest, _: None = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db),
):
    inv = create_invoice(
        conn, customer_name=req.customer_name, customer_email=req.customer_email.strip(),
        description=req.description, amount_cents=int(round(req.amount * 100)),
        inquiry_id=req.inquiry_id,
    )
    return {"ok": True, "invoice": inv}


@router.post("/admin/invoices/record-paid")
def record_paid_invoice_endpoint(
    req: RecordPaidRequest, _: None = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db),
):
    """Record a sale that was already paid outside the site (no Stripe email/charge)."""
    inv = record_paid_invoice(
        conn, customer_name=req.customer_name, customer_email=req.customer_email.strip(),
        description=req.description, amount_cents=int(round(req.amount * 100)),
        inquiry_id=req.inquiry_id, receipt_url=req.receipt_url, paid_at=req.paid_at,
    )
    return {"ok": True, "invoice": inv}


@router.post("/admin/invoices/{invoice_id}/mark-paid")
def mark_invoice_paid(invoice_id: int, _: None = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if row["status"] == "paid":
        return {"ok": True}
    if row["provider"] == "stripe":
        # Record an externally-paid Stripe invoice as paid-out-of-band so our copy
        # matches Stripe's ledger (used when a client paid by other means).
        if not (row["stripe_invoice_id"] and config.STRIPE_SECRET_KEY):
            raise HTTPException(status_code=400, detail="Stripe isn't configured to mark this paid.")
        try:
            import stripe  # noqa: WPS433
            stripe.api_key = config.STRIPE_SECRET_KEY
            stripe.Invoice.pay(row["stripe_invoice_id"], paid_out_of_band=True)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Stripe mark-paid failed: {exc}") from exc
    conn.execute("UPDATE invoices SET status = 'paid', paid_at = datetime('now') WHERE id = ?", (invoice_id,))
    return {"ok": True}


@router.post("/admin/invoices/{invoice_id}/void")
def void_invoice(invoice_id: int, _: None = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if row["provider"] == "stripe" and row["stripe_invoice_id"] and config.STRIPE_SECRET_KEY:
        try:
            import stripe  # noqa: WPS433
            stripe.api_key = config.STRIPE_SECRET_KEY
            stripe.Invoice.void_invoice(row["stripe_invoice_id"])
        except Exception:  # noqa: BLE001 - best-effort; still void locally
            pass
    conn.execute("UPDATE invoices SET status = 'void' WHERE id = ?", (invoice_id,))
    return {"ok": True}
