# Haven UI

A **No Man's Sky discovery mapping and archival system** built for explorers and communities who want to catalog, share, and preserve their discoveries.

---

## What is Haven UI?

Haven UI is a web dashboard where No Man's Sky players can browse, submit, and manage star system discoveries. Whether you're an independent explorer documenting your journey or part of a community building a shared archive, Haven UI gives you the tools to make it happen.

**No installation required** — Haven UI is hosted online at **[havenmap.online](https://havenmap.online)**. Just click and start exploring.

---

## Who's Using Haven?

Multiple No Man's Sky communities are already archiving their discoveries:

| Community | Tag | Focus |
|-----------|-----|-------|
| Haven Hub | Haven | Central archive hub |
| Intergalactic Explorers Alliance | IEA | Exploration collective |
| Black Edge Syndicate | B.E.S | Pirate organization |
| Archive Community | ARCH | Preservation focused |
| The Brotherhood | TBH | Deep space exploration |
| Everion | EVRN | Republic network |
| Independent Explorers | Personal | Solo travelers |

Each community has its own color-coded badge, making it easy to see who discovered what.

---

## What Can You Do?

Haven UI offers different features depending on your role. Click any section below to learn more.

### For Everyone (No Login Required)
> Browse the entire discovery database, search for systems, and submit your own discoveries for review.

**[→ Public Features](#public-features)**

---

### For Partners (Community Admins)
> Manage your community's submissions, approve new systems, and delegate access to trusted members.

**[→ Partner Guide](#partner-guide)**

---

### For Sub-Admins (Delegated Access)
> Help your community with specific tasks assigned by your partner admin.

**[→ Sub-Admin Guide](#sub-admin-guide)**

---

### Build Your Own Tools
> Use API keys to create Discord bots, automate submissions, or build custom visualizations.

**[→ API Integration](#api-integration)**

---

---

# Public Features

Everything in this section is available to anyone — no login required.

## Dashboard

The dashboard is your home base. At a glance you'll see:

- **Live statistics** — Total systems, planets, moons, regions, and discoveries
- **Recent systems** — The 6 most recently added systems
- **Top regions** — Which regions have the most documented systems
- **Activity feed** — Real-time updates as submissions come in and get approved
- **Connection status** — Green indicator when connected to the database

## Systems Browser

Browse all documented star systems organized by region.

- **View modes** — Switch between List view (more data) and Grid view (with photos)
- **Search** — Find systems by name, glyph code, or galaxy
- **Filter by community** — Show only systems from a specific Discord community
- **Region grouping** — Systems are organized under their galactic regions

Click any region to see all its systems. Click any system to see full details.

## Region Detail

When you click into a region, you'll see:

- **Region statistics** — Biome distribution, star types, economy breakdown
- **All systems** — Every documented system in that region
- **Search and filter** — Narrow down within the region
- **Sorting options** — Order by name, date added, or other attributes

## System Detail

The full profile of a star system includes:

- **Coordinates** — Galactic position and portal glyph code
- **Star info** — Color, economy type/tier, conflict level, dominant lifeform
- **Space station** — Details if one exists in the system
- **Planets and moons** — Expandable cards for each body showing:
  - Biome and weather
  - Sentinel activity
  - Fauna and flora richness
  - Environmental hazards (temperature, radiation, toxicity)
  - Resources
- **Photo gallery** — Discovery screenshots

## System Wizard

Submit your own discoveries for community review.

1. **Enter portal glyphs** — Use the interactive glyph picker to decode coordinates
2. **Select your community** — Choose your Discord tag (or "Personal" for independent)
3. **Fill in system details** — Star color, economy, conflict level, lifeform
4. **Add planets** — Full property editor for each planet and moon
5. **Add space station** — Optional details if present
6. **Submit** — Your system goes to the approval queue

A partner or super admin will review your submission before it appears in the database.

## Discoveries

Browse all cataloged discoveries including species, minerals, and anomalies.

- Search by name or description
- Submit new discoveries with photo evidence

## Database Statistics

View comprehensive metrics about everything in the database — discovery counts by category, growth over time, and more.

---

# Partner Guide

Partners are community administrators. If you run a No Man's Sky Discord community, you can become a partner to manage your community's data in Haven.

## Logging In

1. Click **Admin Login** in the navigation bar
2. Enter your credentials
3. Your Discord tag and role appear in the nav bar

## What Partners Can Do

Everything public users can do, plus:

### Pending Approvals

Review submissions tagged with your community.

- **View full details** before making a decision
- **Approve** — System goes live in the database
- **Reject** — Submission removed (requires a reason)
- **Batch mode** — Select multiple submissions and process them at once

**Note:** You cannot approve your own submissions. This prevents self-approval.

### Create Systems Directly

Skip the approval queue entirely. Systems you create are saved immediately.

### Edit Systems

- Edit any system tagged with your community
- Editing untagged systems creates an edit request for super admin approval

### Sub-Admin Management

Delegate access to trusted community members.

- Create sub-admin accounts under your partnership
- Assign specific features to each sub-admin
- Reset passwords and activate/deactivate accounts

Available features to assign:
| Feature | What It Allows |
|---------|----------------|
| `system_create` | Create new systems directly |
| `system_edit` | Edit community systems |
| `approvals` | Review pending submissions |
| `batch_approvals` | Process multiple at once |
| `stats` | View statistics |
| `settings` | Customize theme |

### CSV Import

Bulk import systems from spreadsheet files.

- Drag and drop CSV upload
- Expected format: Region name in row 1, headers in row 2, data starting row 3
- Systems automatically tagged with your community

### Settings

- Change your password
- Customize your theme colors (background, text, card, accent)
- Preview changes before saving

---

# Sub-Admin Guide

Sub-admins are community members who receive delegated access from their partner admin. Your available features depend on what your partner enabled for you.

## What You Might Have Access To

| Feature | Description |
|---------|-------------|
| `system_create` | Create new systems directly |
| `system_edit` | Edit systems in your community |
| `approvals` | Review and approve submissions |
| `batch_approvals` | Process multiple submissions at once |
| `stats` | View database statistics |
| `settings` | Customize your theme |

## Limitations

- You can only access features your partner enabled
- You cannot manage other sub-admins
- You cannot approve your own submissions
- System edits are limited to your community's tagged systems

---

# API Integration

Haven UI supports API keys that let you build custom tools and integrations.

## What Can You Build?

### Discord Bot
Create a bot that posts new discoveries to your Discord server whenever systems get approved in your community.

### Automated Submissions
Build tools that automatically submit discoveries from your own data sources.

### External Visualizations
Pull data from Haven to create custom maps, charts, or analysis tools for your community.

## Getting an API Key

API keys are created by super admins. If you have a project idea, reach out to Haven leadership to request a key with the permissions you need.

---

**Happy exploring, Traveller!**
