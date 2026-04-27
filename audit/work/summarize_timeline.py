"""Summarize timeline.tsv: sessions by project, by cwd, by month."""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import sys

TSV = Path(r"C:/Master-Haven/audit/work/timeline.tsv")

rows = []
with TSV.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter="\t")
    for r in reader:
        rows.append(r)

print(f"total sessions: {len(rows)}")
print(f"date range:     {rows[0]['first_ts'][:10]}  ->  {rows[-1]['first_ts'][:10]}")
print(f"total msgs:     {sum(int(r['msg_count']) for r in rows):,}")
print(f"total tool_uses:{sum(int(r['tool_uses']) for r in rows):,}")
print(f"total bash_cmds:{sum(int(r['bash_cmds']) for r in rows):,}")
print(f"total bytes:    {sum(int(r['size_bytes']) for r in rows):,}")

# By month
month_counts = Counter()
for r in rows:
    m = r["first_ts"][:7]
    if m:
        month_counts[m] += 1
print("\n--- sessions per month ---")
for m in sorted(month_counts):
    print(f"  {m}: {month_counts[m]}")

# By cwd (top 20)
cwd_counts = Counter(r["cwd"] for r in rows)
print(f"\n--- distinct cwds: {len(cwd_counts)} ---")
for c, n in cwd_counts.most_common(20):
    print(f"  {n:4d}  {c}")

# By project_dir (top 20)
proj_counts = Counter(r["project_dir"] for r in rows)
print(f"\n--- distinct project_dirs: {len(proj_counts)} ---")
for c, n in proj_counts.most_common(20):
    print(f"  {n:4d}  {c}")

# Classify by cwd keyword for project attribution
project_map = {
    "haven-ui-backend":  lambda c: "Haven-UI\\backend" in c or "Haven-UI/backend" in c,
    "haven-ui-frontend": lambda c: ("Haven-UI" in c) and not ("backend" in c),
    "haven-extractor":   lambda c: "Haven-Extractor" in c or "NMS-Haven-Extractor" in c,
    "nms-mods":          lambda c: "NMS-" in c and "Haven-Extractor" not in c,
    "master-haven-root": lambda c: c.rstrip("\\/").lower().endswith("master-haven") or c.rstrip("\\/").lower().endswith("master-haven/.claude") or "claude\\worktrees" in c.lower() or "claude/worktrees" in c.lower(),
    "trade-engine-hte":  lambda c: "trade-engine" in c.lower() or "haventradeengine" in c.lower() or "\\hte" in c.lower() or "/hte" in c.lower(),
    "haven-brain":       lambda c: "haven-brain" in c.lower() or "havenbrain" in c.lower(),
    "haven-exchange":    lambda c: "haven-exchange" in c.lower() or "havenexchange" in c.lower(),
    "travelers":         lambda c: "travelers" in c.lower(),
    "viobot":            lambda c: "viobot" in c.lower(),
    "forge":             lambda c: "forge" in c.lower(),
    "keeper":            lambda c: "keeper" in c.lower(),
    "primordial":        lambda c: "primordial" in c.lower(),
    "neural-sim":        lambda c: "neural" in c.lower() or "evo_sim" in c.lower(),
}
proj_bucket = Counter()
for r in rows:
    c = r["cwd"] or ""
    bucket = "other"
    for name, fn in project_map.items():
        if fn(c):
            bucket = name
            break
    proj_bucket[bucket] += 1
print("\n--- sessions by project classification ---")
for b, n in proj_bucket.most_common():
    print(f"  {n:4d}  {b}")

# Gaps > 7 days
prev = None
gaps = []
for r in rows:
    ts = r["first_ts"][:10]
    if not ts: continue
    if prev:
        from datetime import datetime
        try:
            d1 = datetime.fromisoformat(prev)
            d2 = datetime.fromisoformat(ts)
            delta = (d2-d1).days
            if delta >= 7:
                gaps.append((prev, ts, delta))
        except Exception:
            pass
    prev = ts
print(f"\n--- gaps >=7 days between consecutive sessions: {len(gaps)} ---")
for a,b,d in gaps:
    print(f"  {a}  ->  {b}  ({d} days)")
