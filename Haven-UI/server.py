"""
Standalone server to run the Haven Control Room web UI.
Haven-UI is now self-contained with backend code in the backend/ folder.

Usage:
    cd Haven-UI
    python server.py

It imports the FastAPI `app` from `backend.control_room_api` and runs uvicorn.
"""
import os
import sys
from pathlib import Path

# Haven-UI directory structure (self-contained)
HAVEN_UI_DIR = Path(__file__).resolve().parent
BACKEND_DIR = HAVEN_UI_DIR / 'backend'
REPO_ROOT = HAVEN_UI_DIR.parent  # Master-Haven root (for cross-project access)

# Add backend to path for imports
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Set environment variable for Haven UI directory
os.environ['HAVEN_UI_DIR'] = str(HAVEN_UI_DIR)

try:
    from fastapi.staticfiles import StaticFiles
    # Importing control_room_api can execute initialization logic. Wrap it so we
    # provide an actionable error message if an import-time exception occurs
    from control_room_api import app, init_rtai
except Exception as exc:
    print("ERROR: Failed to import critical server modules. This often means there\n      "
          "was a startup-time failure (missing dependency, corrupted DB, or bad paths).\n      "
          "Details follow:\n")
    import traceback
    traceback.print_exc()
    # Re-raise so the calling process sees the same failure, but we've provided
    # a clearer message in case this comes from a systemd/cron supervisor.
    raise

# Note: Static mounts (photos, dist, war-media) are configured in control_room_api.py.
# Do NOT mount them again here — duplicate mounts cause startup errors.

if __name__ == '__main__':
    import uvicorn
    try:
        # Attempt to init RT-AI if available. Keep it optional.
        init_rtai(str(HAVEN_UI_DIR))
    except Exception:
        pass
    print("Starting Haven Control Room Web Server on 0.0.0.0:8005")
    uvicorn.run(app, host='0.0.0.0', port=8005, log_level='info')
