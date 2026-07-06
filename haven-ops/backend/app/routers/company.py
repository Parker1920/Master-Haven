"""Company singleton + the e-signature stream.

The signature image is NEVER bundled into the frontend or the repo — it lives
in the data dir and is only ever served through this endpoint (and embedded
server-side into generated PDFs by docgen).
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from ..config import settings
from ..db import get_session
from ..models import Company
from ..services.activity import log_activity

router = APIRouter(prefix="/api/company", tags=["company"])


@router.get("")
def get_company(session: Session = Depends(get_session)):
    company = session.get(Company, 1)
    if not company:
        raise HTTPException(404, "Company record missing — run the seed")
    return company


@router.put("")
def update_company(body: dict, session: Session = Depends(get_session)):
    company = session.get(Company, 1)
    if not company:
        raise HTTPException(404, "Company record missing — run the seed")
    changes = {k: v for k, v in body.items() if k in Company.model_fields and k != "id"}
    for key, value in changes.items():
        setattr(company, key, value)
    session.add(company)
    log_activity(session, "company", 1, "update", ", ".join(changes) or None)
    session.commit()
    session.refresh(company)
    return company


@router.get("/signature")
def get_signature():
    if not settings.signature_path.is_file():
        raise HTTPException(404, "signature.png not placed in the data dir")
    return FileResponse(settings.signature_path, media_type="image/png")
