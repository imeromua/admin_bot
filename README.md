# admin_bot

Telegram admin/control bot to manage multiple co-located bot services (e.g., `generator_bot`, `inventory_bot`) on the same server.

Repo: https://github.com/imeromua/admin_bot

## Features

- Multi-target support (choose which bot/service to manage).
- Status (systemd), logs (journalctl), restart, git pull.
- View/edit target `.env`.
- View/edit target `requirements.txt` and run pip install using target venv python.
- DB/Redis checks (best-effort based on env variables).
- Self-restart after updating admin bot code.

## Structure

- `admin_bot.py`: entrypoint (kept stable for systemd).
- `app/`: application package (config, services, routers).

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

## Notes on sudo

For `systemctl restart` and `journalctl -u`, configure sudoers to allow only required commands for the admin bot user.
