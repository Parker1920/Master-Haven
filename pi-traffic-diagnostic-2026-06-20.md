# Pi 8GB Traffic + Capacity Diagnostic — 2026-06-20

READ-ONLY diagnostic. All numbers below are measured from NPM access logs and live
system commands on the Pi (`pi8gb`). Logs are live-growing, so totals reflect the
moment of capture (~16:12 local / 15:11 UTC, 2026-06-20). Where a number could not be
measured, that fact is stated instead of an estimate.

Measurement window (longest window common to all 8 active access logs):
**15/Jun/2026 23:10 UTC → 20/Jun/2026 15:11 UTC  (~4.67 days; full days = Jun 16–19)**
Rotated `.1.gz`–`.4.gz` logs extend back to ~late May but were not merged in (keeping a
consistent 5-day active window makes per-domain comparison clean).

================================================================================
## 1. HEADLINE
================================================================================

- **Total requests hitting the Pi origin (all 8 domains, ~4.67 days): 138,167**
  - Internal uptime-monitor polling (Docker gateway 172.18.0.1): **20,726 (15%)**
  - **Real external foot traffic: 117,441** (~23,400/day on full days)
- **Busiest day: Jun 19 = 39,707 requests** (havenmap 16,083 + grandfestival 13,410 lead it)
- **Peak requests/minute: 1,278** — BUT 1,272 of those were ONE vuln-scanner bot
  (`45.148.10.67`, UA `TLM-Audit-Scanner/1.0`). **Genuine peak ~362/min (~6 req/sec).**
- **Bandwidth served from origin: 6,632 MB (~6.5 GB)** over the window (~1.4 GB/day).
- **Current load average: 0.08 / 0.14 / 0.13** on 4 cores → CPU ~3% utilized (idle).
- **RAM available: 5.4 GiB free of 7.9 GiB** → no memory pressure.
- **Throttle status: 0x0** → never throttled (no undervolt / thermal event this boot).
- **Disk: 85% full (18 GB free)** → the ONLY on-box metric in caution range.

One-line: the Pi is loafing. Compute is nowhere near a wall. The real scaling risk is
the residential uplink + WiFi link and the fact that 4 of 8 domains have NO edge in
front of them. A single scanner bot generated more burst load than all real users
combined, and the Pi did not notice.

================================================================================
## 2. PER-DOMAIN TABLE (measurement window)
================================================================================

Path = DNS-only (hits Pi directly, no edge) vs Proxied (Cloudflare in front).
"External" = total minus internal 172.18.0.1 monitor hits.

| Domain                      | Path     | Total  | Monitor | External | Peak/min          | Status mix (top)                      |
|-----------------------------|----------|--------|---------|----------|-------------------|---------------------------------------|
| havenmap.online             | DNS-only | 63,719 | 7,499   | 56,220   | 1,278 (1,272=bot) | 200=54080 404=3293 401=2931 304=1167  |
| grandfestival.online        | DNS-only | 32,244 | 6,609   | 25,635   | 157               | 200=31888 304=169 404=63              |
| nms10.online                | Proxied  | 8,590  | 0       | 8,590    | 862 (burst)       | 200=8499 304=72 404=9                 |
| travelers-exchange.online   | Proxied  | 8,494  | 0       | 8,494    | 489               | 200=6957 404=1478                     |
| status.havenmap.online      | DNS-only | 8,173  | 0       | 8,173    | 39                | 200=8084 404=67                       |
| skyscraper.havenmap.online  | Proxied  | 7,936  | 0       | 7,936    | 11                | 200=7162 404=391 304=378              |
| haven-archive.online        | DNS-only | 7,368  | 6,611   | 757      | 47                | 200=7177 401=158                      |
| viobot.havenmap.online      | Proxied  | 1,623  | 3       | 1,620    | 1,226 (bot)       | 404=1457 200=105                      |
| **TOTAL**                   |          | **138,167** | **20,726** | **117,441** | 1,278 raw / ~362 real | 2xx dominant, 4xx mostly bots |

Per-domain bandwidth (sum of Length field): havenmap 5,200 MB | grandfestival 930 MB |
skyscraper 444 MB | status 22 MB | travelers-exchange 15 MB | haven-archive 13 MB |
nms10 5.6 MB | viobot 2.4 MB. (havenmap = 78% of origin bytes: gzipped React app + posters.)

Distinct external source IPs (reach — DNS-only domains only; proxied ones hide users
behind Cloudflare IPs so reach cannot be measured there): havenmap **791**,
grandfestival **1,637**. Grand Festival reached the widest unique audience.

### Bot / scanner classification (confirmed)
- `45.148.10.67` — UA `TLM-Audit-Scanner/1.0`, 1,272 req in one minute, TWICE (Jun 19
  05:31 + Jun 20 05:06). Pure vuln scan against havenmap. Owns the headline 1,278/min peak.
