"""
Catalogue articles — the wiki half of the merged Archive.

A single generic, namespaced entity that powers browse-by-category, the
article page with its Overview / Sources infobox, and the no-markup
create/edit flow from the v0.3 design. Backed by the `article` table
(migration 0006).

  GET    /api/v1/articles                 list (filters: namespace, q, civ_slug)
  GET    /api/v1/articles/namespaces      per-namespace counts (portal tiles)
  GET    /api/v1/articles/{slug}          detail (body + infobox + sources)
  POST   /api/v1/articles                 create  (team role: diplomat+)
  PATCH  /api/v1/articles/{slug}          edit    (team role: diplomat+)
  DELETE /api/v1/articles/{slug}          soft-delete (admin)

Civilizations are NOT articles — they keep their own richer table/page and
the live-atlas infobox. The system/planet namespaces are sourced from the
live Haven atlas in a later phase and are never authored here.

The catalogue is intentionally more open than the civ/person encyclopedia:
any team member (diplomat or higher) can create and edit, in the spirit of
"anyone in the Discord can improve this page." Each article carries its
infobox rows and source list as JSON on the row, so the wiki never has to
touch the existing entity_revision / source_citation CHECK constraints.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..deps import get_db, require_admin, require_team_role
from ..models.schemas import (
    ArticleDetail,
    ArticlePatch,
    ArticleSource,
    ArticleSummary,
    ArticleWrite,
    Author,
    Envelope,
    FacetDef,
    FacetSchema,
    InfoboxRow,
    Meta,
    NamespaceCount,
)
from ..facets import get_facets
from ..namespaces import ALL_NAMESPACES, is_article_namespace

router = APIRouter(prefix="/api/v1/articles", tags=["articles"])

_QUALITIES = ("primary", "secondary", "community", "rotted")


# ---------------------------------------------------------------------
# JSON column helpers
# ---------------------------------------------------------------------
def _loads(raw, default):
    if not raw:
        return default
    try:
        v = json.loads(raw)
        return v if v is not None else default
    except (TypeError, ValueError):
        return default


def _infobox_from_row(raw) -> list[InfoboxRow]:
    out: list[InfoboxRow] = []
    for item in _loads(raw, []):
        if isinstance(item, dict) and item.get("label"):
            out.append(InfoboxRow(label=str(item["label"]), value=str(item.get("value", ""))))
    return out


def _sources_from_row(raw) -> list[ArticleSource]:
    out: list[ArticleSource] = []
    for item in _loads(raw, []):
        if isinstance(item, dict) and item.get("text"):
            q = item.get("quality", "community")
            if q not in _QUALITIES:
                q = "community"
            out.append(ArticleSource(quality=q, text=str(item["text"]), url=item.get("url")))
    return out


def _check_civ(db: Session, civ_slug: Optional[str]) -> None:
    if civ_slug:
        exists = db.execute(
            text("SELECT 1 FROM civilization WHERE slug = :s AND deleted_at IS NULL"),
            {"s": civ_slug},
        ).first()
        if not exists:
            raise HTTPException(status_code=400, detail=f"civilization '{civ_slug}' not found")


def _read_facets(db: Session, article_id: int) -> dict[str, list[str]]:
    rows = db.execute(
        text("SELECT key, value FROM article_facet WHERE article_id = :a ORDER BY id"),
        {"a": article_id},
    ).fetchall()
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r.key, []).append(r.value)
    return out


def _write_facets(db: Session, article_id: int, facets) -> None:
    """Delete-and-reinsert this article's facet rows. Accepts a
    {key: [values] | value | bool} map; booleans store 'true' when set."""
    db.execute(text("DELETE FROM article_facet WHERE article_id = :a"), {"a": article_id})
    if not facets:
        return
    for key, vals in facets.items():
        if vals is None:
            continue
        if isinstance(vals, bool):
            vals = ["true"] if vals else []
        elif isinstance(vals, str):
            vals = [vals]
        for v in vals:
            sv = str(v).strip()
            if sv:
                db.execute(
                    text("INSERT INTO article_facet (article_id, key, value) VALUES (:a, :k, :v)"),
                    {"a": article_id, "k": str(key), "v": sv},
                )


# ---------------------------------------------------------------------
# GET /api/v1/articles — browse / list
# ---------------------------------------------------------------------
@router.get("", response_model=Envelope[list[ArticleSummary]])
def list_articles(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    namespace: Optional[str] = Query(None, max_length=40),
    q: Optional[str] = Query(None, min_length=2, max_length=120),
    civ_slug: Optional[str] = None,
    f: Optional[list[str]] = Query(None),
):
    where = "WHERE deleted_at IS NULL"
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if namespace:
        where += " AND namespace = :ns"
        params["ns"] = namespace
    if q:
        where += " AND (LOWER(title) LIKE :pat OR LOWER(subtitle) LIKE :pat OR LOWER(body) LIKE :pat)"
        params["pat"] = f"%{q.lower()}%"
    if civ_slug:
        where += " AND civ_slug = :civ"
        params["civ"] = civ_slug
    # Facet filters: repeated `f=key:value`. Values within one key OR;
    # different keys AND. Matched via EXISTS on article_facet.
    if f:
        groups: dict[str, list[str]] = {}
        for item in f:
            if ":" not in item:
                continue
            k, v = item.split(":", 1)
            k, v = k.strip(), v.strip()
            if k and v:
                groups.setdefault(k, []).append(v)
        for gi, (k, vals) in enumerate(groups.items()):
            ph = ",".join(f":fv{gi}_{j}" for j in range(len(vals)))
            where += (
                f" AND EXISTS (SELECT 1 FROM article_facet af{gi} "
                f"WHERE af{gi}.article_id = article.id AND af{gi}.key = :fk{gi} "
                f"AND af{gi}.value IN ({ph}))"
            )
            params[f"fk{gi}"] = k
            for j, v in enumerate(vals):
                params[f"fv{gi}_{j}"] = v
    total = db.execute(text(f"SELECT COUNT(*) FROM article {where}"), params).scalar() or 0
    rows = db.execute(
        text(
            f"SELECT id, namespace, slug, title, subtitle, civ_slug, updated_at "
            f"FROM article {where} "
            f"ORDER BY title ASC LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()
    # Attach facets for the page of results in one query (for card chips).
    ids = [r.id for r in rows]
    facets_by_id: dict[int, dict[str, list[str]]] = {}
    if ids:
        ph = ",".join(f":id{i}" for i in range(len(ids)))
        fparams = {f"id{i}": ids[i] for i in range(len(ids))}
        for fr in db.execute(
            text(f"SELECT article_id, key, value FROM article_facet WHERE article_id IN ({ph}) ORDER BY id"),
            fparams,
        ).fetchall():
            facets_by_id.setdefault(fr.article_id, {}).setdefault(fr.key, []).append(fr.value)
    data = [
        ArticleSummary(
            namespace=r.namespace, slug=r.slug, title=r.title,
            subtitle=r.subtitle, civ_slug=r.civ_slug, updated_at=r.updated_at,
            facets=facets_by_id.get(r.id, {}),
        )
        for r in rows
    ]
    return Envelope(
        data=data,
        meta=Meta(page=page, page_size=page_size, total=total,
                  extra={"namespace": namespace, "q": q}),
    )


# ---------------------------------------------------------------------
# GET /api/v1/articles/namespaces — portal tile counts
# (declared before /{slug} so the literal path wins the match)
# ---------------------------------------------------------------------
@router.get("/namespaces", response_model=Envelope[list[NamespaceCount]])
def namespace_counts(db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            "SELECT namespace, COUNT(*) AS n FROM article "
            "WHERE deleted_at IS NULL GROUP BY namespace"
        )
    ).fetchall()
    counts = {r.namespace: r.n for r in rows}
    # civ tiles count the civilization table, not article rows
    counts["civ"] = db.execute(
        text("SELECT COUNT(*) FROM civilization WHERE deleted_at IS NULL")
    ).scalar() or 0
    data = [NamespaceCount(namespace=ns, count=counts.get(ns, 0)) for ns in ALL_NAMESPACES]
    return Envelope(data=data, meta=Meta(total=len(data)))


# ---------------------------------------------------------------------
# GET /api/v1/articles/facets/{namespace} — the per-section filter schema
# (two path segments, so it never collides with /{slug})
# ---------------------------------------------------------------------
@router.get("/facets/{namespace}", response_model=Envelope[FacetSchema])
def article_facet_schema(namespace: str):
    defs = [FacetDef(**d) for d in get_facets(namespace)]
    return Envelope(data=FacetSchema(namespace=namespace, facets=defs))


# ---------------------------------------------------------------------
# GET /api/v1/articles/{slug}
# ---------------------------------------------------------------------
@router.get("/{slug}", response_model=Envelope[ArticleDetail])
def get_article(slug: str, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT a.id AS aid, a.namespace, a.slug, a.title, a.subtitle, a.body, "
            "a.infobox_json, a.sources_json, a.civ_slug, a.created_at, a.updated_at, "
            "u.id AS uid, u.discord_username AS uslug, u.display_name AS uname, "
            "u.avatar_letter, u.avatar_color, u.base_role "
            "FROM article a "
            "LEFT JOIN archive_user u ON u.id = a.created_by "
            "WHERE a.slug = :s AND a.deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="article not found")
    editor = (
        Author(
            id=row.uid, slug=row.uslug, name=row.uname,
            avatar_letter=row.avatar_letter, avatar_color=row.avatar_color,
            role=row.base_role,
        )
        if row.uid else None
    )
    return Envelope(data=ArticleDetail(
        namespace=row.namespace, slug=row.slug, title=row.title,
        subtitle=row.subtitle, civ_slug=row.civ_slug,
        created_at=row.created_at, updated_at=row.updated_at,
        body=row.body or "",
        infobox=_infobox_from_row(row.infobox_json),
        sources=_sources_from_row(row.sources_json),
        editor=editor,
        facets=_read_facets(db, row.aid),
    ))


# ---------------------------------------------------------------------
# POST /api/v1/articles — create (team role: diplomat+)
# ---------------------------------------------------------------------
@router.post("", response_model=Envelope[ArticleDetail], status_code=201)
def create_article(
    body: ArticleWrite,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
):
    if not is_article_namespace(body.namespace):
        raise HTTPException(
            status_code=400,
            detail=f"'{body.namespace}' is not a writable catalogue namespace",
        )
    if db.execute(text("SELECT 1 FROM article WHERE slug = :s"), {"s": body.slug}).first():
        raise HTTPException(status_code=409, detail=f"slug '{body.slug}' already exists")
    _check_civ(db, body.civ_slug)
    result = db.execute(
        text(
            "INSERT INTO article (namespace, slug, title, subtitle, body, "
            "infobox_json, sources_json, civ_slug, created_by) "
            "VALUES (:namespace, :slug, :title, :subtitle, :body, "
            ":infobox_json, :sources_json, :civ_slug, :created_by)"
        ),
        {
            "namespace": body.namespace,
            "slug": body.slug,
            "title": body.title,
            "subtitle": body.subtitle,
            "body": body.body or "",
            "infobox_json": json.dumps([r.model_dump() for r in body.infobox]),
            "sources_json": json.dumps([r.model_dump() for r in body.sources]),
            "civ_slug": body.civ_slug or None,
            "created_by": user["id"],
        },
    )
    aid = result.lastrowid
    _write_facets(db, aid, body.facets or {})
    log_audit(
        db, user["id"], "article.create", "article", aid,
        metadata={"slug": body.slug, "namespace": body.namespace},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return get_article(body.slug, db)


# ---------------------------------------------------------------------
# PATCH /api/v1/articles/{slug} — edit (team role: diplomat+)
# ---------------------------------------------------------------------
@router.patch("/{slug}", response_model=Envelope[ArticleDetail])
def patch_article(
    slug: str,
    patch: ArticlePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
):
    row = db.execute(
        text("SELECT id FROM article WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="article not found")

    fields = patch.model_dump(exclude_unset=True)
    col: dict = {}
    if "title" in fields:
        col["title"] = fields["title"]
    if "subtitle" in fields:
        col["subtitle"] = fields["subtitle"]
    if "body" in fields:
        col["body"] = fields["body"] or ""
    if "namespace" in fields:
        if not is_article_namespace(fields["namespace"]):
            raise HTTPException(
                status_code=400,
                detail=f"'{fields['namespace']}' is not a writable catalogue namespace",
            )
        col["namespace"] = fields["namespace"]
    if "civ_slug" in fields:
        cv = fields["civ_slug"] or None
        _check_civ(db, cv)
        col["civ_slug"] = cv
    if "infobox" in fields:
        col["infobox_json"] = json.dumps(fields["infobox"] or [])
    if "sources" in fields:
        col["sources_json"] = json.dumps(fields["sources"] or [])

    if col:
        sets = ", ".join(f"{k} = :{k}" for k in col)
        col["id"] = row.id
        db.execute(
            text(f"UPDATE article SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            col,
        )
    if "facets" in fields:
        _write_facets(db, row.id, fields["facets"] or {})
    changed = [k for k in col.keys() if k != "id"]
    log_audit(
        db, user["id"], "article.patch", "article", row.id,
        metadata={"slug": slug, "fields_changed": changed},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return get_article(slug, db)


# ---------------------------------------------------------------------
# DELETE /api/v1/articles/{slug} — soft-delete (admin)
# ---------------------------------------------------------------------
@router.delete("/{slug}", status_code=204)
def delete_article(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    row = db.execute(
        text("SELECT id FROM article WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="article not found")
    db.execute(
        text("UPDATE article SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"),
        {"id": row.id},
    )
    log_audit(
        db, user["id"], "article.delete", "article", row.id,
        metadata={"slug": slug},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return Response(status_code=204)
