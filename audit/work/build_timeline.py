"""Build session timeline from Claude Code JSONL transcripts.

Walks every JSONL under ~/.claude/projects/, extracts:
  session_id, project_dir, cwd, first_ts, last_ts, msg_count,
  first_user_prompt (truncated), files_touched (distinct Edit/Write/Read paths).
Writes a single TSV at audit/work/timeline.tsv for downstream analysis.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

ROOT = Path(r"C:/Users/parke/.claude/projects")
OUT  = Path(r"C:/Master-Haven/audit/work/timeline.tsv")

def parse_file(path: Path):
    first_ts = None
    last_ts  = None
    msg_count = 0
    cwd = ""
    first_user = ""
    files_edited = set()
    files_read   = set()
    tool_uses = 0
    bash_cmds = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                ts = obj.get("timestamp")
                if ts:
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts
                if not cwd and obj.get("cwd"):
                    cwd = obj.get("cwd", "")
                t = obj.get("type")
                if t in ("user", "assistant"):
                    msg_count += 1
                    if t == "user" and not first_user:
                        msg = obj.get("message", {})
                        content = msg.get("content")
                        if isinstance(content, list):
                            for c in content:
                                if c.get("type") == "text":
                                    txt = c.get("text", "")
                                    if not txt.startswith("<"):
                                        first_user = txt[:300].replace("\t", " ").replace("\n", " ")
                                        break
                        elif isinstance(content, str):
                            first_user = content[:300].replace("\t"," ").replace("\n"," ")
                # Track tool uses
                msg = obj.get("message", {}) if isinstance(obj.get("message"), dict) else {}
                content = msg.get("content")
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "tool_use":
                            name = c.get("name","")
                            inp  = c.get("input",{}) or {}
                            tool_uses += 1
                            if name in ("Edit","Write","MultiEdit","NotebookEdit"):
                                p = inp.get("file_path") or inp.get("notebook_path") or ""
                                if p:
                                    files_edited.add(p)
                            elif name == "Read":
                                p = inp.get("file_path","")
                                if p:
                                    files_read.add(p)
                            elif name in ("Bash","PowerShell"):
                                bash_cmds += 1
    except Exception as e:
        return None
    return {
        "session_id": path.stem,
        "project_dir": path.parent.name,
        "cwd": cwd,
        "first_ts": first_ts or "",
        "last_ts":  last_ts or "",
        "msg_count": msg_count,
        "tool_uses": tool_uses,
        "bash_cmds": bash_cmds,
        "edited_count": len(files_edited),
        "read_count":   len(files_read),
        "first_user": first_user,
        "size_bytes": path.stat().st_size,
    }

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    n = 0
    for path in ROOT.rglob("*.jsonl"):
        n += 1
        r = parse_file(path)
        if r:
            rows.append(r)
        if n % 50 == 0:
            print(f"  processed {n} files...", file=sys.stderr)
    rows.sort(key=lambda r: r["first_ts"] or "")
    cols = ["first_ts","last_ts","project_dir","session_id","cwd","msg_count","tool_uses","bash_cmds","edited_count","read_count","size_bytes","first_user"]
    with OUT.open("w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(c,"")) for c in cols) + "\n")
    print(f"wrote {len(rows)} rows to {OUT}")

if __name__ == "__main__":
    main()
