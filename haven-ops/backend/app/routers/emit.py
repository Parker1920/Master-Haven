"""GET /api/emit/project-instructions — Part A (durable) + Part B (live)."""
from fastapi import APIRouter, Depends, Response
from sqlmodel import Session

from ..db import get_session
from ..services.emit import build_project_instructions

router = APIRouter(prefix="/api/emit", tags=["emit"])


@router.get("/project-instructions")
def project_instructions(session: Session = Depends(get_session)):
    markdown = build_project_instructions(session)
    return Response(content=markdown, media_type="text/markdown; charset=utf-8")
