# Master Haven

A comprehensive **No Man's Sky discovery mapping and archival system** featuring live data extraction, automatic submission, and a web dashboard.

## Overview

Master Haven is a suite of tools designed to help No Man's Sky explorers catalog, share, and analyze their discoveries. Whether you're documenting new star systems, tracking rare planets, or building a community archive, Master Haven provides the infrastructure to make it happen.

### Key Features

- **Live Data Extraction** - In-game mod extracts system/planet data automatically as you play
- **Auto-Submission** - Watcher monitors save files and submits discoveries to the Haven database
- **Web Dashboard** - Beautiful React UI for browsing discoveries and managing data
- **Glyph Support** - Full portal glyph encoding/decoding for easy coordinate sharing

## Project Structure

```
Master-Haven/
├── Haven-UI/                 # Web dashboard (React + FastAPI backend)
├── NMS-Haven-Extractor/      # Live game mod for data extraction
├── NMS-Save-Watcher/         # Automatic save file monitoring
├── NMS-Memory-Browser/       # Game memory inspection tool
├── src/                      # Core API and utilities
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

The main web interface for browsing and managing discoveries.

**Features:**
- Dashboard with system/planet statistics
- Discovery browser with search and filters
- Admin panel for data management
- Real-time updates via WebSocket
- Responsive design (works on mobile)

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
# Admin password for web UI login
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

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Server status |
| `/api/stats` | GET | Discovery statistics |
| `/api/systems` | GET | List all systems |
| `/api/systems/{id}` | GET | Get system details |
| `/api/discoveries` | POST | Submit new discovery |
| `/api/planets` | GET | List all planets |
| `/api/galaxies` | GET | List galaxies |

See the [API documentation](docs/API.md) for full details.

## Data Storage

All data is stored locally in the `Haven-UI` folder:

| Path | Contents |
|------|----------|
| `Haven-UI/data/haven_ui.db` | SQLite database |
| `Haven-UI/data/data.json` | Cached discovery data |
| `Haven-UI/photos/` | Discovery screenshots |
| `Haven-UI/logs/` | Application logs |

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
