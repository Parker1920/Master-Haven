"""Documents — list, view/download, uploads, and attach-to-record.

Two file stores under DATA_DIR/uploads/:
  generated/ — PDFs frozen by docgen (immutable, versioned)
  uploaded/  — real files uploaded through the UI (governance PDFs, signed
               copies, receipt scans). Content-addressed names (sha prefix)
               so identical re-uploads are harmless.

Freeze rules:
  * generated/seed records are permanent — no update, no delete.
  * a record may have a file attached ONCE (governance backfill); fixing a
    wrong attachment = new row + new upload, history stays.
  * only origin='uploaded' rows can be deleted, and only while nothing
    (papertrail events, asset receipts) references them.
"""
import hashlib
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..models import Asset, DocumentGenerated, Engagement, EngagementEvent
from ..services.activity import log_activity, now_iso

router = APIRouter(prefix="/api/documents", tags=["documents"])
assets_router = APIRouter(prefix="/api/assets", tags=["assets"])

ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
MEDIA_TYPES = {".pdf": "application/pdf", ".png": "image/png",
               ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
MAX_UPLOAD = 25 * 1024 * 1024


def _uploaded_dir() -> Path:
    p = settings.upload_dir.parent / "uploaded"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _resolve_file(doc: DocumentGenerated) -> Path | None:
    if not doc.filename:
        return None
    for base in (_uploaded_dir(), settings.upload_dir):
        path = base / doc.filename
        if path.is_file():
            return path
    return None


def _store_upload(file: UploadFile) -> tuple[str, str]:
    """Validate + write an upload; returns (filename, sha256).

    Content-addressed filename: same bytes → same name, so a duplicate upload
    just reuses the existing file instead of erroring or duplicating.
    """
    original = Path(file.filename or "file").name
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"File type '{ext}' not allowed. Allowed: {sorted(ALLOWED_EXT)}")
    data = file.file.read(MAX_UPLOAD + 1)
    if not data:
        raise HTTPException(400, "Empty upload")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Upload exceeds 25 MB")
    sha256 = hashlib.sha256(data).hexdigest()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", original)[-80:]
    filename = f"upl_{sha256[:12]}_{safe}"
    path = _uploaded_dir() / filename
    if not path.exists():  # same name ⇒ same sha ⇒ same bytes; skip rewrite
        path.write_bytes(data)
    return filename, sha256


@router.get("")
def list_documents(session: Session = Depends(get_session)):
    docs = session.exec(select(DocumentGenerated).order_by(DocumentGenerated.id)).all()
    engagements = {e.id: e for e in session.exec(select(Engagement)).all()}
    return [{
        **d.model_dump(),
        "engagement_code": getattr(engagements.get(d.engagement_id), "code", None),
        "engagement_state": getattr(engagements.get(d.engagement_id), "state", None),
        "has_file": _resolve_file(d) is not None,
    } for d in docs]


@router.get("/{doc_id}/file")
def get_document_file(doc_id: int, dl: int = 0, session: Session = Depends(get_session)):
    """Default = inline (viewable in the browser); ?dl=1 = attachment."""
    doc = session.get(DocumentGenerated, doc_id)
    if not doc:
        raise HTTPException(404, f"document {doc_id} not found")
    path = _resolve_file(doc)
    if not path:
        raise HTTPException(404, "no file on disk for this record — attach or upload one")
    media = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    if dl:
        return FileResponse(path, media_type=media, filename=doc.filename)
    return FileResponse(path, media_type=media,
                        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'})


@router.post("/upload", status_code=201)
def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form("upload"),
    engagement_id: int | None = Form(None),
    session: Session = Depends(get_session),
):
    """Create a NEW document record from a real file (frozen on arrival)."""
    if engagement_id is not None and not session.get(Engagement, engagement_id):
        raise HTTPException(400, "engagement_id must reference an existing engagement")
    filename, sha256 = _store_upload(file)
    doc = DocumentGenerated(
        engagement_id=engagement_id, doc_type=doc_type.strip() or "upload",
        title=title.strip(), version=1, filename=filename, sha256=sha256,
        generated_at=now_iso(), frozen=1, origin="uploaded",
    )
    session.add(doc)
    session.flush()
    log_activity(session, "document", doc.id, "upload", f"{doc.title} · sha256 {sha256[:12]}…")
    session.commit()
    session.refresh(doc)
    return {**doc.model_dump(), "has_file": True, "file": f"/api/documents/{doc.id}/file"}


