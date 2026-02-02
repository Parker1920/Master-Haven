# Parker Homelab Architecture Plan — Agent Handoff

> **Last updated:** February 1, 2026
> **Purpose:** Complete context for any Claude agent continuing this project AND a learning reference for Parker. All decisions documented here are FINALIZED unless Parker explicitly reopens them. This document should be the single source of truth for this project.

---

## 1. User Profile / Haven Profile

### User Profile

**Name:** Parker
**Location:** Mechanicsburg, PA 17055 (Cumberland County, Pennsylvania). Xfinity/Comcast service area.
**GitHub:** Parker1920 — repository: Master-Haven
**Skill level:** Beginner to Linux/networking, intermediate with Python/HTML. Learning hands-on through building this homelab.
**Dev environment:** Home desktop computer (Windows). Planning sessions sometimes happen on phone but all real work is done at the desktop.

### Working Style
Parker operates as the "manager" and expects Claude to operate as the "coding team." This means:
- **Present options with pros/cons** and a recommendation, but always let Parker make the final call
- **Do not assume or decide on his behalf** — if something is unclear, ask
- **Technical depth is welcome** but skip filler and corporate fluff — get to the point
- **Explain the WHY behind things**, not just the steps — Parker is building long-term knowledge, not just following a recipe
- **Ask clarifying questions** rather than guessing when a request is ambiguous

