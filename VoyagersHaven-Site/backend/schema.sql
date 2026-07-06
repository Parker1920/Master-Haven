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

-- Merch / shop products. Prices in integer cents. Admin-managed.
CREATE TABLE IF NOT EXISTS products (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    description       TEXT,
    price_cents       INTEGER NOT NULL,
    image_url         TEXT,
    active            INTEGER NOT NULL DEFAULT 1,   -- shown in the shop
    requires_shipping INTEGER NOT NULL DEFAULT 1,   -- physical good → collect address
    sort_order        INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_products_active ON products(active, sort_order);

-- Merch orders — one row per completed purchase, with the customer + ship-to
-- info captured from Stripe (live) or the collected form (simulated).
CREATE TABLE IF NOT EXISTS orders (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_reference TEXT,
    item_label        TEXT,
    amount_cents      INTEGER NOT NULL,
    currency          TEXT NOT NULL DEFAULT 'usd',
    customer_name     TEXT,
    customer_email    TEXT,
    customer_phone    TEXT,
    ship_line1        TEXT,
    ship_line2        TEXT,
    ship_city         TEXT,
    ship_state        TEXT,
    ship_postal       TEXT,
    ship_country      TEXT,
    fulfilled         INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);

-- Client invoices. In live mode these mirror a Stripe Invoice (Option C —
-- Stripe auto-numbers, emails, PDFs, and tracks payment). In simulated mode
-- they're local-only records with a VH-YYYY-NNN number so the admin flow is
-- iterable without Stripe.
CREATE TABLE IF NOT EXISTS invoices (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    number             TEXT,
    stripe_invoice_id  TEXT,
    customer_name      TEXT,
    customer_email     TEXT NOT NULL,
    description        TEXT,
    amount_cents       INTEGER NOT NULL,
    currency           TEXT NOT NULL DEFAULT 'usd',
    status             TEXT NOT NULL DEFAULT 'draft',   -- draft | open | paid | void
    hosted_invoice_url TEXT,
    pdf_url            TEXT,
    provider           TEXT NOT NULL DEFAULT 'simulated', -- simulated | stripe
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    paid_at            TEXT
);

CREATE INDEX IF NOT EXISTS idx_invoices_created ON invoices(created_at);
