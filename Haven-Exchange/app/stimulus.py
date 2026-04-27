"""
Travelers Exchange — Auto-Stimulus Trigger Engine (Phase 2J)

Monitors daily GDP drops per nation and generates stimulus mint proposals
when GDP falls by 10%, 20%, or 30% from the previous measurement.

Proposals are **never auto-executed** — they require explicit World Mint
approval via the review endpoints.  The engine only creates proposals; the
World Mint reviews and approves/rejects them via the HTTP API.

Tier definitions (drop measured vs. previous gdp_score):
  - warning (10%+ drop): informational only — proposed_amount = 0
  - mild    (20%+ drop): small mint = 10% of nation treasury_balance (min 100 TC)
  - strong  (30%+ drop): larger mint = 25% of nation treasury_balance (min 500 TC)

One proposal per tier per day per nation: if a proposal already exists for
this nation at the same tier with status='pending' created today, no duplicate
is created.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import Nation, StimulusProposal


# Thresholds (whole-number percentage drops)
_TIER_THRESHOLDS = [
    ("strong", 30),
    ("mild", 20),
    ("warning", 10),
]

# Mint fractions per tier, as basis points of the nation's treasury balance
_TIER_MINT_BPS: dict[str, int] = {
    "warning": 0,
    "mild": 1000,    # 10% of treasury
    "strong": 2500,  # 25% of treasury
}

# Hard floor amounts (TC) per tier
_TIER_FLOOR: dict[str, int] = {
    "warning": 0,
    "mild": 100,
    "strong": 500,
}


def _drop_pct(prev: int, current: int) -> int:
    """Return integer percentage drop from prev to current (0 if no drop)."""
    if prev <= 0:
        return 0
    drop = prev - current
    if drop <= 0:
        return 0
    return math.floor(drop * 100 / prev)


def _compute_proposed_amount(tier: str, nation: Nation) -> int:
    """Compute the proposed mint amount for a tier based on treasury balance."""
    bps = _TIER_MINT_BPS.get(tier, 0)
    if bps == 0:
        return 0
    raw = math.floor(nation.treasury_balance * bps / 10_000)
    return max(raw, _TIER_FLOOR.get(tier, 0))


def _proposal_exists_today(db: Session, nation_id: int, tier: str, today: str) -> bool:
    """Return True if a pending proposal for this nation+tier was already created today."""
    existing = db.execute(
        select(StimulusProposal).where(
            and_(
                StimulusProposal.nation_id == nation_id,
                StimulusProposal.tier == tier,
                StimulusProposal.status == "pending",
                # SQLite stores datetime as text; prefix match on date is safe
                StimulusProposal.proposed_at >= today,
            )
        )
    ).scalar_one_or_none()
    return existing is not None


def check_and_propose_stimulus(
    db: Session,
    nation: Nation,
    previous_gdp_score: int,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Check GDP drop for *nation* and create proposals if thresholds are met.

    ``previous_gdp_score`` must be the GDP score from the snapshot *before*
    today's recalculation.  The caller (daily GDP job) is responsible for
    supplying this.

    Returns a list of newly created proposal dicts (may be empty if no
    thresholds breached or all proposals already exist for today).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    today_str = now.strftime("%Y-%m-%d")
    current_score = nation.gdp_score
    drop = _drop_pct(previous_gdp_score, current_score)

    if drop < 10:
        return []  # no threshold met

    # Determine which tier applies (highest matching threshold wins)
    triggered_tier: str | None = None
    for tier, threshold in _TIER_THRESHOLDS:
        if drop >= threshold:
            triggered_tier = tier
            break

    if triggered_tier is None:
        return []

    created: list[dict[str, Any]] = []

    # Create proposals for all triggered tiers (strong implies mild implies warning)
    for tier, threshold in reversed(_TIER_THRESHOLDS):
        if drop < threshold:
            continue
        if _proposal_exists_today(db, nation.id, tier, today_str):
            continue

        proposed_amount = _compute_proposed_amount(tier, nation)

        proposal = StimulusProposal(
            nation_id=nation.id,
            gdp_score_at_trigger=current_score,
            gdp_score_previous=previous_gdp_score,
            drop_pct=drop,
            tier=tier,
            proposed_amount=proposed_amount,
            status="pending",
        )
        db.add(proposal)
        db.flush()  # populate id before appending to response

        created.append({
            "id": proposal.id,
            "nation_id": nation.id,
            "tier": tier,
            "drop_pct": drop,
            "proposed_amount": proposed_amount,
            "status": "pending",
        })

    if created:
        db.commit()

    return created


def run_stimulus_checks(db: Session, *, now: datetime | None = None) -> dict[str, Any]:
    """Run stimulus checks for all approved nations.

    This is called by the daily GDP scheduler *after* recalculate_all_gdp().
    It reads the most recent GdpSnapshot for each nation to obtain the
    previous GDP score, then calls check_and_propose_stimulus().

    Returns an aggregate summary dict.
    """
    from app.models import GdpSnapshot  # local import to avoid circular

    if now is None:
        now = datetime.now(timezone.utc)

    nations = list(
        db.execute(
            select(Nation).where(Nation.status == "approved")
        )
        .scalars()
        .all()
    )

    total_proposals = 0
    nations_triggered = 0

    for nation in nations:
        # Find the most recent GDP snapshot (not today's — the one before the
        # current daily run).  The daily GDP job writes a snapshot before we
        # are called, so we look for the second-most-recent.
        today_str = now.strftime("%Y-%m-%d")
        snapshots = list(
            db.execute(
                select(GdpSnapshot)
                .where(
                    GdpSnapshot.nation_id == nation.id,
                    GdpSnapshot.snapshot_date != today_str,
                )
                .order_by(GdpSnapshot.snapshot_date.desc())
                .limit(1)
            )
            .scalars()
            .all()
        )

        if not snapshots:
            # No historical snapshot — can't compare; skip
            continue

        previous_score = snapshots[0].composite_score
        proposals = check_and_propose_stimulus(
            db, nation, previous_score, now=now
        )

        if proposals:
            nations_triggered += 1
            total_proposals += len(proposals)

    return {
        "nations_checked": len(nations),
        "nations_triggered": nations_triggered,
        "total_proposals_created": total_proposals,
    }
