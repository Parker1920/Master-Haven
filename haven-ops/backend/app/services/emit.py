"""Emit the Project Instructions doc: Part A (durable, verbatim) + Part B
(rendered live from the registers). This route replaces the mockup's
client-side emitDoc() and is the fix for the June-1 drift — the live
sections stop being typed by hand.

Part B section ⟵ source tables:
  Company            ⟵ company (+ signature file presence, checked live)
  Engagements        ⟵ engagements ⋈ clients (+ live missing-docs check)
  Current State      ⟵ environment
  Priority Stack     ⟵ initiatives (priority set) + P0 flags + near compliance deadlines
  Active Initiatives ⟵ initiatives
  Key People         ⟵ people (partners split out via tags)
  Open Flags         ⟵ flags (status='open')
"""
from datetime import date, timedelta

from sqlmodel import Session, select

from ..config import settings
from ..models import (Client, Company, ComplianceItem, DocumentGenerated,
                      Engagement, EnvironmentItem, Flag, Initiative, Person,
                      RequiredDoc)
from .docgen import money

# ── PART A — copied verbatim from the DURABLE const in mockup v0.7 ───────────
DURABLE = """\
# Haven Project — Claude Instructions

> Paste into the Project Instructions field. Part A is durable (hand-kept). Part B is emitted by Haven Ops.

# PART A — DURABLE

## Project Overview
Parker's (Ekimo) multi-initiative ecosystem for the Voyager's Haven NMS community, operated by Voyager's Haven LLC (now operational). Primary community deliverable: Haven Control Room at havenmap.online. The LLC's back office is Haven Ops. Learning-by-building: explain the WHY.

## Working Dynamic
- Parker = PM. Direction, final decisions, owns ALL git operations.
- Claude = engineering team. Research, options + recommendation, implement.

## Core Rules
- Options + recommendation; Parker decides. Never decide for him.
- Direct. No preamble/hedging/filler. Tables over prose. Don't re-ask answered questions.
- ADHD: repetition fine; connect new to known.
- Commented code. Edits via str_replace text anchors.
- Corrections are data — course-correct without over-apologizing.
- Never assert without verifying. Flag uncertainty; never fabricate.
- Never curate findings — show everything.
- 100% self-hosted, zero paid services (Claude API excepted).
- Do NOT question locked decisions. Planning is not scope creep.
- The mockup is the design contract; then actually present the file.
- Frozen docs (contracts/invoices/receipts) generated once, never re-rendered; live docs re-emitted.
- Haven Ops is the source of truth and emits Part B.
- Persistent data in ~/docker/<name>-data/, never in a repo. Secrets + e-signature via data dir, never committed.

## Response Patterns
"Explain again" -> re-explain differently. "Options" -> table + rec. "What next" -> check phase, propose. "Just the command" -> command + why. "Add to runbook" -> document it.

## Don't
Skip explanations; uncommented code; decide for Parker; paid services; question locked decisions; jump phases; describe a mockup instead of presenting it."""


