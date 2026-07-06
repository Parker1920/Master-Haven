"""Generic CRUD router factory — one implementation for all the flat tables.

Bodies are plain JSON dicts whitelisted to the model's columns (id excluded).
SQLModel table classes skip pydantic validation by design, and this is a
tailnet-internal single-user tool — SQLite's flexible typing is acceptable
here; the auth seam is where hardening lands later.

Every create/update/delete writes an activity_log row that commits atomically
with the change itself.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..db import get_session
from ..services.activity import log_activity


def _clean(model, body: dict) -> dict:
    return {k: v for k, v in body.items() if k in model.model_fields and k != "id"}


def crud_router(model, *, prefix: str, entity: str, order_attr: str | None = None) -> APIRouter:
    router = APIRouter(prefix=f"/api/{prefix}", tags=[prefix])

    @router.get("")
    def list_items(session: Session = Depends(get_session)):
        stmt = select(model)
        stmt = stmt.order_by(getattr(model, order_attr) if order_attr else model.id)
        return session.exec(stmt).all()

    @router.get("/{item_id}")
    def get_item(item_id: int, session: Session = Depends(get_session)):
        obj = session.get(model, item_id)
        if not obj:
            raise HTTPException(404, f"{entity} {item_id} not found")
        return obj

    @router.post("", status_code=201)
    def create_item(body: dict, session: Session = Depends(get_session)):
        obj = model(**_clean(model, body))
        session.add(obj)
        session.flush()  # assign id before logging
        log_activity(session, entity, obj.id, "create", getattr(obj, "title", None) or getattr(obj, "name", None))
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, f"Constraint violation: {exc.orig}")
        session.refresh(obj)
        return obj

    @router.put("/{item_id}")
    def update_item(item_id: int, body: dict, session: Session = Depends(get_session)):
        obj = session.get(model, item_id)
        if not obj:
            raise HTTPException(404, f"{entity} {item_id} not found")
        changes = _clean(model, body)
        for key, value in changes.items():
            setattr(obj, key, value)
        session.add(obj)
        log_activity(session, entity, item_id, "update", ", ".join(changes) or None)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, f"Constraint violation: {exc.orig}")
        session.refresh(obj)
        return obj

    @router.delete("/{item_id}")
    def delete_item(item_id: int, session: Session = Depends(get_session)):
        obj = session.get(model, item_id)
        if not obj:
            raise HTTPException(404, f"{entity} {item_id} not found")
        session.delete(obj)
        log_activity(session, entity, item_id, "delete",
                     getattr(obj, "title", None) or getattr(obj, "name", None))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            # FKs are ON and nothing cascades: referenced rows refuse to die.
            raise HTTPException(409, f"{entity} {item_id} is referenced by other records")
        return {"ok": True, "deleted": item_id}

    return router
