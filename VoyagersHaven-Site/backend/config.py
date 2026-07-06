"""Runtime configuration read from the environment.

Everything here is safe to expose to the frontend EXCEPT the secret keys.
The public shape is served by GET /api/config.
"""

import os

APP_NAME = "Voyager's Haven"
APP_VERSION = "0.1.0"

# 'simulated' (default) drives the in-page mock checkout so the site is fully
# usable locally with no Stripe account. Flip to 'live' once a Stripe account +
# the voyagershaven.online domain are registered and the keys below are set.
STRIPE_MODE = os.environ.get("STRIPE_MODE", "simulated").strip().lower()

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Absolute base URL of the deployed site, used to build Stripe success/cancel
# redirect URLs in live mode. Locally this is fine as-is.
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8090").rstrip("/")

CURRENCY = "usd"
MIN_AMOUNT_CENTS = 100          # $1 floor
MAX_AMOUNT_CENTS = 5_000_000    # $50,000 ceiling (invoice safety cap)

# Public contact address (also the mailto target on the Contact page).
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "ekimo.vhav@gmail.com")

# --- Haven Ops relay (LLC internal records; both optional / off until set) ---
# Inquiries open an engagement papertrail; settled payments land as ledger
# transactions (+ auto receipt). URL is the internal docker-network address in
# production (Haven Ops is tailnet-internal, never public).
HAVEN_OPS_URL = os.environ.get("HAVEN_OPS_URL", "").rstrip("/")
HAVEN_OPS_TOKEN = os.environ.get("HAVEN_OPS_TOKEN", "")

# --- New-inquiry notifications (all optional / off until configured) ---
# Discord: set INQUIRY_WEBHOOK_URL to a channel webhook.
INQUIRY_WEBHOOK_URL = os.environ.get("INQUIRY_WEBHOOK_URL", "")
# Email: set SMTP_* + NOTIFY_EMAIL. For Gmail use an App Password as SMTP_PASSWORD.
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", CONTACT_EMAIL)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "") or SMTP_USER


def public_config() -> dict:
    """The non-secret config the browser is allowed to know."""
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "stripe_mode": STRIPE_MODE,
        "stripe_publishable_key": STRIPE_PUBLISHABLE_KEY if STRIPE_MODE == "live" else "",
        "currency": CURRENCY,
        "min_amount_cents": MIN_AMOUNT_CENTS,
        "max_amount_cents": MAX_AMOUNT_CENTS,
    }
