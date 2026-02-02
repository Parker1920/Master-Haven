# Haven Production Setup: Raspberry Pi 5 + havenmap.online

Complete guide to self-hosting Haven on a Raspberry Pi 5 with your own domain.

**Domain:** havenmap.online
**Estimated Setup Time:** 1-2 hours
**Monthly Cost:** ~$1.17 (electricity only)

---

## Table of Contents

1. [Prerequisites Checklist](#1-prerequisites-checklist)
2. [Phase 1: Cloudflare DNS Setup](#2-phase-1-cloudflare-dns-setup)
3. [Phase 2: Raspberry Pi Preparation](#3-phase-2-raspberry-pi-preparation)
4. [Phase 3: Install and Configure Caddy](#4-phase-3-install-and-configure-caddy)
5. [Phase 4: Xfinity Router Port Forwarding](#5-phase-4-xfinity-router-port-forwarding)
6. [Phase 5: Dynamic DNS Updater](#6-phase-5-dynamic-dns-updater)
7. [Phase 6: Haven Auto-Start Service](#7-phase-6-haven-auto-start-service)
8. [Phase 7: Testing and Verification](#8-phase-7-testing-and-verification)
9. [Phase 8: Update Haven Extractor](#9-phase-8-update-haven-extractor)
10. [Maintenance and Troubleshooting](#10-maintenance-and-troubleshooting)

---

## 1. Prerequisites Checklist

Before starting, ensure you have:

- [ ] Domain purchased: `havenmap.online` (Namecheap) ✓
- [ ] Raspberry Pi 5 with Raspberry Pi OS installed
- [ ] Haven already running on the Pi (port 8005)
- [ ] SSH access to your Raspberry Pi
- [ ] Access to your Xfinity router admin panel
- [ ] Your Pi's internal IP address (e.g., 192.168.1.105)
- [ ] Your public IP address (get from https://ifconfig.me)

### Find Your Pi's Internal IP

SSH into your Pi or run directly:
```bash
hostname -I
```
Write this down: `____________` (e.g., 192.168.1.105)

### Find Your Public IP

Visit https://ifconfig.me or run:
```bash
curl ifconfig.me
```
Write this down: `____________` (e.g., 98.45.123.67)

---

## 2. Phase 1: Cloudflare DNS Setup

Cloudflare provides free DNS hosting with DDoS protection and an easy API for dynamic IP updates.

### Step 1.1: Create Cloudflare Account

1. Go to https://cloudflare.com
2. Click **Sign Up** (free)
3. Verify your email

### Step 1.2: Add Your Domain to Cloudflare

1. Log into Cloudflare dashboard
2. Click **Add a Site**
3. Enter: `havenmap.online`
4. Select the **Free** plan → Click **Continue**
5. Cloudflare will scan for existing DNS records (will likely be empty)
6. Click **Continue**

### Step 1.3: Get Your Cloudflare Nameservers

Cloudflare will show you two nameservers like:
```
aria.ns.cloudflare.com
bob.ns.cloudflare.com
```
**Write these down** - you need them for the next step.

### Step 1.4: Update Namecheap Nameservers

1. Log into **Namecheap** → https://www.namecheap.com
2. Go to **Domain List**
3. Click **Manage** next to `havenmap.online`
4. Find the **Nameservers** section
5. Change from "Namecheap BasicDNS" to **Custom DNS**
6. Enter the two Cloudflare nameservers:
   - `aria.ns.cloudflare.com`
   - `bob.ns.cloudflare.com`
7. Click the **green checkmark** to save

### Step 1.5: Verify in Cloudflare

1. Go back to Cloudflare
2. Click **Done, check nameservers**
3. Status will show "Pending" - this can take 5-30 minutes (sometimes up to 24 hours)
4. You'll get an email when it's active

### Step 1.6: Create DNS A Record

Once nameservers are active:

1. In Cloudflare, go to **DNS** → **Records**
2. Click **Add record**
3. Fill in:

| Field | Value |
|-------|-------|
| Type | `A` |
| Name | `@` |
| IPv4 address | Your public IP (e.g., 98.45.123.67) |
| Proxy status | **OFF** (click the orange cloud to make it grey) |
| TTL | Auto |

4. Click **Save**

5. Add another record for `www`:

| Field | Value |
|-------|-------|
| Type | `CNAME` |
| Name | `www` |
| Target | `havenmap.online` |
| Proxy status | **OFF** (grey cloud) |
| TTL | Auto |

6. Click **Save**

### Step 1.7: Get Cloudflare API Token (for Dynamic DNS)

1. Click your profile icon (top right) → **My Profile**
2. Go to **API Tokens** tab
3. Click **Create Token**
4. Click **Use template** next to "Edit zone DNS"
5. Under **Zone Resources**, select:
   - Include → Specific zone → `havenmap.online`
6. Click **Continue to summary**
7. Click **Create Token**
8. **COPY AND SAVE THIS TOKEN** - you won't see it again!

Write it down: `____________________________________________`

Also get your **Zone ID**:
1. Go to **Websites** → click `havenmap.online`
2. Scroll down on the right side → find **Zone ID**
3. Copy it

Write it down: `____________________________________________`

---

## 3. Phase 2: Raspberry Pi Preparation

### Step 2.1: SSH Into Your Pi

From your Windows machine:
```powershell
ssh pi@192.168.1.105
```
(Replace with your Pi's actual IP and username)

### Step 2.2: Update the System

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2.3: Set a Static Internal IP (Recommended)

This ensures your Pi always gets the same IP on your network.

```bash
sudo nano /etc/dhcpcd.conf
```

Add at the bottom (adjust for your network):
```
interface eth0
static ip_address=192.168.1.105/24
static routers=192.168.1.1
static domain_name_servers=1.1.1.1 8.8.8.8
```

For WiFi, use `interface wlan0` instead.

Save: `Ctrl+X` → `Y` → `Enter`

Reboot:
```bash
sudo reboot
```

Wait a minute, then SSH back in.

### Step 2.4: Verify Haven Is Running

```bash
# Check if Haven API is running on port 8005
sudo ss -tlnp | grep 8005
```

You should see something like:
```
LISTEN  0  128  0.0.0.0:8005  0.0.0.0:*  users:(("python",pid=1234,fd=5))
```

If Haven isn't running, start it:
```bash
cd ~/Master-Haven  # or wherever your repo is
python src/control_room_api.py &
```

---

## 4. Phase 3: Install and Configure Caddy

Caddy is a modern web server that automatically handles HTTPS certificates.

### Step 3.1: Install Caddy

```bash
# Install dependencies
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl

# Add Caddy GPG key
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg

# Add Caddy repository
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list

# Install Caddy
sudo apt update
sudo apt install caddy -y
```

### Step 3.2: Configure Caddy

```bash
sudo nano /etc/caddy/Caddyfile
```

**Delete everything** in the file and replace with:

```
havenmap.online {
    reverse_proxy localhost:8005
}

www.havenmap.online {
    redir https://havenmap.online{uri} permanent
}
```

Save: `Ctrl+X` → `Y` → `Enter`

### Step 3.3: Start Caddy

```bash
# Restart Caddy to apply config
sudo systemctl restart caddy

# Enable Caddy to start on boot
sudo systemctl enable caddy

# Check status
sudo systemctl status caddy
```

You should see "active (running)" in green.

### Step 3.4: Configure Firewall (UFW)

```bash
# Install UFW if not present
sudo apt install ufw -y

# Allow SSH (important - don't lock yourself out!)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

---

## 5. Phase 4: Xfinity Router Port Forwarding

### Step 4.1: Access Router Admin

**Option A: Xfinity App (Recommended)**
1. Open Xfinity app on your phone
2. Go to **Connect** → **See Network**
3. Tap your network name
4. **More** → **Advanced Settings** → **Port Forwarding**

**Option B: Web Browser**
1. Go to http://10.0.0.1 (or http://192.168.1.1)
2. Login:
   - Username: `admin`
   - Password: `password` (or check router sticker)

### Step 4.2: Create Port Forward for HTTPS (Port 443)

| Setting | Value |
|---------|-------|
| Device | Select your Raspberry Pi (or enter IP manually) |
| Internal IP | 192.168.1.105 (your Pi's IP) |
| External Port | 443 |
| Internal Port | 443 |
| Protocol | TCP |
| Enabled | Yes |

Click **Save** or **Apply**

### Step 4.3: Create Port Forward for HTTP (Port 80)

| Setting | Value |
|---------|-------|
| Device | Raspberry Pi |
| Internal IP | 192.168.1.105 |
| External Port | 80 |
| Internal Port | 80 |
| Protocol | TCP |
| Enabled | Yes |

Click **Save** or **Apply**

### Step 4.4: Verify Port Forwards

Your port forwarding list should show:

| External Port | Internal IP | Internal Port | Protocol | Status |
|---------------|-------------|---------------|----------|--------|
| 80 | 192.168.1.105 | 80 | TCP | Enabled |
| 443 | 192.168.1.105 | 443 | TCP | Enabled |

---

## 6. Phase 5: Dynamic DNS Updater

Since your public IP can change, we need a script to update Cloudflare automatically.

### Step 5.1: Create the Update Script

```bash
sudo nano /usr/local/bin/cloudflare-ddns.sh
```

Paste this script (replace the placeholder values):

```bash
#!/bin/bash

# Cloudflare Dynamic DNS Updater for havenmap.online
# Runs via cron to keep DNS updated when IP changes

# ============ CONFIGURATION ============
# Replace these with your actual values from Cloudflare

API_TOKEN="YOUR_CLOUDFLARE_API_TOKEN_HERE"
ZONE_ID="YOUR_ZONE_ID_HERE"
RECORD_NAME="havenmap.online"

# ============ DO NOT EDIT BELOW ============

LOG_FILE="/var/log/cloudflare-ddns.log"

# Get current public IP
CURRENT_IP=$(curl -s https://api.ipify.org)

if [ -z "$CURRENT_IP" ]; then
    echo "$(date): ERROR - Could not get current IP" >> $LOG_FILE
    exit 1
fi

# Get the DNS record ID
RECORD_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=A&name=$RECORD_NAME" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$RECORD_ID" ]; then
    echo "$(date): ERROR - Could not get DNS record ID" >> $LOG_FILE
    exit 1
fi

# Get the IP currently set in DNS
DNS_IP=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" | grep -o '"content":"[^"]*"' | cut -d'"' -f4)

# Compare and update if different
if [ "$CURRENT_IP" != "$DNS_IP" ]; then
    echo "$(date): IP changed from $DNS_IP to $CURRENT_IP - Updating..." >> $LOG_FILE

    UPDATE_RESULT=$(curl -s -X PUT "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json" \
        --data "{\"type\":\"A\",\"name\":\"$RECORD_NAME\",\"content\":\"$CURRENT_IP\",\"ttl\":1,\"proxied\":false}")

    if echo "$UPDATE_RESULT" | grep -q '"success":true'; then
        echo "$(date): SUCCESS - DNS updated to $CURRENT_IP" >> $LOG_FILE
    else
        echo "$(date): ERROR - Failed to update DNS: $UPDATE_RESULT" >> $LOG_FILE
    fi
else
    # Uncomment the line below if you want to log when IP hasn't changed
    # echo "$(date): No change - IP is still $CURRENT_IP" >> $LOG_FILE
    :
fi
```

Save: `Ctrl+X` → `Y` → `Enter`

### Step 5.2: Add Your Cloudflare Credentials

Edit the script and replace:
- `YOUR_CLOUDFLARE_API_TOKEN_HERE` → Your API token from Step 1.7
- `YOUR_ZONE_ID_HERE` → Your Zone ID from Step 1.7

```bash
sudo nano /usr/local/bin/cloudflare-ddns.sh
```

### Step 5.3: Make Script Executable

```bash
sudo chmod +x /usr/local/bin/cloudflare-ddns.sh
```

### Step 5.4: Create Log File

```bash
sudo touch /var/log/cloudflare-ddns.log
sudo chmod 666 /var/log/cloudflare-ddns.log
```

### Step 5.5: Test the Script

```bash
sudo /usr/local/bin/cloudflare-ddns.sh
cat /var/log/cloudflare-ddns.log
```

You should see a success message or "No change" if IP matches.

### Step 5.6: Set Up Cron Job (Runs Every 5 Minutes)

```bash
sudo crontab -e
```

If prompted, choose `nano` as editor (option 1).

Add this line at the bottom:
```
*/5 * * * * /usr/local/bin/cloudflare-ddns.sh
```

Save: `Ctrl+X` → `Y` → `Enter`

---

## 7. Phase 6: Haven Auto-Start Service

Create a systemd service so Haven starts automatically on boot.

### Step 6.1: Find Your Haven Installation Path

```bash
# Common locations - find yours
ls ~/Master-Haven/src/control_room_api.py
# or
ls /home/pi/Master-Haven/src/control_room_api.py
```

Note the full path: `____________________________________________`

### Step 6.2: Create Systemd Service

```bash
sudo nano /etc/systemd/system/haven.service
```

Paste this (adjust paths and username as needed):

```ini
[Unit]
Description=Haven Map API Server
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/Master-Haven
ExecStart=/usr/bin/python3 /home/pi/Master-Haven/src/control_room_api.py
Restart=always
RestartSec=10

# Environment variables (optional)
Environment=PYTHONUNBUFFERED=1

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Adjust these values:**
- `User=pi` → Your Pi username
- `Group=pi` → Your Pi username
- `WorkingDirectory=` → Path to Master-Haven folder
- `ExecStart=` → Full path to control_room_api.py

Save: `Ctrl+X` → `Y` → `Enter`

### Step 6.3: Enable and Start the Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable Haven to start on boot
sudo systemctl enable haven

# Start Haven now
sudo systemctl start haven

# Check status
sudo systemctl status haven
```

You should see "active (running)" in green.

### Step 6.4: Useful Service Commands

```bash
# Check status
sudo systemctl status haven

# View logs
sudo journalctl -u haven -f

# Restart Haven
sudo systemctl restart haven

# Stop Haven
sudo systemctl stop haven
```

---

## 8. Phase 7: Testing and Verification

### Step 7.1: Check All Services Are Running

```bash
# Check Caddy
sudo systemctl status caddy

# Check Haven
sudo systemctl status haven

# Check ports are listening
sudo ss -tlnp | grep -E ':(80|443|8005)'
```

Expected output:
```
LISTEN  0  ...  *:80    *:*   users:(("caddy",...))
LISTEN  0  ...  *:443   *:*   users:(("caddy",...))
LISTEN  0  ...  *:8005  *:*   users:(("python",...))
```

### Step 7.2: Test Local Access

From your Pi:
```bash
curl http://localhost:8005/api/health
```

Should return a response (or check any API endpoint you know exists).

### Step 7.3: Test Public Access

**From your phone (on cellular, NOT WiFi):**

1. Open browser
2. Go to: `https://havenmap.online`
3. You should see the Haven UI with a padlock (HTTPS) in the browser

**From any computer outside your network:**

1. Go to: https://havenmap.online
2. Verify the site loads
3. Check the padlock - click it to verify the SSL certificate

### Step 7.4: Test SSL Certificate

```bash
# From your Pi or any Linux/Mac machine
curl -I https://havenmap.online
```

Should show:
```
HTTP/2 200
...
```

Or use https://www.ssllabs.com/ssltest/ and enter `havenmap.online`

---

## 9. Phase 8: Update Haven Extractor

Now update the game mod to use your new domain.

### Step 8.1: Update the Example Config

On your **Windows machine** (where you develop):

Edit `NMS-Haven-Extractor/haven_config.json.example`:

```json
{
    "api_url": "https://havenmap.online",
    "api_key": "vh_live_HvnXtr8k9Lm2NpQ4rStUvWxYz1A3bC5dE7fG",
    "discord_username": "YourDiscordName",
    "discord_tag": "personal",
    "reality": "Normal"
}
```

### Step 8.2: Update Build Script

Edit `NMS-Haven-Extractor/build_distributable.py`:

Find any references to `ngrok` URLs and replace with `havenmap.online`.

### Step 8.3: Update Your Local Config

If you have a `haven_config.json` in your NMS mod folder, update it:

```json
{
    "api_url": "https://havenmap.online",
    ...
}
```

### Step 8.4: Update CORS Settings (Optional but Recommended)

On your Pi, edit the control room API to restrict CORS:

Find the CORS middleware section in `src/control_room_api.py` and update:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://havenmap.online",
        "https://www.havenmap.online",
        "http://localhost:5173",  # Keep for local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then restart Haven:
```bash
sudo systemctl restart haven
```

---

## 10. Maintenance and Troubleshooting

### Regular Maintenance

**Check logs periodically:**
```bash
# Haven API logs
sudo journalctl -u haven --since "1 hour ago"

# Caddy logs
sudo journalctl -u caddy --since "1 hour ago"

# Dynamic DNS logs
cat /var/log/cloudflare-ddns.log
```

**Check disk space:**
```bash
df -h
```

**Update system monthly:**
```bash
sudo apt update && sudo apt upgrade -y
```

### Common Issues and Solutions

#### Site not loading (timeout)

1. **Check if services are running:**
   ```bash
   sudo systemctl status caddy
   sudo systemctl status haven
   ```

2. **Check port forwarding on router:**
   - Verify ports 80 and 443 are forwarded to Pi's IP
   - Make sure Pi's internal IP hasn't changed

3. **Check firewall:**
   ```bash
   sudo ufw status
   ```

4. **Check if your IP changed:**
   ```bash
   curl ifconfig.me
   # Compare with what's in Cloudflare DNS
   ```

#### SSL certificate errors

Caddy auto-renews certificates. If there's an issue:

```bash
# Check Caddy logs
sudo journalctl -u caddy -n 50

# Restart Caddy to retry certificate
sudo systemctl restart caddy
```

#### Haven API not responding

```bash
# Check Haven status
sudo systemctl status haven

# View recent logs
sudo journalctl -u haven -n 100

# Restart Haven
sudo systemctl restart haven
```

#### Dynamic DNS not updating

```bash
# Check the log
cat /var/log/cloudflare-ddns.log

# Run manually to see errors
sudo /usr/local/bin/cloudflare-ddns.sh

# Check cron is running
sudo systemctl status cron
```

#### After power outage

Everything should start automatically. Verify:
```bash
sudo systemctl status haven
sudo systemctl status caddy
```

### Backup Your Database

Create a simple backup script:

```bash
sudo nano /usr/local/bin/backup-haven.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/pi/haven-backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
cp /home/pi/Master-Haven/Haven-UI/data/haven_ui.db "$BACKUP_DIR/haven_ui_$DATE.db"
# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.db" -mtime +7 -delete
echo "$(date): Backup created: haven_ui_$DATE.db" >> /var/log/haven-backup.log
```

```bash
sudo chmod +x /usr/local/bin/backup-haven.sh
```

Add to cron for daily backups:
```bash
sudo crontab -e
```
Add:
```
0 3 * * * /usr/local/bin/backup-haven.sh
```

---

## Quick Reference Card

### Important URLs

| URL | Purpose |
|-----|---------|
| https://havenmap.online | Your public Haven site |
| https://dash.cloudflare.com | Cloudflare DNS management |
| http://10.0.0.1 | Xfinity router admin |

### Important Commands

```bash
# SSH into Pi
ssh pi@192.168.1.105

# Check all services
sudo systemctl status haven caddy

# Restart everything
sudo systemctl restart haven caddy

# View live logs
sudo journalctl -u haven -f

# Check public IP
curl ifconfig.me

# Manual DNS update
sudo /usr/local/bin/cloudflare-ddns.sh
```

### Important Files on Pi

| File | Purpose |
|------|---------|
| `/etc/caddy/Caddyfile` | Caddy reverse proxy config |
| `/etc/systemd/system/haven.service` | Haven auto-start service |
| `/usr/local/bin/cloudflare-ddns.sh` | Dynamic DNS update script |
| `/var/log/cloudflare-ddns.log` | DNS update log |
| `~/Master-Haven/Haven-UI/data/haven_ui.db` | Haven database |

### Port Reference

| Port | Service | Exposed to Internet? |
|------|---------|---------------------|
| 22 | SSH | No (local only) |
| 80 | Caddy (HTTP→HTTPS redirect) | Yes |
| 443 | Caddy (HTTPS) | Yes |
| 8005 | Haven API | No (internal only) |

---

## Checklist: Final Verification

- [ ] Cloudflare shows green checkmark for nameservers
- [ ] DNS A record points to your public IP
- [ ] Port 80 forwarded to Pi
- [ ] Port 443 forwarded to Pi
- [ ] Caddy is running (`sudo systemctl status caddy`)
- [ ] Haven is running (`sudo systemctl status haven`)
- [ ] https://havenmap.online loads from phone (on cellular)
- [ ] SSL padlock shows valid certificate
- [ ] Dynamic DNS cron job is set up
- [ ] Haven auto-starts after reboot (`sudo reboot` then check)
- [ ] Haven Extractor config updated with new domain
- [ ] ngrok subscription cancelled

---

## Cost Summary

| Item | Cost |
|------|------|
| Domain (havenmap.online) | $10 / 2 years |
| Cloudflare DNS | Free |
| Let's Encrypt SSL | Free |
| Caddy | Free |
| Electricity (~8W) | ~$0.75/month |
| **Total Monthly** | **~$1.17** |

**Previous ngrok cost:** $20/month
**Annual savings:** ~$226

---

*Document created: January 2026*
*For Master-Haven Project*
