-- Voyager's Haven — studio site schema.
-- Idempotent: every statement is CREATE ... IF NOT EXISTS so init_db() can
-- run it on every boot. The DB file lives OUTSIDE the repo/image on the host
-- (see db.py) so pulls/rebuilds never touch it.

-- Support contributions + client invoice payments. amount is stored in cents
-- so we never carry float rounding through the money path.
CREATE TABLE IF NOT EXISTS payments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    reference           TEXT NOT NULL UNIQUE,          -- HVN-XXXX / HVN-INV-XXXX
    kind                TEXT NOT NULL,                 -- 'support' | 'invoice'
    amount_cents        INTEGER NOT NULL,
    currency            TEXT NOT NULL DEFAULT 'usd',
    invoice_number      TEXT,                          -- set when kind='invoice'
    email               TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',   -- pending | paid | failed
    provider            TEXT NOT NULL DEFAULT 'simulated', -- simulated | stripe
    provider_session_id TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    paid_at             TEXT
);

CREATE INDEX IF NOT EXISTS idx_payments_status  ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_created ON payments(created_at);

-- "Start a project" inquiries from the hire section.
CREATE TABLE IF NOT EXISTS inquiries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    email        TEXT NOT NULL,
    project_type TEXT,
    budget       TEXT,
    message      TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    handled      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_inquiries_created ON inquiries(created_at);
