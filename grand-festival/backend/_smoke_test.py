"""Standalone backend smoke test (TestClient). Not part of the shipped app.

Run from the grand-festival/backend dir with the venv python:
    DATA_DIR set to a temp dir, ADMIN_PASSWORD set, GF_COOKIE_SECURE=0.
"""

import io
import os
import sys
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="gf-smoke-"))
os.environ.setdefault("ADMIN_PASSWORD", "test-password-123")
os.environ.setdefault("GF_COOKIE_SECURE", "0")

from PIL import Image  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.db import init_db  # noqa: E402
from backend.main import app  # noqa: E402

init_db()  # lifespan only fires inside a `with TestClient(...)`; do it explicitly here
client = TestClient(app)
failures = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {label}")
    if not cond:
        failures.append(label)


def png_bytes(color=(120, 200, 255)):
    img = Image.new("RGB", (300, 300), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# 1. health
r = client.get("/api/health")
check("health returns ok", r.status_code == 200 and r.json() == {"ok": True})

# 2. seeded civs
r = client.get("/api/civs")
seeded = r.json()
SEED_N = len(seeded)
check("seeded civs present", r.status_code == 200 and SEED_N >= 1)
check("public civs carry logo_url key", all("logo_url" in c for c in seeded))
check("public civs hide submitter fields", all("submitter_discord" not in c for c in seeded))

# 3. single civ
first_id = seeded[0]["id"]
r = client.get(f"/api/civs/{first_id}")
check("GET single approved civ", r.status_code == 200 and r.json()["id"] == first_id)
r = client.get("/api/civs/999999")
check("GET missing civ -> 404", r.status_code == 404)

# 4. submit with valid logo
r = client.post(
    "/api/civs/submit",
    data={
        "name": "Smoke Test Civ",
        "role": "QA District",
        "description": "Submitted by the automated smoke test.",
        "status": "tentative",
        "submitter_discord": "tester#0001",
        "submitter_notes": "please approve me",
    },
    files={"logo": ("logo.png", png_bytes(), "image/png")},
)
check("submit valid civ -> ok", r.status_code == 200 and r.json().get("ok"))
new_id = r.json().get("id")

# 5. pending civ NOT shown publicly
r = client.get("/api/civs")
check("pending civ hidden from public list", len(r.json()) == SEED_N)

# 6. reject oversized image (>2MB)
big = b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024 + 10)
r = client.post(
    "/api/civs/submit",
    data={"name": "Big", "role": "x", "description": "y"},
    files={"logo": ("big.png", big, "image/png")},
)
check("oversized image rejected -> 400", r.status_code == 400)

# 7. reject non-image file
r = client.post(
    "/api/civs/submit",
    data={"name": "Bad", "role": "x", "description": "y"},
    files={"logo": ("evil.txt", b"i am not an image", "text/plain")},
)
check("non-image file rejected -> 400", r.status_code == 400)

# 8. missing required field
r = client.post("/api/civs/submit", data={"name": "", "role": "x", "description": "y"})
check("missing name rejected -> 400", r.status_code == 400)

# 9. admin endpoints require auth
r = client.get("/api/admin/civs")
check("admin list requires auth -> 401", r.status_code == 401)

# 10. login wrong password
r = client.post("/api/admin/login", json={"password": "wrong"})
check("wrong password -> 401", r.status_code == 401)

# 11. login correct
r = client.post("/api/admin/login", json={"password": "test-password-123"})
check("correct password -> ok + cookie", r.status_code == 200 and "gf_admin" in r.cookies)

# 12. admin list shows pending + badge count
r = client.get("/api/admin/civs")
body = r.json()
check("admin list includes pending civ", len(body["civs"]) == SEED_N + 1)
check("pending_count == 1", body["pending_count"] == 1)
check("admin civ exposes submitter fields", any(c.get("submitter_discord") == "tester#0001" for c in body["civs"]))

# 13. approve
r = client.post(f"/api/admin/civs/{new_id}/approve")
check("approve -> ok", r.status_code == 200)
r = client.get("/api/civs")
check("approved civ now public", len(r.json()) == SEED_N + 1)

# 14. edit
r = client.patch(f"/api/admin/civs/{new_id}", json={"role": "Edited Role", "display_order": 5})
check("edit -> reflects new role", r.status_code == 200 and r.json()["role"] == "Edited Role")

# 15. audit log populated
r = client.get("/api/admin/log")
actions = [e["action"] for e in r.json()["log"]]
check("audit log has approved + edited", "approved" in actions and "edited" in actions)

# 16. logo served
r = client.get("/api/civs")
civ = next(c for c in r.json() if c["id"] == new_id)
check("submitted civ has a logo_url", bool(civ["logo_url"]))
r = client.get(civ["logo_url"])
check("logo serves as image/webp", r.status_code == 200 and r.headers["content-type"] == "image/webp")

# 17. delete
r = client.delete(f"/api/admin/civs/{new_id}")
check("delete -> ok", r.status_code == 200)
r = client.get("/api/civs")
check("deleted civ gone from public", len(r.json()) == SEED_N)

# 18. logout invalidates session
r = client.post("/api/admin/logout")
check("logout -> ok", r.status_code == 200)
r = client.get("/api/admin/civs")
check("admin blocked after logout -> 401", r.status_code == 401)

# 19. uploads path traversal guarded
r = client.get("/api/uploads/..%2f..%2fgrand_festival.db")
check("path traversal on uploads -> 404", r.status_code == 404)

print()
if failures:
    print(f"{len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("ALL BACKEND SMOKE CHECKS PASSED")
