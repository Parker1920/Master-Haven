"""Client invoices — Option C (hybrid).

Live mode: drives **Stripe Invoicing** — creates a Customer + Invoice Item +
Invoice, finalizes and emails it. Stripe auto-numbers, hosts the pay page,
generates the PDF, sends reminders, and reports status back via webhook.

Simulated mode: a local-only record with a VH-YYYY-NNN number so the admin
create/list/track flow is fully iterable without a Stripe account.
"""

import sqlite3

from fastapi import HTTPException

from .. import config


def _invoice_dict(conn: sqlite3.Connection, invoice_id: int) -> dict:
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    return dict(row) if row else {}


def _next_local_number(conn: sqlite3.Connection) -> str:
    year = conn.execute("SELECT strftime('%Y','now') AS y").fetchone()["y"]
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM invoices WHERE number LIKE ?", (f"VH-{year}-%",)
    ).fetchone()["c"]
    return f"VH-{year}-{n + 1:03d}"


def create_invoice(conn, *, customer_name, customer_email, description, amount_cents, inquiry_id=None) -> dict:
    if config.STRIPE_MODE == "live":
        return _create_stripe_invoice(conn, customer_name, customer_email, description, amount_cents, inquiry_id)

    number = _next_local_number(conn)
    cur = conn.execute(
        """INSERT INTO invoices
             (number, customer_name, customer_email, description, amount_cents, currency, status, provider, inquiry_id)
           VALUES (?, ?, ?, ?, ?, ?, 'open', 'simulated', ?)""",
        (number, customer_name, customer_email, description, amount_cents, config.CURRENCY, inquiry_id),
    )
    return _invoice_dict(conn, cur.lastrowid)


def record_paid_invoice(conn, *, customer_name, customer_email, description, amount_cents,
                        inquiry_id=None, receipt_url=None, paid_at=None) -> dict:
    """Record an ALREADY-paid sale (paid outside the site — e.g. a past deal).
    No Stripe call, no email: just a local `manual` invoice marked paid, so it
    shows in the pipeline (inquiry -> invoice -> receipt) as a completed record."""
    number = _next_local_number(conn)
    cur = conn.execute(
        """INSERT INTO invoices
             (number, customer_name, customer_email, description, amount_cents, currency,
              status, provider, inquiry_id, receipt_url, paid_at)
           VALUES (?, ?, ?, ?, ?, ?, 'paid', 'manual', ?, ?, COALESCE(?, datetime('now')))""",
        (number, customer_name, customer_email, description, amount_cents, config.CURRENCY,
         inquiry_id, receipt_url, paid_at),
    )
    return _invoice_dict(conn, cur.lastrowid)


def _create_stripe_invoice(conn, name, email, description, amount_cents, inquiry_id=None) -> dict:
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is enabled but not configured.")
    try:
        import stripe  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail="Stripe library is not installed.") from exc

    stripe.api_key = config.STRIPE_SECRET_KEY
    try:
        customer = stripe.Customer.create(name=name or None, email=email)
        # Create the invoice FIRST, then attach the line item to it explicitly via
        # invoice=<id>. Recent Stripe API versions no longer auto-pull pending invoice
        # items into a newly-created invoice, so the old "create item, then invoice"
        # order produced an EMPTY $0 invoice that auto-finalized as paid and never
        # emailed the customer. auto_advance=False so Stripe doesn't finalize the empty
        # shell before we attach the amount.
        invoice = stripe.Invoice.create(
            customer=customer.id, collection_method="send_invoice", days_until_due=14,
            description=description or None, auto_advance=False,
        )
        stripe.InvoiceItem.create(
            customer=customer.id, invoice=invoice.id, amount=amount_cents,
            currency=config.CURRENCY, description=description or "Services",
        )
        invoice = stripe.Invoice.finalize_invoice(invoice.id)
        if invoice.amount_due <= 0:
            raise HTTPException(status_code=400, detail="Invoice finalized with a $0 total — the line item did not attach.")
        try:
            stripe.Invoice.send_invoice(invoice.id)
        except Exception:  # noqa: BLE001 - finalized + payable via hosted URL even if the email send hiccups
            pass
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Stripe invoice error: {exc}") from exc

    cur = conn.execute(
        """INSERT INTO invoices
             (number, stripe_invoice_id, customer_name, customer_email, description,
              amount_cents, currency, status, hosted_invoice_url, pdf_url, provider, inquiry_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, 'stripe', ?)""",
        (invoice.number, invoice.id, name, email, description, amount_cents,
         config.CURRENCY, invoice.hosted_invoice_url, invoice.invoice_pdf, inquiry_id),
    )
    return _invoice_dict(conn, cur.lastrowid)
