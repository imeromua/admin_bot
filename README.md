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
- `state.json`: persisted target selection (auto-created, ignored by git).

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

## Migration checklist (updating from monolithic version)

If you're upgrading from the old single-file `admin_bot.py`:

1. **Backup existing `.env`** before pulling new code:
   ```bash
   cd /home/anubis/admin_bot
   cp .env .env.backup
   ```

2. **Pull new code** (modular structure):
   ```bash
   git pull origin main
   ```

3. **Check `.env` variables**:
   - Ensure `ADMIN_BOT_TOKEN`, `ADMIN_BOT_ADMIN_ID`, `ADMIN_BOT_SELF_SERVICE` are set.
   - Ensure `ADMIN_BOT_REPO` is set (metadata for self-update messages).
   - Ensure `ADMIN_TARGETS` lists all targets (e.g., `generator,inventory`).
   - For each target, verify `ADMIN_TARGET_<X>_SERVICE`, `ADMIN_TARGET_<X>_PATH`, `ADMIN_TARGET_<X>_PYTHON` are correct.
   - `ADMIN_TARGET_<X>_PYTHON` should point to the **target's venv python** (e.g., `/home/anubis/generator_bot/.venv/bin/python`), not admin bot's python.

4. **Verify sudoers configuration**:
   - Admin bot user needs passwordless sudo for:
     - `systemctl restart <target_service>`
     - `systemctl restart admin_bot` (for self-restart)
     - `journalctl -u <target_service>`
   - Example `/etc/sudoers.d/admin_bot`:
     ```
     anubis ALL=(ALL) NOPASSWD: /bin/systemctl restart generator_bot
     anubis ALL=(ALL) NOPASSWD: /bin/systemctl restart inventory_bot
     anubis ALL=(ALL) NOPASSWD: /bin/systemctl restart admin_bot
     anubis ALL=(ALL) NOPASSWD: /bin/journalctl -u generator_bot*
     anubis ALL=(ALL) NOPASSWD: /bin/journalctl -u inventory_bot*
     anubis ALL=(ALL) NOPASSWD: /bin/journalctl -u admin_bot*
     ```

5. **Check file permissions**:
   - Ensure `state.json` (created automatically) is writable by the bot user:
     ```bash
     ls -la /home/anubis/admin_bot/state.json
     ```
   - If missing, it will be created on first target switch.

6. **Restart admin bot**:
   ```bash
   sudo systemctl restart admin_bot
   ```

7. **Test in Telegram**:
   - Send `/start` to your admin bot.
   - Click "🎯 Бот" to switch targets — choice should persist after restart.
   - Test git pull, restart, logs for each target.

## Notes on sudo

For `systemctl restart` and `journalctl -u`, configure sudoers to allow only required commands for the admin bot user (see migration checklist above).
