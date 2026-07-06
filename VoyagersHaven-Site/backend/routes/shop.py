"""Merch shop — public product list + product checkout.

Reuses the same Stripe/simulated checkout machinery as the Support flow. Prices
always come from the DB server-side, so the browser can't tamper with them.
Physical products (requires_shipping) collect a shipping address at checkout.
"""

import secrets
import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import config
from ..db import get_db
from ..ratelimit import check_rate_limit
from ..services.notify import notify_new_order
from ..services.orders import insert_order

router = APIRouter()


@router.get("/shop/products")
def list_products(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        """SELECT id, name, description, price_cents, image_url, requires_shipping
           FROM products WHERE active = 1 ORDER BY sort_order, id"""
    ).fetchall()
    return [dict(r) for r in rows]


class ShopCheckoutRequest(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=20)


@router.post("/shop/checkout")
def shop_checkout(
    req: ShopCheckoutRequest,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
):
    check_rate_limit(request, "checkout", limit=15, window_seconds=600)
    p = conn.execute("SELECT * FROM products WHERE id = ? AND active = 1", (req.product_id,)).fetchone()
    if p is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    amount_cents = p["price_cents"] * req.quantity
    reference = "HVN-SHOP-" + secrets.token_hex(3).upper()
    provider = "stripe" if config.STRIPE_MODE == "live" else "simulated"
    label = p["name"] + (f" ×{req.quantity}" if req.quantity > 1 else "")

    session_id = None
    checkout_url = None
    if provider == "stripe":
        session_id, checkout_url = _create_stripe_session(p, req.quantity, reference)

    conn.execute(
        """INSERT INTO payments
             (reference, kind, amount_cents, currency, item_label, status, provider, provider_session_id)
           VALUES (?, 'merch', ?, ?, ?, 'pending', ?, ?)""",
        (reference, amount_cents, config.CURRENCY, label, provider, session_id),
    )
    return {
        "reference": reference,
        "kind": "merch",
        "amount_cents": amount_cents,
        "currency": config.CURRENCY,
        "provider": provider,
        "checkout_url": checkout_url,
        "label": label,
    }


class ShopCompleteRequest(BaseModel):
    reference: str
    name: str | None = Field(default=None, max_length=140)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    line1: str | None = Field(default=None, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=80)
    postal: str | None = Field(default=None, max_length=20)


@router.post("/shop/complete")
def shop_complete(
    req: ShopCompleteRequest,
    background: BackgroundTasks,
    conn: sqlite3.Connection = Depends(get_db),
):
    """SIMULATED merch settlement: mark paid + record the order with the collected
    contact/shipping info. Live orders are recorded by the Stripe webhook instead."""
    row = conn.execute("SELECT * FROM payments WHERE reference = ?", (req.reference,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if row["provider"] != "simulated":
        raise HTTPException(status_code=400, detail="This order settles through Stripe.")
    if row["status"] != "paid":
        conn.execute(
            "UPDATE payments SET status = 'paid', paid_at = datetime('now') WHERE reference = ?",
            (req.reference,),
        )
    existing = conn.execute("SELECT id FROM orders WHERE payment_reference = ?", (req.reference,)).fetchone()
    if not existing:
        order = insert_order(
            conn,
            reference=req.reference,
            item_label=row["item_label"] or "Order",
            amount_cents=row["amount_cents"],
            currency=row["currency"],
            customer={"name": req.name, "email": req.email, "phone": req.phone},
            shipping={"line1": req.line1, "line2": req.line2, "city": req.city,
                      "state": req.state, "postal": req.postal, "country": "US"},
        )
        background.add_task(notify_new_order, order)
    return {"ok": True, "reference": req.reference, "amount_cents": row["amount_cents"],
            "item_label": row["item_label"], "status": "paid"}


def _create_stripe_session(p: sqlite3.Row, qty: int, reference: str):
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is enabled but not configured.")
    try:
        import stripe  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail="Stripe library is not installed.") from exc

    stripe.api_key = config.STRIPE_SECRET_KEY
    product_data = {"name": p["name"]}
    if p["description"]:
        product_data["description"] = p["description"][:500]
    if p["image_url"]:
        product_data["images"] = [p["image_url"]]

    kwargs = dict(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": config.CURRENCY,
                "product_data": product_data,
                "unit_amount": p["price_cents"],
            },
            "quantity": qty,
        }],
        client_reference_id=reference,
        success_url=f"{config.SITE_URL}/success?ref={reference}",
        cancel_url=f"{config.SITE_URL}/shop?checkout=cancelled",
        metadata={"reference": reference, "kind": "merch", "product_id": str(p["id"])},
    )
    kwargs["phone_number_collection"] = {"enabled": True}
    if p["requires_shipping"]:
        kwargs["shipping_address_collection"] = {"allowed_countries": ["US"]}
    session = stripe.checkout.Session.create(**kwargs)
    return session.id, session.url
