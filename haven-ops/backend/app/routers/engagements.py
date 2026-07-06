"""Engagements — lifecycle, papertrail, per-engagement documents, docgen.

Papertrail rules: events are APPEND-ONLY (GET + POST, no update/delete —
the log is immutable). The live "record gap" state is computed, not stored:
required_docs minus this engagement's generated doc types. A seeded
kind='gap' event stays in the trail forever as history; the computed
`missing_docs` list is what the UI's gap badges key off, so generating the
missing doc closes the gap without rewriting the past.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..db import get_session
from ..models import (Client, DocumentGenerated, Engagement, EngagementEvent,
                      RequiredDoc)
from ..services.activity import log_activity
from ..services.docgen import generate_document

router = APIRouter(prefix="/api/engagements", tags=["engagements"])

LIFECYCLE = ["inquiry", "proposal", "contract", "in_progress", "delivered", "closed"]
STAGE_LABELS = {"inquiry": "Inquiry", "proposal": "Proposal", "contract": "Contract",
                "in_progress": "In progress", "delivered": "Delivered", "closed": "Closed"}


def _missing_docs(session: Session, engagement_id: int) -> list[str]:
    required = [r.doc_type for r in session.exec(select(RequiredDoc)).all()]
    have = {d.doc_type for d in session.exec(
        select(DocumentGenerated).where(DocumentGenerated.engagement_id == engagement_id)).all()}
    return [t for t in required if t not in have]


def _with_extras(session: Session, engagement: Engagement) -> dict:
    client = session.get(Client, engagement.client_id)
    return {
        **engagement.model_dump(),
        "client": client.model_dump() if client else None,
        "missing_docs": _missing_docs(session, engagement.id),
    }


@router.get("")
def list_engagements(session: Session = Depends(get_session)):
    engagements = session.exec(select(Engagement).order_by(Engagement.id)).all()
    return [_with_extras(session, e) for e in engagements]


@router.post("", status_code=201)
def create_engagement(body: dict, session: Session = Depends(get_session)):
    data = {k: v for k, v in body.items() if k in Engagement.model_fields and k != "id"}
    if not session.get(Client, data.get("client_id")):
        raise HTTPException(400, "client_id must reference an existing client")
    engagement = Engagement(**data)
    session.add(engagement)
    session.flush()
    log_activity(session, "engagement", engagement.id, "create", engagement.code)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, f"Constraint violation: {exc.orig}")
    session.refresh(engagement)
    return _with_extras(session, engagement)


@router.get("/{engagement_id}")
def get_engagement(engagement_id: int, session: Session = Depends(get_session)):
    engagement = session.get(Engagement, engagement_id)
    if not engagement:
        raise HTTPException(404, "engagement not found")
    return _with_extras(session, engagement)


@router.put("/{engagement_id}")
def update_engagement(engagement_id: int, body: dict, session: Session = Depends(get_session)):
    engagement = session.get(Engagement, engagement_id)
    if not engagement:
        raise HTTPException(404, "engagement not found")
    changes = {k: v for k, v in body.items() if k in Engagement.model_fields and k != "id"}
    for key, value in changes.items():
        setattr(engagement, key, value)
    session.add(engagement)
    log_activity(session, "engagement", engagement_id, "update", ", ".join(changes) or None)
    session.commit()
    session.refresh(engagement)
    return _with_extras(session, engagement)


@router.post("/{engagement_id}/advance")
def advance_stage(engagement_id: int, body: dict | None = None,
                  session: Session = Depends(get_session)):
    """Move the engagement forward in the lifecycle. Forward only — the
    papertrail records progress, it doesn't rewind. Appends a stage event;
    reaching 'closed' stamps closed_at."""
    engagement = session.get(Engagement, engagement_id)
    if not engagement:
        raise HTTPException(404, "engagement not found")
    if engagement.state == "closed":
        raise HTTPException(400, "engagement is closed — the lifecycle is complete")
    current = LIFECYCLE.index(engagement.state) if engagement.state in LIFECYCLE else 0
    target = (body or {}).get("to") or LIFECYCLE[current + 1]
    if target not in LIFECYCLE or LIFECYCLE.index(target) <= current:
        raise HTTPException(400, f"can only advance forward from '{engagement.state}'")

    from ..services.activity import now_iso
    engagement.state = target
    if target == "closed":
        engagement.closed_at = now_iso()[:10]
    session.add(engagement)
    event = EngagementEvent(
        engagement_id=engagement_id, ts=now_iso()[:10], kind=target,
        actor="Voyager's Haven", title=f"Stage advanced — {STAGE_LABELS[target]}",
        detail=None,
    )
    session.add(event)
    log_activity(session, "engagement", engagement_id, "advance",
                 f"{engagement.code}: → {target}")
    session.commit()
    session.refresh(engagement)
    return _with_extras(session, engagement)


@router.delete("/{engagement_id}")
def delete_engagement(engagement_id: int, session: Session = Depends(get_session)):
    """Only an engagement nothing references can be deleted (FKs are ON, no
    cascades) — real engagements with a papertrail/documents refuse with 409."""
    engagement = session.get(Engagement, engagement_id)
    if not engagement:
        raise HTTPException(404, "engagement not found")
    session.delete(engagement)
    log_activity(session, "engagement", engagement_id, "delete", engagement.code)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "engagement has papertrail/documents/transactions — records don't die")
    return {"ok": True, "deleted": engagement_id}


# ── Papertrail (append-only) ─────────────────────────────────────────────────

@router.get("/{engagement_id}/events")
def list_events(engagement_id: int, session: Session = Depends(get_session)):
    if not session.get(Engagement, engagement_id):
        raise HTTPException(404, "engagement not found")
    return session.exec(
        select(EngagementEvent)
        .where(EngagementEvent.engagement_id == engagement_id)
        .order_by(EngagementEvent.id)   # papertrail order = insertion order
    ).all()


@router.post("/{engagement_id}/events", status_code=201)
def append_event(engagement_id: int, body: dict, session: Session = Depends(get_session)):
    if not session.get(Engagement, engagement_id):
        raise HTTPException(404, "engagement not found")
    data = {k: v for k, v in body.items()
            if k in EngagementEvent.model_fields and k not in ("id", "engagement_id")}
    if not data.get("title") or not data.get("kind"):
        raise HTTPException(400, "events need at least 'kind' and 'title'")
    event = EngagementEvent(engagement_id=engagement_id, **data)
    session.add(event)
    session.flush()
    log_activity(session, "engagement_event", event.id, "create",
                 f"{event.kind}: {event.title}")
    session.commit()
    session.refresh(event)
    return event


# ── Documents for this engagement (+ the live missing-docs check) ────────────

@router.get("/{engagement_id}/documents")
def engagement_documents(engagement_id: int, session: Session = Depends(get_session)):
    if not session.get(Engagement, engagement_id):
        raise HTTPException(404, "engagement not found")
    docs = session.exec(
        select(DocumentGenerated)
        .where(DocumentGenerated.engagement_id == engagement_id)
        .order_by(DocumentGenerated.id)
    ).all()
    required = session.exec(select(RequiredDoc)).all()
    from ..services.docgen import DOC_LABELS
    return {
        "documents": docs,
        "required": required,
        "missing": _missing_docs(session, engagement_id),
        # every type docgen can produce, lifecycle-ordered (Generate picker)
        "generatable": [{"doc_type": k, "label": v} for k, v in DOC_LABELS.items()],
    }


@router.post("/{engagement_id}/documents", status_code=201)
def create_document(engagement_id: int, body: dict, session: Session = Depends(get_session)):
    """Generate + freeze a document (see services/docgen.py for the contract).
    Optional body.fields = per-generation template overrides (change
    description, payment rail, terms…)."""
    doc_type = (body or {}).get("doc_type")
    if not doc_type:
        raise HTTPException(400, "body must include doc_type")
    fields = (body or {}).get("fields")
    if fields is not None and not isinstance(fields, dict):
        raise HTTPException(400, "fields must be an object")
    result = generate_document(session, engagement_id, doc_type, extra=fields)
    result["missing"] = _missing_docs(session, engagement_id)
    return result
