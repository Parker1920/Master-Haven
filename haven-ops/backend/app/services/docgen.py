"""Document generation — render Jinja → HTML → WeasyPrint → frozen PDF.

The freeze contract (hard rule): a generated document is IMMUTABLE. It is
written once, hashed, and recorded with frozen=1. "Re-generating" a doc type
for an engagement produces a NEW version row and a NEW file — nothing is ever
re-rendered or overwritten, and there is no update/delete path for documents.

The e-signature (DATA_DIR/signature.png, placed by hand, never in the repo)
is stamped onto the signed doc types (SOW / completion certificate / receipt).
If the file isn't on disk yet, those docs fall back to a conformed
"/s/ Parker Stouffer" block and the response says so — generation is never
blocked in dev, but the record is honest about what it carries.
"""
import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import Session, select

from ..config import settings
from ..models import (Client, Company, DocumentGenerated, Engagement,
                      EngagementEvent, RequiredDoc, Template)
from .activity import log_activity, now_iso

TEMPLATE_FILES = {
    "intake": "doc_intake.html",
    "proposal": "doc_proposal.html",
    "nda": "doc_nda.html",
    "msa": "doc_msa.html",
    "sow": "doc_sow.html",
    "change_order": "doc_change_order.html",
    "acceptance": "doc_acceptance.html",
    "invoice": "doc_invoice.html",
    "receipt": "doc_receipt.html",
    "completion": "doc_completion.html",
}
# Which docs stamp the e-signature. Invoice and intake carry none: an invoice
# is a demand, not an agreement; intake is an internal record.
SIGNED_TYPES = {"sow", "completion", "receipt", "msa", "nda",
                "change_order", "proposal", "acceptance"}
EVENT_KINDS = {"intake": "inquiry", "proposal": "proposal", "nda": "contract",
               "msa": "contract", "sow": "contract", "change_order": "contract",
               "acceptance": "delivery", "invoice": "invoice",
               "receipt": "receipt", "completion": "completion"}
# Display labels, in lifecycle order — also drives the Generate picker.
DOC_LABELS = {
    "intake": "Inquiry / Intake Record",
    "proposal": "Proposal",
    "nda": "Mutual NDA",
    "msa": "Master Services Agreement",
    "sow": "Statement of Work",
    "change_order": "Change Order",
    "acceptance": "Delivery & Acceptance",
    "invoice": "Invoice",
    "receipt": "Receipt",
    "completion": "Completion Certificate",
}

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)


def money(cents: int) -> str:
    """Integer-cents → '$1,234.56'. No floats near money."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100:,}.{cents % 100:02d}"


def _signature_data_uri() -> str | None:
    p = settings.signature_path
    if p.is_file():
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    return None


def _doc_label(session: Session, doc_type: str) -> str:
    if doc_type in DOC_LABELS:
        return DOC_LABELS[doc_type]
    row = session.exec(select(RequiredDoc).where(RequiredDoc.doc_type == doc_type)).first()
    return row.label if row else doc_type.replace("_", " ").title()


def generate_document(session: Session, engagement_id: int, doc_type: str,
                      extra: dict | None = None) -> dict:
    """Generate + freeze one document; returns the new record + papertrail event."""
    if doc_type not in TEMPLATE_FILES:
        raise HTTPException(400, f"Unknown doc_type '{doc_type}'. Valid: {sorted(TEMPLATE_FILES)}")

    engagement = session.get(Engagement, engagement_id)
    if not engagement:
        raise HTTPException(404, "Engagement not found")
    client = session.get(Client, engagement.client_id)
    company = session.get(Company, 1)
    if not company:
        raise HTTPException(500, "Company record missing — run the seed")

    # Next version for (engagement, doc_type): freeze means re-issues stack up.
    versions = session.exec(
        select(DocumentGenerated.version)
        .where(DocumentGenerated.engagement_id == engagement_id,
               DocumentGenerated.doc_type == doc_type)
    ).all()
    version = (max(versions) if versions else 0) + 1

    label = _doc_label(session, doc_type)
    generated_at = now_iso()
    signature_uri = _signature_data_uri() if doc_type in SIGNED_TYPES else None

    html = _env.get_template(TEMPLATE_FILES[doc_type]).render(
        company=company,
        client=client,
        e=engagement,
        version=version,
        doc_label=label,
        generated_at=generated_at,
        display_date=generated_at[:10],
        amount=money(engagement.value_cents),
        signature_uri=signature_uri,
        # Per-generation overrides (change description, payment rail, terms…)
        # — templates fall back to sensible defaults / fill-in lines without them.
        extra=extra or {},
    )
    # Import here so the app can boot even if WeasyPrint's system libs are
    # absent (bare local dev on Windows); only docgen requires them.
    from weasyprint import HTML
    # base_url makes the letterhead banner's relative asset URL resolve
    pdf_bytes = HTML(string=html, base_url=str(TEMPLATES_DIR) + "/").write_pdf()

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{engagement.code}_{doc_type}_v{version}.pdf"
    out_path = settings.upload_dir / filename
    if out_path.exists():
        # Version math should make this impossible; refuse rather than overwrite.
        raise HTTPException(500, f"{filename} already exists on disk — refusing to overwrite a frozen file")
    out_path.write_bytes(pdf_bytes)
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    template_row = session.exec(select(Template).where(Template.kind == doc_type)).first()

    doc = DocumentGenerated(
        engagement_id=engagement_id,
        doc_type=doc_type,
        title=f"{label} — {engagement.code}",
        version=version,
        filename=filename,
        sha256=sha256,
        generated_at=generated_at,
        frozen=1,
        template_id=template_row.id if template_row else None,
        origin="generated",
    )
    session.add(doc)
    session.flush()  # need doc.id for the event + log

    if doc_type in SIGNED_TYPES:
        sig_note = "signature stamped" if signature_uri else "conformed /s/ — signature.png not on file"
    else:
        sig_note = "no signature required"
    titles = {
        "sow": f"Contract generated — SOW v{version}",
        "completion": f"Completion certificate issued — v{version}",
        "invoice": f"Invoice issued — {money(engagement.value_cents)}",
        "receipt": f"Receipt issued — {money(engagement.value_cents)}",
    }
    event = EngagementEvent(
        engagement_id=engagement_id,
        ts=generated_at,
        kind=EVENT_KINDS.get(doc_type, "note"),
        actor="Voyager's Haven",
        title=titles.get(doc_type, f"{label} issued — v{version}"),
        detail=f"{filename} · sha256 {sha256[:12]}… · {sig_note}",
        document_id=doc.id,
    )
    session.add(event)
    session.flush()

    # A template proven by an actual generation is 'ready' — self-heals the
    # Registry's 'not built' seed rows the first time each type is used.
    if template_row and template_row.status != "ready":
        template_row.status = "ready"
        session.add(template_row)
        log_activity(session, "template", template_row.id, "update",
                     f"{template_row.name}: status → ready (first successful generation)")

    log_activity(session, "document", doc.id, "generate",
                 f"{doc_type} v{version} for {engagement.code} · sha256 {sha256[:12]}… · {sig_note}")
    session.commit()
    session.refresh(doc)
    session.refresh(event)

    return {
        "document": doc,
        "event": event,
        "signature_stamped": bool(signature_uri),
        "file": f"/api/documents/{doc.id}/file",
    }
