"""Phase 1 seed — the real opening state of Voyager's Haven LLC.

Source of truth: HAVEN_STATE in mockup v0.7 + the Stage 1 dispatch seed list.

Idempotent: each table is seeded ONLY when that table is empty, so re-running
(or every app startup) never duplicates rows and never clobbers live edits.
Run AFTER migrate (startup does both in order).

Run manually:   python -m app.seed
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .migrate import connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def _insert(conn: sqlite3.Connection, table: str, cols: tuple[str, ...], rows: list[tuple]) -> int:
    placeholders = ", ".join("?" * len(cols))
    conn.executemany(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})", rows
    )
    return len(rows)


def seed_if_empty(db_path: Path | None = None) -> dict[str, int]:
    """Seed every empty table; returns {table: rows_inserted}."""
    conn = connect(db_path or settings.db_path)
    seeded: dict[str, int] = {}

    def do(table: str, cols: tuple[str, ...], rows: list[tuple]) -> None:
        if _empty(conn, table):
            seeded[table] = _insert(conn, table, cols, rows)
        else:
            print(f"[seed] {table}: has data, skipped")

    try:
        conn.execute("BEGIN")

        # ── Company (singleton) ──────────────────────────────────────────────
        do("company",
           ("id", "legal_name", "entity_type", "entity_no", "ein", "formed", "office",
            "naics", "oa_status", "capital_total_cents", "capital_note", "bank",
            "esig_filename"),
           [(1, "Voyager's Haven LLC", "PA single-member LLC", "15616488",
             "42-3445343", "June 2026", "Mechanicsburg, PA",
             "541511 · 541512 · 541519 · 518210",
             "Executed Jun 26, 2026", 3150093,
             "cash $500 · IP 740hrs×$40=$29,600 · equipment+domains $1,400.93 "
             "(itemize + veil check)",
             "Members 1st FCU — approved, details Monday", "signature.png")])

        # ── People ───────────────────────────────────────────────────────────
        # Rows 9-10 (Had.Sh, AGT) aren't in the dispatch's 8-row list but ARE in
        # HAVEN_STATE.people ("Partners: …") — kept so the Stage 2 emit can
        # reproduce the Key People line without losing the partner communities.
        do("people",
           ("name", "role", "domain", "tags", "sort"),
           [("Stars", "Chief of Staff · Dir. Cartography", "cartography", "co-owner (pending)", 1),
            ("Watcher", "Lead Diplomat", "diplomacy", None, 2),
            ("Lucca", "Co-lead Diplomat", "diplomacy", None, 3),
            ("Jaina", "Diplomat · Bot dev", "diplomacy · engineering", None, 4),
            ("Todd", "Power user · Support", "support", None, 5),
            ("Shadow", "Diplomat · Mod tester", "diplomacy · testing", None, 6),
            ("Jade", "Events · Xenobiology", "events", None, 7),
            ("art3mis (Owen Gaffney)", "Viobot · first client", "client", "external", 8),
            ("Had.Sh", "Partner community", "partners", "partner", 9),
            ("AGT", "Partner community", "partners", "partner", 10)])

        # ── Initiatives (the 12 from HAVEN_STATE.initiatives, in order) ──────
        do("initiatives",
           ("name", "status", "domain", "port", "priority", "note", "sort"),
           [("Haven Control Room", "live", "havenmap.online", None, None,
             "Live atlas; 2.0 retheme rolling · v1.69.0", 1),
            ("Haven Ops", "build", None, "8090", None,
             "Internal LLC admin / record-keeping app; mockup v0.7 is the design contract; Phase 1 in build", 2),
            ("Travelers Collective", "live", None, "8010", None,
             "Federated DB, Phase A live. Postgres → SQLite pivot locked. ⚠ port collision", 3),
            ("Travelers Archive", "build", "travelersarchive.online", None, "P1",
             "Newsroom/encyclopedia; SQLite; spec-complete, not built", 4),
            ("Travelers Exchange", "conflict", "travelers-exchange.online", "8010", None,
             "Economy, live. Rule: exclude from LLC/HTE/homelab. ⚠ verify vs Schedule A", 5),
            ("Viobot dashboard", "delivered", "viobot.havenmap.online", None, None,
             "VHAV-C-2026-001 deliverable; standalone", 6),
            ("NMS10 microsite", "launch-prep", "nms10.online", None, "P2",
             "HEAD 39f0f4e; sessions 1–4 done; hard launch ~July 9", 7),
            ("Grand Festival", "live", "grandfest.online", "8082", None,
             "Multi-race celebration · ⚠ port collision w/ NMS10", 8),
            ("Haven Outpost", "mockup", None, None, "P3/4",
             "Merch · v0.3 mockup", 9),
            ("HTE", "paper", "Kraken", None, None,
             "Grid engine, paper-trading; Layer 2 not trained", 10),
            ("Haven Brain", "live", "localhost:3001", None, None,
             "Local AI", 11),
            ("Skyscraper ARG", "live", "skyscraper.havenmap.online", None, None,
             None, 12)])

        # ── Environment ──────────────────────────────────────────────────────
        do("environment",
           ("item", "status", "sort"),
           [("Haven Control Room", "LIVE v1.69.0 — 13.7k sys / 32.9k planets / 256 galaxies", 1),
            ("Haven Ops", "Phase 1 in build", 2),
            ("Studio site", "voyagershaven.online — v0.6 mockup, not launched", 3),
            ("Extractor Mod", "v1.6.7 — ⚠ verify current status", 4),
            ("Repo", "⚠ CONFIRM public/private + key rotation (P0)", 5),
            ("Compute Rack", "frame + SSD only; no compute node/PSU/wired net — loan to complete", 6),
            ("Tailscale", "phone + PC + Pi + Stars", 7)])

        # ── Flags ────────────────────────────────────────────────────────────
        do("flags",
           ("title", "category", "status"),
           [("FinCEN BOI — status unverified", "compliance", "open"),
            ("Repo public/private + key rotation — P0", "security", "open"),
            ("Travelers Exchange ↔ Schedule A — verify", "legal", "open"),
            ("Port collisions — 8010, 8082", "infra", "open"),
            ("VHAV-C-2026-001 completion certificate gap", "records", "open"),
            ("$50 payment rail predates bank — confirm for veil record", "finance", "open"),
            ("Extractor Mod — confirm status", "product", "open")])

        # ── Client + engagement ──────────────────────────────────────────────
        do("clients",
           ("id", "name", "contact", "entity", "bill_to"),
           [(1, "Owen Gaffney", "art3mis", "Goables (Viobot owner)", "captured at contract")])

        # closed_at deliberately NULL: the engagement is closed but the exact
        # close date is only "on file" — we don't fabricate dates.
        do("engagements",
           ("id", "code", "client_id", "title", "value_cents", "state",
            "opened_at", "closed_at", "note"),
           [(1, "VHAV-C-2026-001", 1, "Viobot dashboard", 5000, "closed",
             "2026-06-26", None,
             "Closed & paid w/ receipt; completion cert missing (record gap)")])

        # ── Templates — all ten ship as Jinja files with the app, so a fresh
        #    DB starts with the full library ready ─────────────────────────────
        do("templates",
           ("id", "name", "kind", "status"),
           [(1, "Statement of Work", "sow", "ready"),
            (2, "Master Services Agreement", "msa", "ready"),
            (3, "Mutual NDA", "nda", "ready"),
            (4, "Invoice", "invoice", "ready"),
            (5, "Change Order", "change_order", "ready"),
            (6, "Inquiry / Intake", "intake", "ready"),
            (7, "Proposal", "proposal", "ready"),
            (8, "Delivery & Acceptance", "acceptance", "ready"),
            (9, "Completion Certificate", "completion", "ready"),
            (10, "Receipt", "receipt", "ready")])

        # ── Frozen documents on record (pre-app; files are placeholders, so
        #    sha256 is NULL — real generated docs always get a hash).
        #    Emptiness check is scoped to ENGAGEMENT docs: migration 003 puts
        #    company-level governance rows (engagement_id NULL) in this table
        #    before seed runs on a fresh DB, and they must not block these. ──
        # Ids are captured per-insert: on a fresh DB, migration 003's governance
        # rows occupy the low ids, so the papertrail events below must reference
        # whatever ids these three actually get — never hardcoded ones.
        doc_ids: dict[str, int] = {}
        eng_docs = conn.execute(
            "SELECT COUNT(*) FROM documents_generated WHERE engagement_id IS NOT NULL"
        ).fetchone()[0]
        if eng_docs == 0:
            for row in [
                (1, "sow", "Statement of Work — VHAV-C-2026-001", 1,
                 "VHAV-C-2026-001_sow_v1.pdf", None, "2026-06-28", 1, 1),
                (1, "invoice", "Invoice — VHAV-C-2026-001", 1,
                 "VHAV-C-2026-001_invoice_v1.pdf", None, None, 1, None),
                (1, "receipt", "Receipt — VHAV-C-2026-001", 1,
                 "VHAV-C-2026-001_receipt_v1.pdf", None, None, 1, None),
            ]:
                cur = conn.execute(
                    "INSERT INTO documents_generated (engagement_id, doc_type, title, "
                    "version, filename, sha256, generated_at, frozen, template_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
                doc_ids[row[1]] = cur.lastrowid
            seeded["documents_generated"] = 3
        else:
            print("[seed] documents_generated: has engagement docs, skipped")

        # ── Papertrail (order = id order; ts NULL = 'on file') ───────────────
        # The completion certificate is ABSENT on purpose — kind='gap' is the
        # red node in the mockup, cleared when the real cert is generated.
        do("engagement_events",
           ("engagement_id", "ts", "kind", "actor", "title", "detail", "document_id"),
           [(1, "2026-06-26", "inquiry", "art3mis", "Inquiry received",
             "art3mis requested a Viobot dashboard build", None),
            (1, "2026-06-27", "proposal", "Voyager's Haven", "Proposal sent",
             "Scope + $50 fixed price agreed", None),
            (1, "2026-06-28", "contract", "Voyager's Haven", "Contract generated — SOW",
             "VHAV-C-2026-001 issued", doc_ids.get("sow")),
            (1, "2026-06-28", "signature", "both parties", "Contract signed — both parties",
             "/s/ Parker Stouffer · /s/ art3mis", None),
            (1, None, "delivery", "Voyager's Haven", "Work delivered",
             "Viobot dashboard shipped (date on file)", None),
            (1, None, "gap", None, "Completion certificate — MISSING",
             "The finish paperwork: art3mis signs off that the work is complete "
             "and accepted. Never generated — generate & send for signature to "
             "seal the record.", None),
            (1, None, "invoice", "Voyager's Haven", "Invoice issued — $50.00",
             "On file", doc_ids.get("invoice")),
            (1, None, "payment", "art3mis", "Payment received",
             "$50.00 · rail on file — confirm which rail it landed in (veil record)", None),
            (1, None, "receipt", "Voyager's Haven", "Receipt issued",
             "Closed with receipt — trail's last page", doc_ids.get("receipt")),
            (1, None, "closed", "Voyager's Haven", "Engagement closed",
             "Sealed — flagged incomplete until the completion-certificate gap "
             "above is filled", None)])

        # ── Required lifecycle docs (missing-doc check = required minus generated)
        do("required_docs",
           ("doc_type", "label"),
           [("sow", "Statement of Work"),
            ("completion", "Completion Certificate"),
            ("invoice", "Invoice"),
            ("receipt", "Receipt")])

        # ── Ledger ───────────────────────────────────────────────────────────
        do("accounts",
           ("id", "name", "kind", "balance_cents_manual", "status"),
           [(1, "Business checking · Members 1st FCU", "bank", None, "opens Monday"),
            (2, "Stripe", "processor", 0, "pending — confirm under EIN; payout not connected"),
            (3, "Kraken · HTE", "exchange-paper", None,
             "paper — benchmark $1,433.15; unverified for real money")])

        # account_id NULL on purpose: the rail is unconfirmed (predates the bank).
        do("transactions",
           ("account_id", "engagement_id", "amount_cents", "kind", "ts", "note", "rail"),
           [(None, 1, 5000, "payment", None,
             "First inflow. ⚠ received before the business account opened — "
             "confirm which rail it landed in, for the veil record.", "on file")])

        do("assets",
           ("label", "category", "value_cents", "documented", "note"),
           [("IP contribution", "capital", 2960000, 1,
             "740 documented hrs × $40 — Schedule A"),
            ("Cash", "capital", 50000, 1, "Opening contribution — Schedule A"),
            ("Equipment + domains", "capital", 140093, 0,
             "Micro Center receipt (Feb 3; OCR mixed hardware + apparel — "
             "hand-itemize + veil check which items are LLC assets) + "
             "Namecheap domain portfolio")])

        # ── Tasks (standing to-do) ───────────────────────────────────────────
        do("tasks",
           ("title", "detail", "done", "owner", "due", "priority", "blocked_by", "category"),
           [("Verify & file FinCEN BOI",
             "Rules changed in 2025 — confirm requirement before anything else",
             0, "Parker", "ASAP", "P0", None, "compliance"),
            ("Run the bank day-1 checklist",
             "Account info lands Monday — OA, CP 575, Certificate, ID, deposit",
             0, "Parker", "2026-07-06", "P0", None, "banking"),
            ("Confirm Stripe account under EIN",
             "Then connect the bank for payouts",
             0, "Parker", None, "P1", None, "banking"),
            ("Connect bank → Stripe payout", None,
             0, "Parker", None, "P1", "Bank day-1 checklist", "banking"),
            ("Issue art3mis's completion certificate",
             "VHAV-C-2026-001 is closed & paid but the finish paperwork was never signed",
             0, "Parker", None, "P1", None, "records"),
            ("Complete Kraken/HTE verification", None,
             0, "Parker", None, "P2", None, "finance"),
            ("Chart of accounts + receipt policy", None,
             0, "Parker", None, "P2", None, "finance"),
            ("SAM.gov registration", "GovCon gate",
             0, "Parker", None, "P3", None, "compliance"),
            ("Owner-of-record migration", "GitHub · Namecheap · Stripe → LLC",
             0, "Parker", None, "P2", None, "ops"),
            ("Launch voyagershaven.online", "Blocked on logo · email · privacy",
             0, "Parker", None, "P2", "logo · email · privacy", "product")])

        # ── Compliance calendar ──────────────────────────────────────────────
        do("compliance_items",
           ("title", "detail", "due_date", "kind", "status"),
           [("FinCEN BOI",
             "Confirm current federal requirement, then file or log exemption",
             None, "flag", "open"),
            ("Business bank account opens", "Run the day-1 checklist",
             "2026-07-06", "deadline", "open"),
            ("NMS10 hard launch", "Engineering — priority stack P2",
             "2026-07-09", "deadline", "open"),
            ("Q3 estimated taxes", "Federal quarterly",
             "2026-09-15", "deadline", "open"),
            ("PA annual report", "First one due · $7",
             "2027-09-30", "deadline", "open"),
            ("Domain renewals", "Namecheap portfolio",
             None, "rolling", "open")])

        # ── Mark the seed itself in the activity log ─────────────────────────
        if seeded:
            conn.execute(
                "INSERT INTO activity_log (ts, actor, entity, entity_id, action, detail) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (_now(), "system", "seed", None, "seed",
                 f"Phase 1 seed applied: {', '.join(sorted(seeded))}"),
            )

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        print("[seed] FAILED — rolled back")
        raise
    finally:
        conn.close()

    for table, n in seeded.items():
        print(f"[seed] {table}: {n} rows")
    if not seeded:
        print("[seed] nothing to do")
    return seeded


if __name__ == "__main__":
    seed_if_empty()
