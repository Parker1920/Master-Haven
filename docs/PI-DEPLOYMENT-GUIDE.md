# Master-Haven Raspberry Pi 5 Production Deployment Guide

## 1. Remove Old Files from the Pi (to avoid conflicts)

**SSH into your Pi:**
```bash
ssh parker@10.0.0.33
```

**Delete any old Master-Haven files/folders:**
```bash
rm -rf /home/parker/Master-Haven
```
*Double-check the path before running this command! It will permanently delete the folder and all its contents.*

---
                                                            
## 2. Transfer ALL Files and Folders from Windows to Pi

### Option A: Use WinSCP (Recommended)
1. Download and install [WinSCP](https://winscp.net/).
2. Connect to your Pi (SFTP, host: 10.0.0.33, user: parker, password: your Pi password).
3. In the left pane, navigate to `C:\Master-Haven`.
4. In the right pane, navigate to `/home/parker/`.
5. Drag the entire `Master-Haven` folder from left to right.
6. Enable “Show hidden files” in WinSCP (Options > Preferences > Panels > Show hidden files).
7. Wait for the transfer to complete and check for errors.

### Option B: Use SCP (Command Line)
On your Windows PC, open PowerShell:
```powershell
scp -r "C:\Master-Haven" parker@10.0.0.33:/home/parker/
```
- To include hidden files, copy them separately if needed:
```powershell
scp "C:\Master-Haven\.*" parker@10.0.0.33:/home/parker/Master-Haven/

### Option B2: Use compressed tarball transfer (recommended for large updates)

If you're pushing multiple files and want a faster, single transfer (and to avoid copying large node_modules or virtual environments), create a compressed archive on your Windows machine then upload that single file to the Pi and extract it.

PowerShell (Windows):

```powershell
# Create a tarball of only the files you want to deploy (exclude node_modules, .venv, .git)
cd C:\Master-Haven
tar -czf Master-Haven-update.tar.gz --exclude='Haven-UI/node_modules' --exclude='.venv' --exclude='.git' *

# Copy to Pi (replace user/IP as needed)
scp -C Master-Haven-update.tar.gz parker@10.0.0.33:/home/parker/
```

Notes:
- `-C` compresses the scp stream (useful if you skip creating a tarball first). We recommend creating the tarball to avoid overhead on the server.
- On older Windows systems without tar, you can use 7zip or WinRAR to create a .tar.gz or .zip; copy the archive the same way with `scp`.

On the Pi:

```bash
ssh parker@10.0.0.33
cd /home/parker
# Extract into the repo (overwrites existing files; be careful!)
mkdir -p /home/parker/Master-Haven
tar -xzf Master-Haven-update.tar.gz -C /home/parker/Master-Haven

# Optionally inspect the patch
ls -la /home/parker/Master-Haven
```

This is often the fastest way to transfer and apply many file changes — it reduces the number of round-trips and gives you an easy rollback option (keep the tarball). After extraction, follow the rebuild/restart steps below.
```

---

## 3. Verify the Transfer on the Pi

SSH into your Pi and check:
```bash
ls -la /home/parker/Master-Haven
ls -la /home/parker/Master-Haven/Haven-UI
ls -la /home/parker/Master-Haven/roundtable_ai
```
You should see all files and folders, including `.env`, `.venv` (if you want to transfer it), and all subfolders.

---

## 4. Python and Virtual Environment Setup

**Recommended:** Recreate the virtual environment on the Pi for best compatibility.

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip -y
cd /home/parker/Master-Haven
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r Haven-UI/requirements.txt
pip install -r keeper-discord-bot-main/requirements.txt
pip install -r roundtable_ai/requirements.txt
```

---

## 5. Node.js and NPM (for Haven-UI React frontend)

```bash
sudo apt install nodejs npm -y
cd /home/parker/Master-Haven/Haven-UI
npm install
npm run build
```

---

## 6. Environment Files

- Ensure `.env` files are present in the correct folders (`Haven-UI`, `keeper-discord-bot-main`, etc.).
- If not, copy them manually using WinSCP or SCP.

---

## 7. ngrok Setup

```bash
cd ~
wget https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-arm.zip
unzip ngrok-stable-linux-arm.zip
sudo mv ngrok /usr/local/bin/
ngrok config add-authtoken <your-ngrok-authtoken>
```

---

## 8. Start the Servers

- For Haven-UI:
  ```bash
  cd /home/parker/Master-Haven/Haven-UI
  source ../.venv/bin/activate
  python3 server.py
  ```
- For the Discord bot:
  ```bash
  cd /home/parker/Master-Haven/keeper-discord-bot-main
  source ../.venv/bin/activate
  python3 src/main.py
  ```
- For ngrok:
  ```bash
  ngrok http 8000
  ```

---

## 9. Verify Everything

- Open the ngrok URL in your browser.
- Check the Discord bot is online.
- Test all endpoints and UI features.

---

## 10. Mobile / Phone Access (ngrok) — common issues & Android S21-specific steps

If others can view your ngrok URL but a single phone (e.g., Galaxy S21 Ultra on Android 15) cannot, follow this checklist. Often this is a device-specific TLS/DNS/VPN setting.

Host checks to run while your friend reproduces the problem:
- Open ngrok web UI: http://127.0.0.1:4040 — watch for the incoming request from your friend's IP.
- Check `Haven-UI/logs/run_server.out.log` for the incoming request and the response code.
- Run `scripts\ngrok_check.ps1` from PowerShell to list tunnels and run a local HTTPS test.

Phone-specific checklist (run on the problem phone):
1. Check Date & Time: Settings → System → Date & time — enable network time.
2. Disable VPNs and Private DNS (Settings → Network & Internet → Private DNS) — set to Automatic or Off.
3. Try Incognito or another browser (Firefox) to bypass Chrome profile/config issues.
4. Clear site data specifically for the ngrok domain: Chrome → lock icon → Site settings → Clear & reset.
5. Try switching network: Wi‑Fi → mobile data or vice versa to exclude network-specific blocking.
6. Open the padlock in Chrome and inspect the certificate; check issuer and validity dates.

Advanced mobile debug (requires more access):
- Connect the phone to desktop Chrome via USB, visit `chrome://inspect`, open the tab, and look at the Network tab while trying to access the ngrok URL.
- Use `chrome://net-export` on the phone to capture TLS handshake traces; share the exported file (large) if you need help interpreting it.
- Use Android `adb logcat` to look for Chrome/Chromium TLS errors, or `adb shell dumpsys connectivity` to inspect network state.

If none of these steps show the issue, ask them to share a screenshot of the Chrome error with the visible full URL and any certificate details — that helps pin down whether Chrome rejects the TLS handshake or something else.

## 11. Applying a small server fix to the Pi (quick)

If you're applying a code fix from this repo to a Pi already running your server, use these helper scripts in `scripts/` to create an update archive and upload it safely.

1) Create the update archive on your host (PowerShell):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_update_archive.ps1
```

2) Upload & apply (dry-run — it prints commands):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy_to_pi.ps1 -Host 10.0.0.33 -User parker
```

3) Upload & apply (interactive deploy — will upload and run the extraction on the Pi):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy_to_pi.ps1 -Host 10.0.0.33 -User parker -DoDeploy
```

The deploy script does not assume how your server is run (systemd, screen, etc.) — after the files are replaced, run the appropriate restart command for your setup (examples are printed by the script).

**If you encounter any issues, repeat the file transfer and setup steps, and ensure all dependencies and environment files are present.**
