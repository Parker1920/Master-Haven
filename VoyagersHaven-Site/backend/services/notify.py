"""New-inquiry notifications — Discord webhook and/or SMTP email.

Both are optional and no-op until configured (see config.py). Everything here
is best-effort and swallows its own errors so a notification failure can never
break the inquiry submission. Called from a FastAPI BackgroundTask (after the
response), so it never adds latency to the submit.

Stdlib only (smtplib + urllib) — no extra dependency.
"""

import json
import logging
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage

from .. import config

log = logging.getLogger("voyagers-haven")


def notify_new_inquiry(inq: dict) -> None:
    _notify_discord(inq)
    _notify_email(inq)


def _notify_discord(inq: dict) -> None:
    url = config.INQUIRY_WEBHOOK_URL
    if not url:
        return
    content = (
        f"**New project inquiry**\n"
        f"**{inq.get('name')}** <{inq.get('email')}>\n"
        f"Type: {inq.get('project_type') or '—'}  ·  Budget: {inq.get('budget') or '—'}\n"
        f">>> {(inq.get('message') or '')[:1500]}"
    )
    try:
        data = json.dumps({"content": content, "username": "Voyager's Haven"}).encode("utf-8")
        r = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "VoyagersHaven/1.0"},
        )
        urllib.request.urlopen(r, timeout=10)
    except Exception as e:  # noqa: BLE001 - best-effort
        log.warning("inquiry Discord notify failed: %s", e)


def _notify_email(inq: dict) -> None:
    if not (config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASSWORD and config.NOTIFY_EMAIL):
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = f"New inquiry: {inq.get('name')} ({inq.get('project_type') or 'project'})"
        msg["From"] = config.SMTP_FROM or config.SMTP_USER
        msg["To"] = config.NOTIFY_EMAIL
        if inq.get("email"):
            msg["Reply-To"] = inq["email"]
        msg.set_content(
            f"Name:    {inq.get('name')}\n"
            f"Email:   {inq.get('email')}\n"
            f"Type:    {inq.get('project_type') or '—'}\n"
            f"Budget:  {inq.get('budget') or '—'}\n"
            f"When:    {inq.get('created_at') or ''}\n\n"
            f"{inq.get('message') or ''}\n"
        )
        ctx = ssl.create_default_context()
        if config.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ctx, timeout=15) as s:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
                s.starttls(context=ctx)
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
                s.send_message(msg)
    except Exception as e:  # noqa: BLE001 - best-effort
        log.warning("inquiry email notify failed: %s", e)


def notify_new_order(order: dict) -> None:
    """Ping Discord on a new paid merch order (reuses the inquiry webhook)."""
    url = config.INQUIRY_WEBHOOK_URL
    if not url:
        return
    c = order.get("customer") or {}
    s = order.get("shipping") or {}
    ship = ", ".join(filter(None, [s.get("line1"), s.get("city"), s.get("state"), s.get("postal")]))
    content = (
        f"**🛒 New order** — {order.get('item_label')}\n"
        f"{c.get('name') or '—'} <{c.get('email') or '—'}>"
        + (f" · {c.get('phone')}" if c.get("phone") else "")
        + (f"\nShip to: {ship}" if ship else "")
    )
    try:
        data = json.dumps({"content": content, "username": "Voyager's Haven"}).encode("utf-8")
        r = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json", "User-Agent": "VoyagersHaven/1.0"},
        )
        urllib.request.urlopen(r, timeout=10)
    except Exception as e:  # noqa: BLE001
        log.warning("order Discord notify failed: %s", e)