@router.post("/{doc_id}/file", status_code=201)
def attach_file(doc_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)):
    """Attach the real file to an existing file-less record (governance
    backfill). One shot: a record that already has a file is frozen — fix a
    wrong attachment by uploading a new document, not by replacing."""
    doc = session.get(DocumentGenerated, doc_id)
    if not doc:
        raise HTTPException(404, f"document {doc_id} not found")
    if doc.sha256 or _resolve_file(doc):
        raise HTTPException(409, "record already has a file (frozen) — upload a new document instead")
    filename, sha256 = _store_upload(file)
    doc.filename, doc.sha256, doc.origin = filename, sha256, "uploaded"
    if not doc.generated_at:
        doc.generated_at = now_iso()
    session.add(doc)
    log_activity(session, "document", doc_id, "attach", f"{doc.title} · sha256 {sha256[:12]}…")
    session.commit()
    session.refresh(doc)
    return {**doc.model_dump(), "has_file": True, "file": f"/api/documents/{doc.id}/file"}


@router.delete("/{doc_id}")
def delete_document(doc_id: int, session: Session = Depends(get_session)):
    """Only uploaded, unreferenced records can die (mistake correction).
    Generated + seed records are permanent."""
    doc = session.get(DocumentGenerated, doc_id)
    if not doc:
        raise HTTPException(404, f"document {doc_id} not found")
    if doc.origin != "uploaded":
        raise HTTPException(403, "generated/seed documents are frozen records — they don't die")
    if session.exec(select(EngagementEvent).where(EngagementEvent.document_id == doc_id)).first():
        raise HTTPException(409, "referenced by the papertrail — records don't die")
    if session.exec(select(Asset).where(Asset.document_id == doc_id)).first():
        raise HTTPException(409, "referenced by an asset receipt — detach it first")
    filename = doc.filename
    session.delete(doc)
    log_activity(session, "document", doc_id, "delete", doc.title)
    session.commit()
    # Remove the file only if no other record shares it (content-addressing
    # means duplicate uploads share one file).
    if filename and not session.exec(
            select(DocumentGenerated).where(DocumentGenerated.filename == filename)).first():
        (_uploaded_dir() / filename).unlink(missing_ok=True)
    return {"ok": True, "deleted": doc_id}


# ── Asset receipts ────────────────────────────────────────────────────────────

@assets_router.post("/{asset_id}/receipt", status_code=201)
def attach_receipt(asset_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)):
    """Upload a receipt scan and link it to the asset (drives the Itemize
    workflow — the $1,400.93 finally gets its evidence)."""
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, f"asset {asset_id} not found")
    filename, sha256 = _store_upload(file)
    doc = DocumentGenerated(
        doc_type="receipt_scan", title=f"Receipt — {asset.label}", version=1,
        filename=filename, sha256=sha256, generated_at=now_iso(),
        frozen=1, origin="uploaded",
    )
    session.add(doc)
    session.flush()
    asset.document_id = doc.id
    session.add(asset)
    log_activity(session, "asset", asset_id, "attach",
                 f"receipt scan for {asset.label} · doc {doc.id}")
    session.commit()
    session.refresh(doc)
    return {"document": doc.model_dump(), "asset_id": asset_id, "file": f"/api/documents/{doc.id}/file"}
