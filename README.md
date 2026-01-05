# Master Haven

A comprehensive **No Man's Sky discovery mapping and archival system** featuring live data extraction, automatic submission, multi-community support, and a full-featured web dashboard.

## Overview

Master Haven is a suite of tools designed to help No Man's Sky explorers catalog, share, and analyze their discoveries. Whether you're documenting new star systems, tracking rare planets, or building a community archive, Master Haven provides the infrastructure to make it happen.

### Key Features

- **Live Data Extraction** - In-game mod extracts system/planet data automatically as you play
- **Auto-Submission** - Watcher monitors save files and submits discoveries to the Haven database
- **Web Dashboard** - Beautiful React UI for browsing discoveries and managing data
- **Glyph Support** - Full portal glyph encoding/decoding for easy coordinate sharing
- **Multi-Community** - Support for multiple Discord communities with data restrictions
- **Approval System** - Moderated submissions with batch approve/reject
- **Partner Management** - Delegate admin access to community partners

## Project Structure

```
Master-Haven/
├── Haven-UI/                 # Web dashboard (React + FastAPI backend)
│   ├── src/
│   │   ├── components/       # Reusable UI components
│   │   ├── pages/            # Page components (Dashboard, Systems, etc.)
│   │   ├── utils/            # Auth context, helpers
│   │   └── data/             # Static data (galaxies, biomes, etc.)
│   ├── dist/                 # Production build output
│   ├── photos/               # Discovery screenshots
│   └── data/                 # SQLite database
├── NMS-Haven-Extractor/      # Live game mod for data extraction
├── NMS-Save-Watcher/         # Automatic save file monitoring
├── NMS-Memory-Browser/       # Game memory inspection tool
├── src/                      # Core API (control_room_api.py)
├── config/                   # Shared configuration
├── scripts/                  # Utility and deployment scripts
├── tests/                    # Test suite
└── docs/                     # Documentation
```

## Quick Start

### Prerequisites

