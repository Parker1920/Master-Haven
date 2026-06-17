#!/usr/bin/env python3
"""
skyscraper_watch.py — change notifier for the Project Skyscraper NMS ARG.

Polls the Architect's public surfaces, diffs against the last snapshot, and
posts a Discord webhook alert describing exactly what changed. Stdlib only
(urllib/json/hashlib/difflib) so it runs on the Pi with no pip installs.

Monitored:
  - project-skyscraper.com WP REST: posts + pages (new, EDITED with old→new
    text diff, and REMOVED) and media (new + removed). Lists are paginated to
    completion every run, so nothing is ever treated as deleted just because it
    rolled off a capped feed — a disappearance is verified with a direct
    GET /{id} and only reported on a real 404/410.
  - key phrases (waking / Self_awareness / Overload / …) scanned across the
    homepage AND every post/page body; alerts when one newly appears anywhere.
  - sitemap index + image-sitemap <lastmod> (incl. the /tr4ce/ "canary")
  - tr4ce image BYTES (sha256) — catches an in-place pixel/stego edit even when
    the upload date / lastmod doesn't move.
  - homepage HTML (digit-normalized hash, so the live visitor counter doesn't
    cause false alerts, but new text/structure does) + key-phrase presence
  - the reserved 2nd site theskyscraperarchitect-ywvhk.wordpress.com — alerts on
    ANY change (post count, non-placeholder count, or latest title), loudly when
    it first gets real content.
  - Bluesky @skyscraper-prj.bsky.social latest post (clean public API)

Config: reads webhook URLs from ./config.env (KEY=VALUE lines) or the
SKYSCRAPER_WEBHOOK_URL env var. Multiple webhooks are supported — repeat
the WEBHOOK_URL line, use suffixed keys (WEBHOOK_URL_2, WEBHOOK_URL_DEV…),
and/or comma-separate URLs on one line. Each is alerted independently, so
one dead webhook won't stop the rest. If none set, changes are logged only.

ETARC forum mirror (optional): if DISCOURSE_USER_API_KEY + DISCOURSE_TOPIC_ID
are set in config.env, the SAME change announcement is also posted as a reply
to that Discourse thread (forums.atlas-65.com). Get the key with --authorize.
Runtime is still pure stdlib — only the one-time --authorize step shells out to
`openssl` (present on the Pi) for the RSA key handshake.

Run: python3 skyscraper_watch.py            (normal poll)
     python3 skyscraper_watch.py --seed     (snapshot now, never alert)
     python3 skyscraper_watch.py --test      (send a test webhook + forum probe)
     python3 skyscraper_watch.py --authorize (one-time: mint an ETARC User API Key)

NOTE: after deploying a version that adds new tracked fields, run once with
--seed so the baseline includes them (otherwise the first real poll could
fire a burst of "newly appeared" phrase alerts against an old-format state).
"""
import json, os, sys, time, hashlib, re, urllib.request, urllib.error, datetime, difflib
from html import unescape
try:
    import fcntl as _fcntl
except ImportError:
    _fcntl = None  # Windows (dev); locking skipped

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "state.json")
LOG_FILE   = os.path.join(HERE, "watch.log")
UA = "Mozilla/5.0 (skyscraper-watch; +havenmap.online)"
SITE = "https://project-skyscraper.com"
SITE2 = "theskyscraperarchitect-ywvhk.wordpress.com"
BSKY_ACTOR = "skyscraper-prj.bsky.social"
DISCOURSE_BASE_DEFAULT = "https://forums.atlas-65.com"
# RSA private key for the one-time User API Key handshake (gitignored).
DISCOURSE_PRIV_KEY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discourse_priv.pem")

# Key phrases scanned across the homepage AND every post/page body. A phrase
# going from absent→present anywhere is high signal (ARG state words).
KEY_PHRASES = ["System Filtering Platform", "Live Connection Attempts", "SECURITY",
               "Access denied", "waking", "Self_awareness", "Overload"]

# Any media URL containing one of these substrings gets its raw bytes hashed
# every run, so an in-place edit is caught even if WP doesn't bump the date.
IMAGE_HASH_MATCH = ("tr4ce",)

# Cap stored body text per item so state.json stays reasonable.
MAX_TEXT_CHARS = 8000


