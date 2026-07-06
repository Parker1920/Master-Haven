"""Relay site events to Haven Ops (the LLC's internal record-keeping app).

Haven Ops opens the engagement papertrail for inquiries and records
transactions/receipts for settled payments. The relay is strictly
best-effort: it runs in BackgroundTasks, times out fast, and swallows every
error — a down or unconfigured Ops instance must NEVER break a visitor's
contact form or a paying customer's checkout. (The site's own SQLite rows
remain the source of truth for what happened on the site.)

Disabled until both HAVEN_OPS_URL and HAVEN_OPS_TOKEN are set. In production
both containers share the Pi, so the URL is the internal docker-network
address (e.g. http://haven-ops:8090) — Haven Ops itself stays tailnet-only.
"""

import json
import urllib.request

from .. import config

_TIMEOUT_SECONDS = 6


def _post(path: str, payload: dict) -> None:
    if not (config.HAVEN_OPS_URL and config.HAVEN_OPS_TOKEN):
        return  # relay not configured — silently off
    try:
        req = urllib.request.Request(
            config.HAVEN_OPS_URL.rstrip("/") + path,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Ops-Token": config.HAVEN_OPS_TOKEN,
            },
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            resp.read()
    except Exception as exc:  # noqa: BLE001 — best-effort by contract
        print(f"[havenops] relay {path} failed (non-fatal): {exc}")


def relay_inquiry(inquiry: dict) -> None:
    """Contact-form inquiry → Ops opens a client + engagement + intake record."""
    _post("/api/hooks/inquiry", {
        "name": inquiry.get("name"),
        "email": inquiry.get("email"),
        "project_type": inquiry.get("project_type"),
        "budget": inquiry.get("budget"),
        "message": inquiry.get("message"),
        "site_inquiry_id": inquiry.get("id"),
    })


def relay_payment(payment: dict) -> None:
    """Settled payment → Ops records the transaction (+ receipt when the
    invoice number carries a VHAV engagement code)."""
    _post("/api/hooks/payment", {
        "amount_cents": payment.get("amount_cents"),
        "reference": payment.get("reference"),
        "kind": payment.get("kind"),
        "provider": payment.get("provider"),
        "paid_at": payment.get("paid_at"),
        "email": payment.get("email"),
        "invoice_number": payment.get("invoice_number"),
        "description": payment.get("description"),
        "receipt_url": payment.get("receipt_url"),
    })
