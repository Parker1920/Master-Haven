"""Shared order-recording — used by both the simulated shop-complete path and
the live Stripe webhook, so a merch order is stored identically either way.
"""

import sqlite3


def insert_order(
    conn: sqlite3.Connection,
    *,
    reference: str,
    item_label: str,
    amount_cents: int,
    currency: str,
    customer: dict,
    shipping: dict,
) -> dict:
    """Record one merch order. `customer` = {name,email,phone};
    `shipping` = {line1,line2,city,state,postal,country}. Returns the order dict."""
    cur = conn.execute(
        """INSERT INTO orders
             (payment_reference, item_label, amount_cents, currency,
              customer_name, customer_email, customer_phone,
              ship_line1, ship_line2, ship_city, ship_state, ship_postal, ship_country)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            reference, item_label, amount_cents, currency,
            customer.get("name"), customer.get("email"), customer.get("phone"),
            shipping.get("line1"), shipping.get("line2"), shipping.get("city"),
            shipping.get("state"), shipping.get("postal"), shipping.get("country"),
        ),
    )
    return {
        "id": cur.lastrowid,
        "reference": reference,
        "item_label": item_label,
        "amount_cents": amount_cents,
        "customer": customer,
        "shipping": shipping,
    }
