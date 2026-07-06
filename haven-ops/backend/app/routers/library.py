"""Template library — the document types docgen can produce, made visible.

GET  /api/template-library            → every type: label, purpose, per-type
                                        generation fields, signature policy,
                                        usage count, template-table status
GET  /api/template-library/{k}/preview → SPECIMEN PDF (sample data, watermark,
                                        no signature) — streamed inline, never
                                        recorded, never written to disk

Distinct prefix on purpose: /api/templates is the CRUD register for the
templates table; the library is the read-only docgen catalogue layered on it.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlmodel import Session, func, select

from ..db import get_session
from ..models import DocumentGenerated, Template
from ..services.docgen import (DOC_DESCRIPTIONS, DOC_FIELDS, DOC_LABELS,
                               SIGNED_TYPES, render_specimen)

router = APIRouter(prefix="/api/template-library", tags=["template-library"])


@router.get("")
def template_library(session: Session = Depends(get_session)):
    rows = {t.kind: t for t in session.exec(select(Template)).all() if t.kind}
    used = dict(session.exec(
        select(DocumentGenerated.doc_type, func.count())
        .where(DocumentGenerated.origin == "generated")
        .group_by(DocumentGenerated.doc_type)
    ).all())
    return [{
        "doc_type": kind,
        "label": label,
        "description": DOC_DESCRIPTIONS.get(kind),
        "fields": DOC_FIELDS.get(kind, []),
        "signed": kind in SIGNED_TYPES,
        "status": getattr(rows.get(kind), "status", "ready"),
        "template_id": getattr(rows.get(kind), "id", None),
        "generated_count": used.get(kind, 0),
        "preview": f"/api/template-library/{kind}/preview",
    } for kind, label in DOC_LABELS.items()]


@router.get("/{doc_type}/preview")
def preview_template(doc_type: str, session: Session = Depends(get_session)):
    pdf = render_specimen(session, doc_type)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="SPECIMEN_{doc_type}.pdf"',
        # sample data only, but keep specimens out of shared caches anyway
        "Cache-Control": "no-store",
    })
