-- Grand Festival / Summer Unification Day — SQLite schema
-- Idempotent: safe to run on every startup.

CREATE TABLE IF NOT EXISTS civilizations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    role            TEXT    NOT NULL,            -- e.g. "Pavilion District", "Festival Coordinator"
    description     TEXT    NOT NULL,
    status          TEXT    NOT NULL CHECK (status IN ('host', 'confirmed', 'tentative')),
    logo_filename   TEXT,                        -- e.g. "voyagers-haven.webp" — file lives in /uploads
    submitter_discord TEXT,                      -- Discord handle of person submitting
    submitter_notes TEXT,                        -- "We'd love to bring our cartographer team..."
    approval_state  TEXT NOT NULL DEFAULT 'pending'
                    CHECK (approval_state IN ('pending', 'approved', 'rejected')),
    display_order   INTEGER DEFAULT 100,         -- Admin can reorder; lower = earlier
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    approved_at     DATETIME,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_civ_approval ON civilizations(approval_state);
CREATE INDEX IF NOT EXISTS idx_civ_status   ON civilizations(status);

-- Trigger to bump updated_at on UPDATE
CREATE TRIGGER IF NOT EXISTS civ_updated_at
AFTER UPDATE ON civilizations
BEGIN
    UPDATE civilizations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Audit log
CREATE TABLE IF NOT EXISTS admin_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT    NOT NULL,                -- 'approved', 'rejected', 'edited', 'deleted'
    target_id   INTEGER,                         -- civilizations.id
    target_type TEXT    DEFAULT 'civilization',
    notes       TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
