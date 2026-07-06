"""Support contributions + client invoice payments.

Two providers behind one API:

  * simulated (default) — records a real pending -> paid row in SQLite and
    drives the in-page mock Stripe modal. Lets the whole flow work locally
    with no Stripe account.
  * stripe (STRIPE_MODE=live) — creates a real Stripe Checkout Session and
    returns its hosted URL; the webhook marks the row paid.

The money path stores amounts in integer cents and validates against the
floor/ceiling in config so a bad or hostile amount can never reach a provider.
"""

import secrets
import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import config
from ..db import get_db
from ..ratelimit import check_rate_limit
from ..services.havenops import relay_payment
from ..services.notify import notify_new_order
from ..services.orders import insert_order

router = APIRouter()


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class CheckoutRequest(BaseModel):
    kind: str = Field(..., pattern="^(support|invoice)$")
    # Amount in whole/decimal dollars as entered in the UI.
    amount: float = Field(..., gt=0)
    invoice_number: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=254)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _make_reference(kind: str) -> str:
    prefix = "HVN-INV-" if kind == "invoice" else "HVN-"
    return prefix + secrets.token_hex(3).upper()


def _to_cents(amount: float) -> int:
    cents = int(round(amount * 100))
    if cents < config.MIN_AMOUNT_CENTS:
        raise HTTPException(status_code=400, detail="Amount is below the $1 minimum.")
    if cents > config.MAX_AMOUNT_CENTS:
        raise HTTPException(status_code=400, detail="Amount exceeds the maximum.")
    return cents


