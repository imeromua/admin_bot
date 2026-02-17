import re
from typing import Dict, Optional, Tuple

from app.context import Context
from app.core.exec import run_command, safe_html
from app.core.targets import Target
from app.core.envfile import parse_env_file


def _parse_postgres_from_env(env: Dict[str, str]) -> Optional[Tuple[str, str, str, str]]:
    dsn = env.get("POSTGRES_DSN", "").strip()
    if dsn:
        m = re.match(r"postgresql://(.*?):(.*?)@(.*?):(.*?)/(.*)", dsn)
        if m:
            user, _pw, host, port, dbname = m.groups()
            return host, port, user, dbname

    host = env.get("DB_HOST")
    port = env.get("DB_PORT")
    user = env.get("DB_USER")
    dbname = env.get("DB_NAME")
    if host and port and user and dbname:
        return host, port, user, dbname

    return None


def get_db_status(target: Target, *, ctx: Context) -> str:
    env = parse_env_file(target.resolved_env_file())
    parsed = _parse_postgres_from_env(env)
    if not parsed:
        return "ℹ️ PostgreSQL: немає налаштувань (POSTGRES_DSN або DB_HOST/DB_USER/DB_NAME)"

    host, port, user, dbname = parsed
    out = run_command(["pg_isready", "-h", host, "-p", str(port), "-U", user, "-d", dbname], timeout=10, max_output_size=ctx.config.max_output_size)
    healthy = "accepting connections" in out
    icon = "🟢" if healthy else "🔴"
    return (
        f"{icon} <b>PostgreSQL</b>\n"
        f"Target: <code>{target.key}</code>\n"
        f"DSN: <code>{safe_html(f'{host}:{port}/{dbname}', max_len=ctx.config.max_output_size)}</code>\n\n"
        f"<blockquote expandable>{safe_html(out, max_len=ctx.config.max_output_size)}</blockquote>"
    )