def cfg_get(key, default=""):
    """Read a single KEY=VALUE from config.env, falling back to env then default."""
    import os
    path=os.path.join(HERE,"config.env")
    if os.path.exists(path):
        for ln in open(path, encoding="utf-8"):
            ln=ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k,v=ln.split("=",1)
                if k.strip()==key:
                    return v.strip().strip('"').strip("'")
    return os.environ.get(key, default)


def trigger_archive_crawl():
    """Ask the GoodGuysFree archive to re-crawl after we post a real change. Fire-and-forget."""
    import hmac, hashlib, time, os, requests
    secret=cfg_get("ARCHIVE_TRIGGER_SECRET").strip()
    url=cfg_get("ARCHIVE_TRIGGER_URL").strip()
    if not secret or not url:
        return
    ts=str(int(time.time()))
    body="{}"
    sig=hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
    try:
        r=requests.post(url, headers={"Content-Type":"application/json","X-Timestamp":ts,"X-Signature":f"sha256={sig}"}, data=body, timeout=10)
        log(f"[archive] trigger -> {r.status_code}")
    except Exception as e:
        log(f"[archive] trigger failed: {e}")


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


def load_setting(key, default=""):
    """Read a single KEY=VALUE setting from the env or ./config.env (env wins)."""
    env = os.environ.get(key)
    if env:
        return env
    p = os.path.join(HERE, "config.env")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                if k.strip().upper() == key.upper():
                    return v.strip().strip('"').strip("'")
    return default


def _bust(url):
    """Append a unique throwaway query param so WordPress.com's edge cache
    treats every poll as a fresh URL → forces a cache MISS → reads origin.

    project-skyscraper.com is on WordPress.com Atomic (a8c CDN). It caches each
    REST URL as its own bucket; a post-edit purge doesn't reliably hit every
    parametrized variant, so repeatedly polling the SAME url gets served a stale
    cached snapshot (cache;desc=HIT) for ~8-13 min after an edit even though
    origin already has the change. A unique _cb nonce sidesteps the HIT entirely.
    """
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}_cb={time.time_ns()}"


def fetch(url, as_json=True, timeout=25, nocache=False):
    if nocache:
        url = _bust(url)
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if nocache:
        headers["Cache-Control"] = "no-cache"
        headers["Pragma"] = "no-cache"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw.decode("utf-8", "replace")) if as_json else raw.decode("utf-8", "replace")


def fetch_bytes(url, timeout=30, nocache=True):
    """Raw-bytes fetch (for hashing images — fetch() would mangle binary)."""
    if nocache:
        url = _bust(url)
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if nocache:
        headers["Cache-Control"] = "no-cache"
        headers["Pragma"] = "no-cache"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_all(url_base, per_page=100, max_pages=25, timeout=25, nocache=True):
    """Fetch a WP REST collection across ALL pages.

    Returns (items, complete). `complete` is True only if we walked the whole
    collection without a network/parse error — callers use it to decide whether
    'missing now' can be trusted as a deletion. A page past the end returns WP's
    400 rest_post_invalid_page_number, which we treat as a clean stop.

    nocache=True (default) busts the edge cache per request so the modified-desc
    feed reflects an edit on the very next poll instead of lagging the WP.com
    cache TTL — see _bust().
    """
    items, page = [], 1
    while page <= max_pages:
        sep = "&" if "?" in url_base else "?"
        url = f"{url_base}{sep}per_page={per_page}&page={page}"
        try:
            batch = fetch(url, timeout=timeout, nocache=nocache)
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):   # past last page → done
                return items, True
            return items, False        # real HTTP error → incomplete
        except Exception:
            return items, False
        if not isinstance(batch, list) or not batch:
            break
        items.extend(batch)
        if len(batch) < per_page:      # last partial page
            break
        page += 1
    return items, True


