"""Auth seam — Phase 1 has NO login; the Tailscale tailnet IS the perimeter.

Every router added from Stage 2 on should declare
    dependencies=[Depends(require_user)]
so that when Discord-OAuth role tiers land (post-Phase-1 — e.g. money
visibility flips when Stars co-owns), real verification slots in HERE
without touching any call site.
"""


async def require_user() -> dict:
    # Phase 1 no-op: anyone who can reach the tailnet-internal port is Parker.
    return {"user": "parker", "role": "owner"}
