#!/usr/bin/env python3
"""
skyscraper_watch.py — change notifier for the Project Skyscraper NMS ARG.

Polls the Architect's public surfaces, diffs against the last snapshot, and
posts a Discord webhook alert describing exactly what changed. Stdlib only
(urllib/json/hashlib) so it runs on the Pi with no pip installs.

Monitored:
  - project-skyscraper.com WP REST: posts (new + EDITED via modified_gmt), pages, media
  - sitemap index + image-sitemap <lastmod> (incl. the /tr4ce/ "canary")
  - homepage HTML (digit-normalized hash, so the live visitor counter doesn't
    cause false alerts, but new text/structure does) + key-phrase presence
  - the reserved 2nd site theskyscraperarchitect-ywvhk.wordpress.com (posts count
    + latest title — fires loud when it finally goes live)
  - Bluesky @skyscraper-prj.bsky.social latest post (clean public API)

Config: reads webhook URLs from ./config.env (KEY=VALUE lines) or the
SKYSCRAPER_WEBHOOK_URL env var. Multiple webhooks are supported — repeat
the WEBHOOK_URL line, use suffixed keys (WEBHOOK_URL_2, WEBHOOK_URL_DEV…),
and/or comma-separate URLs on one line. Each is alerted independently, so
one dead webhook won't stop the rest. If none set, changes are logged only.

Run: python3 skyscraper_watch.py            (normal poll)
     python3 skyscraper_watch.py --seed     (snapshot now, never alert)
     python3 skyscraper_watch.py --test      (send a test webhook and exit)
"""
import json, os, sys, time, hashlib, re, urllib.request, urllib.error, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "state.json")
LOG_FILE   = os.path.join(HERE, "watch.log")
UA = "Mozilla/5.0 (skyscraper-watch; +havenmap.online)"
SITE = "https://project-skyscraper.com"
SITE2 = "theskyscraperarchitect-ywvhk.wordpress.com"
BSKY_ACTOR = "skyscraper-prj.bsky.social"


def log(msg):
    line = f"{datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds')}Z  {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        # Windows cp1252 console can't render emoji; Pi/Linux UTF-8 is fine.
        print(line.encode("ascii", "replace").decode("ascii"))
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_config():
    """Return the list of Discord webhook URLs to notify.

    Collects every config.env line whose key starts with WEBHOOK_URL — so
    WEBHOOK_URL, WEBHOOK_URL_2, WEBHOOK_URL_DEV, … all count, and simply
    repeating the WEBHOOK_URL line on multiple lines works too. Values may
    also be comma- or whitespace-separated to list several URLs on one line.
    The SKYSCRAPER_WEBHOOK_URL env var is appended (same multi-value rules).
    Blanks and duplicates are dropped; original order is preserved.
    """
    raw = []
    p = os.path.join(HERE, "config.env")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                if k.strip().upper().startswith("WEBHOOK_URL"):
                    raw.append(v.strip().strip('"').strip("'"))
    env = os.environ.get("SKYSCRAPER_WEBHOOK_URL", "")
    if env:
        raw.append(env)
    webhooks = []
    for item in raw:
        for url in item.replace(",", " ").split():
            if url and url not in webhooks:
                webhooks.append(url)
    return webhooks


def fetch(url, as_json=True, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw.decode("utf-8", "replace")) if as_json else raw.decode("utf-8", "replace")


