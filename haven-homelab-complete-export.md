# Haven Homelab — Complete Project Export

> **Exported:** February 4, 2026
> **Owner:** Parker (Parker1920 on GitHub)
> **Primary Project:** Haven Control Room at havenmap.online
> **Community:** Voyager's Haven (No Man's Sky)

---

# TABLE OF CONTENTS

1. [Project Overview & Instructions](#project-overview--instructions)
2. [Parker Profile — Skills, Tools, Knowledge](#parker-profile)
3. [Master Plan v3.3 — Phases, Hardware, Architecture](#master-plan)
4. [Hardware Rationale — Why Each Component](#hardware-rationale)
5. [Multi-Agent AI Architecture — Phases 4-5](#ai-planning)
6. [Kubernetes Cluster Design — Phase 6](#kubernetes-planning)
7. [Haven API Specification](#haven-api-spec)
8. [Runbook — Troubleshooting](#runbook)
9. [Cleanup Report — Repository Restructure](#cleanup-report)
10. [Claude's Memory Context](#claude-memory-context)

---
---

# 1. PROJECT OVERVIEW & INSTRUCTIONS

## Project Overview

This is Parker's personal homelab project building self-hosted infrastructure for the **Voyager's Haven** community. The primary project is **Haven Control Room** at havenmap.online, with the overall scope being a full dream homelab built in phases over months/years.

**This is a learning project.** Parker is self-teaching Linux, networking, Docker, and infrastructure through building. Every explanation should reinforce understanding, not just provide commands to copy.

## Where to Find What

| Question | Document |
|----------|----------|
| What phase are we in? What's the current state? | Master Plan v3.3 (Section 3) |
| What are Parker's skill levels? | Parker Profile (Section 2) |
| Why was this hardware chosen? | Hardware Rationale (Section 4) |
| What's the AI vision? | AI Planning (Section 5) |
| What's the K8s plan? | K8s Planning (Section 6) |
| What does the Haven API look like? | Haven API Spec (Section 7) |
| How do we fix known issues? | Runbook (Section 8) |

**The master plan is the single source of truth for current state.**

## Working Dynamic

**Parker = Project Manager.** Sets direction, makes decisions, asks questions.
**Claude = Engineering Team.** Research, explain options, provide implementations, execute on Parker's decisions.

### Core Rules

1. **Present options with pros/cons and a recommendation** — but Parker makes all final decisions
2. **Never assume or decide on Parker's behalf** — if unclear, ask
3. **Explain the WHY**, not just the WHAT — Parker is building long-term knowledge
4. **Repetition is good** — Parker has ADHD; restating concepts aids retention
5. **Connect new concepts to known ones** — "This is like X you already know, but..."
6. **Code needs comments** — Parker can edit code if he understands what each section does
7. **Check the current phase** before suggesting next steps — don't jump ahead
8. **Skip filler and fluff** — be direct, use tables for comparisons
9. **100% self-hosted** — no subscription services except Claude API
10. **Do NOT question locked decisions** — hardware choices, project scope, and what relates to Haven are Parker's calls to make

### Response Patterns

| Parker says... | Claude should... |
|----------------|------------------|
| "Explain that again" | Re-explain with different words, simpler analogy |
| "Give me options" | Table with pros/cons/recommendation |
| "What's next?" | Check current phase in master plan, present next logical step |
| "Just give me the command" | Command with brief explanation |
| "Add this to the runbook" | Document the issue/solution in runbook.md |

### Don't Do These Things

- Don't skip explanations — brief reminders are always okay
- Don't provide code without comments
- Don't make decisions for Parker
- Don't suggest subscription services
- Don't question locked decisions (hardware, scope, what relates to Haven)
- Don't jump phases
- Don't over-explain concepts Parker has already demonstrated

---
---

# 2. PARKER PROFILE

> **Last Updated:** February 4, 2026
> **Purpose:** Living document tracking Parker's skills, tools, knowledge, and learning progress.

## Who Is Parker

**Location:** Mechanicsburg, PA (Xfinity/Comcast service area)
**GitHub:** Parker1920 — repository: Master-Haven
**Primary Project:** Voyager's Haven — No Man's Sky community (Discord + Haven Control Room web app)
**Domain:** havenmap.online
**Claude Subscription:** Max ($100/month)

**Learning Context:** This is a personal project outside any academic environment. Parker is self-teaching through building. The goal is practical knowledge that sticks, not certificates or grades.

**Learning Style (IMPORTANT):**
- Has ADHD — repetition and explaining concepts out loud helps with retention
- Learns best by doing, not just reading
- Needs explicit connections between new concepts and things already understood
- Benefits from comments in code that explain what each section does
- Prefers to understand WHY something works, not just WHAT to type
- Will ask for clarification when needed — Claude should encourage this

## Working Style

Parker operates as the **project manager**. Claude operates as the **engineering team**.

### Communication Preferences
- Direct and concise, but not terse
- Tables and structured comparisons help with decision-making
- Step-by-step numbered lists for procedures
- Confirm understanding before moving to next major step

### Planning vs Execution — IMPORTANT

- **Planning happens on phone** — While at work, commuting, or away from the computer. Parker reads documents, thinks of changes, discusses architecture with Claude.
- **Execution happens at desktop** — When Parker is home at the computer, that's when implementation work gets done (SSH, Docker, file transfers, etc.).

**Do NOT interpret planning time as scope creep.** If Parker spends an hour discussing Phase 3 compute specs while Phase 1 Step 7 is incomplete, that doesn't mean execution has stalled — it means Parker is using phone time productively while unable to do hands-on work.

**Claude's job is to teach as we go.** If Parker's skill level is listed as 2/10 for Docker, that's the *starting point*, not a gap Parker has to solve alone.

**Future phases are documented vision, not competing priorities.** The AI infrastructure (Phase 4-5) and Kubernetes (Phase 6) documentation exists so the research is done when Parker is ready — potentially months or years from now.

**Spec changes usually come from real research.** When Parker revisits a hardware decision (like upgrading Phase 3 from 6c/32GB to 8c/64GB), it's often based on new information — in that case, surveying 40+ NMS communities about hosting needs.

## Skills Inventory

### Linux / Command Line — Level: 5/10

**What Parker Knows:**
- Basic navigation (cd, ls, pwd)
- File operations (cp, mv, rm, mkdir, cat, nano)
- SSH from Windows (`ssh user@ip`)
- SCP for file transfers
- Package management basics (`sudo apt update`, `sudo apt install`)
- Service management (`sudo systemctl start/stop/restart/status`)
- nmcli for network configuration
- Basic permissions concepts (chmod, file ownership)

**Commands Parker has used and understands:**
- `hostname -I`, `ping`, `ip route`, `ip addr show`, `curl`, `iwconfig`, `arp -a`, `nmcli con show`, `nmcli con mod`, `sudo ufw`

**Still Learning:**
- Shell scripting, advanced text processing (grep, awk, sed), process management, cron jobs, log analysis

### Python — Level: 3/10

**What Parker Can Do:**
- Read and understand Python code if it has comments
- Edit existing code to change behavior
- Basic syntax (variables, functions, loops, conditionals)
- Run Python scripts, use pip

**Still Learning:**
- Writing functions from scratch, pip/venv, FastAPI specifics, error handling, OOP

### Networking — Level: 6/10

**What Parker Knows Well:**
- Ports, DNS basics (A records), reverse proxy (NPM), SSL/TLS termination, port forwarding, CGNAT vs public IP, subnet masks (/24), gateway concept, static vs DHCP, basic routing, ARP, loopback, network interfaces
- Cloudflare DNS setup (account, nameservers, A records, API tokens)
- NPM reverse proxy configuration with SSL

**Still Learning:**
- VLANs, advanced firewall, VPN internals (WireGuard specifics)

### Docker — Level: 3/10

**What Parker Has Done:**
- Installed Docker on Raspberry Pi, added user to docker group, deployed NPM container via docker compose
- Has NOT written a Dockerfile or docker-compose.yml from scratch yet

### Git / GitHub — Level: 3/10
- Clone, commit, push, pull — basic operations only

### 3D Printing / CAD — Level: 2-3/10
- Bambu Lab A1 printer (256x256x256mm), Blender installed, basic familiarity

## Software Inventory

### Windows Desktop (Primary Development Machine)

| Category | Software |
|----------|----------|
| Code Editor | VS Code |
| Version Control | Git (command line) |
| SSH | Windows built-in SSH |
| File Transfer | WinSCP |
| 3D Modeling | Blender |
| 3D Slicer | Bambu Studio |
| GPU | NVIDIA RTX 4060 8GB |

## Accounts & Services

| Service | Status | Purpose |
|---------|--------|---------|
| GitHub | ✅ Active (Parker1920) | Code repository, Master-Haven |
| Cloudflare | ✅ Account exists | DNS management, DDNS |
| Namecheap | ✅ Active | Domain registrar (havenmap.online) |
| Claude | ✅ Max subscription | AI assistant |
| Discord | ✅ Active | Voyager's Haven community |
| ngrok | ✅ Active (to be cancelled) | Current Haven hosting ($20/month) |

## Hardware Inventory

| Item | Specs | Status |
|------|-------|--------|
| Raspberry Pi 5 2GB | BCM2712, WiFi, static IP 10.0.0.33 | Active, SSH hardened |
| Raspberry Pi 5 8GB | BCM2712, Ethernet, static IP 10.0.0.34 | Active, Docker installed, SSH hardened |
| Windows Desktop | RTX 4060 8GB, 32GB RAM | Primary dev machine |
| Bambu Lab A1 | 256x256x256mm FDM printer | Available |
| Xfinity Gateway | Router, 10.0.0.0/24 subnet | Active |
| TP-Link SG108PE | 8-port managed switch with PoE | Purchased, not yet deployed |
| Crucial X9 1TB | USB SSD for NAS/backups | Purchased, not yet deployed |

## Concept Checklist

### Networking Concepts
- [x] Ports (0-65535, well-known ports like 22, 53, 80, 443)
- [x] DNS basics (domain → IP, A records)
- [x] Reverse proxy (routes by hostname, owns 80/443)
- [x] SSL/TLS termination
- [x] Port forwarding
- [x] CGNAT vs public IP
- [x] Subnet masks (/24)
- [x] Gateway (router's LAN IP)
- [x] Static vs DHCP
- [x] Routing tables (basics)
- [x] ARP
- [x] Loopback
- [x] Network interfaces (eth0/wlan0)
- [ ] VLANs
- [x] Cloudflare DNS management
- [ ] DNS record types beyond A (CNAME, MX, TXT)
- [ ] VPN internals

### Linux Concepts
- [x] SSH key authentication (ed25519)
- [x] sshd_config hardening
- [x] File permissions (chmod basics)
- [x] Package management (apt)
- [x] Service management (systemctl)
- [x] nmcli for network config
- [ ] Cron jobs
- [ ] Shell scripting
- [ ] Log analysis

### Docker Concepts
- [x] What containers are (conceptual)
- [x] Images vs containers (conceptual)
- [x] Docker Compose purpose (conceptual)
- [x] Actually running containers (NPM deployed on 8GB Pi)
- [ ] Writing Dockerfiles
- [ ] Docker networking
- [ ] Docker volumes

### Homelab Concepts
- [x] What a NAS is
- [x] Why containerization helps
- [x] Two-Pi architecture reasoning
- [x] Traditional port forwarding vs Cloudflare Tunnel (chose traditional for learning)
- [x] Dual rack architecture (Haven Rack + Compute Rack)
- [ ] Kubernetes basics
- [ ] LLM inference concepts
- [ ] Voice assistant pipeline

## Learning Goals

1. Confidently manage Linux servers
2. Understand Docker well enough to containerize applications
3. Understand networking well enough to troubleshoot connectivity issues
4. Design and print functional mechanical parts
5. Run a self-hosted homelab
6. Understand enough Python to modify Haven
7. Learn Kubernetes basics
8. Deploy and interact with local LLMs

---
---

# 3. MASTER PLAN v3.3

> **Version:** 3.3
> **Last Updated:** February 4, 2026
> **Repository:** Parker1920/Master-Haven
> **Domain:** havenmap.online
> **Status:** Phase 1 In Progress — Haven Migration to 8GB Pi

## Vision & Current State

### The Vision

Build a fully self-hosted homelab inside custom 10-inch mini server racks — entirely owned, zero subscription costs for infrastructure. This homelab serves:

1. **Haven Control Room** — Primary project. NMS community web app at havenmap.online.
2. **Multi-Tenant Hosting Platform** — Game servers, Discord bots, and applications for multiple communities.
3. **Multi-Agent AI System** — Voice assistant and specialized AI agents (Phase 4+).
4. **AI Training Lab** — Fine-tune custom LLMs, reduce Claude costs (Phase 5+).

### What's Working Now

| Item | Status | Details |
|------|--------|---------|
| **Haven Control Room** | ✅ **LIVE** | Running on 2GB Pi behind NPM at havenmap.online |
| havenmap.online | ✅ Active | SSL working, Cloudflare DNS configured |
| ngrok | ✅ Cancelled | Running parallel until subscription expires |
| Voyager's Haven Discord | ✅ Active | Community hub |
| Raspberry Pi 5 2GB | ✅ Online | 10.0.0.33, running Haven + NPM, SSH hardened |
| Raspberry Pi 5 8GB | ✅ Configured | 10.0.0.34, Docker installed, NPM installed (not configured), SSH hardened |
| Cloudflare | ✅ Configured | DNS active, API token created, A record pointing to home IP |
| Port Forwarding | ✅ Active | 80/443 → 10.0.0.33 (2GB Pi) |
| GitHub Repository | ✅ Active | Parker1920/Master-Haven |
| Bambu Lab A1 | ✅ Owned | 256x256x256mm, ready for rack printing |
| Windows Desktop | ✅ Primary Dev | RTX 4060 8GB, 32GB RAM |

### Current Blocker

**Haven codebase restructure required.** The Haven-UI folder has imports reaching into the parent Master-Haven/src directory. Need to restructure so Haven-UI is self-contained before deploying to 8GB Pi.

### Haven Architecture Note

Haven Control Room is a "tri-synergy" system with three independent data input methods:

1. **Haven UI** — Web app with manual Create tab (stable, 4 months of work)
2. **Haven Extractor Mod** — Game mod that auto-populates data (almost complete)
3. **Haven Discord Bot** — Planned, for console players who can't use the mod

### Network Configuration

| Parameter | Value |
|-----------|-------|
| ISP | Xfinity/Comcast |
| Subnet | 10.0.0.0/24 |
| Router/Gateway | 10.0.0.1 |
| Public IP | Dynamic (DDNS will handle) |
| CGNAT | Confirmed absent ✅ |

### IP Address Assignments

| IP | Device | Role | Status |
|----|--------|------|--------|
| 10.0.0.1 | Xfinity Gateway | Router | Active |
| 10.0.0.33 | Pi 5 2GB | Currently: Haven + NPM. After Phase 1: Network infrastructure | ✅ Active |
| 10.0.0.34 | Pi 5 8GB | Application server (Haven destination) | ✅ Configured |
| 10.0.0.35 | Jetson Orin | AI inference | Phase 4 |
| 10.0.0.36 | x86 Compute Node | Multi-tenant hosting | Phase 3 |

## Hardware & Shopping Lists

**Total Budget: ~$3,140** (all phases)

### Phase 1-2: Foundation (~$461) — ✅ HARDWARE COMPLETE

#### Micro Center Parkville — ✅ PURCHASED Feb 3, 2026

| Item | Purchased | Price |
|------|-----------|-------|
| Raspberry Pi 5 8GB | ✅ | $95 |
| Official 27W USB-C PSU | ✅ | $12 |
| Official Pi 5 Active Cooler | ✅ | $10 |
| Samsung Pro 128GB A2 microSD | ✅ | $15 |
| SD Card Reader | ✅ | $8 |
| TP-Link SG108PE (8-port managed + PoE) | ✅ | $50 |
| Cat6 Patch Cables 1ft (x5) | ✅ | $10 |
| Crucial X9 1TB USB SSD | ✅ | $70 |
| Inland PLA+ 1kg | ✅ | $18 |
| Inland PETG 1kg | ✅ | $22 |
| **Subtotal** | | **~$310** |

#### Amazon — ⬜ NOT YET ORDERED

| Item | Notes | Price |
|------|-------|-------|
| GeeekPi 12-port 0.5U Patch Panel | | $15 |
| SunFounder USB Mini Microphone | Phase 4 but cheap to bundle | $12 |
| CanaKit USB Speaker | Phase 4 but cheap to bundle | $14 |
| M3/M4 Screw Assortment | 500+ pieces | $12 |
| M3 Brass Heat-Set Inserts | 50-100 pack | $8 |
| 1U Rack Mount PDU | 10-inch compatible | $30 |
| CyberPower EC450G UPS | 450VA / 260W | $60 |
| **Subtotal** | | **~$151** |

### Phase 3: Multi-Tenant Compute Platform (~$550)

| Item | Notes | Price |
|------|-------|-------|
| AMD Ryzen 7 5700X | 8c/16t, 65W TDP | $160 |
| B550M Micro-ATX Motherboard | 4 RAM slots, 128GB ceiling | $90 |
| 64GB DDR4 (2x32GB) | Expandable to 128GB later | $80 |
| 256GB NVMe SSD | OS + game servers | $25 |
| 450W SFX PSU | Comfortable headroom | $80 |
| Scythe Big Shuriken 3 | 69mm height, fits 4U | $45 |
| 2x 92mm Fans | Intake/exhaust | $15 |
| Cat6 Cable (1m) | Haven rack → Compute rack | $5 |
| Power Extension (3-6ft) | Haven PDU → Compute node | $10 |
| Filament for rack + sled | PETG | ~$40 |
| **Total** | | **~$550** |

### Phase 4: AI Infrastructure (~$2,129)

| Item | Source | Price |
|------|--------|-------|
| RTX 4090 24GB | Newegg/Best Buy | $1,600 |
| 64GB DDR4 Kit (2x32GB) | Amazon | $80 |
| Jetson Orin Nano Super Dev Kit | NVIDIA Store | $249 |
| Cloud Training Budget (Year 1) | Vast.ai, RunPod | $200 |
| **Total** | | **~$2,129** |

## Rack Architecture

### Dual Rack Layout

Two identical 10-inch 8U racks side by side, sharing one UPS and one PDU.

```
┌─────────────────────┐ ┌─────────────────────┐
│   HAVEN RACK        │ │   COMPUTE RACK      │
├─────────────────────┤ ├─────────────────────┤
│ 1U  Patch Panel     │ │ 1U  (reserved)      │
├─────────────────────┤ ├─────────────────────┤
│ 1U  Switch (SG108PE)│ │ 4U  mATX Compute    │
├─────────────────────┤ │     Node            │
│ 1U  Dual Pi Mount   │ │     (Ryzen 7,64GB)  │
│     (2GB + 8GB)     │ │                     │
├─────────────────────┤ │                     │
│ 1U  (reserved)      │ ├─────────────────────┤
├─────────────────────┤ │ 1U  (reserved)      │
│ 1U  (reserved)      │ ├─────────────────────┤
├─────────────────────┤ │ 1U  (reserved)      │
│ 1U  PDU ────────────┼─┼──→ power to compute │
├─────────────────────┤ ├─────────────────────┤
│ 1U  (reserved)      │ │ 1U  (reserved)      │
└─────────────────────┘ └─────────────────────┘
         8U                      8U
         
    ┌─────────┐
    │   UPS   │  (sits behind/between racks)
    └─────────┘
```

## Network Architecture

```
INTERNET
    │
    ▼
Cloudflare DNS (Free) — havenmap.online, A record → public IP
    │
    ▼
XFINITY GATEWAY (10.0.0.1)
  Port Forwards (CURRENT):
    80/tcp  → 10.0.0.33:80   (2GB Pi - NPM)
    443/tcp → 10.0.0.33:443  (2GB Pi - NPM)
  Port Forwards (AFTER PHASE 1):
    80/tcp  → 10.0.0.34:80   (8GB Pi - NPM)
    443/tcp → 10.0.0.34:443  (8GB Pi - NPM)
    51820/udp → 10.0.0.33:51820 (WireGuard on 2GB Pi)
    2456-2457/udp → 10.0.0.36  (Valheim) [Phase 3]
    │
    ▼
TP-LINK TL-SG108PE MANAGED SWITCH (Haven Rack)
  Port 1: Pi 5 2GB (10.0.0.33)
  Port 2: Pi 5 8GB (10.0.0.34)
  Port 3: Jetson Orin (10.0.0.35) [Phase 4]
  Port 4: Compute Node (10.0.0.36) [Phase 3]
  Port 5: Windows Desktop (DHCP)
  Port 8: Uplink to Xfinity Gateway
    │
    ▼
USB SSD (1TB) — Connected to Pi 8GB, NFS: /mnt/storage
```

## Service Catalog

| Service | Node | Ports | Access | Phase |
|---------|------|-------|--------|-------|
| **NPM** | 8GB Pi | 80, 443, 81 | 80/443 public, 81 LAN | 1 |
| **Haven** | 8GB Pi | 8005 | Via NPM | 1 |
| **Pi-hole** | 2GB Pi | 53, 80 | LAN only | 2 |
| **Cloudflare DDNS** | 2GB Pi | — | Outbound | 2 |
| **WireGuard** | 2GB Pi | 51820/udp | Public | 2 |
| **Uptime Kuma** | 2GB Pi | 3001 | VPN | 2 |
| **Portainer** | 8GB Pi | 9443 | VPN | 2 |
| **Homepage** | 8GB Pi | 3000 | VPN | 2 |
| **n8n** | 8GB Pi | 5678 | VPN | 2 |
| **Grafana** | 8GB Pi | 3100 | VPN | 2 |
| **Loki** | 8GB Pi | 3101 | Internal | 2 |
| **Watchtower** | 8GB Pi | — | Internal | 2 |
| **Promtail** | Both Pis | — | Internal | 2 |
| **Valheim** | Compute | 2456-2457/udp | Public | 3 |
| **Discord Bots** | Compute | — | Outbound | 3 |
| **Minecraft** | Compute | 25565 | Public | 3 |
| **Ollama** | Jetson | 11434 | LAN | 4 |
| **Open WebUI** | Jetson | 3080 | VPN | 4 |

## Phase Roadmap

| Phase | Focus | Cost | Status |
|-------|-------|------|--------|
| 1 | Haven Migration to 8GB Pi | ~$310 | 🔄 **IN PROGRESS** |
| 2 | Infrastructure Services + Haven Rack | ~$151 | ⬜ Not started |
| 3 | Multi-Tenant Compute Platform | ~$550 | ⬜ Not started |
| 4 | AI Infrastructure | ~$2,129 | ⬜ Not started |
| 5 | Fine-Tuning | $0 | ⬜ Not started |
| 6 | Kubernetes (Optional) | $0 | ⬜ Not started |

### Phase 1: Haven Migration to 8GB Pi — 🔄 IN PROGRESS

**Goal:** Haven running in Docker on 8GB Pi behind NPM with SSL. Port forwarding switched from 2GB to 8GB Pi.

#### Completed Steps

| # | Task | Status |
|---|------|--------|
| 1 | Purchase hardware (Micro Center) | ✅ |
| 2 | Flash Pi 8GB with Raspberry Pi OS Lite | ✅ |
| 3 | Configure static IP (10.0.0.34) | ✅ |
| 4 | SSH hardening (ed25519 key, password disabled) | ✅ |
| 5 | Install Docker | ✅ |
| 6 | Add user to docker group | ✅ |
| 7 | Install NPM container | ✅ |
| 8 | Create Cloudflare account | ✅ |
| 9 | Add domain to Cloudflare | ✅ |
| 10 | Update Namecheap nameservers | ✅ |
| 11 | Create A record | ✅ |
| 12 | Create Cloudflare API token | ✅ |
| 13 | Configure port forwarding (currently to 2GB Pi) | ✅ |
| 14 | Haven running at havenmap.online (on 2GB Pi) | ✅ |

#### Remaining Steps

| # | Task | Status | Notes |
|---|------|--------|-------|
| 15 | Restructure Haven-UI codebase | ⬜ | Make self-contained |
| 16 | Create Haven Dockerfile | ⬜ | Based on restructured code |
| 17 | Create .env file on 8GB Pi | ⬜ | |
| 18 | Clone Haven-UI to 8GB Pi | ⬜ | |
| 19 | Deploy Haven container | ⬜ | `docker compose up -d` |
| 20 | Configure NPM proxy host on 8GB Pi | ⬜ | havenmap.online → localhost:8005 |
| 21 | Request SSL certificate | ⬜ | Via NPM |
| 22 | Test Haven on 8GB Pi locally | ⬜ | |
| 23 | Update port forwarding to 8GB Pi | ⬜ | xFi app: 80/443 → 10.0.0.34 |
| 24 | Test external access | ⬜ | From phone on cellular |
| 25 | Verify stable for 24 hours | ⬜ | |
| 26 | Shut down Haven on 2GB Pi | ⬜ | Clear for Phase 2 |

### Phase 2: Infrastructure Services + Haven Rack

**Goal:** Full monitoring, Pi-hole DNS, VPN access, Haven rack assembled.

| # | Task |
|---|------|
| 1 | Order Amazon items |
| 2 | Print Haven rack frame (2x 4U sections, PETG) |
| 3 | Print dual Pi mount (PETG) |
| 4 | Deploy 2GB Pi stack (Pi-hole, DDNS, WireGuard, Uptime Kuma) |
| 5 | Set router DNS to Pi-hole |
| 6 | Deploy 8GB Pi Phase 2 services |
| 7 | Configure Uptime Kuma monitors |
| 8 | Create Discord webhook |
| 9 | Port forward WireGuard |
| 10 | Generate VPN client config |
| 11 | Format USB SSD |
| 12 | Configure Samba |
| 13 | Create backup scripts |
| 14 | Configure UFW on both Pis |
| 15 | Assemble Haven rack |

## Docker Configurations

### Docker Compose Profiles
- **Phase 1:** `docker compose up -d` (NPM + Haven only)
- **Phase 2:** `docker compose --profile phase2 up -d` (all services)

### Pi 5 8GB: Application Stack

```yaml
services:
  # PHASE 1 SERVICES
  nginx-proxy-manager:
    image: jc21/nginx-proxy-manager:latest
    container_name: npm
    ports:
      - '80:80'
      - '443:443'
      - '81:81'
    volumes:
      - ./npm-data:/data
      - ./letsencrypt:/etc/letsencrypt
    restart: unless-stopped

  haven-control-room:
    build: ./haven
    container_name: haven
    volumes:
      - ./haven-data:/app/data
    expose:
      - '8005'
    labels:
      - "com.centurylinklabs.watchtower.enable=false"
    restart: unless-stopped

  # PHASE 2 SERVICES (use --profile phase2)
  portainer:
    image: portainer/portainer-ce:latest
    container_name: portainer
    profiles: [phase2]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./portainer:/data
    ports: ['9443:9443']
    restart: unless-stopped

  homepage:
    image: ghcr.io/gethomepage/homepage:latest
    container_name: homepage
    profiles: [phase2]
    volumes: [./homepage:/app/config]
    ports: ['3000:3000']
    restart: unless-stopped

  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    profiles: [phase2]
    ports: ['5678:5678']
    volumes: [./n8n-data:/home/node/.n8n]
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - TZ=${TZ}
      - WEBHOOK_URL=http://10.0.0.34:5678/
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.2.0
    container_name: grafana
    profiles: [phase2]
    ports: ['3100:3000']
    volumes: [./grafana-data:/var/lib/grafana]
    environment:
      - GF_SECURITY_ADMIN_USER=${GRAFANA_USER}
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
    restart: unless-stopped

  loki:
    image: grafana/loki:2.9.0
    container_name: loki
    profiles: [phase2]
    ports: ['3101:3100']
    volumes:
      - ./loki-data:/loki
      - ./loki-config.yml:/etc/loki/local-config.yaml:ro
    command: -config.file=/etc/loki/local-config.yaml
    restart: unless-stopped

  promtail:
    image: grafana/promtail:latest
    container_name: promtail
    profiles: [phase2]
    volumes:
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./promtail-config.yml:/etc/promtail/config.yml:ro
    command: -config.file=/etc/promtail/config.yml
    restart: unless-stopped

  watchtower:
    image: containrrr/watchtower:latest
    container_name: watchtower
    profiles: [phase2]
    volumes: [/var/run/docker.sock:/var/run/docker.sock]
    environment:
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_POLL_INTERVAL=86400
      - WATCHTOWER_NOTIFICATIONS=shoutrrr
      - WATCHTOWER_NOTIFICATION_URL=${DISCORD_WEBHOOK}
      - WATCHTOWER_LABEL_ENABLE=false
    restart: unless-stopped
```

### Pi 5 2GB: Network Infrastructure Stack (Phase 2)

```yaml
services:
  pihole:
    image: pihole/pihole:2024.07.0
    container_name: pihole
    network_mode: host
    environment:
      - TZ=${TZ}
      - WEBPASSWORD=${PIHOLE_PASSWORD}
    volumes:
      - ./pihole/etc:/etc/pihole
      - ./pihole/dnsmasq:/etc/dnsmasq.d
    deploy:
      resources:
        limits:
          memory: 256M
    restart: unless-stopped

  cloudflare-ddns:
    image: favonia/cloudflare-ddns:latest
    container_name: ddns
    network_mode: host
    environment:
      - CF_API_TOKEN=${CF_API_TOKEN}
      - DOMAINS=${DOMAINS}
      - PROXIED=false
      - IP6_PROVIDER=none
    restart: unless-stopped

  wireguard:
    image: ghcr.io/wg-easy/wg-easy:latest
    container_name: wireguard
    environment:
      - WG_HOST=${WG_HOST}
      - PASSWORD_HASH=${WG_PASSWORD_HASH}
      - WG_PORT=51820
    volumes: [./wireguard:/etc/wireguard]
    ports:
      - '51820:51820/udp'
      - '51821:51821/tcp'
    cap_add: [NET_ADMIN, SYS_MODULE]
    sysctls:
      - net.ipv4.ip_forward=1
    restart: unless-stopped

  uptime-kuma:
    image: louislam/uptime-kuma:1
    container_name: uptime-kuma
    volumes: [./uptime-kuma:/app/data]
    ports: ['3001:3001']
    restart: unless-stopped

  promtail:
    image: grafana/promtail:latest
    container_name: promtail
    volumes:
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./promtail-config.yml:/etc/promtail/config.yml:ro
    command: -config.file=/etc/promtail/config.yml
    restart: unless-stopped
```

### Compute Node: Multi-Tenant Hosting (Phase 3)

```yaml
services:
  valheim:
    image: lloesche/valheim-server
    container_name: valheim
    ports: ['2456-2457:2456-2457/udp']
    volumes:
      - ./valheim-config:/config
      - ./valheim-data:/opt/valheim
    environment:
      - SERVER_NAME=${VALHEIM_SERVER_NAME}
      - WORLD_NAME=${VALHEIM_WORLD_NAME}
      - SERVER_PASS=${VALHEIM_PASSWORD}
      - SERVER_PUBLIC=true
    cap_add: [SYS_NICE]
    restart: unless-stopped

  promtail:
    image: grafana/promtail:latest
    container_name: promtail
    volumes:
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./promtail-config.yml:/etc/promtail/config.yml:ro
    command: -config.file=/etc/promtail/config.yml
    restart: unless-stopped

  watchtower:
    image: containrrr/watchtower:latest
    container_name: watchtower
    volumes: [/var/run/docker.sock:/var/run/docker.sock]
    environment:
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_POLL_INTERVAL=86400
    restart: unless-stopped
```

## Security & Secrets

### SSH Hardening (All Nodes) — ✅ COMPLETE
Both Pis have ed25519 key auth, password auth disabled.

### UFW Firewall Rules

**Pi 2GB (Phase 2):**
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 53 comment 'DNS'
sudo ufw allow 51820/udp comment 'WireGuard'
sudo ufw allow from 10.0.0.0/24 to any port 80 comment 'Pi-hole admin'
sudo ufw allow from 10.0.0.0/24 to any port 3001 comment 'Uptime Kuma'
sudo ufw enable
```

**Pi 8GB:**
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'
sudo ufw allow from 10.0.0.0/24 to any port 81 comment 'NPM admin'
sudo ufw allow from 10.0.0.0/24 to any port 3000 comment 'Homepage'
sudo ufw allow from 10.0.0.0/24 to any port 3100 comment 'Grafana'
sudo ufw allow from 10.0.0.0/24 to any port 5678 comment 'n8n'
sudo ufw allow from 10.0.0.0/24 to any port 9443 comment 'Portainer'
sudo ufw enable
```

### Secrets Template (.env)
```bash
# HAVEN HOMELAB SECRETS — DO NOT COMMIT TO GIT
TZ=America/New_York
PIHOLE_PASSWORD=CHANGE_ME
CF_API_TOKEN=CHANGE_ME
DOMAINS=havenmap.online,www.havenmap.online
WG_HOST=havenmap.online
WG_PASSWORD_HASH=CHANGE_ME
N8N_USER=parker
N8N_PASSWORD=CHANGE_ME
GRAFANA_USER=parker
GRAFANA_PASSWORD=CHANGE_ME
DISCORD_WEBHOOK=discord://token@webhook_id
VALHEIM_SERVER_NAME=Voyager's Haven Valheim
VALHEIM_WORLD_NAME=HavenWorld
VALHEIM_PASSWORD=CHANGE_ME
```

## Observability & Automation (Phase 2)

### n8n Self-Healing Workflow
```
Trigger: Uptime Kuma webhook (service down)
    ↓
Switch: Which service?
    ├── Haven → SSH: docker restart haven
    ├── Valheim → SSH: docker restart valheim
    └── Pi-hole → SSH: docker restart pihole
    ↓
Wait: 30 seconds
    ↓
Check: Is service back?
    ├── Yes → Discord: "✅ [Service] auto-recovered"
    └── No → Discord: "🚨 @Parker [Service] needs help"
```

## Backup & Recovery

### Storage Layout
```
/mnt/storage (1TB USB SSD on Pi 8GB)
├── haven-data/backups/     # Haven database snapshots
├── valheim-worlds/         # Valheim saves (rsync from compute)
├── docker-volumes/         # Critical container data
└── pi-images/              # Monthly SD card backups
```

## Power Budget & Costs

| Node | Typical (W) | Max (W) |
|------|-------------|---------|
| Pi 5 2GB | 5 | 8 |
| Pi 5 8GB | 7 | 12 |
| Switch | 5 | 8 |
| USB SSD | 2 | 3 |
| **Haven Rack Total** | **19** | **31** |
| Compute Node (idle) | 50 | 200 |
| **Combined** | **~70** | **~230** |

### Monthly Operating Costs

| Category | Monthly |
|----------|---------|
| Electricity (~50 kWh × $0.12) | ~$6 |
| Domain ($20/2 years) | ~$0.85 |
| **TOTAL** | **~$7/month** |

### Agent Instructions

If you're a Claude agent picking up this project:

1. Parker is the manager — present options, let him decide
2. Technical depth without filler
3. Python is primary language
4. Explain WHY, not just WHAT
5. Parker has ADHD — repetition helps
6. Hardware decisions are LOCKED
7. Haven is the primary project — everything else supports it
8. Check current phase before suggesting next steps
9. Secrets go in .env files
10. Two racks share one UPS and one PDU

---
---

# 4. HARDWARE RATIONALE

> **Purpose:** Explains WHY each hardware component was chosen
> **Total Budget:** ~$3,140

## Rack Frames ($80 total)

**Choice:** Two matching 8U racks — each built from 2x 4U printed sections

- Two racks instead of one = separation of concerns, modular growth, cleaner cables, mini data center aesthetic
- 10-inch instead of 19-inch = desk-friendly, hardware exists, proven by Jeff Geerling
- Printed instead of purchased = metal racks cost $100-200 each, filament costs ~$25 each
- Community design for frame + custom mounts = proven structural design + easy iteration

## Network ($50)

### Switch: TP-Link TL-SG108PE
**Upgraded from planned SG108E to SG108PE** (added PoE as a bonus).

| Feature | Unmanaged (SG108) | Managed (SG108PE) |
|---------|-------------------|-------------------|
| VLANs | ❌ | ✅ Up to 32 |
| QoS | ❌ | ✅ |
| Web UI | ❌ | ✅ |
| PoE | ❌ | ✅ 4 ports |
| Price | $20 | $50 |

$30 more buys future-proofing. One switch for both racks (8 ports is plenty).

## ARM Compute ($125)

### Pi 5 8GB vs 4GB
$5 difference buys headroom for more services, memory spikes, no OOM kills.

### 27W PSU
Pi 5 can draw 25W under load. 15W PSU causes CPU throttling and USB brownouts.

### Active Cooler
Without cooling: 80°C+ under Docker load, thermal throttling at 85°C. Active cooler keeps 50-65°C.

### A2-rated SD Card
Docker does constant random I/O. A2 makes container starts 2-4 seconds instead of 8-15 seconds.

## AI Accelerator ($2,129) — PHASE 4, FUTURE

### Jetson Orin Nano Super ($249)
- Always-on AI at 15-25W vs desktop at 300-500W
- 67 TOPS, best performance per dollar for edge AI

### RTX 4090 ($1,600)
- 24GB VRAM = train up to 20B, inference up to 30B
- $600 more than 4080 buys 50% more VRAM

## x86 Compute Platform ($550)

### Why x86?
Valheim requires x86. No ARM version exists.

### Why Ryzen 7 5700X?
8 cores/16 threads handles multiple simultaneous workloads (Valheim + Minecraft + Discord bots + more).

### Why Micro-ATX?
4 RAM slots = upgrade path from 64GB to 128GB.

### Why 450W SFX PSU?
PicoPSU was for old 6c build. 8c/65W Ryzen needs more headroom.

### Why 4U Sled?
Micro-ATX board + 69mm cooler + SFX PSU + airflow all fit comfortably.

## Storage ($70)

### Crucial X9 1TB USB SSD
- USB SSD + Samba is simple Phase 1 strategy
- Upgrade path: Synology NAS when 1TB feels tight

## Power ($90)

### One Shared UPS (CyberPower EC450G, 450VA/260W)
- Combined typical: ~70W, combined max: ~220W
- 5-8 minutes at max = enough for graceful shutdown

### One Shared PDU
- Single point of power management
- Saves $30 vs second PDU

---
---

# 5. MULTI-AGENT AI ARCHITECTURE (Phases 4-5)

> **Status:** Phase 4-5 Planning
> **Prerequisites:** Phases 1-3 complete
> **Hardware Required:** RTX 4090, Jetson Orin Nano Super, 64GB RAM
> **Estimated Cost:** ~$2,129

## Overview

Multiple specialized models instead of one AI that does everything okay. Reduces Claude API costs from $100/month to $10-30/month.

## Agent Roles

| Agent | Base Model | Fine-Tuned For | Runs On | When Used |
|-------|-----------|----------------|---------|-----------|
| **Router** | 1-3B | Query classification | Jetson/Pi | Every query |
| **Voice** | 7B | Quick responses, chat, home control | Jetson | Always-on |
| **Monitor** | 3B | Homelab status, alerts | Jetson | Always-on |
| **Coder** | 30B code-specialized | Haven codebase, debugging | Desktop 4090 | On demand |
| **Planner** | 70B | Architecture, strategy, documentation | Desktop 4090 | On demand |

## Query Routing Flow

```
[Your Query] → [Router Agent]
  ├── Simple questions → Voice Agent (7B, Jetson)
  ├── Status checks → Monitor Agent (3B, Jetson)
  ├── Code tasks → Coder Agent (30B, Desktop)
  ├── Planning → Planner Agent (70B, Desktop)
  └── Complex reasoning → Claude API
```

## Voice Assistant Pipeline

```
[USB Mic on Pi 8GB] → [OpenWakeWord] → [whisper.cpp] → [n8n router]
  ├── Command → Execute action (no AI needed)
  ├── Simple/quick → Jetson Ollama (Qwen 3B ~35 tok/s)
  ├── Complex → Desktop Ollama (Llama 8B ~89 tok/s)
  └── Research/coding → Claude API (Haiku 4.5)
      → [Piper TTS] → [USB Speaker]
```

## Jetson Performance (JetPack 6.2 Super Mode)

| Model | Tokens/sec | Use Case |
|-------|-----------|----------|
| Qwen2.5 1.5B (INT4) | ~45-55 | Quick voice responses |
| Llama 3.2 3B (INT4) | ~28-35 | General assistant |
| Qwen2.5 7B (INT4) | ~20-22 | Complex reasoning |

## Model Quality Reality Check

| Model Size | Quality vs Claude Sonnet | Trainable on 4090? |
|------------|--------------------------|---------------------|
| 7B | 50-60% general, **85-95% fine-tuned** | ✅ Yes |
| 13B | 60-70% general, **90-95% fine-tuned** | ✅ Yes |
| 30B | 70-80% general | ⚠️ Cloud needed |
| 70B | 75-85% general | ⚠️ Cloud needed |

**Key insight:** Fine-tuning closes the capability gap. A 7B model fine-tuned on YOUR codebase can outperform Claude for those specific tasks.

## Cost Reduction Goal

| Current | Target |
|---------|--------|
| Claude Max: $100/month | Claude API: $10-30/month |
| All queries to Claude | 80% local, 20% API |
| Generic responses | Fine-tuned for YOUR tasks |

## Training Data Categories

| Category | Examples Needed | Source |
|----------|-----------------|--------|
| Haven codebase | 500+ | GitHub repo with explanations |
| Debugging sessions | 200+ | Past Claude conversations |
| Architecture decisions | 200+ | Planning docs, rationale |
| Communication style | 500+ | How Parker phrases things |
| Homelab commands | 300+ | Common Linux/Docker tasks |
| Project management | 300+ | Decision-making patterns |

---
---

# 6. KUBERNETES CLUSTER DESIGN (K3s) — Phase 6

> **Status:** Phase 6 Planning
> **Prerequisites:** Phases 1-5 complete
> **Cost:** $0 (software only)

## Why Kubernetes?

| Without K3s | With K3s |
|-------------|----------|
| Manage Docker Compose separately on each node | Single control plane manages everything |
| Manual container placement | Automatic scheduling based on labels/taints |
| If container crashes, manually restart | Self-healing — K3s restarts automatically |
| SSH into each node to deploy | `kubectl apply` deploys from anywhere |
| Config scattered across nodes | All manifests in GitHub (GitOps) |

## Cluster Layout

```
K3s Control Plane (Pi 5 8GB)
├── Pi 5 8GB (control plane + worker)
│   Labels: arch=arm64, role=apps, audio=true
│   Pods: Haven, NPM, Portainer, Homepage, voice-pipeline
├── Pi 5 2GB (worker)
│   Labels: arch=arm64, role=network
│   Taint: network-only=true:PreferNoSchedule
│   Pods: Pi-hole, DDNS, Uptime Kuma, WireGuard
├── Jetson Orin Nano (worker)
│   Labels: arch=arm64, role=ai, gpu=nvidia, accelerator=jetson
│   Taint: ai-workloads=true:PreferNoSchedule
│   Pods: Ollama, Open WebUI
└── x86 Compute Node (worker)
    Labels: arch=amd64, role=compute, gaming=true
    Pods: Valheim, future game servers
```

## Persistent Storage with NFS

```
[Pi 8GB with 1TB USB SSD]
    │ NFS exports /mnt/storage
    ├── /mnt/storage/haven-data
    ├── /mnt/storage/valheim-worlds
    ├── /mnt/storage/ollama-models
    └── /mnt/storage/backups
```

---
---

# 7. HAVEN API SPECIFICATION (Planned)

> **Status:** SPECIFICATION — These endpoints do not exist yet
> **Base URL (Planned):** `https://havenmap.online/api`

## Planned Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/status` | GET | Health check and statistics |
| `/api/systems` | GET | List star systems (paginated) |
| `/api/systems/{id}` | GET | System details with planets |
| `/api/planets` | GET | List planets (filterable by type, weather, sentinels) |
| `/api/planets/{id}` | GET | Planet details |
| `/api/stats` | GET | Aggregate statistics |

## Rate Limiting (Planned)
- Public (external IP): 60 requests/minute
- Internal (10.0.0.0/24): Unlimited

---
---

# 8. RUNBOOK — Troubleshooting

> **Purpose:** Troubleshooting procedures and solutions for common issues
> **Policy:** Entries added only with Parker's explicit permission

## How This Document Works

This runbook is populated as issues arise and are solved. When Parker encounters a problem and we solve it together, Parker can say "add this to the runbook" and the issue gets documented with:
1. The symptom
2. The diagnosis steps
3. The solution
4. How to prevent it next time

*(No entries yet — document will grow as issues are encountered and solved)*

---
---

# 9. CLEANUP REPORT — Repository Restructure

> **Generated:** February 4, 2026
> **Status:** CLEANUP FINISHED

## Summary

Haven-UI was restructured to be fully self-contained. Previously, the Haven-UI folder had imports reaching into the parent Master-Haven/src directory. All backend code was moved into Haven-UI/backend/, scripts were consolidated, tests were merged, and stale files were deleted.

## Final Repository Structure

```
C:\Master-Haven\
├── .claude/                        # Claude Code settings
├── .gitignore
├── .gitmodules                     # Planet_Atlas submodule
├── CLAUDE.md                       # Master project documentation
├── LICENSE
├── README.md
├── transfer_to_pi.bat              # Cross-project utility
├── update_planet_atlas.bat         # Submodule management
│
├── Haven-UI/                       # FULLY SELF-CONTAINED
│   ├── backend/                    # Python backend code
│   │   ├── control_room_api.py     # Main FastAPI server (666KB, 10,859 lines)
│   │   ├── glyph_decoder.py
│   │   ├── migrations.py
│   │   ├── paths.py
│   │   ├── planet_atlas_wrapper.py
│   │   ├── migrate_atlas_pois.py
│   │   └── CLAUDE.md
│   ├── data/                       # Databases
│   ├── dist/                       # Built React frontend
│   ├── docs/                       # Documentation
│   ├── scripts/                    # Utility scripts
│   ├── src/                        # React source (JavaScript)
│   ├── tests/                      # All tests
│   ├── server.py                   # Entry point
│   ├── package.json
│   ├── requirements.txt
│   └── README.md
│
├── keeper-discord-bot-main/        # SELF-CONTAINED
├── NMS-Haven-Extractor/            # SELF-CONTAINED
├── NMS-Memory-Browser/             # SELF-CONTAINED
├── NMS-Save-Watcher/               # SELF-CONTAINED
└── Planet_Atlas/                   # Git submodule (external)
```

## Key Import Changes Applied
- `from src.X` → `from X` (direct import from backend/)
- `from config.paths` → `from paths`
- `parents[1]` → uses `BACKEND_DIR.parent`

## Next Steps After Cleanup
1. Test Haven-UI server: `cd Haven-UI && python server.py`
2. Run npm build: `cd Haven-UI && npm run build`
3. Review git status before committing
4. Deploy to Pi using transfer_to_pi.bat or scp

---
---

# 10. CLAUDE'S MEMORY CONTEXT

## What Claude Remembers About This Project

Parker is building the Haven Homelab project, a comprehensive self-hosted infrastructure centered around migrating his No Man's Sky community web app "Haven Control Room" from ngrok to a custom domain at havenmap.online. The project involves building a homelab using Raspberry Pi 5 boards with custom 3D-printed 10-inch server racks, with plans to expand into AI infrastructure and game servers.

Parker has completed Phase 1 hardware procurement, having visited Micro Center with real-time shopping assistance. When exact items weren't available, he successfully evaluated alternatives like the TP-Link SG108PE switch (which included Power over Ethernet as a bonus). The project documentation has been restructured from a massive 2,655-line master plan into six focused, actionable documents.

Parker is actively setting up a Claude AI project for homelab infrastructure planning and management, working to ensure all necessary documentation is properly configured.

**Immediate next step:** Phase 1 implementation — codebase restructure, Dockerfile creation, Docker deployment on 8GB Pi.

**Approach:** Parker prefers detailed technical explanations with clear rationale for hardware and software choices, but shifts to wanting concise, actionable guidance when actively working on implementation tasks. He maintains a systematic approach to project organization.

**No user-specific memory edits are currently stored.**

---
---

*End of Haven Homelab Complete Export — February 4, 2026*