### What Parker Knows So Far
Through our planning sessions and hands-on work, Parker has learned and understands the following concepts:
- What ports are (service identifiers 0-65535), well-known ports (22=SSH, 53=DNS, 80=HTTP, 443=HTTPS), and how browsers auto-append default ports
- How DNS works at a basic level (domain names resolve to IP addresses so browsers know where to connect). Nameservers, A records, and the details of DNS configuration are NOT yet solidified — explain these thoroughly when reaching Phase 1/Section 7.
- What a reverse proxy does (owns ports 80/443 externally, routes to internal services by hostname)
- How SSL/TLS termination works (NPM decrypts, proxies internally unencrypted, re-encrypts response)
- What port forwarding is (mapping external router port → internal device IP:port)
- The difference between CGNAT and a direct public IP, and why it matters
- What Docker containers are conceptually and why they're useful for isolating services
- What a NAS is and how it fits into a homelab
- The difference between Cloudflare Tunnel (zero-trust, abstracts networking) vs traditional port forwarding (manual, educational)
- How `nmcli` works for managing network connections — listing connections (`con show`), modifying settings (`con mod`), activating/deactivating (`con up`/`con down`), and the difference between `ipv4.method auto` (DHCP) and `manual` (static)
- What a subnet mask is (`/24` means first three octets define the network, last octet identifies the device, giving 254 usable addresses)
- What a gateway is (the router's local IP — the exit door from LAN to internet) and why it's required for internet access
- How Linux routing tables work (`ip route`), what metrics mean (lower = higher priority), and how a dead interface with a lower metric can hijack traffic from a working interface
- What ARP does (translates IP addresses to physical MAC addresses for local network communication)
- What loopback is (`lo` / `127.0.0.1` / `localhost` — the machine talking to itself)
- The difference between `eth0` (wired ethernet) and `wlan0` (WiFi), and that each interface has its own routes and IP config
- How to read and interpret `hostname -I`, `ping`, `ip route`, `ip addr show`, `iwconfig`, `arp -a`, and `curl` for network diagnostics
- How SSH works from Windows Command Prompt (`ssh user@ip` for terminal access, `scp` for file transfers)
- How SSH key authentication works — ed25519 key pairs, public key goes on the server (`authorized_keys`), private key stays on the client, passphrase protects the private key locally. Understands `chmod 700`/`600` permission requirements and how to disable password auth in `sshd_config`

### Haven Control Room

Haven Control Room is a No Man's Sky community web application. It is the **first and primary service** in Parker's homelab — everything else exists to support it.

**What It Does:**
The project extracts planet and system data from NMS via a Python mod (pyMHF/NMS.py), writes JSON files, and serves an interactive web UI that the NMS community can browse. Think of it as a living encyclopedia of discovered planets and systems, auto-populated from actual gameplay.

**Technical Stack:**
- **Language:** Python with HTML templates (~85% of codebase)
- **Web server:** Local Python web server running on port 8005
- **Data storage:** JSON files + database (SQLite or similar, stored locally on disk)
- **Game integration:** pyMHF/NMS.py mod extracts game data → writes JSON → web server reads and displays
- **Current hosting:** ngrok tunnel ($20/month paid tier, being migrated away)
- **GitHub:** Parker1920/Master-Haven (public repository)
- **Domain:** havenmap.online (purchased from Namecheap, 2-year registration)

**Why It's Being Migrated:**
Parker is currently on ngrok's $20/month paid tier. Haven doesn't generate revenue, so a recurring subscription for hosting a community project doesn't make financial sense long-term — especially since costs would only increase if the project gains traction and needs higher ngrok tiers. Self-hosting on hardware Parker already owns eliminates that ongoing cost entirely. As a bonus, Parker gets a permanent custom domain URL instead of ngrok's generated subdomains, and full control over the infrastructure.

**Migration Path: ngrok → Self-Hosted:**
1. Haven currently runs as a bare Python process on port 8005
2. Phase 1: Put it behind NPM on the 8GB Pi with the custom domain (still bare process)
3. Phase 2: Containerize Haven in Docker (Dockerfile wrapping the Python app)
4. Long-term: Haven runs as a Docker container, managed by Portainer, monitored by Uptime Kuma, accessible at `https://havenmap.online`

---

## 2. Hardware

### Currently Owned
| Item | Specs | Role | Notes |
|------|-------|------|-------|
| Raspberry Pi 5 | 2GB RAM | Network infrastructure | Running at static IP 10.0.0.33 over WiFi. Will host Pi-hole, DDNS updater, and VPN. Ethernet recommended for production — plan to switch to wired when possible. |
| Xfinity Router/Gateway | Residential gateway, LAN subnet 10.0.0.0/24, gateway IP 10.0.0.1 | Internet + port forwarding | Port forwarding via xFi app only (not web interface). Supports TCP and UDP forwarding |
| Domain | havenmap.online, purchased from Namecheap, 2-year registration | Public URL for Haven | Needs nameservers pointed to Cloudflare |

### Planned Purchases
| Item | Specs | Role | Notes |
|------|-------|------|-------|
| Raspberry Pi 5 | 8GB RAM | Application server | Haven, NPM, monitoring stack. Not yet purchased — this is the next hardware buy |
| USB SSD | Any reliable brand, 256GB+ | NAS starter | Plugs into Pi for Samba file sharing and backups |
| Network Switch (future) | 8-port unmanaged gigabit (TP-Link TL-SG108 or Netgear GS308) | Expand wired connections | Not urgent — only needed when devices exceed router ports |
| NAS (future) | Synology DS223 (~$250 diskless) + 2x 4TB IronWolf (~$200) | Dedicated storage | Upgrade from USB SSD when that feels limiting. Runs Docker, 17W power draw |

### 2GB Pi Hardware Notes
Docker runs fine on 2GB with lightweight containers. Key optimizations:
- Set `gpu_mem=16` in `/boot/config.txt` (frees ~100MB by minimizing GPU allocation since this is headless)
- Enable cgroup memory accounting for Docker memory limits
- Use a USB SSD for Docker storage instead of the SD card (SD cards wear out from frequent writes)
- The planned services (Pi-hole ~150MB + WireGuard ~50MB + DDNS ~25MB) total ~225MB, leaving ~1.4GB headroom

### 2.5 Network Configuration (Confirmed)

#### Local Network Details
| Item | Value |
|------|-------|
| Subnet | 10.0.0.0/24 |
| Router/Gateway IP | 10.0.0.1 |
| 2GB Pi IP | 10.0.0.33 (static, WiFi) |
| 8GB Pi IP | TBD (assign static when purchased, e.g., 10.0.0.34) |
| Public IP | 174.59.238.206 (dynamic, DDNS handles updates) |
| CGNAT | Confirmed absent ✅ |

#### 2GB Pi Static IP — Already Configured
The 2GB Pi has a static IP set via NetworkManager on the WiFi interface (`Superweeniehutjrs`). Configuration was applied with:
```bash
sudo nmcli con mod "Superweeniehutjrs" ipv4.addresses 10.0.0.33/24
sudo nmcli con mod "Superweeniehutjrs" ipv4.gateway 10.0.0.1
sudo nmcli con mod "Superweeniehutjrs" ipv4.dns "10.0.0.1"
sudo nmcli con mod "Superweeniehutjrs" ipv4.method manual
sudo nmcli con up "Superweeniehutjrs"
```

**WiFi vs Ethernet:** The 2GB Pi currently connects via WiFi, not ethernet. This works for development and setup, but wired ethernet is recommended for production — it's faster, more reliable, and lower latency. Plan to switch to wired when practical. When switching, the static IP commands would need to be applied to the wired connection instead, and the WiFi config can be reverted to auto or left as a fallback.

**Lesson learned during setup:** A static IP was initially applied to the wired interface (`Wired connection 1`) by mistake. Because the wired interface had a lower routing metric (100) than WiFi (600), the Pi tried to route all traffic through the dead ethernet port, killing network connectivity. Fix was to clear the wired config and bring the WiFi connection back up. If the 8GB Pi setup is done over WiFi, verify which interface is active with `nmcli con show --active` before applying static IP config.

### Architecture Decisions (Finalized)

These were discussed, debated, and decided by Parker. **Do not revisit unless Parker explicitly asks.**

#### Traditional Port Forwarding (NOT Cloudflare Tunnel)

**What was decided:** Use Cloudflare as the DNS provider (free tier) with a DDNS updater container + traditional port forwarding on the Xfinity router + Nginx Proxy Manager as the reverse proxy with Let's Encrypt SSL certificates.

**What was rejected:** Cloudflare Tunnel (also called cloudflared or Argo Tunnel). This was fully evaluated and understood. It's objectively easier to set up and more secure out of the box — but it abstracts away all the networking concepts Parker wants to learn.

**Why traditional was chosen:** Parker's goal isn't just "get Haven online" — it's to learn networking fundamentals that transfer to real DevOps work. Traditional port forwarding teaches DNS resolution, NAT traversal, reverse proxy configuration, SSL certificate management, and firewall rules. These are skills that apply everywhere, not just to Cloudflare's ecosystem.

**When to revisit:** If Parker ever hits a wall where Xfinity blocks critical ports and DNS-01 workarounds aren't sufficient, Cloudflare Tunnel is the fallback. But this should be Parker's call, not the agent's.

#### CGNAT Status: ✅ CONFIRMED CLEAR

**Tested:** February 1, 2026
**Result:** No CGNAT. Public IP (174.59.238.206) matches Xfinity WAN IPv4 exactly.
**What this means:** Parker has a direct public IP from Xfinity, so port forwarding will work as expected. Incoming connections to 174.59.238.206:443 will reach his router, and port forward rules will send them to the correct Pi.
**Important note:** This is a dynamic IP (Xfinity residential doesn't guarantee a static IP). It may change after router reboots or extended outages. The Cloudflare DDNS container automatically detects changes and updates the DNS A record, so this is handled. If port forwarding ever stops working unexpectedly, re-check the IP match first.

**How it was verified:**
```bash
# Public IP check (via VS Code Claude agent): 174.59.238.206
# Xfinity gateway WAN IPv4 (logged into Xfinity profile): 174.59.238.206
# IPs match = direct public IP, no CGNAT. Phase 1 is unblocked.
```

#### Two-Pi Architecture

**Why two Pis instead of one?** Separation of concerns and fault isolation. If the application Pi crashes or needs a restart during a Haven update, the entire home network's DNS (Pi-hole) and VPN access don't go down with it. It's the same reason you don't run your router and your web server on the same machine in production.

**2GB Pi — Network Infrastructure (always-on, lightweight):**
| Service | RAM Usage | Purpose |
|---------|-----------|---------|
| Pi-hole | 80-150 MB | DNS server + ad blocking for all home devices |
| Cloudflare DDNS | 15-25 MB | Auto-updates DNS A record when public IP changes |
| WireGuard (if chosen) | 30-50 MB | VPN server for remote admin access |
| **Total** | **~200-300 MB** | **Leaves ~1.4GB headroom on 2GB Pi** |

**8GB Pi — Applications (higher resource, restart-tolerant):**
| Service | RAM Usage | Purpose |
|---------|-----------|---------|
| Nginx Proxy Manager | 150-250 MB | Reverse proxy + SSL termination |
| Haven Control Room | 100-300 MB | The main application |
| Uptime Kuma | 100-200 MB | Service monitoring + alerts |
| Portainer | 150-250 MB | Docker management GUI |
| Homepage | 30-80 MB | Dashboard showing all services |
| **Total** | **~600-1100 MB** | **Leaves 6+ GB free on 8GB Pi** |

#### Docker for Everything

Every service runs in a Docker container managed by Docker Compose. One `docker-compose.yml` per Pi. This gives:
- **Isolation:** Services can't interfere with each other or the host OS
- **Reproducibility:** The compose file IS the documentation. Rebuild from scratch in minutes.
- **Easy updates:** `docker compose pull && docker compose up -d` updates everything
- **Resource limits:** Memory caps per container prevent runaway services

Portainer on the 8GB Pi provides a web GUI for managing containers on both Pis (via Portainer Agent on the 2GB Pi).

#### Monitoring: Existing Tools First, Custom Later

**Decision:** Deploy Uptime Kuma + Portainer + Homepage as the monitoring/management stack. Total footprint under 400MB.

**Why not build custom from scratch?** A custom monitoring dashboard was estimated at 130-240 hours of development and would replicate what Uptime Kuma does out of the box. The smarter path: run existing tools for a few weeks, identify what's missing, then build targeted customizations for the gaps.

**Notification chain:**
1. Uptime Kuma detects a service is down
2. Sends alert to Discord webhook (instant in Discord server/DMs)
3. Optionally also sends phone push notification via ntfy.sh (free, self-hostable) or Pushover ($5 one-time)

#### VPN for Remote Admin — PENDING PARKER'S DECISION

This is for accessing admin interfaces (Portainer, Pi-hole, Uptime Kuma, NPM admin panel) when away from home. This is separate from Haven's public access.

**Option A — Tailscale (recommended for starting out):**
- Free tier: 100 devices, 3 users
- Setup: `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up` on each device
- No port forwarding needed, works even with CGNAT
- Zero configuration networking — devices find each other automatically
- 15 minutes to full deployment
- Trade-off: It's a managed service (Tailscale Inc controls the coordination server)

**Option B — Self-hosted WireGuard (more learning value):**
- wg-easy Docker container provides a web UI for managing VPN clients
- Requires UDP port 51820 forwarded on Xfinity router
- 2-4 hours to set up properly
- Full control, no external dependency
- Trade-off: More maintenance, need to handle key distribution manually

**Key insight Parker understands:** Using Tailscale for admin VPN does NOT contradict using traditional port forwarding for Haven. These solve different problems. Haven needs to be publicly accessible (port forwarding). Admin tools need to be privately accessible (VPN). They coexist.

#### Reverse Proxy: Nginx Proxy Manager

**What a reverse proxy does:** It sits in front of all your services, owns ports 80 and 443 (the only ports exposed to the internet), and routes incoming requests to the right internal service based on the domain name in the request. This means `havenmap.online` and `dashboard.havenmap.online` can both use port 443 externally but go to completely different services internally.

**Why NPM over Caddy or Traefik:** All three are excellent. NPM was chosen because it has a graphical web interface — you click buttons to add a new domain, select your SSL options, and point to an internal service. Caddy and Traefik use config files, which are powerful but introduce syntax errors that are harder to debug as a beginner. NPM also handles Let's Encrypt certificate requests and renewals with a few clicks.

**If Xfinity blocks ports 80/443:** Let's Encrypt normally validates domain ownership by connecting to your server on port 80 (HTTP-01 challenge). If those ports are blocked, NPM can use DNS-01 challenge instead — it proves ownership by creating a temporary DNS TXT record via the Cloudflare API. No inbound ports needed for validation. Cloudflare also natively supports HTTPS on alternative ports: 8443, 2053, 2083, 2087, 2096.

---

## 3. Development Workflow

### How Code Gets From Windows PC to Pi

**Current method (pre-Phase 2):** Edit files on Windows → transfer via `scp` to Pi → SSH in and restart Haven process.

**Target method (post-Phase 2, Haven containerized):**
1. Edit code on Windows PC
2. Test locally (run Haven on PC to verify changes)
3. `git push` to GitHub
4. SSH into Pi: `ssh parker@10.0.0.33`
5. On the Pi: `cd ~/docker/haven && git pull`
6. Rebuild container: `docker compose up -d --build`
7. Haven restarts with changes (~30 seconds on Pi 5)

GitHub becomes the transport mechanism instead of manual file transfers. Builds are reproducible — anyone can clone and deploy.

### SSH Access — Key Authentication Configured ✅
- **SSH:** `ssh parker@10.0.0.33` from Windows Command Prompt (ed25519 key pair, passphrase protected)
- **File transfer:** `scp C:\path\to\file parker@10.0.0.33:~/destination/` (use `-r` flag for folders)
- **Password login is disabled.** `PasswordAuthentication no` and `KbdInteractiveAuthentication no` are set in `/etc/ssh/sshd_config`
- **Public key:** `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGpZxpe5x1TJPI01vJuoACyltfyxWBCqjzLFR6QUEOgj parker-desktop` is in `~/.ssh/authorized_keys` on the Pi
- **WinSCP is no longer used.** SSH + scp from Command Prompt handles everything.

---

## 4. Network Topology

### Complete Traffic Flow — What Happens When Someone Visits Haven

Here's every step, in order, when someone types `https://havenmap.online` in their browser:

**Step 1 — DNS Resolution:**
The browser asks "what IP address is havenmap.online?" This query goes to Cloudflare's DNS servers (because the Namecheap nameservers were pointed to Cloudflare). Cloudflare looks up the A record and returns Parker's public IP (e.g., 174.59.238.206). The DDNS container running on the 2GB Pi keeps this A record updated automatically whenever the IP changes.

**Step 2 — Connection to Router:**
The browser connects to 174.59.238.206 on port 443 (HTTPS default). This packet arrives at the Xfinity router's public interface. The router checks its port forwarding rules and sees: "port 443 → forward to 8GB Pi's local IP on port 443." Without this rule, the packet would be silently dropped.

**Step 3 — SSL/TLS Termination at NPM:**
The packet reaches Nginx Proxy Manager running on the 8GB Pi. NPM performs the TLS handshake: it presents the Let's Encrypt certificate for `havenmap.online`, the browser verifies it's legit, and they negotiate an encryption key. NPM then decrypts the request and reads the hostname header to know which service should handle it.

**Step 4 — Internal Proxy to Haven:**
NPM sees the hostname is `havenmap.online` and has a rule: forward to `localhost:8005`. It creates a new HTTP request (unencrypted, but this is fine — it never leaves the Pi) and sends it to Haven's Python web server on port 8005. Haven processes the request, generates the HTML response, and sends it back to NPM.

**Step 5 — Response Returns:**
NPM re-encrypts the response using the TLS session, sends it back through the router (which handles the NAT translation), and the browser receives the encrypted response. The user sees the Haven Control Room page with the green lock icon.

### Port Assignments — Complete Reference
| Service | Pi | Internal Port | External Access | Protocol | Notes |
|---------|-----|---------------|-----------------|----------|-------|
| Pi-hole DNS | 2GB | 53 | LAN only | TCP/UDP | All home devices use this for DNS |
| Pi-hole Admin | 2GB | 80 | VPN only | TCP | Web UI for managing blocklists |
| WireGuard VPN | 2GB | 51820 | Port forwarded | UDP | Only if self-hosting VPN (not Tailscale) |
| DDNS Updater | 2GB | N/A | Outbound only | HTTPS | Talks to Cloudflare API, no inbound port needed |
| NPM HTTP | 8GB | 80 | Port forwarded | TCP | Redirects to 443, also used for Let's Encrypt HTTP-01 |
| NPM HTTPS | 8GB | 443 | Port forwarded | TCP | All public HTTPS traffic enters here |
| NPM Admin | 8GB | 81 | VPN only | TCP | NPM's own management interface |
| Haven | 8GB | 8005 | Via NPM only | TCP | Never directly exposed to internet |
| Uptime Kuma | 8GB | 3001 | VPN only | TCP | Monitoring dashboard |
| Portainer | 8GB | 9443 | VPN only | TCP | Docker management GUI |
| Homepage | 8GB | 3000 | VPN only | TCP | Personal dashboard |

### Xfinity Router Port Forwarding Rules
These are configured via the **xFi app** (not the web interface — Xfinity's web interface doesn't support port forwarding for newer gateways).

| External Port | Destination IP | Destination Port | Protocol | Purpose |
|---------------|---------------|------------------|----------|---------|
| 80 | 8GB Pi static IP (TBD) | 80 | TCP | HTTP → NPM (redirects to HTTPS + Let's Encrypt validation) |
| 443 | 8GB Pi static IP (TBD) | 443 | TCP | HTTPS → NPM (all public web traffic) |
| 51820 | 10.0.0.33 (2GB Pi) | 51820 | UDP | WireGuard VPN (only if self-hosting, not needed for Tailscale) |

**Important:** The 2GB Pi already has a static IP (10.0.0.33) configured via NetworkManager on WiFi. The 8GB Pi will need its own static IP assigned when purchased (e.g., 10.0.0.34 or 10.0.0.50 — Parker's choice). Both Pis must have static IPs or port forwarding breaks when DHCP reassigns addresses.

---

## 5. Phased Deployment Roadmap

Each phase builds on the previous. **Do not skip phases.** Validate each phase works before advancing. Parker should be able to test and confirm success at each checkpoint.

### Phase 1: Get Haven Live on Domain
**Goal:** Replace ngrok with self-hosted domain access. This is the most critical phase — nothing else matters until Haven is accessible at `https://havenmap.online`.

**Prerequisites:** CGNAT confirmed absent ✅ (Feb 1, 2026). Domain purchased ✅. SSH key auth configured ✅.

**Steps:**
1. Create Cloudflare account, add domain, note assigned nameservers
2. Update Namecheap nameservers to Cloudflare's (see Section 7)
3. Wait for DNS propagation (check status in Cloudflare dashboard)
4. Create A record in Cloudflare pointing to home IP (174.59.238.206)
5. Install Docker on 8GB Pi (or 2GB Pi temporarily if 8GB not purchased yet)
6. Deploy NPM container from the compose file
7. Configure Xfinity port forwarding via xFi app: 80→Pi:80, 443→Pi:443
8. Access NPM admin at `http://pi-local-ip:81`, change default credentials
9. Add proxy host: domain → forward to `http://localhost:8005` → request SSL → force HTTPS
10. Start Haven on port 8005 on the same Pi
11. Test from phone (not on home WiFi) or ask someone external to test
12. If working: shut down ngrok permanently

**Success checkpoint:** Visiting `https://havenmap.online` from outside the home network shows Haven with a green padlock.

**Blocks everything else.** Do not proceed to Phase 2 until this works.

### Phase 2: Containerize Haven
**Goal:** Move Haven from a bare Python process to a Docker container for easier management and portability.

**Steps:**
1. Clone Master-Haven repo into the compose project directory
2. Create Dockerfile based on Haven's dependencies
3. Add haven-control-room service to docker-compose.yml
4. Run `docker compose up -d --build`
5. Update NPM proxy host to point to the container (may need Docker network adjustment)
6. Verify external access still works

**Success checkpoint:** Haven runs inside Docker, managed by `docker compose`, and is still accessible externally.

### Phase 3: Network Infrastructure on 2GB Pi
**Goal:** Pi-hole for network-wide ad blocking, DDNS for automatic IP updates.

**Steps:**
1. Flash Raspberry Pi OS Lite (no desktop) onto 2GB Pi's SD card
2. Configure static IP for the 2GB Pi
3. Install Docker and Docker Compose
4. Deploy the 2GB Pi compose stack (Pi-hole + DDNS, skip WireGuard for now)
5. In Xfinity router: set primary DNS to 2GB Pi's local IP
6. Test ad blocking: visit an ad-heavy site, verify ads are blocked
7. Verify DDNS: check Cloudflare dashboard shows correct IP, change should auto-update

**Success checkpoint:** All home devices have ad blocking. Cloudflare DNS record auto-updates.

### Phase 4: Monitoring and Notifications
**Goal:** Know when things break before users report it.

**Steps:**
1. Deploy Uptime Kuma on 8GB Pi (already in compose file)
2. Create monitors:
   - Haven: HTTPS check on `https://havenmap.online` (every 60 seconds)
   - Pi-hole: HTTP check on `http://10.0.0.33/admin` (every 60 seconds)
   - Both Pis: Ping monitor (every 60 seconds)
   - SSL certificate: Expiry check (alerts when < 14 days remaining)
3. Set up Discord webhook: Server Settings → Integrations → Webhooks → copy URL → paste in Uptime Kuma notification settings
4. Optional: Add ntfy.sh or Pushover for phone push notifications
5. Deploy Homepage dashboard, configure widgets to show service status

**Success checkpoint:** When you manually stop Haven, you get a Discord alert within 2 minutes. Homepage shows all services green.

### Phase 5: VPN for Remote Admin
**Goal:** Securely access Portainer, Pi-hole admin, Uptime Kuma, and NPM admin from anywhere.

**If Tailscale:** Install on both Pis (`curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`), install on phone/laptop, done. Access services via Tailscale IP addresses.

**If WireGuard:** Deploy wg-easy on 2GB Pi (already in compose file), forward UDP 51820 on Xfinity router, access wg-easy web UI at `http://10.0.0.33:51821`, generate client configs, install WireGuard app on phone/laptop, import config.

**Parker has not decided yet.** Present both options when reaching this phase.

**Success checkpoint:** From a coffee shop or phone on cellular, you can access Portainer at the Pi's VPN IP.

### Phase 6: Custom Admin UI (Ongoing, Low Priority)
**Goal:** Build targeted customizations after learning what's missing from existing tools.

**Approach:** Run Phase 4 stack for several weeks. Take notes on what's annoying, missing, or could be better. Then build a Python-based dashboard (Flask or FastAPI) that addresses those specific gaps — NOT a from-scratch replacement.

**Success checkpoint:** Defined by whatever gaps Parker identifies.

### Phase 7: NAS Integration
**Goal:** Automated backups for Haven data and Docker volumes.

**Steps:**
1. Connect USB SSD to a Pi, format as ext4
2. Install and configure Samba for network file sharing
3. Create backup scripts using rsync:
   - Haven data directory → NAS
   - Docker volume directories → NAS
   - (Optional) Pi SD card image → NAS using `dd`
4. Add to cron for daily execution (e.g., 3 AM)
5. **Test restore** — a backup is worthless if you can't restore from it

**Success checkpoint:** Haven data is automatically backed up daily. You can restore from backup to a fresh Pi.

### Phase 8: Finalize Two-Pi Architecture
**Goal:** Everything unified and documented.

**Steps:**
1. Deploy Portainer Agent on 2GB Pi
2. In main Portainer (8GB Pi): add 2GB Pi as a remote endpoint
3. Verify you can manage both Pis' containers from one Portainer instance
4. Verify Uptime Kuma monitors cover all services on both Pis
5. Document everything: IP addresses, ports, passwords (in a password manager)
6. Create SD card backup images for both Pis using `dd` or Raspberry Pi Imager
7. Store backups on the NAS

**Success checkpoint:** One Portainer dashboard manages everything. Full documentation exists. SD card backups are stored safely.

---

## 6. Open Decisions

These items were discussed but **not finalized**. When continuing this project, present as options and let Parker decide.

### 6.1 VPN Method — NOT DECIDED
Tailscale (simple, recommended) vs self-hosted WireGuard (more learning). Parker understands both approaches and their tradeoffs. Full comparison is in Section 2, Architecture Decisions.

### 6.2 Custom Admin UI Scope — UNDEFINED
Run existing monitoring stack first, identify gaps, then define scope. Python stack preferred (Flask/FastAPI) but flexible. No features or design decided yet — this depends entirely on what Parker discovers after running Phase 4 tools for a few weeks.

### 6.3 CGNAT Status — ✅ RESOLVED
No CGNAT. Confirmed Feb 1, 2026. Public IP 174.59.238.206 matches Xfinity WAN IPv4. Phase 1 is fully unblocked. Dynamic IP handled by DDNS container.

### 6.4 8GB Pi Purchase Timeline — NOT YET PURCHASED
Parker plans to buy it but hasn't yet. The 2GB Pi can run a minimal stack temporarily (Haven + NPM + DDNS fits comfortably), but the two-Pi architecture described here is the target state. Don't build the full monitoring stack on the 2GB Pi — it will be reorganized when the 8GB arrives.

---

## 7. Configurations

### DNS & Domain Configuration

#### Step-by-Step: Namecheap → Cloudflare Migration

**Why Cloudflare for DNS?** It's free, fast (one of the largest DNS networks globally), provides DDoS protection, and has an API that the DDNS container uses to auto-update records. The domain stays registered at Namecheap — we're only moving DNS resolution to Cloudflare.

1. **Create Cloudflare account** at dash.cloudflare.com (free)
2. **Add your domain** — click "Add a Site," type your domain, select the Free plan
3. **Note the assigned nameservers** — Cloudflare gives you two (e.g., `aria.ns.cloudflare.com` and `bob.ns.cloudflare.com`). These are unique to your account.
4. **Update Namecheap nameservers:**
   - Log into Namecheap → Domain List → click "Manage" next to your domain
   - Find "Nameservers" section → change from "Namecheap BasicDNS" to "Custom DNS"
   - Enter both Cloudflare nameservers → Save
5. **Wait for propagation** — can take 24-48 hours, but often completes in 1-4 hours. Cloudflare shows a "pending" status until it detects the change.

#### Cloudflare DNS Records

Once Cloudflare is active, create these records:

**A Record (required):**
- Name: `@` (root domain) or a subdomain like `haven`
- Content: Your public IP (174.59.238.206 as of Feb 1, 2026)
- Proxy: OFF (gray cloud) initially — this makes debugging easier. Can enable later for DDoS protection.
- TTL: Auto

**CNAME Record (optional, for www):**
- Name: `www`
- Content: `havenmap.online`
- This makes `www.havenmap.online` work in addition to `havenmap.online`

The DDNS container automatically updates the A record's IP whenever it changes, so after initial setup this is hands-off.

#### Cloudflare API Token (for DDNS Container)

The DDNS container needs permission to update your DNS records. Create a scoped API token:

1. Cloudflare dashboard → Profile icon (top right) → API Tokens
2. Click "Create Token"
3. Use the "Edit zone DNS" template
4. Under "Zone Resources," select "Include → Specific zone → havenmap.online"
5. Click "Continue to summary" → "Create Token"
6. **Copy the token immediately** — it's shown only once. This goes into the DDNS container's `CF_API_TOKEN` environment variable.

#### SSL Certificate Strategy

**Primary method — HTTP-01 (automatic):**
NPM requests a Let's Encrypt certificate by proving it controls the domain. Let's Encrypt connects to your server on port 80, NPM responds with a verification token, certificate is issued. Renewal happens automatically every 60-90 days.

**Fallback — DNS-01 (if ports 80/443 are blocked):**
Instead of connecting to your server, Let's Encrypt asks you to create a DNS TXT record. NPM does this automatically via the Cloudflare API token. No inbound ports needed for validation. Slightly more complex setup in NPM but works around ISP port blocks.

**Cloudflare alternative HTTPS ports:** If Xfinity blocks 443 specifically, Cloudflare natively proxies HTTPS on these alternative ports: 8443, 2053, 2083, 2087, 2096. Users would need to include the port in the URL (e.g., `https://havenmap.online:8443`), which is less clean but functional.

### Docker Compose Configurations

#### Understanding Docker Compose
A `docker-compose.yml` file defines all your containers, their settings, and how they connect. Running `docker compose up -d` starts everything defined in the file. Running `docker compose down` stops everything. The file IS your infrastructure documentation — anyone can read it and know exactly what's running.

#### 2GB Pi: Network Infrastructure Stack

Save as `~/docker/docker-compose.yml` on the 2GB Pi:

```yaml
version: '3.8'
services:
  pihole:
    image: pihole/pihole:latest
    container_name: pihole
    network_mode: host          # Uses Pi's network directly (required for DNS)
    environment:
      - TZ=America/New_York     # Eastern time for correct log timestamps
      - WEBPASSWORD=your_secure_password  # Pi-hole admin UI password
    volumes:
      - ./pihole/etc:/etc/pihole          # Pi-hole config persists across restarts
      - ./pihole/dnsmasq:/etc/dnsmasq.d   # Custom DNS config
    deploy:
      resources:
        limits:
          memory: 256M          # Hard cap prevents runaway memory usage
    restart: unless-stopped     # Auto-restart on crash, but not if manually stopped

  wireguard:
    # ONLY include this if Parker chooses self-hosted WireGuard (not Tailscale)
    image: ghcr.io/wg-easy/wg-easy:latest
    container_name: wireguard
    environment:
      - WG_HOST=havenmap.online            # Public domain for client configs
      - PASSWORD_HASH=$2b$12$your_bcrypt_hash  # Admin UI password (bcrypt hash)
      - WG_PORT=51820                     # Must match router port forward
    volumes:
      - ./wireguard:/etc/wireguard        # Client configs and keys persist
    ports:
      - '51820:51820/udp'    # VPN tunnel traffic
      - '51821:51821/tcp'    # Web admin UI (access via VPN only)
    cap_add:
      - NET_ADMIN             # Required for creating VPN network interfaces
      - SYS_MODULE            # Required for loading WireGuard kernel module
    sysctls:
      - net.ipv4.ip_forward=1  # Allows routing traffic through the VPN
    deploy:
      resources:
        limits:
          memory: 128M
    restart: unless-stopped

  cloudflare-ddns:
    image: favonia/cloudflare-ddns:latest
    container_name: ddns
    network_mode: host          # Needs direct network access to detect public IP
    environment:
      - CF_API_TOKEN=your_cloudflare_token  # From Section 7 API token setup
      - DOMAINS=havenmap.online,www.havenmap.online  # Which DNS records to update
      - PROXIED=false           # Gray cloud (direct connection, not through Cloudflare proxy)
      - IP6_PROVIDER=none       # Skip IPv6 (Xfinity residential doesn't need it)
    restart: unless-stopped
```

#### 8GB Pi: Application Stack

Save as `~/docker/docker-compose.yml` on the 8GB Pi:

```yaml
version: '3.8'
services:
  nginx-proxy-manager:
    image: jc21/nginx-proxy-manager:latest
    container_name: npm
    ports:
      - '80:80'      # HTTP (redirects to HTTPS + Let's Encrypt validation)
      - '443:443'    # HTTPS (all public traffic)
      - '81:81'      # NPM admin UI (restrict to VPN/local access)
    volumes:
      - ./npm-data:/data                    # Proxy host configs, user accounts
      - ./letsencrypt:/etc/letsencrypt      # SSL certificates
    restart: unless-stopped
    # Default login: admin@example.com / changeme (change immediately on first login)

  haven-control-room:
    # Phase 2: This replaces the bare Python process with a Docker container
    build: ./haven              # Dockerfile in ./haven/ directory
    container_name: haven
    volumes:
      - ./haven-data:/app/data  # Persist game data, JSON files, database
    expose:
      - '8005'                  # Internal only — NPM proxies to this. NOT published to host.
    restart: unless-stopped

  uptime-kuma:
    image: louislam/uptime-kuma:1
    container_name: uptime-kuma
    volumes:
      - ./uptime-kuma:/app/data  # Monitor configs, alert history, status data
    ports:
      - '3001:3001'             # Web UI — access via VPN only
    restart: unless-stopped

  portainer:
    image: portainer/portainer-ce:latest
    container_name: portainer
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # Gives Portainer control over Docker
      - ./portainer:/data                          # Portainer settings, endpoint configs
    ports:
      - '9443:9443'             # Web UI (HTTPS) — access via VPN only
    restart: unless-stopped

  homepage:
    image: ghcr.io/gethomepage/homepage:latest
    container_name: homepage
    volumes:
      - ./homepage:/app/config  # Dashboard layout, service widgets, bookmarks
    ports:
      - '3000:3000'             # Web UI — access via VPN only
    restart: unless-stopped
```

#### Haven Dockerfile (Phase 2)
This will be created during Phase 2. General structure:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8005
CMD ["python", "your_main_script.py"]
```
The exact details depend on Haven's current structure — the agent working on Phase 2 should examine the Master-Haven repo to determine the correct entrypoint and dependencies.

#### UFW Firewall Configuration

UFW (Uncomplicated Firewall) is Linux's beginner-friendly firewall. It controls which incoming connections are allowed and blocks everything else by default — so if you forget to open a port, traffic is denied rather than allowed. This is the safe default.

**2GB Pi rules:**
```bash
sudo apt install ufw
sudo ufw default deny incoming       # Block everything by default
sudo ufw default allow outgoing      # Allow all outbound (updates, DDNS, etc.)
sudo ufw allow 22/tcp               # SSH (change port later for extra security)
sudo ufw allow 53                    # DNS (Pi-hole) — TCP and UDP
sudo ufw allow 51820/udp            # WireGuard (only if self-hosting VPN)
sudo ufw enable
```

**8GB Pi rules:**
```bash
sudo apt install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp                                # SSH
sudo ufw allow 80/tcp                                # HTTP (NPM)
sudo ufw allow 443/tcp                               # HTTPS (NPM)
sudo ufw allow from 10.0.0.0/24 to any port 81   # NPM admin — local network only
sudo ufw allow from 10.0.0.0/24 to any port 3001 # Uptime Kuma — local only
sudo ufw allow from 10.0.0.0/24 to any port 9443 # Portainer — local only
sudo ufw allow from 10.0.0.0/24 to any port 3000 # Homepage — local only
sudo ufw enable
```

The `from 10.0.0.0/24` rules mean "only allow connections from devices on the local network." This prevents random internet users from accessing your admin interfaces even if they somehow knew the port numbers.

---

## 8. SSH Hardening (Completed ✅)

### What Was Done
SSH key authentication is fully configured on the 2GB Pi. Password login is disabled.

**Key generation (on Windows PC):**
```
ssh-keygen -t ed25519 -C "parker-desktop"
```
This created a key pair:
- **Private key:** `C:\Users\<username>\.ssh\id_ed25519` — stays on the Windows PC, never shared. Passphrase-protected.
- **Public key:** `C:\Users\<username>\.ssh\id_ed25519.pub` — placed on the Pi.

**Key installation (on the Pi):**
```bash
mkdir -p ~/.ssh                  # Create .ssh directory if it doesn't exist
chmod 700 ~/.ssh                 # Only owner can read/write/enter
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGpZxpe5x1TJPI01vJuoACyltfyxWBCqjzLFR6QUEOgj parker-desktop" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys # Only owner can read/write
```

**Password login disabled (in `/etc/ssh/sshd_config` on the Pi):**
```
PasswordAuthentication no
KbdInteractiveAuthentication no
```
Applied with `sudo systemctl restart ssh`.

### Current State
- SSH login requires the ed25519 private key + passphrase. No password fallback.
- Connection: `ssh parker@10.0.0.33` from Windows Command Prompt
- File transfer: `scp C:\path\to\file parker@10.0.0.33:~/destination/`

### Remaining Task
- Change SSH port from 22 to a non-standard port (e.g., 2222) before enabling public port forwarding. This reduces automated scanning noise.

### Additional Security Measures (Not Yet Done)
- **fail2ban:** Install on both Pis. Monitors login attempts and automatically bans IPs that fail too many times. Protects SSH and nginx.
- **Cloudflare settings:** Enable "Always Use HTTPS" (redirects HTTP to HTTPS automatically), "Bot Fight Mode" (blocks known malicious bots), set Security Level to Medium.
- **Docker security:** Use specific image tags in production (e.g., `pihole/pihole:2024.07.0` instead of `:latest`). Only pull from official publishers on Docker Hub.
- **Secrets management:** Store passwords and API tokens in `.env` files that docker-compose reads. Add `.env` to `.gitignore` so secrets never end up in GitHub. Never hardcode secrets in compose files.
- **Regular updates:** Schedule `sudo apt update && sudo apt upgrade -y` periodically. Update Docker images with `docker compose pull && docker compose up -d`.

---

## 9. NAS (Network Attached Storage)

### What It Is
A NAS is a dedicated file server that all devices on your network can access. Think of it as your personal Google Drive that lives in your house — you own the hardware, you control the data, there are no monthly fees. You connect to it via your local network (or through VPN when you're away from home) and it appears as a regular folder/drive on your computer.

### Why Parker's Homelab Needs One
- **Haven database backups:** The JSON files and database are the heart of the project. If the SD card dies without backups, all that data is gone forever. Automated daily backups to the NAS prevent this catastrophe.
- **Docker volume snapshots:** Container data (Pi-hole config, Uptime Kuma history, NPM certificates) should be backed up. Without this, rebuilding after a failure means reconfiguring everything from scratch.
- **SD card images:** Full Pi disk images stored on the NAS mean you can restore a dead Pi in 20 minutes by flashing the image to a new SD card, instead of rebuilding from scratch over hours.
- **Remote file access:** VPN into the homelab from anywhere, access NAS files as if you were home. Great for when you're traveling and need to check on things.

### NAS Strategy (Phased)

**Phase 1 — Start simple ($0-80):**
Connect a USB SSD to a Pi. Install Samba (the Linux file sharing protocol). Share a folder. All devices on the network can now access it. Speed: 80-110 MB/s over gigabit ethernet. This handles Haven database backups, Docker volume snapshots, and Pi SD card images.

**Phase 2 — Dedicated NAS (when Phase 1 feels limiting):**
Synology DS223 (~$250 diskless) + two 4TB Seagate IronWolf drives (~$100 each). This gives you: hardware RAID for drive redundancy (one drive can die without data loss), a polished web UI for management, built-in Docker support, automatic cloud sync if desired, and only 17W power consumption. An old PC running TrueNAS is also viable if spare hardware is available.

### Growth Path
| Stage | Setup | Cost | Speed | When to Use |
|-------|-------|------|-------|-------------|
| 1 | USB SSD on Pi + Samba | $0-80 | 80-110 MB/s | Start here — learn the concepts |
| 2 | Synology DS223 + 2x 4TB IronWolf | ~$450 | 110+ MB/s | When USB feels limiting or you want RAID redundancy |
| 3 | DS224+ (Intel CPU) | ~$500 | 110+ MB/s | If you need media transcoding (Plex/Jellyfin) |

---

## 10. Instructions for Continuing Agents

If you are a Claude agent picking up this project, follow these rules:

1. **Parker is the manager.** Present options with pros/cons, let him decide. Never assume or decide on his behalf.
2. **Technical depth without filler.** Get to the point. Skip corporate pleasantries and fluff.
3. **All development happens on his home desktop (Windows).** Don't suggest mobile workflows.
4. **Python is his primary language.** Default to Python unless something else is clearly better for the task.
5. **He's a beginner to Linux/networking but learns fast.** Explain WHY things work, not just WHAT to type. But don't over-explain concepts listed in "What Parker Knows" (Section 1) — he already understands those.
6. **The architecture in this document is FINALIZED** unless Parker explicitly reopens a decision. Don't second-guess choices like traditional port forwarding vs Cloudflare Tunnel.
7. **Haven Control Room on port 8005 is the primary project.** Everything else exists to support it.
8. **Traditional port forwarding was deliberately chosen** over Cloudflare Tunnel for learning purposes. This was not an oversight or a mistake.
9. **Ask clarifying questions** rather than guessing when something is ambiguous.
10. **When presenting options,** include pros, cons, and your recommendation — but Parker makes the call.
11. **Check which phase Parker is currently on** before suggesting next steps. Don't jump ahead.
12. **Parker reviews everything.** He reads all output carefully and learns from it. Write as if your audience is both a future agent AND a person actively learning.