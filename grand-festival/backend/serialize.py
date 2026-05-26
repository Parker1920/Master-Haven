"""Row -> dict helpers shared by the public and admin routes."""

import sqlite3
from typing import Optional


def logo_url(filename: Optional[str]) -> Optional[str]:
    return f"/api/uploads/{filename}" if filename else None


def civ_public(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "role": row["role"],
        "description": row["description"],
        "status": row["status"],
        "logo_filename": row["logo_filename"],
        "logo_url": logo_url(row["logo_filename"]),
        "display_order": row["display_order"],
    }


def civ_admin(row: sqlite3.Row) -> dict:
    data = civ_public(row)
    data.update(
        {
            "submitter_discord": row["submitter_discord"],
            "submitter_notes": row["submitter_notes"],
            "approval_state": row["approval_state"],
            "created_at": row["created_at"],
            "approved_at": row["approved_at"],
            "updated_at": row["updated_at"],
        }
    )
    return data
