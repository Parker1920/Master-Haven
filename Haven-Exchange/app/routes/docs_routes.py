"""
Travelers Exchange — Documentation Pages

Public docs hub and three full-page guides:

- GET /docs                    — index / hub with three doc cards
- GET /docs/learn              — power-user "Under the Hood" guide
- GET /docs/nation-leaders     — community-leader pitch document

All routes are publicly accessible (no login required) and serve
standalone marketing-style templates that do not extend ``base.html``.
The marketing templates have their own header/footer/nav layered on
``static/css/marketing-base.css`` plus ``static/css/docs.css``.

Kept in a separate module rather than ``page_routes.py`` because that
file already weighs in over 3,500 lines (per V2 audit notes).
"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates


# Templates dir matches the rest of the app.  Path is relative to the
# project root the way main.py mounts static files.
templates = Jinja2Templates(directory="app/templates")

router = APIRouter(tags=["docs"])


# ---------------------------------------------------------------------------
# GET /docs — Documentation hub
# ---------------------------------------------------------------------------
@router.get("/docs")
def docs_index(request: Request):
    """Hub page listing the three available docs (getting-started,
    under-the-hood, nation-leader-pitch).  Public.
    """
    return templates.TemplateResponse(
        "docs/index.html",
        {"request": request},
    )


# ---------------------------------------------------------------------------
# GET /docs/learn — Power-user / "Under the Hood" guide
# ---------------------------------------------------------------------------
@router.get("/docs/learn")
def docs_power_user(request: Request):
    """Long-form guide covering economy mechanics for power users and
    business operators.  Public.
    """
    return templates.TemplateResponse(
        "docs/power_user.html",
        {"request": request},
    )


# ---------------------------------------------------------------------------
# GET /docs/nation-leaders — Pitch / proposal document for NLs
# ---------------------------------------------------------------------------
@router.get("/docs/nation-leaders")
def docs_nation_leaders(request: Request):
    """Pitch / decision-aid for Discord community leaders considering
    bringing their community into the Travelers Exchange as a
    sovereign nation.  Public.
    """
    return templates.TemplateResponse(
        "docs/nation_leaders.html",
        {"request": request},
    )