- viobot 404 flood: 1,457 of 1,620 "external" hits are 404s for `/.env`, `/.env.prod`,
  `/.git/config`, `/config.json` — classic secret-scraping bot (came via Cloudflare).
  Real viobot human traffic is ~160 requests, not 1,620.
- travelers-exchange 1,478 404s and the nms10 862/min burst (Jun 16 15:46) are similar
  scanner noise relayed through Cloudflare.
- havenmap top IP `65.30.235.252` (10,734 hits) is NOT a scanner — referers are
  `/haven-ui` and `/pending-approvals` and it polls `/api/activity_logs`; this is a heavy
  authenticated admin/dashboard session (almost certainly Parker or an admin tab left open).
  Same pattern for `50.5.100.253`, `94.7.190.28`.

### Haven Control Room (uvicorn/FastAPI) in-process view
uvicorn access logging IS on. `docker logs haven` only retains since the last restart
(~11h ago): **7,897 HTTP requests in ~11h ≈ 17K/day to the API alone** — consistent with
the NPM havenmap count. The API log shows real client IPs (NPM forwards them) and is
dominated by `/api/activity_logs?limit=50` dashboard polling. NPM logs remain the
authoritative full-window source; the uvicorn log is too short-lived for trend work.

================================================================================
## 3. RESOURCE SNAPSHOT (live, 2026-06-20 ~16:12 local)
================================================================================

| Metric               | Value                          | Reading                                   |
|----------------------|--------------------------------|-------------------------------------------|
| Uptime               | 14 days, 16h                   | Stable                                    |
| Load avg (1/5/15m)   | 0.08 / 0.14 / 0.13             | 4 cores → ~3% used. CPU idle.             |
| RAM total            | 7.9 GiB                        |                                           |
| RAM used             | 2.5 GiB                        |                                           |
| RAM free             | 1.4 GiB                        |                                           |
| buff/cache           | 4.4 GiB                        |                                           |
| RAM available        | **5.4 GiB**                    | No memory pressure                        |
| Swap used            | 410 MiB / 2.0 GiB              | Light, normal                             |
| Disk / and ~/docker  | 95G / 117G (**85%**, 18G free) | Same partition; closest to a wall         |
| Temp                 | 48.3°C                         | Cool                                      |
| Throttled            | **0x0**                        | Never throttled (no power/thermal events) |
| CPU cores            | 4                              |                                           |

### Per-container RAM — NOT AVAILABLE via docker stats
`docker stats` reports `0B / 0B` for every container because the kernel cmdline has
**`cgroup_disable=memory`** (memory cgroup accounting is OFF on this Pi). Per-container RAM
was therefore NOT fabricated. Substitute = host-wide top processes by RSS:

  397 MB dockerd | 213 MB containerd | 191 MB haven-trade-engine paper_book loop |
  187 MB node (nms10) | 164 MB python server.py | 159 MB headless_shell (Haven poster
  Chromium) | 131 MB playwright driver | 109 MB uvicorn (haven) | 99 MB tailscaled |
  93 MB haven-trade-engine uvicorn | 70–91 MB several app workers.

Notes: ~610 MB is Docker engine overhead; ~284 MB is the **Haven Trade Engine running
directly on the Pi** (an algo-trading process, not a website). Web apps themselves are
modest (each uvicorn/node worker 70–190 MB). Per-container CPU% (this DOES report): all
<1% except haven-status 2.5% and npm 1.4%.

================================================================================
## 4. PROXY PATH SUMMARY
================================================================================

All 8 domains terminate at Nginx Proxy Manager (`npm` container, host ports 80/81/443)
on the Pi. Each has a live `proxy_host/N.conf` and a non-empty access log.

DNS-only (resolve to residential 174.59.238.206, **NO edge — Pi eats 100%**): 4 domains
  - havenmap.online (→ haven:8005)
  - grandfestival.online (→ grand-festival:8000)
  - haven-archive.online (→ archive:8020)
  - status.havenmap.online (→ haven-status :8011)

Proxied via Cloudflare (104.x / 172.6x–7x): 4 domains
  - travelers-exchange.online (→ exchange:8010)
  - nms10.online (→ nms10-frontend :8090)
  - skyscraper.havenmap.online (→ skyscraper-static:80)
  - viobot.havenmap.online (→ viobot-static:80)

What this means for origin load:
- The 4 DNS-only domains include the 3 heaviest real apps (Control Room, Grand Festival,
  Status). Every request, byte, and bot scan lands on the Pi through the home connection
  with zero edge shielding. This is where the foot traffic — and the risk — concentrates.
- For the 4 proxied domains, Cloudflare absorbs static assets and floods at the edge, but
  NPM has NO caching of its own, so uncached/dynamic requests still reach the Pi. IMPORTANT
  SIDE EFFECT: NPM logs Cloudflare's connecting IP for these domains (no real-IP /
  X-Forwarded restoration configured), so real end-user IPs and bot-vs-human split CANNOT
  be measured for the proxied 4 from these logs.

================================================================================
## 5. BOTTLENECK CALL
================================================================================

