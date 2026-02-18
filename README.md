# admin_bot

Telegram admin/control bot to manage multiple co-located bot services (e.g., `generator_bot`, `inventory_bot`) on the same server.

Repo: https://github.com/imeromua/admin_bot

## Features

### 👁️ Core Management
- Multi-target support (choose which bot/service to manage)
- Status (systemd), logs (journalctl), restart, git pull
- View/edit target `.env`
- View/edit target `requirements.txt` and run pip install using target venv python
- DB/Redis checks (best-effort based on env variables)
- Self-update from git and self-restart (env: `ADMIN_BOT_GIT_URL`)

### ✨ New in v6.1

#### 📝 Audit Logging
- All administrative actions are logged to `audit.log`
- Command `/audit` to view recent entries (20/50 or download full log)
- Format: `timestamp | user_id | action | target | status | details`

#### 🔥 Enhanced Log Filters
- **Critical filter**: View only CRITICAL/FATAL/Traceback errors
- **Timeframe filters**: View logs from last 1h, 3h, or 24h
- **Download filtered logs**: Save errors/warnings/critical as separate files (20/30/50 lines)

#### 🚨 Automated Monitoring (Watchdog)
- Continuous monitoring of all target services
- Automatic Telegram alerts when:
  - Service goes down (status != active)
  - Critical errors appear in logs
- Anti-spam: 15-minute cooldown between identical alerts
- Configurable via `.env` (see Configuration section)

#### 💿 Disk Space Warnings
- `🟡 WARNING` indicator when disk usage > 80%
- `🔴 CRITICAL` indicator when disk usage > 90% or free space < 2GB
- Displayed in `/sysinfo` command

## Structure

- `admin_bot.py`: entrypoint (kept stable for systemd)
- `app/`: application package (config, services, routers)
- `state.json`: persisted target selection (auto-created, ignored by git)
- `audit.log`: administrative action history (auto-created)

## Quick start (server)

1) Clone
```bash
cd /home/anubis
git clone https://github.com/imeromua/admin_bot.git
cd admin_bot
```

2) Create venv and install deps
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

3) Configure
```bash
cp .env.example .env
nano .env
```

**Required configuration:**
```bash
ADMIN_BOT_TOKEN=your_telegram_bot_token
ADMIN_BOT_ADMIN_ID=your_telegram_user_id
ADMIN_TARGETS=generator,inventory
```

**Optional (v6.1+) - Watchdog configuration:**
```bash
# Enable monitoring and alerts
ADMIN_BOT_ALERTS_ENABLED=true

# Check interval in seconds (default: 300 = 5 minutes)
ADMIN_BOT_ALERT_INTERVAL=300

# Alert on critical errors (default: true)
ADMIN_BOT_ALERT_ON_CRITICAL=true
```

4) Run (manual)
```bash
. .venv/bin/activate
python admin_bot.py
```

## systemd (example)

Create `/etc/systemd/system/admin_bot.service`:
```ini
[Unit]
Description=admin_bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=anubis
WorkingDirectory=/home/anubis/admin_bot
EnvironmentFile=/home/anubis/admin_bot/.env
ExecStart=/home/anubis/admin_bot/.venv/bin/python /home/anubis/admin_bot/admin_bot.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now admin_bot
```

## Available Commands

### Basic
- `/start` - Show current target and main menu
- `/help` - Display help information

### Monitoring (v6.1+)
- `/audit` - View audit log (administrative action history)
- `/sysinfo` - System information with disk space warnings

### Logs
- `📜 Логи` button - Access log menu with filters:
  - View last 50/100/200 lines
  - View today's logs
  - `🔥 Critical (10)` - Last 10 critical errors
  - `🚨 Errors (50)` - Last 50 errors
  - `⚠️ Warnings (50)` - Last 50 warnings
  - `⏰ Timeframes` - Last 1h/3h/24h
  - Download filtered logs as files

## Migration checklist (updating from v6.0 or earlier)

1. **Backup existing `.env`** before pulling new code:
   ```bash
   cd /home/anubis/admin_bot
   cp .env .env.backup
   ```

2. **Pull new code**:
   ```bash
   git pull origin main
   ```

3. **Add new optional env variables** (see `.env.example`):
   ```bash
   # Optional: Enable watchdog
   echo "ADMIN_BOT_ALERTS_ENABLED=false" >> .env
   echo "ADMIN_BOT_ALERT_INTERVAL=300" >> .env
   echo "ADMIN_BOT_ALERT_ON_CRITICAL=true" >> .env
   ```

4. **Restart admin bot**:
   ```bash
   sudo systemctl restart admin_bot
   ```

5. **Test new features**:
   - Send `/audit` to view audit log
   - Check `/sysinfo` for disk space warnings
   - View `🔥 Critical` and timeframe filters in logs menu
   - (Optional) Set `ADMIN_BOT_ALERTS_ENABLED=true` to enable monitoring

## Notes on sudo

For `systemctl restart` and `journalctl -u`, configure sudoers to allow only required commands for the admin bot user.

Example `/etc/sudoers.d/admin_bot`:
```
anubis ALL=(ALL) NOPASSWD: /bin/systemctl restart generator_bot
anubis ALL=(ALL) NOPASSWD: /bin/systemctl restart inventory_bot
anubis ALL=(ALL) NOPASSWD: /bin/systemctl restart admin_bot
anubis ALL=(ALL) NOPASSWD: /bin/journalctl -u generator_bot*
anubis ALL=(ALL) NOPASSWD: /bin/journalctl -u inventory_bot*
anubis ALL=(ALL) NOPASSWD: /bin/journalctl -u admin_bot*
```

## Version History

### v6.1 (2026-02-18)
- ✨ Added audit logging system (`/audit` command)
- 🔥 Enhanced log filters (Critical, timeframes 1h/3h/24h)
- 🚨 Automated monitoring with Telegram alerts (optional watchdog)
- 💿 Disk space warnings in sysinfo
- 📥 Download filtered logs as separate files

### v6.0
- Initial modular architecture
- Multi-target management
- Basic monitoring and control features
