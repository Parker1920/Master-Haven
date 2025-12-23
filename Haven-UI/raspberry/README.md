Raspberry Pi 5 Deployment Guide for Haven Control Room
======================================================

This short guide shows how to deploy the Haven Control Room Web UI and Python backend to a Raspberry Pi 5.

Prerequisites
- Raspberry Pi 5 with Raspberry Pi OS (64-bit) or Ubuntu 22.04/24.04.
- Python 3.10+ installed with `pip` and `venv`.
- Node.js (optional) only if building on the Pi; otherwise, prebuild on a dev machine and copy `dist/`.

Quick steps
1. Create a Python virtual environment in the repo root:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r Haven-UI\requirements.txt
```
2. If you're building the web UI on the Pi (optional):
```powershell
cd Haven-UI
npm ci
npm run build
```
Alternatively, build on your dev machine and copy `Haven-UI/dist` and `Haven-UI/static` to the Pi's `Haven-UI` folder.

3. Create a systemd service file (example shown below) and reload systemd:
```bash
sudo cp haven-control-room.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now haven-control-room.service
```

Troubleshooting
- If WebSocket connections fail, check firewall and proxy settings. Use `sudo netstat -tulpen` and verify `uvicorn` is bound to the expected port.
- If updates to the UI are not served, ensure `HAVEN_UI_DIR` is properly set to the repo's `Haven-UI/` folder and restart the service.

Notes
 - The server mounts `Haven-UI/dist` as `'/haven-ui'`. When `dist` is missing, `Haven-UI/static` is mounted under `'/haven-ui'` for preview parity; `'/haven-ui-static'` is still available as a legacy alias. Ensure correct file locations when copying over assets.