def _payment_row(conn: sqlite3.Connection, reference: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM payments WHERE reference = ?", (reference,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return row


def _receipt(row: sqlite3.Row) -> dict:
    return {
        "reference": row["reference"],
        "kind": row["kind"],
        "amount_cents": row["amount_cents"],
        "currency": row["currency"],
        "invoice_number": row["invoice_number"],
        "status": row["status"],
        "paid_at": row["paid_at"],
    }


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.post("/checkout")
def create_checkout(
    req: CheckoutRequest,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Start a checkout. Returns the provider + what the frontend needs next."""
    check_rate_limit(request, "checkout", limit=15, window_seconds=600)
    amount_cents = _to_cents(req.amount)
    reference = _make_reference(req.kind)
    provider = "stripe" if config.STRIPE_MODE == "live" else "simulated"

    session_id = None
    checkout_url = None

    if provider == "stripe":
        session_id, checkout_url = _create_stripe_session(req, amount_cents, reference)

    conn.execute(
        """INSERT INTO payments
             (reference, kind, amount_cents, currency, invoice_number, email,
              status, provider, provider_session_id)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (
            reference,
            req.kind,
            amount_cents,
            config.CURRENCY,
            req.invoice_number,
            req.email,
            provider,
            session_id,
        ),
    )

    return {
        "reference": reference,
        "kind": req.kind,
        "amount_cents": amount_cents,
        "currency": config.CURRENCY,
        "provider": provider,
        # simulated: frontend shows the in-page modal, then POSTs /complete.
        # stripe: frontend redirects the browser to checkout_url.
        "checkout_url": checkout_url,
    }


@router.post("/checkout/{reference}/complete")
def complete_simulated(reference: str, background: BackgroundTasks,
                       conn: sqlite3.Connection = Depends(get_db)):
    """Mark a SIMULATED payment paid. Real (stripe) rows are settled by the
    webhook and reject this call so the mock path can't spoof a live payment."""
    row = _payment_row(conn, reference)
    if row["provider"] != "simulated":
        raise HTTPException(
            status_code=400,
            detail="This payment settles through Stripe, not the simulated path.",
        )
    if row["status"] != "paid":
        conn.execute(
            "UPDATE payments SET status = 'paid', paid_at = datetime('now') WHERE reference = ?",
            (reference,),
        )
        row = _payment_row(conn, reference)
        # Relay to Haven Ops too (flagged as simulated there) so the whole
        # pipeline is testable end-to-end without real money.
        background.add_task(relay_payment, {
            "amount_cents": row["amount_cents"], "reference": reference,
            "kind": row["kind"], "provider": "simulated",
            "paid_at": row["paid_at"], "email": row["email"],
            "invoice_number": row["invoice_number"],
        })
    return _receipt(row)


@router.get("/checkout/{reference}")
def get_checkout(reference: str, conn: sqlite3.Connection = Depends(get_db)):
    """Look up a payment (used by the /success return page in live mode)."""
    return _receipt(_payment_row(conn, reference))


# --------------------------------------------------------------------------- #
# Stripe (live mode only) — imported lazily so simulated mode needs no keys.
# --------------------------------------------------------------------------- #
def _create_stripe_session(req: CheckoutRequest, amount_cents: int, reference: str):
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Stripe is enabled but STRIPE_SECRET_KEY is not configured.",
        )
    try:
        import stripe  # noqa: WPS433 (lazy import by design)
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=503, detail="Stripe library is not installed."
        ) from exc

    stripe.api_key = config.STRIPE_SECRET_KEY
    label = "Client invoice" if req.kind == "invoice" else "Voyager's Haven support"
    if req.kind == "invoice" and req.invoice_number:
        label = f"Invoice {req.invoice_number}"

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": config.CURRENCY,
                    "product_data": {"name": label},
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }
        ],
        client_reference_id=reference,
        customer_email=req.email or None,
        success_url=f"{config.SITE_URL}/success?ref={reference}",
        cancel_url=f"{config.SITE_URL}/?checkout=cancelled",
        metadata={"reference": reference, "kind": req.kind},
    )
    return session.id, session.url


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, background: BackgroundTasks, conn: sqlite3.Connection = Depends(get_db)):
    """Stripe settles a live payment here. Verifies the signature, then marks the
    matching payment row paid on `checkout.session.completed`. Only active in
    live mode (simulated payments settle via /checkout/{ref}/complete)."""
    if config.STRIPE_MODE != "live":
        raise HTTPException(status_code=404, detail="Not found.")
    if not config.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured.")
    try:
        import stripe  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail="Stripe library is not installed.") from exc

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, config.STRIPE_WEBHOOK_SECRET)
    except Exception as exc:  # noqa: BLE001 - includes signature failures
        raise HTTPException(status_code=400, detail="Invalid webhook signature.") from exc

    etype = event.get("type")
    if etype == "checkout.session.completed":
        sess = event["data"]["object"]
        reference = sess.get("client_reference_id") or (sess.get("metadata") or {}).get("reference")
        if reference:
            conn.execute(
                """UPDATE payments
                     SET status = 'paid', paid_at = datetime('now'), provider_session_id = ?
                   WHERE reference = ? AND status != 'paid'""",
                (sess.get("id"), reference),
            )
            row = conn.execute("SELECT * FROM payments WHERE reference = ?", (reference,)).fetchone()
            if row:
                # Haven Ops ledger: transaction (+ receipt when the invoice
                # number names a VHAV engagement). Best-effort, post-response.
                cd = sess.get("customer_details") or {}
                background.add_task(relay_payment, {
                    "amount_cents": row["amount_cents"], "reference": reference,
                    "kind": row["kind"], "provider": "stripe",
                    "paid_at": row["paid_at"],
                    "email": row["email"] or cd.get("email"),
                    "invoice_number": row["invoice_number"],
                    "description": row["item_label"] if "item_label" in row.keys() else None,
                })
            already = conn.execute("SELECT id FROM orders WHERE payment_reference = ?", (reference,)).fetchone()
            if row and row["kind"] == "merch" and not already:
                cd = sess.get("customer_details") or {}
                sd = sess.get("shipping_details") or sess.get("shipping") or {}
                addr = sd.get("address") or {}
                order = insert_order(
                    conn, reference=reference, item_label=row["item_label"] or "Order",
                    amount_cents=row["amount_cents"], currency=row["currency"],
                    customer={"name": sd.get("name") or cd.get("name"), "email": cd.get("email"), "phone": cd.get("phone")},
                    shipping={"line1": addr.get("line1"), "line2": addr.get("line2"), "city": addr.get("city"),
                              "state": addr.get("state"), "postal": addr.get("postal_code"), "country": addr.get("country")},
                )
                background.add_task(notify_new_order, order)
    elif etype in ("invoice.paid", "invoice.payment_succeeded"):
        inv = event["data"]["object"]
        # Grab the payment receipt URL so the admin pipeline can show "with this receipt".
        receipt_url = None
        charge_id = inv.get("charge")
        if charge_id:
            try:
                receipt_url = stripe.Charge.retrieve(charge_id).get("receipt_url")
            except Exception:  # noqa: BLE001 - receipt is a nicety; never fail the webhook
                receipt_url = None
        conn.execute(
            "UPDATE invoices SET status = 'paid', paid_at = datetime('now'), "
            "receipt_url = COALESCE(?, receipt_url) WHERE stripe_invoice_id = ?",
            (receipt_url, inv.get("id")),
        )
        inv_row = conn.execute(
            "SELECT * FROM invoices WHERE stripe_invoice_id = ?", (inv.get("id"),)
        ).fetchone()
        if inv_row:
            # Stripe-hosted invoice settled → Haven Ops transaction + receipt.
            background.add_task(relay_payment, {
                "amount_cents": inv_row["amount_cents"],
                "reference": inv_row["number"] or inv.get("id"),
                "kind": "invoice", "provider": "stripe",
                "paid_at": inv_row["paid_at"],
                "email": inv_row["customer_email"],
                "invoice_number": inv_row["number"],
                "description": inv_row["description"],
                "receipt_url": receipt_url,
            })
    elif etype in ("invoice.finalized", "invoice.sent"):
        inv = event["data"]["object"]
        conn.execute(
            "UPDATE invoices SET status = 'open', hosted_invoice_url = ?, pdf_url = ? "
            "WHERE stripe_invoice_id = ? AND status != 'paid'",
            (inv.get("hosted_invoice_url"), inv.get("invoice_pdf"), inv.get("id")),
        )
    elif etype in ("invoice.voided", "invoice.marked_uncollectible"):
        inv = event["data"]["object"]
        conn.execute("UPDATE invoices SET status = 'void' WHERE stripe_invoice_id = ?", (inv.get("id"),))
    return {"received": True}
