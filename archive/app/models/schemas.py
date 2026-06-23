"""
Pydantic v2 schemas for API responses.

One consolidated file covering every resource. Split into per-resource
files if/when this gets unwieldy (probably Phase 4 when writes are
added and request schemas appear).

Conventions:
- Every list endpoint returns Envelope[list[T]] with meta carrying
  pagination + count
- Every detail endpoint returns Envelope[T] with empty meta
- Summary models are card-shaped (no body); Detail models include body
- Field names match what the v0.9 mockup's frontend expects so the
  Phase 5 rebuild has no impedance mismatch
"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------
T = TypeVar("T")


class Meta(BaseModel):
    # Pagination fields are present on list responses, absent on detail.
    page: Optional[int] = None
    page_size: Optional[int] = None
    total: Optional[int] = None
    # Free-form extras (filter echo, search query, etc.)
    extra: Optional[dict[str, Any]] = None


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Meta = Field(default_factory=Meta)


# ---------------------------------------------------------------------
# Author / byline (compact user fragment shown on stories, inquisitions)
# ---------------------------------------------------------------------
class Author(BaseModel):
    id: int
    slug: str                              # the user's discord_username, used in URL
    name: str                              # display_name
    avatar_letter: Optional[str] = None
    avatar_color: Optional[str] = None
    role: Optional[str] = None             # base_role: reader/diplomat/historian


# ---------------------------------------------------------------------
# Civilizations
# ---------------------------------------------------------------------
class CivStats(BaseModel):
    entries: int = 0                       # stories + inquisitions
    inquisitions: int = 0
    people: int = 0
    years: int = 0


class CivilizationSummary(BaseModel):
    slug: str
    name: str
    status: str                            # active / dormant / archived
    galaxy: Optional[str] = None
    founded: Optional[str] = None
    ended: Optional[str] = None
    tagline: Optional[str] = None
    color_primary: str
    color_secondary: str
    stats: CivStats


class CivilizationDetail(CivilizationSummary):
    description: Optional[str] = None
    founded_year: Optional[int] = None
    ended_year: Optional[int] = None


# ---------------------------------------------------------------------
# Live atlas data (synced from the main Haven control-room API)
# ---------------------------------------------------------------------
class AtlasCivStats(BaseModel):
    """Per-civilization live figures, cached from Haven. `matched` is
    False when no Haven community could be tied to this civ."""
    matched: bool = False
    haven_tag: Optional[str] = None
    display_name: Optional[str] = None
    total_systems: int = 0
    total_discoveries: int = 0
    unique_contributors: int = 0
    manual_systems: int = 0
    extractor_systems: int = 0
    synced_at: Optional[str] = None


class AtlasSummary(BaseModel):
    """Global atlas totals for the masthead/home live strip."""
    total_systems: int = 0
    total_discoveries: int = 0
    total_communities: int = 0
    total_contributors: int = 0
    synced_at: Optional[str] = None


class SyncRunStatus(BaseModel):
    """Last sync attempt + current sync configuration."""
    source: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    ok: Optional[bool] = None
    communities_synced: Optional[int] = None
    error: Optional[str] = None
    enabled: bool = True
    interval_minutes: int = 30
    api_base: Optional[str] = None


# Coverage = combined stories + inquisitions list for one civ
class CoverageItem(BaseModel):
    # 'story' or 'inquisition' so the frontend can route to the right page
    kind: str
    id: int
    slug: Optional[str] = None
    doctype: Optional[str] = None          # brief / feature / inquisition
    headline: str                          # title for inquisitions, headline for stories
    deck: Optional[str] = None
    beat: Optional[str] = None
    published_at: Optional[str] = None     # for stories
    started_at: Optional[str] = None       # for inquisitions
    numeral: Optional[str] = None          # for inquisitions
    state: Optional[str] = None            # for inquisitions
    author: Optional[Author] = None        # primary author


# ---------------------------------------------------------------------
# People
# ---------------------------------------------------------------------
class PersonDetail(BaseModel):
    slug: str
    name: str
    discord_username: Optional[str] = None
    civ_slug: Optional[str] = None
    role_in_civ: Optional[str] = None
    bio: Optional[str] = None


# ---------------------------------------------------------------------
# Events (historical events, not the archive_user kind)
# ---------------------------------------------------------------------
class EventDetail(BaseModel):
    slug: str
    title: str
    event_date: Optional[str] = None
    event_year: Optional[int] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------
# Places
# ---------------------------------------------------------------------
class PlaceDetail(BaseModel):
    slug: str
    name: str
    galaxy: Optional[str] = None
    region: Optional[str] = None
    coordinates: Optional[str] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------
# Stories
# ---------------------------------------------------------------------
class StorySummary(BaseModel):
    id: int
    slug: str
    doctype: str                           # brief / feature
    headline: str
    deck: Optional[str] = None
    beat: Optional[str] = None
    civs: list[str] = Field(default_factory=list)   # civ slugs
    author: Author
    published_at: str
    read_minutes: Optional[int] = None


class StoryDetail(StorySummary):
    body: str


# ---------------------------------------------------------------------
# Inquisitions
# ---------------------------------------------------------------------
class InquisitionSummary(BaseModel):
    id: int
    slug: str
    numeral: str
    title: str
    subtitle: Optional[str] = None
    deck: Optional[str] = None
    state: str                             # in_progress / closed / archived
    progress: int
    sources_count: int
    started_at: str
    closed_at: Optional[str] = None
    authors: list[Author] = Field(default_factory=list)
    civs: list[str] = Field(default_factory=list)


class InquisitionDetail(InquisitionSummary):
    body: str


# ---------------------------------------------------------------------
# Timeline (mixed stream)
# ---------------------------------------------------------------------
class TimelineEntry(BaseModel):
    # 'event' (historical event), 'story' (publication date), 'inquisition' (start)
    kind: str
    date: str                              # ISO date or year-only display string
    year: Optional[int] = None
    title: str
    slug: Optional[str] = None
    id: Optional[int] = None
    doctype: Optional[str] = None
    civs: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------
class SearchHit(BaseModel):
    # 'story' / 'inquisition' / 'civilization' / 'person'
    kind: str
    id: int
    slug: str
    title: str                             # headline / title / name
    snippet: Optional[str] = None          # ~120 chars of context


# =====================================================================
# Phase 4: Drafts
# =====================================================================

class DraftCoauthor(BaseModel):
    user_id: int
    slug: str                              # discord_username
    name: str
    avatar_letter: Optional[str] = None
    avatar_color: Optional[str] = None


class DraftSummary(BaseModel):
    id: int
    doctype: str                           # brief / feature / inquisition
    headline: Optional[str] = None
    deck: Optional[str] = None
    beat: Optional[str] = None
    numeral: Optional[str] = None          # inquisitions only
    status: str                            # draft / in_review / returned / ready / published
    author: Author
    coauthors: list[DraftCoauthor] = Field(default_factory=list)
    civs: list[str] = Field(default_factory=list)
    last_edited_at: str
    created_at: str
    reviewed_by_id: Optional[int] = None
    reviewed_at: Optional[str] = None


class DraftDetail(DraftSummary):
    body: str
    published_as_story_id: Optional[int] = None
    published_as_inquisition_id: Optional[int] = None


class DraftCreate(BaseModel):
    doctype: str = Field(..., pattern="^(brief|feature|inquisition)$")
    headline: Optional[str] = None
    deck: Optional[str] = None
    body: Optional[str] = ""
    beat: Optional[str] = None
    civs: list[str] = Field(default_factory=list)
    # numeral: optional for inquisitions; auto-assigned if missing
    numeral: Optional[str] = None


class DraftPatch(BaseModel):
    """Every field optional — auto-save sends partial updates."""
    headline: Optional[str] = None
    deck: Optional[str] = None
    body: Optional[str] = None
    beat: Optional[str] = None
    civs: Optional[list[str]] = None


class CoauthorAdd(BaseModel):
    user_id: int


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)
    quoted_text: Optional[str] = None


class CommentDetail(BaseModel):
    id: int
    draft_id: int
    author: Author
    body: str
    quoted_text: Optional[str] = None
    created_at: str


# =====================================================================
# Phase 4: Notifications
# =====================================================================

class NotificationDetail(BaseModel):
    id: int
    type: str
    title: str
    body: Optional[str] = None
    link: Optional[str] = None
    related_draft_id: Optional[int] = None
    related_user_id: Optional[int] = None
    is_read: bool
    created_at: str


# =====================================================================
# Phase 4: Watchlist
# =====================================================================

class WatchlistAdd(BaseModel):
    target_type: str = Field(..., pattern="^(civilization|person|event|place|inquisition|user)$")
    target_id: int


class WatchlistItem(BaseModel):
    id: int
    target_type: str
    target_id: int
    created_at: str


# =====================================================================
# Phase 4: Entity writes (civilizations / people / events / places)
# =====================================================================

class CivilizationWrite(BaseModel):
    slug: str = Field(..., pattern="^[a-z0-9][a-z0-9-]{0,63}$")
    name: str = Field(..., min_length=1, max_length=200)
    status: str = Field("active", pattern="^(active|dormant|archived)$")
    galaxy: Optional[str] = None
    founded: Optional[str] = None
    founded_year: Optional[int] = None
    ended: Optional[str] = None
    ended_year: Optional[int] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    color_primary: str = "#534AB7"
    color_secondary: str = "#1D9E75"


class CivilizationPatch(BaseModel):
    """All fields optional. slug is immutable — change requires delete+create."""
    name: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|dormant|archived)$")
    galaxy: Optional[str] = None
    founded: Optional[str] = None
    founded_year: Optional[int] = None
    ended: Optional[str] = None
    ended_year: Optional[int] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None


class PersonWrite(BaseModel):
    slug: str = Field(..., pattern="^[a-z0-9][a-z0-9-]{0,63}$")
    name: str = Field(..., min_length=1, max_length=200)
    discord_username: Optional[str] = None
    civ_slug: Optional[str] = None
    role_in_civ: Optional[str] = None
    bio: Optional[str] = None


class PersonPatch(BaseModel):
    name: Optional[str] = None
    discord_username: Optional[str] = None
    civ_slug: Optional[str] = None
    role_in_civ: Optional[str] = None
    bio: Optional[str] = None


class EventWrite(BaseModel):
    slug: str = Field(..., pattern="^[a-z0-9][a-z0-9-]{0,63}$")
    title: str = Field(..., min_length=1, max_length=200)
    event_date: Optional[str] = None
    event_year: Optional[int] = None
    description: Optional[str] = None


class EventPatch(BaseModel):
    title: Optional[str] = None
    event_date: Optional[str] = None
    event_year: Optional[int] = None
    description: Optional[str] = None


class PlaceWrite(BaseModel):
    slug: str = Field(..., pattern="^[a-z0-9][a-z0-9-]{0,63}$")
    name: str = Field(..., min_length=1, max_length=200)
    galaxy: Optional[str] = None
    region: Optional[str] = None
    coordinates: Optional[str] = None
    description: Optional[str] = None


class PlacePatch(BaseModel):
    name: Optional[str] = None
    galaxy: Optional[str] = None
    region: Optional[str] = None
    coordinates: Optional[str] = None
    description: Optional[str] = None


class RevisionEntry(BaseModel):
    id: int
    changed_by: Author
    change_summary: Optional[str] = None
    snapshot: dict[str, Any]
    created_at: str


# =====================================================================
# Admin: user management
# =====================================================================

class AdminUserRow(BaseModel):
    id: int
    discord_username: str
    display_name: str
    avatar_letter: Optional[str] = None
    avatar_color: Optional[str] = None
    base_role: str                         # reader / diplomat / historian
    is_editor: bool
    is_admin: bool
    is_suspended: bool = False
    civ_slug: Optional[str] = None
    beat: Optional[str] = None
    created_at: str


class AdminUserPatch(BaseModel):
    base_role: Optional[str] = Field(None, pattern="^(reader|diplomat|historian)$")
    is_editor: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_suspended: Optional[bool] = None
    civ_slug: Optional[str] = None
    beat: Optional[str] = None
    display_name: Optional[str] = None


# =====================================================================
# Self-edit profile (PATCH /auth/me)
# =====================================================================

class SelfProfilePatch(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    bio: Optional[str] = None
    civ_slug: Optional[str] = None
    beat: Optional[str] = None
    avatar_letter: Optional[str] = Field(None, max_length=2)
    avatar_color: Optional[str] = None


# =====================================================================
# Sources & citations (Phase 4)
# =====================================================================

class SourceWrite(BaseModel):
    title: str = Field(..., min_length=1, max_length=400)
    url: Optional[str] = Field(None, max_length=2000)
    source_type: str = Field(..., pattern="^(discord|reddit|forum|wiki|video|screenshot|interview|other)$")
    quality: str = Field("community", pattern="^(primary|secondary|community|rotted)$")
    notes: Optional[str] = None
    archived_url: Optional[str] = Field(None, max_length=2000)


class SourceDetail(BaseModel):
    id: int
    title: str
    url: Optional[str] = None
    source_type: str
    quality: str
    notes: Optional[str] = None
    archived_url: Optional[str] = None
    added_by_id: Optional[int] = None
    added_by_name: Optional[str] = None
    created_at: str


class SourceCitationCreate(BaseModel):
    source_id: int
    target_type: str = Field(..., pattern="^(inquisition|civilization|person|event|place)$")
    target_id: int
    note: Optional[str] = None


class SourceCitation(BaseModel):
    id: int
    source_id: int
    source: SourceDetail
    target_type: str
    target_id: int
    note: Optional[str] = None
    created_at: str


# =====================================================================
# Inquisition lifecycle (Phase 4)
# =====================================================================

class InquisitionPatch(BaseModel):
    """Partial update of an inquisition lifecycle row."""
    title: Optional[str] = Field(None, min_length=1, max_length=400)
    subtitle: Optional[str] = None
    deck: Optional[str] = None
    body: Optional[str] = None
    state: Optional[str] = Field(None, pattern="^(in_progress|closed|archived)$")
    progress: Optional[int] = Field(None, ge=0, le=100)
    sources_count: Optional[int] = Field(None, ge=0)


# =====================================================================
# Story PATCH (Phase 4)
# =====================================================================

class StoryPatch(BaseModel):
    headline: Optional[str] = Field(None, min_length=1, max_length=400)
    deck: Optional[str] = None
    body: Optional[str] = None
    beat: Optional[str] = None
    civs: Optional[list[str]] = None


# =====================================================================
# Admin user suspension
# =====================================================================

class AdminUserSuspendPatch(BaseModel):
    is_suspended: Optional[bool] = None


# =====================================================================
# Media upload response
# =====================================================================

class MediaUploadResponse(BaseModel):
    id: int
    filename: str
    url: str
    mime_type: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    alt_text: Optional[str] = None
    created_at: str
