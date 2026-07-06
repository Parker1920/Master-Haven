-- 001_init.sql — Haven Ops initial schema.
--
-- Conventions (locked by the Phase 1 dispatch):
--   * ids are INTEGER PRIMARY KEY (SQLite rowid)
--   * money is integer CENTS, never floats
--   * timestamps are ISO8601 TEXT; NULL means "on file, exact date unknown"
--     (this is a record-keeping app — we don't fabricate dates)
--   * booleans are INTEGER 0/1
--   * NO ON DELETE CASCADE anywhere: records here are deleted deliberately
--     or not at all, and frozen documents are immutable
--
-- schema_version is bootstrapped by migrate.py before any migration runs;
-- declared here too (IF NOT EXISTS) so the schema file reads complete.
CREATE TABLE IF NOT EXISTS schema_version (
    version    TEXT PRIMARY KEY,          -- migration filename, e.g. 001_init.sql
    applied_at TEXT NOT NULL
);

-- ── Reference layer (Company screen; feeds the emitted Project Instructions) ─

CREATE TABLE company (
    id                  INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton
    legal_name          TEXT NOT NULL,
    entity_no           TEXT,
    ein                 TEXT,
    formed              TEXT,
    office              TEXT,
    naics               TEXT,
    oa_status           TEXT,
    capital_total_cents INTEGER NOT NULL DEFAULT 0,
    capital_note        TEXT,
    bank                TEXT,
    esig_filename       TEXT               -- file lives in DATA_DIR, never the repo
);

CREATE TABLE people (
    id     INTEGER PRIMARY KEY,
    name   TEXT NOT NULL,
    role   TEXT,
    domain TEXT,
    tags   TEXT,                           -- e.g. 'co-owner (pending)', 'external'
    sort   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE initiatives (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    status   TEXT,                         -- live / build / draft / paper / conflict / …
    domain   TEXT,                         -- host or URL
    port     TEXT,
    priority TEXT,                         -- P0…P4 where assigned
    note     TEXT,
    sort     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE environment (
    id     INTEGER PRIMARY KEY,
    item   TEXT NOT NULL,
    status TEXT,
    sort   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE flags (
    id       INTEGER PRIMARY KEY,
    title    TEXT NOT NULL,
    category TEXT,                         -- compliance / security / legal / infra / …
    status   TEXT NOT NULL DEFAULT 'open'  -- open / resolved
);

-- ── Engagements (client work lifecycle + immutable papertrail) ───────────────

CREATE TABLE clients (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    contact TEXT,
    entity  TEXT,
    bill_to TEXT
);

CREATE TABLE engagements (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,      -- VHAV-C-YYYY-NNN
    client_id   INTEGER NOT NULL REFERENCES clients(id),
    title       TEXT NOT NULL,
    value_cents INTEGER NOT NULL DEFAULT 0,
    -- lifecycle: inquiry → proposal → contract → in_progress → delivered → closed
    state       TEXT NOT NULL DEFAULT 'inquiry',
    opened_at   TEXT,
    closed_at   TEXT,
    note        TEXT
);

CREATE TABLE templates (
    id     INTEGER PRIMARY KEY,
    name   TEXT NOT NULL,
    kind   TEXT,                           -- sow / msa / nda / invoice / completion / …
    status TEXT NOT NULL DEFAULT 'not built'
);

CREATE TABLE documents_generated (
    id            INTEGER PRIMARY KEY,
    engagement_id INTEGER REFERENCES engagements(id),
    doc_type      TEXT NOT NULL,           -- matches required_docs.doc_type
    title         TEXT,
    version       INTEGER NOT NULL DEFAULT 1,
    filename      TEXT,                    -- under DATA_DIR/uploads/generated/
    sha256        TEXT,                    -- NULL only for pre-app seeded records
    generated_at  TEXT,
    frozen        INTEGER NOT NULL DEFAULT 1,  -- frozen docs are NEVER regenerated;
                                               -- a re-issue is a new row + new file
    template_id   INTEGER REFERENCES templates(id)
);

CREATE TABLE engagement_events (
    id            INTEGER PRIMARY KEY,     -- papertrail order = id order
    engagement_id INTEGER NOT NULL REFERENCES engagements(id),
    ts            TEXT,                    -- NULL = 'on file'
    kind          TEXT NOT NULL,           -- inquiry / proposal / contract / signature /
                                           -- delivery / invoice / payment / receipt /
                                           -- closed / gap
    actor         TEXT,
    title         TEXT NOT NULL,
    detail        TEXT,
    document_id   INTEGER REFERENCES documents_generated(id)
);

CREATE TABLE required_docs (
    id       INTEGER PRIMARY KEY,
    doc_type TEXT NOT NULL UNIQUE,
    label    TEXT NOT NULL
);

-- ── Ledger ───────────────────────────────────────────────────────────────────

CREATE TABLE accounts (
    id                   INTEGER PRIMARY KEY,
    name                 TEXT NOT NULL,
    kind                 TEXT,             -- bank / processor / exchange-paper
    balance_cents_manual INTEGER,          -- NULL = unknown (no live money feeds in Phase 1)
    status               TEXT
);

CREATE TABLE transactions (
    id            INTEGER PRIMARY KEY,
    account_id    INTEGER REFERENCES accounts(id),   -- NULL = rail unconfirmed
    engagement_id INTEGER REFERENCES engagements(id),
    amount_cents  INTEGER NOT NULL,        -- signed: inflow positive
    kind          TEXT,                    -- payment / expense / transfer / …
    ts            TEXT,
    note          TEXT,
    rail          TEXT                     -- how the money moved; 'on file' if unconfirmed
);

CREATE TABLE assets (
    id          INTEGER PRIMARY KEY,
    label       TEXT NOT NULL,
    category    TEXT,                      -- capital (Schedule A) / equipment / …
    value_cents INTEGER NOT NULL DEFAULT 0,
    documented  INTEGER NOT NULL DEFAULT 0,
    note        TEXT
);

-- ── Compliance / workflow ────────────────────────────────────────────────────

CREATE TABLE tasks (
    id         INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    detail     TEXT,
    done       INTEGER NOT NULL DEFAULT 0,
    owner      TEXT,
    due        TEXT,                       -- ISO date, or a label like 'ASAP'
    priority   TEXT,
    blocked_by TEXT,
    category   TEXT
);

CREATE TABLE compliance_items (
    id       INTEGER PRIMARY KEY,
    title    TEXT NOT NULL,
    detail   TEXT,
    due_date TEXT,                         -- ISO date; NULL for asap/rolling (see kind)
    kind     TEXT,                         -- deadline / flag / rolling
    status   TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE activity_log (
    id        INTEGER PRIMARY KEY,
    ts        TEXT NOT NULL,
    actor     TEXT,
    entity    TEXT,                        -- table/kind the action touched
    entity_id INTEGER,
    action    TEXT NOT NULL,               -- create / update / delete / generate / seed
    detail    TEXT
);

-- ── Indexes on the hot lookups ───────────────────────────────────────────────
CREATE INDEX idx_events_engagement ON engagement_events(engagement_id);
CREATE INDEX idx_docs_engagement   ON documents_generated(engagement_id);
CREATE INDEX idx_tx_engagement     ON transactions(engagement_id);
CREATE INDEX idx_tx_account        ON transactions(account_id);
CREATE INDEX idx_activity_ts       ON activity_log(ts);
