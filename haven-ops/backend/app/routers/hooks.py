"""Machine-to-machine hooks — the voyagershaven.online backend calls these.

Public traffic never reaches Haven Ops: the studio site is the public front
door, and its BACKEND relays events here server-to-server (same Pi / docker
network in production). Every call must carry X-Ops-Token matching
OPS_SERVICE_TOKEN; with no token configured the hooks are dead (503), so
they can never be open by accident.

  POST /api/hooks/inquiry   site contact form  → client + engagement +
                            auto-generated Inquiry/Intake record
  POST /api/hooks/payment   Stripe webhook / simulated settle → transaction
                            (+ auto-generated Receipt when the payment names
                            an engagement code in its invoice number)
"""
import re
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..models import Account, Client, Engagement
from ..services.activity import log_activity
from ..services.docgen import generate_document, money

router = APIRouter(prefix="/api/hooks", tags=["hooks"])

ENGAGEMENT_CODE_RE = re.compile(r"(VHAV-C-\d{4}-\d+)", re.IGNORECASE)


def require_service_token(x_ops_token: str = Header(default="")) -> None:
    if not settings.ops_service_token:
        raise HTTPException(503, "hooks disabled — OPS_SERVICE_TOKEN not configured")
    if x_ops_token != settings.ops_service_token:
        raise HTTPException(401, "bad service token")


def _next_code(session: Session) -> str:
    """Next free VHAV-C-YYYY-NNN for the current year (server-side twin of the
    Work screen's suggestion)."""
    year = date.today().year
    pattern = re.compile(rf"^VHAV-C-{year}-(\d+)$")
    top = 0
    for e in session.exec(select(Engagement)).all():
        m = pattern.match(e.code or "")
        if m:
            top = max(top, int(m.group(1)))
    return f"VHAV-C-{year}-{top + 1:03d}"


@router.post("/inquiry", status_code=201, dependencies=[Depends(require_service_token)])
def hook_inquiry(body: dict, session: Session = Depends(get_session)):
    """Site contact form → the papertrail starts itself.

    Expected: {name, email, message, project_type?, budget?, site_inquiry_id?}
    """
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip()
    message = (body.get("message") or "").strip()
    if not name or not message:
        raise HTTPException(400, "inquiry needs at least name and message")

    # Find-or-create the client (case-insensitive name match; email as contact).
    client = next((c for c in session.exec(select(Client)).all()
                   if c.name.strip().lower() == name.lower()
                   or (email and (c.contact or "").strip().lower() == email.lower())), None)
    if not client:
        client = Client(name=name, contact=email or None, bill_to=email or None)
        session.add(client)
        session.flush()
        log_activity(session, "client", client.id, "create",
                     f"{name} (site inquiry)", actor="voyagershaven.online")

    title = (body.get("project_type") or "").strip() or f"Site inquiry — {name}"
    note_bits = [b for b in [(body.get("budget") or "").strip() and f"budget: {body['budget'].strip()}",
                             message[:300] + ("…" if len(message) > 300 else "")] if b]
    engagement = Engagement(
        code=_next_code(session), client_id=client.id, title=title,
        value_cents=0, state="inquiry", opened_at=date.today().isoformat(),
        note=" · ".join(note_bits) or None,
    )
    session.add(engagement)
    session.flush()
    log_activity(session, "engagement", engagement.id, "create",
                 f"{engagement.code} from site inquiry #{body.get('site_inquiry_id', '?')}",
                 actor="voyagershaven.online")
    session.commit()

    # The intake record freezes the inquiry verbatim (its own transaction —
    # docgen commits; a docgen hiccup must not lose the engagement itself).
    intake = None
    try:
        result = generate_document(session, engagement.id, "intake", extra={
            "received": date.today().isoformat(),
            "channel": "voyagershaven.online — contact form",
            "request": message,
            "size": (body.get("budget") or "to be established at Proposal."),
        })
        intake = result["document"].id
    except Exception:  # noqa: BLE001 — engagement exists either way
        log_activity(session, "engagement", engagement.id, "note",
                     "intake auto-generation failed — generate manually",
                     actor="voyagershaven.online")
        session.commit()

    return {"ok": True, "engagement_id": engagement.id, "code": engagement.code,
            "client_id": client.id, "intake_document_id": intake}


@router.post("/payment", status_code=201, dependencies=[Depends(require_service_token)])
def hook_payment(body: dict, session: Session = Depends(get_session)):
    """Money settled on the site → ledger transaction (+ receipt if it names
    an engagement).

    Expected: {amount_cents, reference, kind, provider, paid_at?, email?,
               invoice_number?, description?, receipt_url?}
    """
    amount = body.get("amount_cents")
    if not isinstance(amount, int) or amount <= 0:
        raise HTTPException(400, "amount_cents must be a positive integer")
    reference = (body.get("reference") or "").strip()
    provider = (body.get("provider") or "stripe").strip()
    kind = (body.get("kind") or "payment").strip()

    # Match an engagement via a VHAV code in the invoice number (our invoice
    # PDFs are numbered '{code}-INV-{v}', so this matches automatically).
    engagement = None
    m = ENGAGEMENT_CODE_RE.search(body.get("invoice_number") or "")
    if m:
        engagement = session.exec(
            select(Engagement).where(Engagement.code == m.group(1).upper())).first()

    stripe_account = session.exec(
        select(Account).where(Account.kind == "processor")).first()

    from ..models import Transaction
    note_bits = [f"site {kind} · ref {reference}"]
    if body.get("description"):
        note_bits.append(str(body["description"])[:200])
    if body.get("email"):
        note_bits.append(f"payer {body['email']}")
    if body.get("receipt_url"):
        note_bits.append(f"stripe receipt: {body['receipt_url']}")
    if provider != "stripe":
        note_bits.append("⚠ SIMULATED provider — not real money")

    tx = Transaction(
        account_id=stripe_account.id if (stripe_account and provider == "stripe") else None,
        engagement_id=engagement.id if engagement else None,
        amount_cents=amount, kind="payment",
        ts=(body.get("paid_at") or date.today().isoformat())[:10],
        note=" · ".join(note_bits),
        rail=f"Stripe ({reference})" if provider == "stripe" else f"simulated ({reference})",
    )
    session.add(tx)
    session.flush()
    log_activity(session, "transaction", tx.id, "create",
                 f"{money(amount)} via {provider} · {reference}"
                 + (f" → {engagement.code}" if engagement else " · unmatched (no engagement)"),
                 actor="voyagershaven.online")
    session.commit()

    # Receipt only when we know which engagement the money belongs to —
    # support contributions stay ledger-only.
    receipt = None
    if engagement and provider == "stripe":
        try:
            result = generate_document(session, engagement.id, "receipt", extra={
                "amount_received": money(amount),
                "paid_date": tx.ts,
                "rail": f"Stripe · ref {reference}",
                "balance": "PAID IN FULL" if amount >= engagement.value_cents else
                           f"{money(engagement.value_cents - amount)} remaining",
            })
            receipt = result["document"].id
        except Exception:  # noqa: BLE001
            log_activity(session, "engagement", engagement.id, "note",
                         "receipt auto-generation failed — generate manually",
                         actor="voyagershaven.online")
            session.commit()

    return {"ok": True, "transaction_id": tx.id,
            "engagement_code": engagement.code if engagement else None,
            "receipt_document_id": receipt}
