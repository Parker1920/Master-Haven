"""
Standalone server to run the Haven Control Room web UI using the existing repo back-end.
This works when run from the repository root.

Usage:
    python server.py

It imports the FastAPI `app` from `src.control_room_api` and runs uvicorn.
"""
import os
import sys
from pathlib import Path

# Ensure project root and src in path so imports like 'common' and 'src' work
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
src_dir = REPO_ROOT / 'src'
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Ensure control_room_api picks up the right HAVEN_UI_DIR BEFORE importing it
os.environ['HAVEN_UI_DIR'] = str(REPO_ROOT / 'Haven-UI')
try:
    from fastapi.staticfiles import StaticFiles
    # Importing control_room_api can execute initialization logic. Wrap it so we
    # provide an actionable error message if an import-time exception occurs
    from src.control_room_api import app, init_rtai
except Exception as exc:
    print("ERROR: Failed to import critical server modules. This often means there\n      "
          "was a startup-time failure (missing dependency, corrupted DB, or bad paths).\n      "
          "Details follow:\n")
    import traceback
    traceback.print_exc()
    # Re-raise so the calling process sees the same failure, but we've provided
    # a clearer message in case this comes from a systemd/cron supervisor.
    raise
# Mount the photos folder for static serving
photos_dir = REPO_ROOT / 'Haven-UI' / 'photos'
if photos_dir.exists():
    app.mount('/haven-ui-photos', StaticFiles(directory=str(photos_dir)), name='haven-ui-photos')

# Note: Static mounts are already configured in control_room_api.py
# This prevents duplicate mount errors

if __name__ == '__main__':
    import uvicorn
    try:
        # Attempt to init RT-AI if available. Keep it optional.
        init_rtai(str(REPO_ROOT / 'Haven-UI'))
    except Exception:
        pass
    print("Starting Haven Control Room Web Server on 0.0.0.0:8005")
    uvicorn.run(app, host='0.0.0.0', port=8005, log_level='info')
