import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from app.context import Context
from app.core.targets import Target
from app.core.envfile import parse_env_file


def backup_postgres(target: Target, *, ctx: Context) -> Tuple[bool, str, Optional[Path]]:
    env = parse_env_file(target.resolved_env_file())
    dsn = env.get("POSTGRES_DSN", "").strip()
    if not dsn:
        return False, "POSTGRES_DSN не знайдено (для backup потрібен саме DSN)", None

    m = re.match(r"postgresql://(.*?):(.*?)@(.*?):(.*?)/(.*)", dsn)
    if not m:
        return False, "Неправильний формат POSTGRES_DSN", None

    user, password, host, port, dbname = m.groups()
    filename = Path(f"backup_{target.key}_{dbname}_{datetime.now().strftime('%Y%m%d_%H%M')}.sql")

    cmd = ["pg_dump", "-U", user, "-h", host, "-p", str(port), dbname]
    env2 = os.environ.copy()
    env2["PGPASSWORD"] = password

    try:
        with filename.open("w", encoding="utf-8") as f:
            res = subprocess.run(cmd, env=env2, stdout=f, stderr=subprocess.PIPE, timeout=180, text=True)
        if res.returncode != 0:
            filename.unlink(missing_ok=True)
            err = (res.stderr or "").strip()
            if len(err) > ctx.config.max_output_size:
                err = err[: ctx.config.max_output_size] + "\n\n... (обрізано)"
            return False, f"pg_dump error (exit {res.returncode}):\n{err}", None

        return True, "OK", filename
    except subprocess.TimeoutExpired:
        filename.unlink(missing_ok=True)
        return False, "Timeout (180s)", None
    except Exception as e:
        filename.unlink(missing_ok=True)
        return False, str(e), None
