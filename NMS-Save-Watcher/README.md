# NMS Save Watcher

Companion application for **Voyagers Haven** - automatically uploads your No Man's Sky discoveries as you play.

## Features

- **Automatic Detection**: Watches your NMS save files for changes in real-time
- **Discovery Extraction**: Extracts system, planet, moon, and base data when you scan
- **API Integration**: Submits discoveries to Voyagers Haven for approval
- **Duplicate Detection**: Checks server before submitting to avoid duplicates
- **Offline Queue**: Saves submissions locally when offline, retries when available
- **Web Dashboard**: Monitor status, view history, manage settings (6 pages)
- **Windows Notifications**: Toast notifications for successful submissions
- **Edit Detection**: Detects changes to previously submitted systems

## Quick Start

1. Double-click `start.bat` to run
2. Open the dashboard at http://localhost:8006
3. Configure your API key in Settings
4. Play No Man's Sky - discoveries are uploaded automatically!

## Web Dashboard

The dashboard runs at `http://localhost:8006` and includes:

| Page | Description |
|------|-------------|
| **Dashboard** | Status overview, recent activity, quick stats |
| **History** | All submission history with status badges |
| **Stats** | Save file statistics - systems, planets, moons, bases by galaxy |
| **Queue** | Offline queue management, retry/remove items |
| **Keys** | Unknown obfuscated keys log for debugging |
| **Settings** | API configuration, save path, notifications |

## Configuration

Edit `config.json` or use the web dashboard Settings page:

```json
{
  "api": {
    "base_url": "http://localhost:8005",
    "key": "vh_live_your_api_key_here"
  },
  "watcher": {
    "save_path": "auto",
    "save_slot": 1,
    "debounce_seconds": 2,
    "enabled": true
  },
  "notifications": {
    "enabled": true,
    "on_success": true,
    "on_duplicate": false,
    "on_error": true,
    "on_offline_queue": true
  },
  "dashboard": {
    "port": 8006,
    "host": "127.0.0.1"
  },
  "debug": {
    "enabled": false,
    "log_file": "watcher.log",
    "log_level": "INFO"
  }
}
```

### Settings Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `api.base_url` | `http://localhost:8005` | Voyagers Haven API server URL |
| `api.key` | `""` | Your API key (starts with `vh_live_`) |
| `watcher.save_path` | `"auto"` | Auto-detect or explicit path to save folder |
| `watcher.save_slot` | `1` | Which save slot to monitor (1-10) |
| `watcher.debounce_seconds` | `2` | Wait time after save before processing |
| `watcher.enabled` | `true` | Enable/disable file watching |
| `notifications.enabled` | `true` | Enable Windows toast notifications |
| `notifications.on_success` | `true` | Notify on successful submission |
| `notifications.on_duplicate` | `false` | Notify when duplicate detected |
| `notifications.on_error` | `true` | Notify on errors |
| `notifications.on_offline_queue` | `true` | Notify when queued offline |
| `dashboard.port` | `8006` | Dashboard web server port |
| `dashboard.host` | `127.0.0.1` | Dashboard bind address |
| `debug.enabled` | `false` | Enable file logging |
| `debug.log_file` | `watcher.log` | Log file name |
| `debug.log_level` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |

### Save Slots

NMS uses numbered save slots:

| Slot | File | Description |
|------|------|-------------|
| 1 | `save.hg` | Auto-save slot 1 |
| 2 | `save2.hg` | Manual save slot 1 |
| 3 | `save3.hg` | Auto-save slot 2 |
| 4 | `save4.hg` | Manual save slot 2 |
| 5-10 | `save5.hg` - `save10.hg` | Additional slots |

## Getting an API Key

1. Log into Voyagers Haven as admin
2. Go to Admin > API Keys
3. Create a new key with a descriptive name
4. Copy the key (shown only once!) to your config
5. Keys start with `vh_live_` prefix

## Building from Source

### Run from Source

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m src
```

### Build Standalone Executable

```bash
# Using build script (recommended)
build.bat

# Or manually
pip install pyinstaller
pyinstaller nms_watcher.spec
```

The executable will be in `dist/NMS-Save-Watcher.exe`.

## How It Works

1. **Watch**: Monitors `%APPDATA%\HelloGames\NMS\st_<steamid>\save.hg`
2. **Detect**: Catches file changes with debouncing (waits for write completion)
3. **Decompress**: Decompresses LZ4-compressed save file
4. **Deobfuscate**: Converts obfuscated JSON keys using MBINCompiler mappings
5. **Extract**: Pulls discovery data (systems, planets, moons, bases)
6. **Convert**: Transforms coordinates to portal glyph codes
7. **Check**: Verifies against server to avoid duplicates
8. **Submit**: Sends to Voyagers Haven API (pending approval)
9. **Track**: Records locally to prevent re-uploading

### Data Extracted

For each **System**:
- Name, star type (Yellow/Red/Green/Blue)
- Economy type and level
- Conflict level
- Original discoverer
- Discovery timestamp
- Portal glyph code
- Galaxy name

For each **Planet/Moon**:
- Name, biome, climate
- Sentinel level
- Fauna/flora levels
- Resources
- Base locations (if any)

## Troubleshooting

### Save file not found
- Make sure NMS has been played and saved at least once
- Check the save slot matches your active save (default is slot 1)
- Try setting `save_path` manually in config

### API connection failed
- Verify the API URL is correct
- Check your API key is valid and active
- Ensure Voyagers Haven server is running
- Check the Keys page for any authentication errors

### No discoveries detected
- Use the stellar scanner on systems to register discoveries in NMS
- Make sure you've saved the game after scanning
- Check the Stats page to see what's in your save file
- Enable debug logging to see detailed processing info

### Offline queue not processing
- Check your internet connection
- Verify API server is reachable
- Use the Queue page to manually retry items
- Check for errors in the submission history

### Unknown keys warnings
- This is normal when NMS updates add new data
- Report unknown keys via the Keys page export feature
- The app will continue working with known keys

## File Structure

```
NMS-Save-Watcher/
├── src/                    # Python source code
│   ├── main.py            # Entry point
│   ├── watcher.py         # File watcher
│   ├── parser.py          # Save file parser
│   ├── extractor.py       # Discovery extraction
│   ├── api_client.py      # API integration
│   ├── database.py        # Local database
│   ├── dashboard.py       # Web dashboard
│   ├── notifications.py   # Toast notifications
│   └── config.py          # Configuration
├── templates/             # Dashboard HTML
├── data/                  # JSON mappings
│   ├── mapping.json       # Key deobfuscation
│   ├── galaxies.json      # Galaxy names
│   ├── resources.json     # Resource names
│   └── levels.json        # Level mappings
├── assets/                # App icon
├── config.json            # Your configuration
├── start.bat              # Run script
├── build.bat              # Build script
└── requirements.txt       # Dependencies
```

## Requirements

- Python 3.10+ (for running from source)
- Windows 10/11 (for toast notifications)
- No Man's Sky (Steam version)
- Voyagers Haven server (for API)

## Dependencies

- `watchdog` - File system monitoring
- `lz4` - Save file decompression
- `requests` - HTTP client
- `fastapi` - Web dashboard
- `uvicorn` - ASGI server
- `jinja2` - HTML templates
- `win10toast` - Windows notifications

## License

MIT License - See LICENSE file

## Credits

- Key deobfuscation mappings from [MBINCompiler](https://github.com/monkeyman192/MBINCompiler)
- Galaxy names from [No Man's Sky Wiki](https://nomanssky.fandom.com/wiki/Galaxy)
- Built for the Voyagers Haven project