No compute resource is near a wall — with numbers:
- CPU: load 0.13 across 4 cores = ~3%. Even the worst scanner burst (1,272 req/min ~21/s)
  left load near zero. CPU is NOT the constraint.
- RAM: 5.4 GiB available, swap barely touched. NOT the constraint. (The brief anticipated a
  "RAM ceiling" — the measured numbers do not support that; there is large headroom. The
  cgroup_disable=memory flag hid per-container RAM, but the HOST has ample free memory.)
- Thermal/power: 48°C, throttled=0x0. NOT the constraint.

Closest to a wall, in order:
1. **Disk: 85% (18 GB free).** Slow-moving but the only on-box metric in caution range.
   Growth drivers: haven_ui.db + uploaded photos + NPM access/error logs + letsencrypt.log
   (which rotates absurdly — hundreds of ~22 KB copies). Not urgent; watch it.
2. **Residential uplink + WiFi link (the true scaling limit).** The Pi is on 5 GHz WiFi
   (not wired) behind a Comcast/Xfinity residential upload, and 4 domains have no edge. All
   DNS-only domains share this one uplink simultaneously. A single bot already pushed ~21
   req/sec; many concurrent real users during an event would saturate the home upload and
   add WiFi jitter long before the Pi CPU/RAM cared.

Bottom line: the box can take far more load than it currently sees. The first thing to break
under real growth is the network path (home upload + WiFi + no edge on DNS-only domains),
not the Pi hardware.

================================================================================
## 6. NMS10 GROWTH PROJECTION
================================================================================

Base = MEASURED Grand Festival ORIGIN load (DNS-only, the closest comparable real app):
  - ~25,635 external requests over the window; busiest day 13,410; peak 157 req/min; ~930 MB.
Conservative note: nms10.online is actually Cloudflare-PROXIED, so for equal end-user traffic
its ORIGIN load is LOWER than Grand Festival (CF serves static from edge). Modeling it as if
DNS-only is therefore a worst case.

| Scale | Busiest day (req) | Peak req/min (~req/s) | Bandwidth (window) | First resource to feel it          |
|-------|-------------------|------------------------|--------------------|------------------------------------|
| 1x    | 13,410            | 157 (~3/s)             | ~0.93 GB           | nothing notices                    |
| 2x    | ~26,800           | ~314 (~5/s)            | ~1.9 GB            | nothing notices                    |
| 5x    | ~67,000           | ~785 (~13/s)           | ~4.6 GB            | uplink during peak minutes; CPU ~10–20% of 1 core |
| 10x   | ~134,000          | ~1,570 (~26/s)         | ~9.3 GB            | **residential UPLOAD + WiFi link saturates first** during spikes; disk fills faster from DB/photo growth |

At 10x, the Pi CPU (4 cores) and RAM (5.4 GiB free) still have room — 26 req/s of a FastAPI/
nginx app is well within a Pi 5. The wall is the home upload bandwidth and WiFi during peak
minutes, made worse by no edge on DNS-only domains. Because nms10 is CF-proxied, in practice
Cloudflare absorbs most of a 10x spike and the Pi origin barely scales up — nms10 is the LEAST
risky of the apps to grow. Moving the DNS-only domains (especially Control Room + Grand
Festival) behind Cloudflare would shift their static load to the edge and remove the uplink as
the bottleneck.

================================================================================
## 7. PORT 8082 COLLISION CHECK
================================================================================

NO live collision. Verified:
- grand-festival compose: `8082:8000` (host 8082). Compose lives at the non-obvious nested
  path `~/docker/haven-ui/Master-Haven/grand-festival/docker-compose.yml` (inside the haven-ui
  repo checkout, NOT a top-level ~/docker/<name>/ dir).
- nms10 compose (`~/docker/nms10/docker-compose.yml`): backend `8000:8000`, frontend `8090:80`.
  nms10 does NOT use 8082.
- A grep for `8082` across every compose/env file under ~/docker returns ONLY the
  grand-festival line. No other service claims 8082.

So both nms10 and grand-festival compose configs exist and both are running, but they do NOT
collide (8082 vs 8000/8090). The only footgun is grand-festival's compose being buried inside
the haven-ui repo path rather than its own ~/docker/grand-festival/ dir — easy to miss during
maintenance. No action needed for ports.

================================================================================
## APPENDIX — Caveats / things NOT measured
================================================================================
- Proxied-domain real client IPs / human-vs-bot split: NOT measurable (NPM logs Cloudflare
  IPs; no real-IP restoration). Only request counts and status mix are reliable there.
- Per-container RAM: NOT measurable via docker stats (cgroup_disable=memory). RSS substitute used.
- Cloudflare edge-served bytes (cache hits never reaching the Pi): NOT visible from the Pi;
  origin bandwidth here is uncached-only for the 4 proxied domains.
- Window is the 4.67-day active-log span; older rotated .gz logs were not merged.
- Logs are live-growing; counts are a snapshot at capture time (~15:11 UTC 2026-06-20).
