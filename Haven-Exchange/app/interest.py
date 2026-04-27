"""
Travelers Exchange — Loan Interest Accrual Engine

Daily background job that walks every active loan and applies simple
interest to ``Loan.accrued_interest`` based on the loan's snapshot
``interest_rate`` (basis points, annual).

Design choices:

- **Simple interest, not compound.**  Daily interest is computed against the
  original ``principal`` rather than ``outstanding``.  Compound interest on
  consumer/peer loans creates runaway debt spirals; the audit V2 called for
  a 100% lifetime cap which is naturally enforceable with simple interest.

- **100% running-balance cap.**  ``cap_amount`` is fixed at loan creation
  to the principal value.  ``accrued_interest`` (the *currently outstanding*
  unpaid interest) can never exceed that cap.  When the cap is hit,
  ``interest_frozen`` flips to ``True`` and accrual halts.  But the flag is
  a real-time "currently at cap" cache, not a permanent latch: when borrower
  payments reduce ``accrued_interest`` below ``cap_amount``, ``pay_loan``
  flips the flag back to ``False`` and the next daily run resumes accrual.
  This is the running-balance interpretation of the 100% cap (see
  ``INTEREST_CAP_BEHAVIOR.md``).

- **Idempotency by elapsed-day computation.**  The job computes how many full
  days have passed since ``last_accrual_at`` and accrues that many days at
  once.  Running the job twice in the same calendar day adds 0 days the
  second time.  This means a missed run (server outage) auto-recovers on the
  next run by accruing the backlog.

- **Open loans only.**  Closed/defaulted loans are skipped.  ``interest_rate
  == 0`` loans are also skipped (avoids dirtying ``last_accrual_at`` for
  zero-interest loans).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Loan


# ---------------------------------------------------------------------------
# Per-loan accrual
# ---------------------------------------------------------------------------
def _accrue_loan(loan: Loan, now: datetime) -> int:
    """Apply daily-compounded simple interest to a single loan.

    Returns the integer TC of interest added (0 if none).  Mutates the
    loan in place — caller is responsible for flushing/committing.

    The amount added per elapsed day is:

        floor(principal * interest_rate_bps / 10000 / 365)

    Capped so cumulative ``accrued_interest`` never exceeds ``cap_amount``.
    """
    # Skip non-active or zero-interest loans.  Note: we no longer skip
    # frozen loans here — under the running-balance cap, a frozen loan
    # whose accrued_interest has been paid down below cap_amount needs
    # to re-enter accrual.  The frozen flag is updated below when the
    # current accrued_interest is compared against cap_amount.
    if loan.status != "active":
        return 0
    if loan.interest_rate <= 0:
        return 0
    if loan.cap_amount <= 0:
        # Defensive: a loan with no cap can't accrue.  Should never happen
        # because cap is initialised at creation, but the migration backfill
        # could miss exotic rows.
        return 0
    if loan.accrued_interest >= loan.cap_amount:
        # Already at cap — flip the flag, advance last_accrual_at so time
        # spent at the cap doesn't bank up, and stop.  Under the running-
        # balance cap, days spent at cap should not retroactively accrue
        # interest after a paydown.
        loan.interest_frozen = True
        loan.last_accrual_at = now
        return 0

    # Bootstrap last_accrual_at to opened_at on the first run.
    last = loan.last_accrual_at or loan.opened_at
    if last.tzinfo is None:
        # SQLite stores naïve timestamps; treat them as UTC.
        last = last.replace(tzinfo=timezone.utc)

    elapsed = now - last
    elapsed_days = elapsed.days
    if elapsed_days <= 0:
        return 0

    # Daily rate (integer floor to avoid sub-1-TC drift).
    daily_interest = (loan.principal * loan.interest_rate) // (10000 * 365)
    if daily_interest <= 0:
        # Loan principal × rate is too small to produce ≥1 TC/day.
        # Still advance last_accrual_at so we don't recompute every run.
        loan.last_accrual_at = now
        return 0

    add_amount = daily_interest * elapsed_days

    # Apply the cap.  If adding the full amount would overshoot, fill only
    # to the cap and flip interest_frozen.  Otherwise, ensure interest_frozen
    # is False — a previously-frozen loan whose accrued_interest has been
    # paid down to below the cap re-enters accrual under the running-balance
    # interpretation.
    headroom = loan.cap_amount - loan.accrued_interest
    if add_amount >= headroom:
        add_amount = headroom
        loan.interest_frozen = True
    else:
        loan.interest_frozen = False

    loan.accrued_interest += add_amount
    loan.last_accrual_at = now
    return add_amount


# ---------------------------------------------------------------------------
# Daily job
# ---------------------------------------------------------------------------
def accrue_daily_interest(db: Session, *, now: Optional[datetime] = None) -> dict:
    """Apply daily interest to every open loan.

    Args:
        db: SQLAlchemy session.
        now: Optional injection for tests.  Defaults to ``datetime.now(UTC)``.

    Returns:
        A summary dict: ``{"loans_processed": N, "loans_accrued": M,
        "total_interest_added": X, "loans_frozen": Y}``.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Note: we no longer filter out frozen loans.  Under the running-balance
    # cap, a frozen loan whose accrued_interest has dropped below cap_amount
    # (because the borrower paid interest down) needs to be re-evaluated and
    # potentially have its frozen flag reset by ``_accrue_loan``.
    loans = list(
        db.execute(
            select(Loan).where(Loan.status == "active")
        ).scalars().all()
    )

    total_added = 0
    accrued_count = 0
    frozen_count = 0

    for loan in loans:
        was_frozen = loan.interest_frozen
        added = _accrue_loan(loan, now)
        if added > 0:
            accrued_count += 1
            total_added += added
        if loan.interest_frozen and not was_frozen:
            frozen_count += 1

    if total_added > 0 or frozen_count > 0 or accrued_count > 0:
        db.commit()

    return {
        "loans_processed": len(loans),
        "loans_accrued": accrued_count,
        "total_interest_added": total_added,
        "loans_frozen": frozen_count,
    }