def clean_inline(s):
    """HTML → single-line plain text (for titles)."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def html_to_text(s):
    """HTML → readable plain text, keeping line breaks so diffs are legible."""
    s = s or ""
    s = re.sub(r"(?i)<\s*br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</\s*(p|div|h[1-6]|li|tr)\s*>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", s)
    return s.strip()[:MAX_TEXT_CHARS]


def item_record(kind, p):
    """Normalize a raw WP REST object into the compact shape we store."""
    if kind == "media":
        return {"date": p.get("date_gmt", ""), "url": p.get("source_url", ""),
                "slug": p.get("slug", ""), "link": p.get("link", ""),
                "title": clean_inline((p.get("title") or {}).get("rendered", ""))}
    rec = {"mod": p["modified_gmt"], "date": p["date_gmt"], "slug": p["slug"],
           "link": p["link"], "title": clean_inline(p["title"]["rendered"])}
    rec["text"] = html_to_text((p.get("content") or {}).get("rendered", ""))
    return rec

# sentinel: item almost certainly still exists, but the REST API refuses to
# confirm it (auth lockdown). Caller should KEEP it and stay quiet — not alert,
# not spam the inconclusive WARN every cycle.
API_LOCKED = "api_locked"

def verify_item(kind, item_id, timeout=20):
    """Direct existence check for a disappeared item.
    Returns the live REST object if it still exists, None on 404/410 (truly
    removed), API_LOCKED on 401/403 (REST locked — presume live, can't confirm),
    or False if the check itself was inconclusive (network error)."""
    url = f"{SITE}/wp-json/wp/v2/{kind}/{item_id}"
    try:
        return fetch(url, timeout=timeout, nocache=True)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return None
        if e.code in (401, 403):
            return API_LOCKED
        return False
    except Exception:
        return False


def render_text_diff(old, new, max_lines=40, max_chars=1500):
    """Unified old→new diff in a Discord ```diff block (+/- render green/red)."""
    if old == new:
        return ""
    old_lines = old.splitlines() or [old]
    new_lines = new.splitlines() or [new]
    raw = difflib.unified_diff(old_lines, new_lines, lineterm="", n=1)
    body = [l for l in raw if not l.startswith(("---", "+++", "@@"))]
    if not body:
        return ""
    body = body[:max_lines]
    out = "```diff\n" + "\n".join(body) + "\n```"
    if len(out) > max_chars:
        out = out[:max_chars] + "\n… ```"
    return out


def _scan_phrases(text, where, into):
    if not text:
        return
    low = text.lower()
    for ph in KEY_PHRASES:
        if ph.lower() in low:
            into.setdefault(ph, [])
            if where not in into[ph]:
                into[ph].append(where)


def snapshot():
    """Build the current state. Each source is best-effort; a fetch failure for
    one source leaves that key absent so we never false-alert on an outage."""
    s = {}
    phrase_locations = {}
    # --- WP posts (new + edited + removed) — full pagination ---
    try:
        posts, complete = fetch_all(f"{SITE}/wp-json/wp/v2/posts?orderby=modified&order=desc")
        if posts or complete:
            s["posts"] = {str(p["id"]): item_record("posts", p) for p in posts}
            s["posts_complete"] = complete
            for rec in s["posts"].values():
                _scan_phrases(rec.get("title", "") + "\n" + rec.get("text", ""),
                              f"post: {rec.get('title','?')}", phrase_locations)
    except Exception as e:
        log(f"WARN posts fetch failed: {e}")
    # --- WP pages (new + edited + removed) — full pagination ---
    try:
        pages, complete = fetch_all(f"{SITE}/wp-json/wp/v2/pages?orderby=modified&order=desc")
        if pages or complete:
            s["pages"] = {str(p["id"]): item_record("pages", p) for p in pages}
            s["pages_complete"] = complete
            for rec in s["pages"].values():
                _scan_phrases(rec.get("title", "") + "\n" + rec.get("text", ""),
                              f"page: {rec.get('title','?')}", phrase_locations)
    except Exception as e:
        log(f"WARN pages fetch failed: {e}")
    # --- WP media (new + removed) — full pagination ---
    try:
        media, complete = fetch_all(f"{SITE}/wp-json/wp/v2/media?orderby=date&order=desc")
        if media or complete:
            s["media"] = {str(m["id"]): item_record("media", m) for m in media}
            s["media_complete"] = complete
    except Exception as e:
        log(f"WARN media fetch failed: {e}")
    # --- sitemaps (incl. /tr4ce/ canary) ---
    try:
        # NOTE: sitemap XML is a virtual WP route that 404s on an extra query
        # param, so it can't be _cb-busted; left on the normal cached fetch.
        idx = fetch(f"{SITE}/sitemap.xml", as_json=False)
        s["sitemap_lastmods"] = dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", idx))
        img = fetch(f"{SITE}/image-sitemap-1.xml", as_json=False)
        pairs = re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", img)
        s["image_lastmods"] = {loc: lm for loc, lm in pairs}
    except Exception as e:
        log(f"WARN sitemap fetch failed: {e}")
    # --- tr4ce image BYTES hash (catches in-place pixel/stego edits) ---
    try:
        targets = sorted({m.get("url", "") for m in s.get("media", {}).values()
                          if m.get("url") and any(t in m["url"].lower() for t in IMAGE_HASH_MATCH)})
        # also pick up tr4ce image-sitemap entries that resolve to a file URL
        img_hashes = {}
        for u in targets:
            try:
                b = fetch_bytes(u)
                img_hashes[u] = {"sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
            except Exception as e:
                log(f"WARN image hash fetch failed for {u}: {e}")
        if img_hashes:
            s["image_hashes"] = img_hashes
    except Exception as e:
        log(f"WARN image-hash stage failed: {e}")
    # --- homepage (digit-normalized hash + key phrases) ---
    try:
        home = fetch(f"{SITE}/", as_json=False, nocache=True)
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
        s["home_phrases"] = sorted({ph for ph in KEY_PHRASES if ph.lower() in home.lower()})
        _scan_phrases(home, "homepage", phrase_locations)
    except Exception as e:
        log(f"WARN homepage fetch failed: {e}")
    # --- reserved 2nd site ---
    try:
        p2 = fetch(f"https://public-api.wordpress.com/wp/v2/sites/{SITE2}/posts?per_page=20", nocache=True)
        non_default = [x for x in p2 if x.get("slug") != "hello-world"]
        s["site2"] = {"count": len(p2), "non_default": len(non_default),
                      "latest": (re.sub("<[^>]+>", "", p2[0]["title"]["rendered"]).strip() if p2 else "")}
    except Exception as e:
        log(f"WARN site2 fetch failed: {e}")
    # --- Bluesky latest post ---
    try:
        feed = fetch(f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor={BSKY_ACTOR}&limit=5", nocache=True)
        items = feed.get("feed", [])
        if items:
            top = items[0]["post"]
            s["bsky"] = {"cid": top.get("cid", ""),
                         "text": (top.get("record", {}).get("text", "") or "")[:200],
                         "indexedAt": top.get("indexedAt", "")}
    except Exception as e:
        log(f"WARN bluesky fetch failed: {e}")
    # finalize cross-content phrase index
    s["phrase_locations"] = {k: v for k, v in phrase_locations.items()}
    s["phrases_present"] = sorted(phrase_locations)
    return s


def diff(old, new):
    """Return (changes, preserve).

    `changes` is a list of human-readable change strings (highest signal first).
    `preserve` maps kind→{id:record} of items that LOOKED deleted but verified as
    still-present (or were inconclusive) — main() merges these into the new state
    before writing, so a feed glitch never silently drops a real item.
    """
    ch = []
    preserve = {}

    # second site: any change, loud when it first gets real content
    o2, n2 = old.get("site2"), new.get("site2")
    if o2 and n2 and (o2.get("count") != n2.get("count")
                      or o2.get("non_default") != n2.get("non_default")
                      or o2.get("latest") != n2.get("latest")):
        if n2.get("non_default", 0) > o2.get("non_default", 0):
            ch.append(f"🚨 **RESERVED 2ND SITE HAS NEW CONTENT** — {SITE2} now has "
                      f"{n2['non_default']} non-placeholder post(s). Latest: “{n2.get('latest','')}”. "
                      f"https://{SITE2}/")
        else:
            bits = []
            if o2.get("count") != n2.get("count"):
                bits.append(f"posts {o2.get('count')}→{n2.get('count')}")
            if o2.get("non_default") != n2.get("non_default"):
                bits.append(f"non-placeholder {o2.get('non_default')}→{n2.get('non_default')}")
            if o2.get("latest") != n2.get("latest"):
                bits.append(f"latest “{o2.get('latest','')}”→“{n2.get('latest','')}”")
            ch.append(f"🛰️ **Reserved 2nd site changed** — {', '.join(bits)}. https://{SITE2}/")

    # posts: new + edited (with text diff)
    op, np_ = old.get("posts", {}), new.get("posts", {})
    for pid, p in np_.items():
        if pid not in op:
            ch.append(f"🆕 **New post** — “{p['title']}” ({p['slug']}) published {p.get('date','')}Z\n{p['link']}")
        elif op[pid].get("mod") != p.get("mod"):
            o_text = op[pid].get("text")
            if o_text is None:
                detail = "_(no prior text on record — re-seed to enable diffs)_"
            else:
                d = render_text_diff(o_text, p.get("text", ""))
                detail = d if d else "_(modified timestamp bumped; no visible text change)_"
            verb = "Post edited" if (op[pid].get("text") != p.get("text")) else "Post re-saved"
            ch.append(f"✏️ **{verb}** — “{p['title']}” ({p['slug']}) modified {p['mod']}Z\n{p['link']}\n{detail}")

    # pages: new + edited (with text diff)
    opg, npg = old.get("pages", {}), new.get("pages", {})
    for pid, p in npg.items():
        if pid not in opg:
            ch.append(f"📄 **New page** — “{p['title']}” ({p['slug']})\n{p['link']}")
        elif opg[pid].get("mod") != p.get("mod"):
            o_text = opg[pid].get("text")
            if o_text is None:
                detail = "_(no prior text on record — re-seed to enable diffs)_"
            else:
                d = render_text_diff(o_text, p.get("text", ""))
                detail = d if d else "_(modified timestamp bumped; no visible text change)_"
            verb = "Page edited" if (opg[pid].get("text") != p.get("text")) else "Page re-saved"
            ch.append(f"📝 **{verb}** — “{p['title']}” ({p['slug']}) modified {p['mod']}Z\n{p['link']}\n{detail}")

    # media: new uploads
    om, nm = old.get("media", {}), new.get("media", {})
    for mid, m in nm.items():
        if mid not in om:
            ch.append(f"🖼️ **New media upload** — {m['url']} ({m.get('date','')}Z)")

    # removals (posts/pages/media) — only on a COMPLETE fetch, verified by 404
    for kind, label in (("posts", "post"), ("pages", "page"), ("media", "media")):
        o = old.get(kind, {})
        n = new.get(kind, {})
        if not o or not new.get(f"{kind}_complete"):
            continue
        for did in set(o) - set(n):
            live = verify_item(kind, did)
            rec = o[did]
            name = rec.get("title") or rec.get("url") or did
            if live is None:                       # confirmed gone
                ch.append(f"🗑️ **{label.capitalize()} removed** — “{name}” "
                          f"({rec.get('slug','')}) returned HTTP 404\n{rec.get('link','')}")
            elif live is API_LOCKED:               # REST locked — presume live, keep quietly
                preserve.setdefault(kind, {})[did] = rec
            elif live is False:                    # inconclusive — keep, don't alert
                log(f"WARN deletion verify inconclusive for {kind} {did}; carrying forward")
                preserve.setdefault(kind, {})[did] = rec
            else:                                  # still exists — fetch missed it; refresh+keep
                log(f"NOTE {kind} {did} absent from list but still live; carrying forward")
                preserve.setdefault(kind, {})[did] = item_record(kind, live)

    # canary: per-image lastmod changes (esp. /tr4ce/)
    oil, nil = old.get("image_lastmods", {}), new.get("image_lastmods", {})
    for loc, lm in nil.items():
        if loc in oil and oil[loc] != lm:
            tag = "  ⚠️ TR4CE CANARY TRIPPED" if "tr4ce" in loc.lower() else ""
            ch.append(f"🗺️ **Image re-uploaded** — {loc} lastmod {oil[loc]} → {lm}{tag}")

    # tr4ce image BYTES changed (pixel/stego edit even if lastmod didn't move)
    oih, nih = old.get("image_hashes", {}), new.get("image_hashes", {})
    for u, info in nih.items():
        if u in oih and oih[u].get("sha256") != info.get("sha256"):
            ch.append(f"🧬 **Image BYTES changed** — {u}\n"
                      f"sha256 {oih[u].get('sha256','')[:12]}… → {info.get('sha256','')[:12]}… "
                      f"({oih[u].get('bytes')}→{info.get('bytes')} bytes)  "
                      f"⚠️ pixel/stego change even if the upload date didn't move")

    # key phrases newly appearing anywhere (homepage or any post/page body)
    if "phrases_present" in old:
        op_set, np_set = set(old.get("phrases_present", [])), set(new.get("phrases_present", []))
        loc = new.get("phrase_locations", {})
        for ph in sorted(np_set - op_set):
            where = ", ".join(loc.get(ph, [])) or "somewhere"
            ch.append(f"🔔 **Key phrase appeared** — “{ph}” now present in: {where}")
        for ph in sorted(op_set - np_set):
            ch.append(f"🔕 **Key phrase gone** — “{ph}” no longer present anywhere")

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
    return ch, preserve


def send_discord(webhook, changes):
    when = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M UTC")
    desc = "\n\n".join(changes)
    if len(desc) > 3900:
        desc = desc[:3900] + "\n… (truncated)"
    payload = {
        "username": "Skyscraper Watch",
        "embeds": [{
            "title": f"🛰️ Project Skyscraper — {len(changes)} {'change' if len(changes) == 1 else 'changes'} detected",
            "description": desc,
            "color": 0xF7C948,
            "footer": {"text": f"skyscraper_watch • {when}"},
        }],
    }
    req = urllib.request.Request(webhook, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def send_discourse(base, user_api_key, topic_id, changes):
    """Post the same change announcement as a reply to a Discourse topic.

    Uses a User API Key (header `User-Api-Key`) — no admin key needed. The body
    reuses the exact `changes` lines the Discord channel gets, so the forum post
    mirrors the dedicated channel. Discourse renders the ```diff blocks, bold,
    links and emoji the same way Discord does.
    """
    when = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M UTC")
    n = len(changes)
    noun = "change" if n == 1 else "changes"
    # Discourse markdown: ## heading = title, --- rules = card separation, the
    # change lines keep their ```diff fences + bare URLs (which Discourse oneboxes
    # into preview cards — the closest thing to a native embed).
    raw = (f"## 🛰️ Project Skyscraper — {n} {noun} detected\n\n"
           "---\n\n"
           + "\n\n".join(changes)
           + f"\n\n---\n*🔭 skyscraper_watch · {when}*")
    if len(raw) > 30000:                       # Discourse max_post_length is 32000
        raw = raw[:30000] + "\n… (truncated)"
    payload = {"topic_id": int(topic_id), "raw": raw}
    req = urllib.request.Request(
        base.rstrip("/") + "/posts.json",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Api-Key": user_api_key, "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status


def authorize_user_api_key():
    """One-time: mint a Discourse User API Key via the public key handshake.

    Generates (or reuses) an RSA keypair with `openssl`, prints the authorize
    URL, and decrypts the payload you paste back. Prints the config.env lines to
    add. openssl is only needed here — the cron runtime never touches crypto.
    """
    import subprocess, base64, secrets, urllib.parse
    base = (load_setting("DISCOURSE_BASE") or DISCOURSE_BASE_DEFAULT).rstrip("/")
    if not os.path.exists(DISCOURSE_PRIV_KEY):
        subprocess.run(["openssl", "genrsa", "-out", DISCOURSE_PRIV_KEY, "2048"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            os.chmod(DISCOURSE_PRIV_KEY, 0o600)
        except OSError:
            pass
        print(f"Generated RSA private key at {DISCOURSE_PRIV_KEY} (keep it secret; it's gitignored).")
    pub = subprocess.run(["openssl", "rsa", "-in", DISCOURSE_PRIV_KEY, "-pubout"],
                         check=True, capture_output=True, text=True).stdout
    nonce = secrets.token_hex(16)
    params = {
        "application_name": "Skyscraper Haven Watch",
        "client_id": secrets.token_hex(16),
        "scopes": "write",
        "public_key": pub,
        "nonce": nonce,
    }
    url = base + "/user-api-key/new?" + urllib.parse.urlencode(params)
    print("\n1) In a browser logged into the forum as your account, open:\n")
    print(url)
    print("\n2) Click Authorize, copy the payload it shows, paste it below,")
    print("   then press Enter on a blank line:\n")
    lines = []
    try:
        while True:
            ln = input()
            if ln.strip() == "":
                if lines:
                    break
                continue
            lines.append(ln.strip())
    except EOFError:
        pass
    payload_b64 = re.sub(r"\s+", "", "".join(lines))
    if not payload_b64:
        print("No payload entered; aborting."); return
    try:
        enc = base64.b64decode(payload_b64)
    except Exception as e:
        print(f"Payload isn't valid base64: {e}"); return
    dec = subprocess.run(["openssl", "pkeyutl", "-decrypt", "-inkey", DISCOURSE_PRIV_KEY],
                         input=enc, capture_output=True)
    if dec.returncode != 0:
        print("Decryption failed:", dec.stderr.decode("utf-8", "replace")); return
    try:
        obj = json.loads(dec.stdout)
    except ValueError:
        print("Decrypted payload wasn't JSON; aborting."); return
    if obj.get("nonce") != nonce:
        print("Nonce mismatch — aborting (possible replay or wrong key)."); return
    print("\n✅ Authorized. Add these lines to config.env (gitignored):\n")
    print(f"DISCOURSE_BASE={base}")
    print(f"DISCOURSE_USER_API_KEY={obj.get('key','')}")
    print("DISCOURSE_TOPIC_ID=9299   # 9299 = 'Sunday Morning poem' thread; 9239 = 'Skyscraper Haven Map'")


def main():
    webhooks = load_config()
    if "--authorize" in sys.argv:
        authorize_user_api_key()
        return

    d_key = load_setting("DISCOURSE_USER_API_KEY")
    d_topic = load_setting("DISCOURSE_TOPIC_ID")
    d_base = load_setting("DISCOURSE_BASE") or DISCOURSE_BASE_DEFAULT

    if "--test" in sys.argv:
        if not webhooks and not d_key:
            log("--test: nothing configured (no WEBHOOK_URL, no DISCOURSE_USER_API_KEY)"); sys.exit(1)
        msg = ["✅ Test alert — skyscraper_watch is wired up and can reach this channel."]
        for i, w in enumerate(webhooks, 1):
            try:
                st = send_discord(w, msg)
                log(f"--test: webhook {i}/{len(webhooks)} -> HTTP {st}")
            except Exception as e:
                log(f"--test: webhook {i}/{len(webhooks)} ERROR: {e}")
        if d_topic:
                try:
                    st = send_discourse(d_base, d_key, d_topic,
                        ["🛰️ **skyscraper_watch test** — integration check; automated updates will drop here. (safe to delete)"])
                    log(f"--test: ETARC forum post (topic {d_topic}) -> HTTP {st}")
                except Exception as e:
                    log(f"--test: ETARC forum post ERROR: {e}")
        return

    # Prevent concurrent cron runs from racing on state.json.
    # SSL timeouts can push a single run past 2 minutes, so the next cron
    # instance starts while the previous one is still sending webhooks.
    _lock_fh = None
    if _fcntl is not None:
        lock_path = os.path.join(HERE, "watch.lock")
        try:
            _lock_fh = open(lock_path, "w")
            _fcntl.flock(_lock_fh, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        except OSError:
            log("WARN another instance is already running — exiting to avoid duplicate alerts.")
            sys.exit(0)

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

    if seeding:
        changes, preserve = [], {}
    else:
        changes, preserve = diff(old, new)

    # carry forward items that looked deleted but verified as still-present
    for kind, items in preserve.items():
        new.setdefault(kind, {}).update(items)

    # Carry forward any section that failed to fetch this cycle.
    # An SSL/timeout exception in snapshot() leaves those keys absent from `new`.
    # Without this, the NEXT successful cycle sees an empty old-state for that
    # section and reports every item as brand-new — flooding Discord and the
    # ETARC forum with duplicate alerts on every intermittent network blip.
    for _k in ("pages", "pages_complete", "media", "media_complete",
               "image_hashes", "image_lastmods", "home_hash", "home_phrases",
               "site2", "bsky"):
        if _k not in new and _k in old:
            new[_k] = old[_k]

    json.dump(new, open(STATE_FILE, "w", encoding="utf-8"), indent=1)

    if seeding:
        log(f"Seeded baseline: {len(new.get('posts',{}))} posts, {len(new.get('pages',{}))} pages, "
            f"{len(new.get('media',{}))} media, {len(new.get('phrases_present',[]))} key-phrases present, "
            f"{len(new.get('image_hashes',{}))} image-hash(es). No alert sent.")
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

    # mirror the same announcement to the ETARC Discourse thread, if configured
    if d_key and d_topic:
        try:
            st = send_discourse(d_base, d_key, d_topic, changes)
            log(f"ETARC forum post (topic {d_topic}) -> HTTP {st}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            log(f"ERROR posting to ETARC forum: HTTP {e.code} {detail}")
        except Exception as e:
            log(f"ERROR posting to ETARC forum: {e}")
    elif d_key and not d_topic:
        log("DISCOURSE_USER_API_KEY set but DISCOURSE_TOPIC_ID missing — forum mirror skipped.")

    # --- ping the GoodGuysFree archive to re-crawl now that a real change posted ---
    try:
        trigger_archive_crawl()
    except Exception as e:
        log(f"ERROR triggering archive re-crawl: {e}")



if __name__ == "__main__":
    main()
