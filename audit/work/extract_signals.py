"""Extract signal-bearing snippets from all Claude Code JSONL transcripts.

For each pattern category, produce a TSV with columns:
  category, session_file, date, role, snippet

Only matches in *user* or *assistant* text (not tool_use/tool_result metadata)
count, to keep signal high.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(r"C:/Users/parke/.claude/projects")
OUT_DIR = Path(r"C:/Master-Haven/audit/work/signals")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Pattern categories. Each regex is applied case-insensitive.
PATTERNS = {
    "abandoned_gru_ppo": r"\b(gru[ _]?v[0-9]|ppo\b|reinforcement learn|32[- ]?model|pattern recognition experiment|direction[ -]prediction)",
    "abandoned_rtai_datajson": r"(rtai|data_json|datajson write[- ]through)",
    "abandoned_grid": r"(arithmetic grid|grid spacing|geometric (replaced|spacing)|allocation optimizer|atr bands?)",
    "docker_issues": r"(docker[ -]desktop|dockerfile|docker compose|workdir|arm build|image build fail)",
    "auth_pat": r"(personal access token|\bPAT\b|github pat|credential helper|git push.*auth)",
    "migration_issues": r"(migration fail|schema migration|alembic|sqlite threading|write.*concurrent)",
    "superseded_language": r"(we decided|going with|sticking with|final answer|rolling back|reverting|abandon(ed|ing)?|scrap(ped|ping)?|replaced? (with|by))",
    "todos_open": r"(\bTODO\b|\bFIXME\b|come back to this|revisit later|for now|temporary (hack|fix)|quick fix|placeholder)",
    "incidents": r"(outage|crashed|thermal|melt|hang(ing|ed)?|dead lock|thread unsafe)",
    "hte_specific": r"(engine_state\.json|live_fills\.csv|circuit breaker|capital manager|range guardian|mode selector|hte)",
    "haven_brain": r"(haven[ -]brain|mindselector|mindSelector)",
    "viobot": r"(viobot|intent handler|node index\.js)",
    "travelers": r"(travelers[ -]collective|sync hub|endpoint scanner)",
    "forge": r"(\bforge\b|evolutionary nn|evo[ _]sim|primordial)",
    "galaxies_252": r"(galaxy (256|252|dropdown)|galaxies\.json|all 256 galax)",
    "shared_api_key": r"(_OLD_SHARED_KEY|shared api key|leaked key|rotate(d)? key)",
    "secrets_leak": r"(api[_ ]?key[ =:]|secret[ =:]|password[ =:]|token[ =:])[^\\s\"]{8,}",
    "march_cleanup": r"(march cleanup|claim(ed)? done|hadn.?t land|19272 line|19,272)",
}

COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in PATTERNS.items()}

def iter_text_blocks(obj):
    """Yield (role, text) from a JSONL entry's message content."""
    if obj.get("type") not in ("user", "assistant"):
        return
    msg = obj.get("message", {})
    if not isinstance(msg, dict):
        return
    role = msg.get("role", obj.get("type", ""))
    content = msg.get("content")
    if isinstance(content, str):
        yield role, content
    elif isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                t = c.get("text", "")
                if t:
                    yield role, t

def snippet_around(text, match, pad=160):
    s = max(0, match.start() - pad)
    e = min(len(text), match.end() + pad)
    return text[s:e].replace("\t"," ").replace("\n"," ").strip()

def main():
    # open one output file per category
    out_files = {k: (OUT_DIR / f"{k}.tsv").open("w", encoding="utf-8") for k in PATTERNS}
    counts = defaultdict(int)
    for k, f in out_files.items():
        f.write("session_file\tdate\trole\tsnippet\n")
    n_files = 0
    for path in ROOT.rglob("*.jsonl"):
        n_files += 1
        session_file = str(path).replace(str(ROOT), "").lstrip("\\/")
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    ts = obj.get("timestamp","")[:19]
                    for role, text in iter_text_blocks(obj):
                        if len(text) > 200000:
                            continue
                        for cat, pat in COMPILED.items():
                            for m in pat.finditer(text):
                                snip = snippet_around(text, m)
                                out_files[cat].write(f"{session_file}\t{ts}\t{role}\t{snip}\n")
                                counts[cat] += 1
                                if counts[cat] > 2000:  # cap per category
                                    break
        except Exception:
            continue
        if n_files % 100 == 0:
            print(f"  processed {n_files} files")
    for f in out_files.values():
        f.close()
    print(f"\nprocessed {n_files} files total")
    print("\n--- hits per category ---")
    for k in sorted(counts):
        print(f"  {counts[k]:5d}  {k}")

if __name__ == "__main__":
    main()
