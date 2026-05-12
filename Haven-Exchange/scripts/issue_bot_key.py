"""Issue a new bot bearer token for the Travelers Exchange API.

Usage (run inside the container):

    docker exec economy bash -c \\
        "cd /app && python scripts/issue_bot_key.py --label 'the-keeper-prod' --scope bot_full"

Or locally with the same Python that the app uses:

    python -m scripts.issue_bot_key --label 'dev-test'

Plaintext key is printed exactly once.  Hand it to Stars (or whoever owns
the bot) and store it in a secret manager.  The Exchange only stores the
bcrypt hash; the plaintext can never be recovered.

Listing existing keys:

    python scripts/issue_bot_key.py --list

Revoking a key (sets is_active=False; existing bot processes will start
seeing 401 on the next request):

    python scripts/issue_bot_key.py --revoke <id>
"""

import argparse
import sys
from pathlib import Path

# Make `app` importable when run as a top-level script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import generate_api_key  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import ApiKey  # noqa: E402


def cmd_issue(label: str, scope: str) -> int:
    plaintext, prefix, hashed = generate_api_key()
    db = SessionLocal()
    try:
        row = ApiKey(
            key_prefix=prefix,
            key_hash=hashed,
            label=label,
            scope=scope,
            is_active=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        print()
        print("=" * 70)
        print("  Travelers Exchange bot key issued")
        print("=" * 70)
        print(f"  ID:         {row.id}")
        print(f"  Label:      {row.label}")
        print(f"  Scope:      {row.scope}")
        print(f"  Prefix:     {row.key_prefix}")
        print()
        print("  PLAINTEXT KEY (shown ONCE — copy it now):")
        print()
        print(f"      {plaintext}")
        print()
        print("  Send to The_Keeper as Authorization: Bearer <key>")
        print("=" * 70)
        return 0
    finally:
        db.close()


def cmd_list() -> int:
    db = SessionLocal()
    try:
        rows = db.query(ApiKey).order_by(ApiKey.id).all()
        if not rows:
            print("No bot keys issued yet.")
            return 0
        print(f"{'ID':>3}  {'PREFIX':<14}  {'SCOPE':<10}  {'ACTIVE':<7}  {'LAST USED':<26}  LABEL")
        for r in rows:
            last = r.last_used_at.isoformat() if r.last_used_at else "—"
            print(
                f"{r.id:>3}  {r.key_prefix:<14}  {r.scope:<10}  "
                f"{'yes' if r.is_active else 'no':<7}  {last:<26}  {r.label}"
            )
        return 0
    finally:
        db.close()


def cmd_revoke(key_id: int) -> int:
    db = SessionLocal()
    try:
        row = db.get(ApiKey, key_id)
        if row is None:
            print(f"No key with id={key_id}", file=sys.stderr)
            return 1
        if not row.is_active:
            print(f"Key {key_id} ({row.label}) is already inactive.")
            return 0
        row.is_active = False
        db.commit()
        print(f"Revoked key {key_id} ({row.label}).")
        return 0
    finally:
        db.close()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--issue", action="store_true", help="Issue a new key (default action)")
    g.add_argument("--list", action="store_true", help="List existing keys")
    g.add_argument("--revoke", type=int, metavar="ID", help="Revoke key by id")
    p.add_argument("--label", help="Human-readable label (required for --issue)")
    p.add_argument("--scope", default="bot_full", choices=["bot_full"], help="Capability scope")
    args = p.parse_args()

    if args.list:
        return cmd_list()
    if args.revoke is not None:
        return cmd_revoke(args.revoke)
    # default = --issue
    if not args.label:
        p.error("--label is required when issuing a key")
    return cmd_issue(args.label, args.scope)


if __name__ == "__main__":
    sys.exit(main())
