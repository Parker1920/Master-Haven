"""
Webhook URL redactor.

PROPOSAL §10.7 hard requirement: any string matching the Discord webhook URL
pattern must be replaced before it goes into an alert payload, log line, or
stack trace echo.

The pattern matches both `discord.com` and the legacy `discordapp.com` host.
"""

from __future__ import annotations

import re

WEBHOOK_RE = re.compile(
    r"https://discord(?:app)?\.com/api/webhooks/\S+",
    re.IGNORECASE,
)

REDACTION_PLACEHOLDER = "[REDACTED-WEBHOOK]"


def redact(text: str) -> str:
    """Return `text` with any Discord webhook URL replaced.

    Idempotent: running it twice produces the same output.
    Safe on None/empty: returns input unchanged.
    """
    if not text:
        return text
    return WEBHOOK_RE.sub(REDACTION_PLACEHOLDER, text)
