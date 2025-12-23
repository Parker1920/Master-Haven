# Haven-UI (Web Control Room)

This folder contains a deployable web UI for the Haven Control Room. It is intended as a browser frontend and lightweight server wrapper for the existing repo's FastAPI backend at `src/control_room_api.py`.

## What this contains
- `server.py`: a minimal runner to start the existing FastAPI app
- `static/`: UI files for the browser (HTML/JS/CSS)
- `requirements.txt`: python dependencies for the web server

## Quickstart (development)
1. Create & activate a Python virtualenv:

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows
# or for Linux/macOS
# source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the server (Windows). Two options are available:

- Use the convenience batch script:

```powershell
cd Haven-UI
run_server.bat
```

- Or run with environment variables (PowerShell) — ensure `ExecutionPolicy` allows activation or use `cmd.exe`:

```powershell
cd path\to\Master-Haven
$env:PYTHONPATH = "$PWD\src"
$env:HAVEN_UI_DIR = "$PWD\Haven-UI"
python -m uvicorn src.control_room_api:app --host 127.0.0.1 --port 8005 --reload
```

4. Open a browser to `http://localhost:8000/haven-ui/`.

Note: This server expects to be run from the repo root so that it can import shared modules (e.g., `src.control_room_api`). If you want a fully standalone package, copy `src/common` and other required modules, or adapt PYTHONPATH accordingly.

React/Vite Development & Production Build
---------------------------------------
This project includes a React + Vite UI. To run the UI in development mode with hot reload:

```powershell
cd Haven-UI
npm install
npm run dev
```

By default Vite serves at http://localhost:5173 — use this during development. To run the production build (served via the FastAPI app):

```powershell
cd Haven-UI
npm install
npm run build
# This writes the build output into Haven-UI/dist. Then start the API server
cd ..
# On Windows, use the convenience batch script (it calls the preview PS script with the same params)
Haven-UI\run_server.bat -Build -Port 8000
## Or run the preview script directly (PowerShell):
powershell -ExecutionPolicy Bypass -File .\Haven-UI\scripts\preview.ps1 -Build -Port 8000
```

While the SPA is in development (`npm run dev`) it bypasses the FastAPI server and connects to the API endpoints (CORS enabled in the API if required). When you `npm run build` the built files are served by the FastAPI server from `Haven-UI/dist`.

## Next steps
- Replace the static HTML with a React/Vue SPA for richer UI and full parity with the desktop app.
	- The included vanilla JS SPA (`/haven-ui/spa.js`) is a lightweight SPA shell implementing systems browsing, wizard, tests, logs, and RT-AI monitoring. It uses WebSocket endpoints `/ws/logs` and `/ws/rtai` for real-time streaming and fetch-based API calls for CRUD operations.
- Improve authentication and security for public or networked deployments.

## Admin & Authentication (Local)

This server supports a simple password-powered admin session for protecting admin-only actions (backup, DB upload, system edits, etc.).

1. Configure the admin password in your environment, either by exporting env var:

```powershell
$env:HAVEN_ADMIN_PASSWORD = 'your-secret-password'
```

Or by creating a `.env` file or editing the `.env.sample` provided in the `Haven-UI` folder and sourcing it.

2. Start the server and open the UI. Use the "Unlock" button in the top navigation to log in (the Settings item is now hidden when not logged in).
	- Enter the admin password from the `Haven-UI/.env` file or the `HAVEN_ADMIN_PASSWORD` env var.
	- On success, the top navigation will reveal the admin tabs (RT-AI, Settings, Tests) and a Logout button.

3. For bot integration use `HAVEN_API_KEY` to configure the bot and set the header `X-API-Key` when the bot POSTs to `/api/discoveries`.


## Data isolation & Storage
All runtime data for this web UI is stored inside the `Haven-UI` folder to avoid interacting with the original `Haven_mdev` repository data:
	- JSON: `Haven-UI/data/data.json`
	- Database: `Haven-UI/data/haven_ui.db`
	- Photos: `Haven-UI/photos/`
	- Logs: `Haven-UI/logs/`
	- Generated map: `Haven-UI/dist/VH-Map.html`

Set `HAVEN_UI_DIR` environment variable if you wish to change the default storage location.

## Production & Raspberry Pi Deployment Checklist
1. Build the React UI on a developer machine (recommended) and copy the `Haven-UI/dist` folder to the Pi because `npm` and Node builds can be heavy on Pi:
```bash
# On dev: cd Haven-UI; npm ci; npm run build
# Copy Haven-UI/dist and Haven-UI/static to Pi (e.g., rsync, scp)
```
2. On the Pi, create venv and install requirements:
```bash
cd /home/pi/Haven_mdev
python -m venv .venv
source .venv/bin/activate
pip install -r Haven-UI/requirements.txt
```
3. Configure your environment or systemd service to start the server with `HAVEN_UI_DIR`:
	- Use the provided `raspberry/haven-control-room.service` as a sample.
	- Reload systemctl, enable and start the service: `sudo systemctl enable --now haven-control-room.service`.

## Smoke Test & Sanity Check
Run the included `Haven-UI/scripts/smoke_test.py` to verify the basic endpoints and UI are reachable.
Usage:
```bash
python Haven-UI/scripts/smoke_test.py --base http://127.0.0.1:8000
```
The test checks `/api/status`, `/api/stats`, `/api/systems`, and the SPA routes.

## PWA & Offline
- A Vite PWA plugin (`vite-plugin-pwa`) integrated into `vite.config.mjs` now handles generating `dist/manifest.webmanifest` and `dist/sw.js` during `npm run build`.
- The service worker supports caching the app shell and included assets; test PWA behavior under `https` or `http://localhost` with `vite preview`.

