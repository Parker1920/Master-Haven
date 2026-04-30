"""
Discord webhook alerter for the Haven smoke suite.

Reads HAVEN_SMOKE_WEBHOOK_URL from env. Posts a single embed per failure
batch. Redacts any webhook URL from the body before posting (defense in
depth — see PROPOSAL §10.7).

Usage (from run_smoke.sh / run_verify.sh):

    python -m haven_smoke.alerter \
        --log /path/to/pytest.log \
        --mode smoke \
        --severity p0 \
        --hostname pi5

If $HAVEN_SMOKE_WEBHOOK_URL is unset, writes a WARN line to
~/haven-smoke-alerts.log instead of POSTing.

Exit code: 0 on success or graceful no-op, 1 on POST failure.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .redact import redact, WEBHOOK_RE

FALLBACK_LOG = Path(os.environ.get("HAVEN_SMOKE_FALLBACK_LOG",
                                   str(Path.home() / "haven-smoke-alerts.log")))


COLORS = {
    "p0": 15158332,   # red
    "p1": 16753920,   # orange
    "info": 3447003,  # blue
}


def build_embed(
    *,
    title: str,
    description: str,
    severity: str,
    mode: str,
    hostname: str,
) -> dict:
    """Construct the Discord embed payload."""
    color = COLORS.get(severity, COLORS["p0"])
    # Truncate the description to Discord's 4096-char field limit and redact.
    safe_desc = redact(description)[:3900]
    return {
        "embeds": [
            {
                "title": redact(title)[:256],
                "description": safe_desc,
                "color": color,
                "fields": [
                    {"name": "Mode", "value": mode, "inline": True},
                    {"name": "Severity", "value": severity, "inline": True},
                    {"name": "Host", "value": hostname, "inline": True},
                    {"name": "Run time",
                     "value": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "inline": False},
                ],
                "footer": {"text": "haven-tests v1.0"},
            }
        ]
    }


def post_to_webhook(url: str, payload: dict, timeout: int = 10) -> bool:
    """POST the payload to the Discord webhook. Returns True on success."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "haven-tests/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout) as e:
        # The error message itself may contain the webhook URL — redact before logging.
        log_line = f"[{datetime.now().isoformat()}] webhook POST failed: {redact(str(e))}\n"
        FALLBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with FALLBACK_LOG.open("a", encoding="utf-8") as fh:
            fh.write(log_line)
        sys.stderr.write(log_line)
        return False


def fallback_log(message: str) -> None:
    FALLBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
    with FALLBACK_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now().isoformat()}] {redact(message)}\n")


def alert(
    *,
    title: str,
    body: str,
    severity: str,
    mode: str,
    hostname: Optional[str] = None,
) -> int:
    """Send an alert. Returns 0 on success or graceful no-op, 1 on failure."""
    hostname = hostname or socket.gethostname()
    url = os.environ.get("HAVEN_SMOKE_WEBHOOK_URL", "").strip()

    if not url or "REPLACE_ME" in url or not url.startswith("https://discord"):
        fallback_log(
            f"WARN: no valid HAVEN_SMOKE_WEBHOOK_URL configured. "
            f"Would have alerted: severity={severity} mode={mode} title={title!r}"
        )
        return 0

    payload = build_embed(
        title=title, description=body, severity=severity,
        mode=mode, hostname=hostname,
    )
    ok = post_to_webhook(url, payload)
    return 0 if ok else 1


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Haven smoke suite Discord alerter.")
    parser.add_argument("--log", type=Path, required=True,
                        help="Path to pytest log file to summarize.")
    parser.add_argument("--mode", default="smoke",
                        choices=("smoke", "verify", "pi_check"),
                        help="Which suite produced this output.")
    parser.add_argument("--severity", default="p0",
                        choices=("p0", "p1", "info"))
    parser.add_argument("--title", default="Haven smoke FAILED",
                        help="Embed title.")
    parser.add_argument("--hostname", default=None)
    args = parser.parse_args(argv)

    if not args.log.exists():
        sys.stderr.write(f"--log {args.log} does not exist\n")
        return 2

    body = args.log.read_text(encoding="utf-8", errors="replace")
    return alert(
        title=args.title,
        body=body,
        severity=args.severity,
        mode=args.mode,
        hostname=args.hostname,
    )


if __name__ == "__main__":
    raise SystemExit(main())
