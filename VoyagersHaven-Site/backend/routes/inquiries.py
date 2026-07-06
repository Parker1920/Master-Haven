"""'Start a project' inquiries from the contact page.

A real, backend-backed contact form. Rows land in the `inquiries` table, a
notification fires (Discord/email, if configured), and the endpoint is rate
limited + honeypot-guarded against spam.
"""

import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field

from ..db import get_db
from ..ratelimit import check_rate_limit
from ..services.havenops import relay_inquiry
from ..services.notify import notify_new_inquiry

router = APIRouter()


class InquiryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=254)
    project_type: str | None = Field(default=None, max_length=80)
    budget: str | None = Field(default=None, max_length=80)
    message: str = Field(..., min_length=1, max_length=4000)
    # Honeypot: a hidden field real users never see. Bots fill it → we drop it.
    website: str | None = Field(default=None, max_length=200)


@router.post("/inquiries")
def create_inquiry(
    req: InquiryRequest,
    request: Request,
    background: BackgroundTasks,
    conn: sqlite3.Connection = Depends(get_db),
):
    check_rate_limit(request, "inquiries", limit=5, window_seconds=600)

    # Honeypot tripped → almost certainly a bot. Return success without storing
    # or notifying, so the bot believes it worked and moves on.
    if req.website:
        return {"ok": True, "id": 0}

    cur = conn.execute(
        """INSERT INTO inquiries (name, email, project_type, budget, message)
           VALUES (?, ?, ?, ?, ?)""",
        (req.name, req.email.strip(), req.project_type, req.budget, req.message),
    )
    inquiry_id = cur.lastrowid

    payload = {
        "id": inquiry_id,
        "name": req.name,
        "email": req.email.strip(),
        "project_type": req.project_type,
        "budget": req.budget,
        "message": req.message,
    }
    background.add_task(notify_new_inquiry, payload)
    # Haven Ops opens the engagement papertrail (client + engagement + frozen
    # intake record). Best-effort — never blocks or fails the visitor's form.
    background.add_task(relay_inquiry, payload)
    return {"ok": True, "id": inquiry_id}
