"""Pydantic schemas for request/response bodies.

Civ submission itself arrives as multipart/form-data (optional logo file),
so that endpoint parses Form(...) fields directly — see routes/submit.py.
"""

from typing import Literal, Optional

from pydantic import BaseModel

CivStatus = Literal["host", "confirmed", "tentative"]
ApprovalState = Literal["pending", "approved", "rejected"]


class CivPublic(BaseModel):
    """Shape returned to the public site (approved civs only)."""

    id: int
    name: str
    role: str
    description: str
    status: CivStatus
    logo_filename: Optional[str] = None
    logo_url: Optional[str] = None
    display_order: int = 100


class CivAdmin(CivPublic):
    """Full shape for the admin dashboard (includes submitter + workflow fields)."""

    submitter_discord: Optional[str] = None
    submitter_notes: Optional[str] = None
    approval_state: ApprovalState
    created_at: Optional[str] = None
    approved_at: Optional[str] = None
    updated_at: Optional[str] = None


class CivPatch(BaseModel):
    """Admin edit — any subset of these fields may be sent."""

    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CivStatus] = None
    display_order: Optional[int] = None
    approval_state: Optional[ApprovalState] = None


class AdminLogin(BaseModel):
    password: str


class RejectBody(BaseModel):
    notes: Optional[str] = None
