from typing import Dict, Optional

from app.context import Context
from app.core.exec import run_command, safe_html
from app.core.targets import Target
from app.core.envfile import parse_env_file


def _truthy(val: Optional[str]) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on", "y"}


def _build_redis_url(env: Dict[str, str]) -> Optional[str]:
    url = env.get("REDIS_URL")
    if url:
        return url

    host = env.get("REDIS_HOST")
    port = env.get("REDIS_PORT")
    db = env.get("REDIS_DB")
    password = env.get("REDIS_PASSWORD", "")

    if host and port and db is not None:
        if password:
            return f"redis://:{password}@{host}:{port}/{db}"
        return f"redis://{host}:{port}/{db}"

    return None


def _is_redis_enabled(env: Dict[str, str]) -> bool:
    if _truthy(env.get("REDIS_ENABLED")):
        return True
    if _truthy(env.get("ENABLE_REDIS_CACHE")):
        return True
    return False


def get_redis_status(target: Target, *, ctx: Context) -> str:
    env = parse_env_file(target.resolved_env_file())
    if not _is_redis_enabled(env):
        return "ℹ️ Redis вимкнено"

    url = _build_redis_url(env)
    if not url:
        return "⚠️ Redis увімкнено, але немає REDIS_URL або REDIS_HOST/REDIS_PORT/REDIS_DB"

    out = run_command(["redis-cli", "-u", url, "PING"], timeout=5, max_output_size=ctx.config.max_output_size)
    healthy = "PONG" in out
    icon = "🟢" if healthy else "🔴"
    return (
        f"{icon} <b>Redis</b>\n"
        f"Target: <code>{target.key}</code>\n"
        f"URL: <code>{safe_html(url, max_len=ctx.config.max_output_size)}</code>\n\n"
        f"<blockquote expandable>{safe_html(out, max_len=ctx.config.max_output_size)}</blockquote>"
    )