- **Python 3.10+** (from [python.org](https://python.org), NOT Windows Store)
- **Node.js 18+** (for Haven-UI frontend)
- **No Man's Sky** (Steam version recommended)
- **Git** (for cloning the repository)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/Master-Haven.git
   cd Master-Haven
   ```

2. **Set up Python environment**
   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # Linux/macOS
   source .venv/bin/activate

   pip install -r Haven-UI/requirements.txt
   ```

3. **Set up the frontend**
   ```bash
   cd Haven-UI
   npm install
   cd ..
   ```

4. **Configure environment**
   ```bash
   # Copy the example environment file
   cp Haven-UI/.env.example Haven-UI/.env

   # Edit .env and set your values (see Configuration section)
   ```

5. **Start the application**
   ```bash
   # Development mode (two terminals needed)

   # Terminal 1 - Backend
   python src/control_room_api.py

   # Terminal 2 - Frontend
   cd Haven-UI
   npm run dev
   ```

6. **Access the dashboard**
   - Development: http://localhost:5173
   - Production: http://localhost:8000/haven-ui/

## Components

### Haven-UI (Web Dashboard)

The main web interface for browsing and managing discoveries. Haven-UI uses a role-based access system that provides different features depending on your access level.

---

## Haven-UI User Guide

### Accessing the Dashboard

- **Development**: http://localhost:5173
- **Production**: http://localhost:8000/haven-ui/

The dashboard loads with public access by default. Click **Admin Login** in the navigation bar to authenticate with elevated permissions.

---

### User Roles Overview

| Role | Who | Access |
|------|-----|--------|
| **Public** | Anyone | Browse, search, submit for approval |
| **Partner** | Community admins | Approve submissions, manage sub-admins, customize theme |
| **Sub-Admin** | Partner delegates | Limited features assigned by partner |
| **Super Admin** | Haven leadership | Full system control |

---

### Public Users (No Login Required)

Public users can browse the entire discovery database and submit new systems for community review.

#### Dashboard (`/`)
- View live statistics: system count, planets, moons, regions, discoveries
- See connection status indicator
- Browse the 6 most recent systems
- View top 5 regions by system count
- Watch real-time activity feed (submissions, approvals, map updates)
- Use quick action buttons to navigate

#### Systems Browser (`/systems`)
- Browse all systems organized by region
- Toggle between **List** and **Grid** view modes
- Search by system name, glyph code, or galaxy
- Filter by Discord community tag
- Click any region to view its systems
- Systems display Discord community badges with unique colors

#### Region Detail (`/regions/:rx/:ry/:rz`)
- View all systems in a specific region
- See region statistics: biome distribution, star types, economies
- Search, filter, and sort systems within the region
- Click any system card to view full details

#### System Detail (`/systems/:id`)
- View complete system information:
  - Galactic coordinates and glyph code
  - Star color, economy, conflict level, dominant lifeform
  - Space station details (if present)
- Browse all planets with expandable details:
  - Biome, sentinels, fauna/flora richness
  - Environmental hazards (temperature, radiation, toxicity)
  - Resource distribution
  - Nested moons
- View discovery photo galleries

#### Discoveries (`/discoveries`)
- Browse all discoveries (species, minerals, anomalies)
- Search by name or description
- Submit new discoveries with photos/evidence

#### Database Statistics (`/db_stats`)
- View comprehensive database metrics
- Track discovery counts by category

#### System Wizard (`/wizard`)
- **Submit new systems for approval**
- Use the interactive glyph picker to decode portal coordinates
- Select your Discord community tag (required)
- Choose "Personal" if not affiliated with a community
- Fill in system attributes:
  - Star color, economy type/tier, conflict level
  - Dominant lifeform
- Add planets with full property editors
- Add space station details (optional)
- Submit for community review

**Note**: Public submissions go to the approval queue. A partner or super admin must approve before they appear in the database.

---

### Partners (Community Admins)

Partners are community administrators who can approve submissions and manage their community's data.

#### Logging In
1. Click **Admin Login** in the navigation bar
2. Enter your username and password
3. Your Discord tag and role appear in the nav bar

#### All Public Features Plus:

#### Pending Approvals (`/pending-approvals`)
- Review submissions tagged with your community
- View complete system details before approving
- **Approve** or **Reject** individual submissions
  - Rejections require a reason
- **Batch Mode** (if enabled):
  - Select multiple submissions
  - Approve or reject all at once
  - View results summary
- Review edit requests from other partners on untagged systems
- **Cannot approve your own submissions** (security measure)

#### System Creation & Editing
- Create systems directly (saved immediately, no approval needed)
- Edit systems tagged with your community
- Editing untagged systems creates an edit request for super admin approval

#### Settings (`/settings`)
- View your account information
- Change your password
- Customize your theme colors:
  - Background, text, card, and primary colors
  - Preview changes before saving

#### Sub-Admin Management (`/admin/sub-admins`)
- Create sub-admin accounts under your partnership
- Assign specific features to each sub-admin:
  - `system_create` - Create new systems
  - `system_edit` - Edit community systems
  - `approvals` - Review pending submissions
  - `batch_approvals` - Batch operations
  - `stats` - View statistics
  - `settings` - Customize theme
- Reset sub-admin passwords
- Activate/deactivate sub-admins

#### CSV Import (`/csv-import`) (if enabled)
- Import systems in bulk from CSV files
- Drag and drop or browse to upload
- Expected format:
  - Row 1: Region name
  - Row 2: Headers
  - Row 3+: Data (Coordinates, System Name required)
- Systems auto-tagged with your community

---

### Sub-Admins (Partner Delegates)

Sub-admins receive delegated access from their parent partner. Features vary based on what the partner enabled.

#### Available Features (Partner-Assigned):

| Feature | Description |
|---------|-------------|
| `system_create` | Create new systems directly |
| `system_edit` | Edit systems in your community |
| `approvals` | Review and approve submissions |
| `batch_approvals` | Process multiple submissions at once |
| `stats` | View database statistics |
| `settings` | Customize your theme |

#### Limitations:
- Can only access features enabled by parent partner
- Cannot manage other sub-admins
- Cannot approve own submissions
- System edits limited to community-tagged systems

---

### Super Admin (Full Access)

Super admins have complete control over the Haven system.

#### All Partner Features Plus:

#### Partner Management (`/admin/partners`)
- Create new partner accounts:
  - Username, password, Discord tag, display name
  - Select enabled features
- Edit existing partners
- Reset partner passwords
- Activate/deactivate partner accounts
- View partner activity (creation date, last login)

#### Sub-Admin Management (Global)
- Create sub-admins under any partner
- View all sub-admins across all partners
- Manage sub-admins for any community

#### Pending Approvals (Enhanced)
- **Filter by Discord tag** to focus on specific communities
- **"Untagged only"** filter for independent submissions
- Approve any submission regardless of community
- Process edit requests from partners

#### API Keys (`/api-keys`)
- Create API keys for companion apps (Save Watcher, bots):
  - Set rate limits (requests/hour)
  - Assign Discord community tag
  - Configure permissions (submit, check_duplicate)
- View key usage statistics
- Revoke or reactivate keys

#### Settings (Global)
- Change password
- Set **global theme** (applies to all users by default)
- **Database backup**: Create timestamped backups
- **Database restore**: Upload .db file to restore
- **Data migration**: Hub tag migration tool

#### Approval Audit (`/admin/audit`)
- View complete history of all approval actions
- Track who approved/rejected what and when
- Audit trail for accountability

#### Data Restrictions (`/data-restrictions`)
- Configure per-community data visibility
- Control what data each community can access

#### Region Name Management
- Directly update region names (no approval needed)
- Review region name submissions from partners

---

### Common Features for All Authenticated Users

#### Navigation Bar
- Shows your display name and role
- Discord tag badge (for partners/sub-admins)
- Quick access to all enabled features
- Logout button

#### Theme Customization
- Personal theme overrides global defaults
- Four customizable colors:
  - Background (`--app-bg`)
  - Text (`--app-text`)
  - Card (`--app-card`)
  - Primary accent (`--app-primary`)

#### Inactivity Timeout
- Automatic overlay after period of inactivity
- Click to dismiss and continue working
- Protects against unauthorized access

---

### Discord Community Tags

Systems are organized by Discord community. Each community has a unique color badge:

| Tag | Community | Color |
|-----|-----------|-------|
| Haven | Haven Hub | Cyan |
| IEA | Intergalactic Exploration Agency | Green |
| B.E.S | Bureau of Exploration Services | Orange |
| ARCH | Archive Community | Purple |
| TBH | The Black Hole | Yellow |
| EVRN | Euclid Virtual Republic Network | Pink |
| Personal | Independent explorers | Magenta |

Custom community tags receive auto-assigned unique colors.

---

### Tips for Effective Use

1. **Use the glyph picker** - The interactive glyph decoder automatically calculates all coordinates from portal glyphs
2. **Filter by community** - Use Discord tag filters to focus on your community's data
3. **Batch processing** - Use batch mode for efficient approval workflows
4. **Search everything** - Global search works on names, glyph codes, and galaxies
5. **Grid vs List** - Grid view shows photos, list view shows more systems at once
6. **Activity feed** - Watch the dashboard activity feed to see real-time submissions

---

**UI Features:**
- Responsive design (desktop/tablet/mobile)
- Dark theme optimized for space exploration
- List and grid view modes
- Collapsible stat breakdowns
- Real-time search with debouncing
- Inactivity timeout with overlay

[See Haven-UI README](Haven-UI/README.md)

### NMS-Save-Watcher

Automatically monitors your NMS save files and submits discoveries.

**Features:**
- Real-time file watching
- Automatic discovery extraction
- Duplicate detection
- Offline queue with retry
- Web dashboard at localhost:8006

[See NMS-Save-Watcher README](NMS-Save-Watcher/README.md)

### NMS-Haven-Extractor

A live game mod that extracts data directly from game memory.

**Features:**
- Real-time extraction while playing
- More detailed data than save files
- Works with NMS.py/pyMHF framework

[See NMS-Haven-Extractor README](NMS-Haven-Extractor/README.md)

### NMS-Memory-Browser

A PyQt6 GUI tool for inspecting live game memory.

**Features:**
- Browse game structures in real-time
- Hex dump viewer
- JSON export for analysis

[See NMS-Memory-Browser README](NMS-Memory-Browser/README.md)

## Configuration

### Environment Variables

Create a `.env` file in the `Haven-UI` folder:

```env
# Admin password for web UI login (super admin)
HAVEN_ADMIN_PASSWORD=your_secure_password

# API key for external integrations (e.g., Discord bot)
HAVEN_API_KEY=your_api_key_here
```

### Save Watcher Configuration

Edit `NMS-Save-Watcher/config.json`:

```json
{
  "api": {
    "base_url": "http://localhost:8000",
    "key": "your_api_key_here"
  },
  "watcher": {
    "save_slot": 1,
    "enabled": true
  }
}
```

## Authentication & Permissions

Master Haven uses a tiered permission system:

| Role | Description | Permissions |
|------|-------------|-------------|
| **Super Admin** | Full system access | All features, partner management, audit logs |
| **Partner** | Community admin | Approvals, settings, sub-admin management (scoped to their community) |
| **Sub-Admin** | Delegated access | Limited features assigned by their partner |
| **User** | Public access | View systems, submit discoveries |

### Feature Permissions

Partners and sub-admins can be granted specific features:
- `approvals` - Review pending submissions
- `batch_approvals` - Batch approve/reject
- `settings` - Modify system settings
- `csv_import` - Import data from CSV
- `system_create` - Create new systems
- `system_edit` - Edit existing systems
- `stats` - View detailed statistics

## Development vs Production

### Development Mode

Best for making changes - provides hot reload.

```bash
# Terminal 1 - Backend API
python src/control_room_api.py

# Terminal 2 - Frontend with hot reload
cd Haven-UI && npm run dev
```

Access at: **http://localhost:5173**

### Production Mode

Best for sharing and deployment.

```bash
# Build the frontend
cd Haven-UI
npm run build

# Start the server (serves both API and built frontend)
cd ..
python src/control_room_api.py
```

Access at: **http://localhost:8000/haven-ui/**

### Sharing via ngrok

```bash
# Start production server, then:
ngrok http 8000
```

## API Reference

The Haven API provides REST endpoints for discovery management:

### Public Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Server status |
| `/api/stats` | GET | Discovery statistics |
| `/api/systems` | GET | List all systems |
| `/api/systems/{id}` | GET | Get system details |
| `/api/systems/search` | GET | Search systems by name/glyph/galaxy |
| `/api/regions/grouped` | GET | List regions with system counts |
| `/api/regions/{rx}/{ry}/{rz}` | GET | Get region details |
| `/api/regions/{rx}/{ry}/{rz}/systems` | GET | Get systems in a region |
| `/api/planets` | GET | List all planets |
| `/api/galaxies` | GET | List galaxies |
| `/api/discord_tags` | GET | List community tags |

### Submission Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/discoveries` | POST | Submit new discovery |
| `/api/pending_submissions` | GET | List pending approvals |
| `/api/approve_system/{id}` | POST | Approve a submission |
| `/api/reject_system/{id}` | POST | Reject a submission |
| `/api/approve_systems/batch` | POST | Batch approve submissions |
| `/api/reject_systems/batch` | POST | Batch reject submissions |

### Admin Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/partners` | GET/POST | Manage partners |
| `/api/partners/{id}/sub-admins` | GET/POST | Manage sub-admins |
| `/api/api_keys` | GET/POST | Manage API keys |
| `/api/settings` | GET/POST | System settings |
| `/api/data_restrictions` | GET/POST | Data visibility rules |
| `/api/audit_log` | GET | Approval audit history |

See the [API documentation](docs/API.md) for full details.

## Data Storage

All data is stored locally in the `Haven-UI` folder:

| Path | Contents |
|------|----------|
| `Haven-UI/data/haven_ui.db` | SQLite database (systems, planets, discoveries) |
| `Haven-UI/data/pending.db` | Pending submissions database |
| `Haven-UI/photos/` | Discovery screenshots |
| `Haven-UI/logs/` | Application logs |

### Database Tables

- `systems` - Star systems with coordinates, galaxy, star type
- `planets` - Planets/moons with biome, resources, sentinels
- `discoveries` - Flora, fauna, minerals
- `regions` - Named regions with custom names
- `pending_submissions` - Submissions awaiting approval
- `partners` - Partner admin accounts
- `sub_admins` - Sub-admin accounts
- `api_keys` - External API keys
- `sessions` - Active login sessions

## Troubleshooting

### Common Issues

**"Cannot connect to API"**
- Ensure the backend is running on port 8000
- Check firewall settings

**"Save file not found"**
- Verify NMS save location in config
- Check save slot number (default: 1)

**"Module not found"**
- Activate virtual environment
- Run `pip install -r requirements.txt`

**"npm command not found"**
- Install Node.js from [nodejs.org](https://nodejs.org)

**"Session expired" / Inactivity timeout**
- The UI automatically logs out after inactivity
- Click to dismiss the overlay and re-authenticate

### Logs

Check logs for detailed error information:
- Haven-UI: `Haven-UI/logs/control-room-web.log`
- Save Watcher: `NMS-Save-Watcher/watcher.log`

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See [LICENSE](LICENSE) for details.

## Credits

- [NMS.py](https://github.com/monkeyman192/NMS.py) - Game memory hooks
- [pyMHF](https://github.com/monkeyman192/pyMHF) - Memory injection framework
- [MBINCompiler](https://github.com/monkeyman192/MBINCompiler) - Save file parsing
- [No Man's Sky Wiki](https://nomanssky.fandom.com) - Game data reference

## Support

- Open an issue on GitHub for bugs or feature requests
- Check the [docs](docs/) folder for detailed guides

---

**Happy exploring, Traveller!**
