"""Public "Pay an invoice" flow.

A client enters their invoice number; we look it up in our own `invoices` table
and return the (public-safe) details so the amount/description auto-populate —
they can't change the amount. Then:

  * live (Stripe invoice): the frontend redirects to the stored hosted invoice
    URL, where Stripe collects the card, marks the invoice paid, and emails a
    receipt. Our copy flips to paid via the invoice.paid webhook.
  * simulated (local dev): the frontend runs the mock card modal, then POSTs
    /invoices/pay-simulated which marks our record paid and returns a receipt.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..db import get_db
from ..ratelimit import check_rate_limit

router = APIRouter()


@router.get("/invoices/lookup")
def lookup_invoice(number: str, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    check_rate_limit(request, "invoice_lookup", limit=20, window_seconds=600)
    number = (number or "").strip()
    if not number:
        raise HTTPException(status_code=400, detail="Enter an invoice number.")
    row = conn.execute("SELECT * FROM invoices WHERE number = ? COLLATE NOCASE", (number,)).fetchone()
    if row is None:
        return {"found": False}
    return {
        "found": True,
        "number": row["number"],
        "customer_name": row["customer_name"],
        "amount_cents": row["amount_cents"],
        "currency": row["currency"],
        "description": row["description"],
        "status": row["status"],
        "provider": row["provider"],
        # only offer a pay link while the invoice is still open
        "hosted_invoice_url": row["hosted_invoice_url"] if row["status"] == "open" else None,
    }


@router.get("/invoices/receipt")
def invoice_receipt(number: str, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    """Public receipt for a PAID invoice — works for simulated, manual, and Stripe
    invoices alike, so every completed sale has a real, shareable receipt."""
    check_rate_limit(request, "invoice_receipt", limit=40, window_seconds=600)
    number = (number or "").strip()
    if not number:
        raise HTTPException(status_code=400, detail="Enter an invoice number.")
    row = conn.execute("SELECT * FROM invoices WHERE number = ? COLLATE NOCASE", (number,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    if row["status"] != "paid":
        raise HTTPException(status_code=400, detail="This invoice hasn't been paid yet.")
    return {
        "number": row["number"],
        "customer_name": row["customer_name"],
        "customer_email": row["customer_email"],
        "description": row["description"],
        "amount_cents": row["amount_cents"],
        "currency": row["currency"],
        "paid_at": row["paid_at"],
        "provider": row["provider"],
        "stripe_receipt_url": row["receipt_url"],
        "invoice_pdf": row["pdf_url"],
    }


class PayInvoiceRequest(BaseModel):
    number: str


@router.post("/invoices/pay-simulated")
def pay_invoice_simulated(req: PayInvoiceRequest, conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT * FROM invoices WHERE number = ? COLLATE NOCASE", (req.number.strip(),)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if row["provider"] != "simulated":
        raise HTTPException(status_code=400, detail="This invoice is paid through Stripe.")
    if row["status"] == "void":
        raise HTTPException(status_code=400, detail="This invoice has been voided.")
    if row["status"] != "paid":
        conn.execute("UPDATE invoices SET status = 'paid', paid_at = datetime('now') WHERE id = ?", (row["id"],))
        row = conn.execute("SELECT * FROM invoices WHERE id = ?", (row["id"],)).fetchone()
    return {
        "number": row["number"],
        "amount_cents": row["amount_cents"],
        "description": row["description"],
        "status": row["status"],
        "paid_at": row["paid_at"],
    }