def snapshot():
    """Build the current state. Each source is best-effort; a fetch failure for
    one source leaves that key absent so we never false-alert on an outage."""
    s = {}
    # --- WP posts (new + edited) ---
    try:
        posts = fetch(f"{SITE}/wp-json/wp/v2/posts?per_page=40&orderby=modified&order=desc")
        s["posts"] = {str(p["id"]): {"mod": p["modified_gmt"], "date": p["date_gmt"],
                                     "slug": p["slug"], "link": p["link"],
                                     "title": re.sub("<[^>]+>", "", p["title"]["rendered"]).strip()}
                      for p in posts}
    except Exception as e:
        log(f"WARN posts fetch failed: {e}")
    # --- WP pages ---
    try:
        pages = fetch(f"{SITE}/wp-json/wp/v2/pages?per_page=50&orderby=modified&order=desc")
        s["pages"] = {str(p["id"]): {"mod": p["modified_gmt"], "slug": p["slug"], "link": p["link"],
                                     "title": re.sub("<[^>]+>", "", p["title"]["rendered"]).strip()}
                      for p in pages}
    except Exception as e:
        log(f"WARN pages fetch failed: {e}")
    # --- WP media (new uploads / image swaps) ---
    try:
        media = fetch(f"{SITE}/wp-json/wp/v2/media?per_page=30&orderby=date&order=desc")
        s["media"] = {str(m["id"]): {"date": m["date_gmt"], "url": m.get("source_url", "")} for m in media}
    except Exception as e:
        log(f"WARN media fetch failed: {e}")
    # --- sitemaps (incl. /tr4ce/ canary) ---
    try:
        idx = fetch(f"{SITE}/sitemap.xml", as_json=False)
        s["sitemap_lastmods"] = dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", idx))
        img = fetch(f"{SITE}/image-sitemap-1.xml", as_json=False)
        # per-page image lastmods, keyed by page loc
        pairs = re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", img)
        s["image_lastmods"] = {loc: lm for loc, lm in pairs}
    except Exception as e:
        log(f"WARN sitemap fetch failed: {e}")
    # --- homepage (digit-normalized hash + key phrases) ---
    try:
        home = fetch(f"{SITE}/", as_json=False)
        body = re.search(r"<body.*?</body>", home, re.S)
        body = body.group(0) if body else home
        # Hash VISIBLE TEXT only: strip scripts/styles/tags so per-request markup
        # noise (nonces, cache-busters, random ids) can't false-alert; then drop
        # digits so the live visitor counter doesn't either.
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\d+", "#", text)
        text = re.sub(r"\s+", " ", text).strip()
        s["home_hash"] = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
        s["home_phrases"] = sorted({ph for ph in
            ["System Filtering Platform", "Live Connection Attempts", "SECURITY", "Access denied",
             "waking", "Self_awareness", "Overload"] if ph.lower() in home.lower()})
    except Exception as e:
        log(f"WARN homepage fetch failed: {e}")
    # --- reserved 2nd site ---
    try:
        p2 = fetch(f"https://public-api.wordpress.com/wp/v2/sites/{SITE2}/posts?per_page=20")
        non_default = [x for x in p2 if x.get("slug") != "hello-world"]
        s["site2"] = {"count": len(p2), "non_default": len(non_default),
                      "latest": (re.sub("<[^>]+>", "", p2[0]["title"]["rendered"]).strip() if p2 else "")}
    except Exception as e:
        log(f"WARN site2 fetch failed: {e}")
    # --- Bluesky latest post ---
    try:
        feed = fetch(f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor={BSKY_ACTOR}&limit=5")
        items = feed.get("feed", [])
        if items:
            top = items[0]["post"]
            s["bsky"] = {"cid": top.get("cid", ""),
                         "text": (top.get("record", {}).get("text", "") or "")[:200],
                         "indexedAt": top.get("indexedAt", "")}
    except Exception as e:
        log(f"WARN bluesky fetch failed: {e}")
    return s


def diff(old, new):
    """Return a list of human-readable change strings (highest signal first)."""
    ch = []
    # second site going live = top priority
    o2, n2 = old.get("site2"), new.get("site2")
    if o2 and n2 and n2.get("non_default", 0) > o2.get("non_default", 0):
        ch.append(f"🚨 **RESERVED 2ND SITE HAS NEW CONTENT** — {SITE2} now has "
                  f"{n2['non_default']} non-placeholder post(s). Latest: “{n2.get('latest','')}”. "
                  f"https://{SITE2}/")
    # posts: new + edited
    op, np_ = old.get("posts", {}), new.get("posts", {})
    for pid, p in np_.items():
        if pid not in op:
            ch.append(f"🆕 **New post** — “{p['title']}” ({p['slug']}) published {p['date']}Z\n{p['link']}")
        elif op[pid]["mod"] != p["mod"]:
            ch.append(f"✏️ **Post edited** — “{p['title']}” ({p['slug']}) modified {p['mod']}Z\n{p['link']}")
    # pages: new + edited
    opg, npg = old.get("pages", {}), new.get("pages", {})
    for pid, p in npg.items():
        if pid not in opg:
            ch.append(f"📄 **New page** — “{p['title']}” ({p['slug']})\n{p['link']}")
        elif opg[pid]["mod"] != p["mod"]:
            ch.append(f"📝 **Page edited** — “{p['title']}” ({p['slug']}) modified {p['mod']}Z\n{p['link']}")
    # media: new uploads
    om, nm = old.get("media", {}), new.get("media", {})
    for mid, m in nm.items():
        if mid not in om:
            ch.append(f"🖼️ **New media upload** — {m['url']} ({m['date']}Z)")
    # canary: per-image lastmod changes (esp. /tr4ce/)
    oil, nil = old.get("image_lastmods", {}), new.get("image_lastmods", {})
    for loc, lm in nil.items():
        if loc in oil and oil[loc] != lm:
            tag = "  ⚠️ TR4CE CANARY TRIPPED" if "tr4ce" in loc.lower() else ""
            ch.append(f"🗺️ **Image re-uploaded** — {loc} lastmod {oil[loc]} → {lm}{tag}")
    # homepage structure
    if old.get("home_hash") and new.get("home_hash") and old["home_hash"] != new["home_hash"]:
        added = sorted(set(new.get("home_phrases", [])) - set(old.get("home_phrases", [])))
        removed = sorted(set(old.get("home_phrases", [])) - set(new.get("home_phrases", [])))
        extra = (f" (+{added})" if added else "") + (f" (-{removed})" if removed else "")
        ch.append(f"🏠 **Homepage changed** (structure/text, ignoring the live counter){extra}\n{SITE}/")
    # bluesky
    ob, nb = old.get("bsky"), new.get("bsky")
    if ob and nb and ob.get("cid") != nb.get("cid"):
        ch.append(f"🦋 **New Bluesky post** ({nb.get('indexedAt','')}): “{nb.get('text','')}”\n"
                  f"https://bsky.app/profile/{BSKY_ACTOR}")
    return ch


def send_discord(webhook, changes):
    when = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M UTC")
    desc = "\n\n".join(changes)
    if len(desc) > 3900:
        desc = desc[:3900] + "\n… (truncated)"
    payload = {
        "username": "Skyscraper Watch",
        "embeds": [{
            "title": f"🛰️ Project Skyscraper — {len(changes)} change(s) detected",
            "description": desc,
            "color": 0xF7C948,
            "footer": {"text": f"skyscraper_watch • {when}"},
        }],
    }
    req = urllib.request.Request(webhook, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def main():
    webhooks = load_config()
    if "--test" in sys.argv:
        if not webhooks:
            log("--test: no WEBHOOK_URL configured"); sys.exit(1)
        msg = ["✅ Test alert — skyscraper_watch is wired up and can reach this channel."]
        for i, w in enumerate(webhooks, 1):
            try:
                st = send_discord(w, msg)
                log(f"--test: webhook {i}/{len(webhooks)} -> HTTP {st}")
            except Exception as e:
                log(f"--test: webhook {i}/{len(webhooks)} ERROR: {e}")
        return

    new = snapshot()
    if not new.get("posts"):
        log("ERROR: core posts feed unreachable; skipping this cycle (no state write).")
        sys.exit(0)

    seeding = ("--seed" in sys.argv) or (not os.path.exists(STATE_FILE))
    old = {}
    if os.path.exists(STATE_FILE):
        try:
            old = json.load(open(STATE_FILE, encoding="utf-8"))
        except (OSError, ValueError):
            old = {}

    changes = [] if seeding else diff(old, new)
    json.dump(new, open(STATE_FILE, "w", encoding="utf-8"), indent=1)

    if seeding:
        log(f"Seeded baseline: {len(new.get('posts',{}))} posts, {len(new.get('pages',{}))} pages, "
            f"{len(new.get('media',{}))} media. No alert sent.")
        return
    if not changes:
        log("No changes."); return

    log(f"{len(changes)} change(s) detected:")
    for c in changes:
        log("  • " + c.replace("\n", " | "))
    if webhooks:
        for i, w in enumerate(webhooks, 1):
            try:
                st = send_discord(w, changes)
                log(f"Discord webhook {i}/{len(webhooks)} POST -> HTTP {st}")
            except Exception as e:
                log(f"ERROR sending webhook {i}/{len(webhooks)}: {e}")
    else:
        log("No WEBHOOK_URL set — changes logged only. Add it to config.env to enable Discord alerts.")


if __name__ == "__main__":
    main()