def _md_table(head: list[str], rows: list[list[str]]) -> str:
    def esc(cell: str | None) -> str:
        return (cell or "—").replace("|", "\\|")
    lines = ["| " + " | ".join(head) + " |",
             "| " + " | ".join("---" for _ in head) + " |"]
    lines += ["| " + " | ".join(esc(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _priority_key(p: str) -> int:
    digits = [int(ch) for ch in p if ch.isdigit()]
    return min(digits) if digits else 9


def build_project_instructions(session: Session) -> str:
    company = session.get(Company, 1)
    people = session.exec(select(Person).order_by(Person.sort)).all()
    initiatives = session.exec(select(Initiative).order_by(Initiative.sort)).all()
    environment = session.exec(select(EnvironmentItem).order_by(EnvironmentItem.sort)).all()
    open_flags = session.exec(select(Flag).where(Flag.status == "open")).all()
    engagements = session.exec(select(Engagement)).all()
    required = [r.doc_type for r in session.exec(select(RequiredDoc)).all()]
    compliance = session.exec(select(ComplianceItem).where(ComplianceItem.status == "open")).all()

    # ── Company ──────────────────────────────────────────────────────────────
    legal = company.legal_name + (f" · {company.entity_type}" if company.entity_type else "")
    sig_state = ("On file (signature.png)" if settings.signature_path.is_file()
                 else "⚠ NOT on file — place signature.png in the data dir")
    company_rows = [
        ["Legal name", legal],
        ["Entity # · EIN", f"{company.entity_no} · {company.ein}"],
        ["Formed", f"{company.formed} · {company.office}"],
        ["NAICS", company.naics],
        ["Operating Agreement", company.oa_status],
        ["Schedule A capital", f"{money(company.capital_total_cents)} — {company.capital_note}"],
        ["Bank", company.bank],
        ["E-signature", sig_state],
    ]

    # ── Engagements (with the LIVE missing-docs check) ───────────────────────
    eng_rows = []
    for e in engagements:
        client = session.get(Client, e.client_id)
        have = {d.doc_type for d in session.exec(
            select(DocumentGenerated).where(DocumentGenerated.engagement_id == e.id)).all()}
        missing = [t for t in required if t not in have]
        state = e.state.capitalize()
        if e.note:
            state += f" · {e.note}"
        if missing:
            state += f" · ⚠ missing: {', '.join(missing)}"
        label = f"{client.contact} ({client.name} / {client.entity})" if client else "—"
        eng_rows.append([e.code, label, e.title, money(e.value_cents), state])

    # ── Priority stack: P0 flags, then prioritized initiatives, then admin ──
    stack = [f"**P0** {f.title}" for f in open_flags if "P0" in (f.title or "")]
    stack += [f"**{i.priority}** {i.name}"
              for i in sorted((i for i in initiatives if i.priority),
                              key=lambda i: _priority_key(i.priority))]
    soon = date.today() + timedelta(days=60)
    admin = [f"{c.title} ({c.due_date})" for c in compliance
             if c.kind == "deadline" and c.due_date and c.due_date <= soon.isoformat()]
    priority_line = " · ".join(stack) or "—"
    if admin:
        priority_line += " · admin: " + ", ".join(admin)

    # ── Initiatives bullets ──────────────────────────────────────────────────
    init_lines = []
    for i in initiatives:
        parts = "; ".join(p for p in (i.status, i.note) if p)
        init_lines.append(f"- {i.name} — {parts}" if parts else f"- {i.name}")

    # ── Key people (partners split out) ─────────────────────────────────────
    partners = [p.name for p in people if (p.tags or "") == "partner"]
    core = [f"{p.name} ({p.role})" if p.role else p.name
            for p in people if (p.tags or "") != "partner"]
    people_line = " · ".join(core)
    if partners:
        people_line += f". Partners: {', '.join(partners)}."

    part_b = "\n".join([
        "",
        "<!-- HAVEN-OPS:LIVE-STATE:BEGIN -->",
        "",
        "# PART B — LIVE STATE",
        f"*Emitted {date.today().isoformat()} from Haven Ops state — do not hand-edit once the app is live.*",
        "",
        "## Company ⟵ Company / Ledger",
        _md_table(["Field", "Value"], company_rows),
        "",
        "## Engagements ⟵ Engagements",
        _md_table(["ID", "Client", "Work", "$", "State"], eng_rows),
        "",
        "## Current State ⟵ Environment",
        _md_table(["Item", "Status"], [[env.item, env.status] for env in environment]),
        "",
        "## Priority Stack ⟵ Compliance / Initiatives",
        priority_line,
        "",
        "## Active Initiatives ⟵ Initiatives",
        "\n".join(init_lines),
        "",
        "## Key People ⟵ People",
        people_line,
        "",
        "## Open Flags to Resolve ⟵ Compliance",
        "\n".join(f"- {f.title}" for f in open_flags),
        "",
        "<!-- HAVEN-OPS:LIVE-STATE:END -->",
    ])
    return DURABLE + "\n" + part_b + "\n"
