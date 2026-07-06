"""SQLModel table models — mirrors of the migration-owned schema.

The .sql migrations own the schema (create_all is never called); these
classes exist so the API layer can read/write it. Column sets must match
migrations/ exactly — when a migration adds a column, add it here too.

Conventions carried through from 001_init.sql: money in integer cents,
ISO8601 TEXT timestamps (NULL = "on file"), booleans as INTEGER 0/1.
"""
from sqlmodel import Field, SQLModel


class Company(SQLModel, table=True):
    __tablename__ = "company"
    id: int | None = Field(default=None, primary_key=True)  # singleton, always 1
    legal_name: str
    entity_no: str | None = None
    ein: str | None = None
    formed: str | None = None
    office: str | None = None
    naics: str | None = None
    oa_status: str | None = None
    capital_total_cents: int = 0
    capital_note: str | None = None
    bank: str | None = None
    esig_filename: str | None = None
    entity_type: str | None = None  # added by 002_company_entity_type.sql


class Person(SQLModel, table=True):
    __tablename__ = "people"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    role: str | None = None
    domain: str | None = None
    tags: str | None = None
    sort: int = 0


class Initiative(SQLModel, table=True):
    __tablename__ = "initiatives"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    status: str | None = None
    domain: str | None = None
    port: str | None = None
    priority: str | None = None
    note: str | None = None
    sort: int = 0


class EnvironmentItem(SQLModel, table=True):
    __tablename__ = "environment"
    id: int | None = Field(default=None, primary_key=True)
    item: str
    status: str | None = None
    sort: int = 0


class Flag(SQLModel, table=True):
    __tablename__ = "flags"
    id: int | None = Field(default=None, primary_key=True)
    title: str
    category: str | None = None
    status: str = "open"


class Client(SQLModel, table=True):
    __tablename__ = "clients"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    contact: str | None = None
    entity: str | None = None
    bill_to: str | None = None


class Engagement(SQLModel, table=True):
    __tablename__ = "engagements"
    id: int | None = Field(default=None, primary_key=True)
    code: str
    client_id: int
    title: str
    value_cents: int = 0
    state: str = "inquiry"  # inquiry → proposal → contract → in_progress → delivered → closed
    opened_at: str | None = None
    closed_at: str | None = None
    note: str | None = None


class Template(SQLModel, table=True):
    __tablename__ = "templates"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    kind: str | None = None
    status: str = "not built"


class DocumentGenerated(SQLModel, table=True):
    __tablename__ = "documents_generated"
    id: int | None = Field(default=None, primary_key=True)
    engagement_id: int | None = None
    doc_type: str
    title: str | None = None
    version: int = 1
    filename: str | None = None
    sha256: str | None = None  # NULL only on pre-app seeded records
    generated_at: str | None = None
    frozen: int = 1  # immutable once written; re-issue = new row + new file
    template_id: int | None = None
    origin: str = "seed"  # generated / uploaded / seed (see 004 migration)


class EngagementEvent(SQLModel, table=True):
    __tablename__ = "engagement_events"
    id: int | None = Field(default=None, primary_key=True)  # papertrail order
    engagement_id: int
    ts: str | None = None  # NULL = "on file"
    kind: str
    actor: str | None = None
    title: str
    detail: str | None = None
    document_id: int | None = None


class RequiredDoc(SQLModel, table=True):
    __tablename__ = "required_docs"
    id: int | None = Field(default=None, primary_key=True)
    doc_type: str
    label: str


class Account(SQLModel, table=True):
    __tablename__ = "accounts"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    kind: str | None = None
    balance_cents_manual: int | None = None
    status: str | None = None


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    id: int | None = Field(default=None, primary_key=True)
    account_id: int | None = None  # NULL = rail unconfirmed
    engagement_id: int | None = None
    amount_cents: int
    kind: str | None = None
    ts: str | None = None
    note: str | None = None
    rail: str | None = None


class Asset(SQLModel, table=True):
    __tablename__ = "assets"
    id: int | None = Field(default=None, primary_key=True)
    label: str
    category: str | None = None
    value_cents: int = 0
    documented: int = 0
    note: str | None = None
    document_id: int | None = None  # receipt scan (uploaded document row)


class Task(SQLModel, table=True):
    __tablename__ = "tasks"
    id: int | None = Field(default=None, primary_key=True)
    title: str
    detail: str | None = None
    done: int = 0
    owner: str | None = None
    due: str | None = None
    priority: str | None = None
    blocked_by: str | None = None
    category: str | None = None


class ComplianceItem(SQLModel, table=True):
    __tablename__ = "compliance_items"
    id: int | None = Field(default=None, primary_key=True)
    title: str
    detail: str | None = None
    due_date: str | None = None  # ISO date; NULL for asap/rolling (see kind)
    kind: str | None = None  # deadline / flag / rolling
    status: str = "open"


class ActivityLog(SQLModel, table=True):
    __tablename__ = "activity_log"
    id: int | None = Field(default=None, primary_key=True)
    ts: str
    actor: str | None = None
    entity: str | None = None
    entity_id: int | None = None
    action: str
    detail: str | None = None
