from __future__ import annotations

from typing import Tuple
from urllib.parse import urlsplit, urlunsplit

from app.context import Context
from app.core.exec import run_command


def _mask_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        if parts.username or parts.password:
            host = parts.hostname or ""
            if parts.port:
                host = f"{host}:{parts.port}"
            return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
        return url
    except Exception:
        return "<hidden>"


def self_git_update(*, ctx: Context) -> Tuple[str, str, bool]:
    repo_root = ctx.repo_root
    git_url = (ctx.config.self_git_url or "").strip()
    branch = (ctx.config.self_git_branch or "main").strip() or "main"

    if not git_url:
        return "❌ ADMIN_BOT_GIT_URL is empty in .env", "", False

    before = run_command(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_root,
        timeout=15,
        max_output_size=ctx.config.max_output_size,
    ).strip()

    # Keep output safe: don't leak credentials if the URL contains them.
    masked_url = _mask_url(git_url)

    set_url = run_command(
        ["git", "remote", "set-url", "origin", git_url],
        cwd=repo_root,
        timeout=15,
        max_output_size=ctx.config.max_output_size,
    )
    fetch = run_command(
        ["git", "fetch", "origin", "--prune"],
        cwd=repo_root,
        timeout=60,
        max_output_size=ctx.config.max_output_size,
    )
    reset = run_command(
        ["git", "reset", "--hard", f"origin/{branch}"],
        cwd=repo_root,
        timeout=60,
        max_output_size=ctx.config.max_output_size,
    )

    after = run_command(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_root,
        timeout=15,
        max_output_size=ctx.config.max_output_size,
    ).strip()

    log1 = run_command(
        ["git", "log", "-1", "--format=%h - %s (%cr) <%an>"],
        cwd=repo_root,
        timeout=30,
        max_output_size=ctx.config.max_output_size,
    )

    updated = (
        before
        and after
        and (not before.startswith("❌"))
        and (not after.startswith("❌"))
        and before != after
    )

    out = "\n".join(
        [
            f"origin: {masked_url}",
            f"branch: {branch}",
            f"before: {before}",
            "",
            "$ git remote set-url origin <...>",
            set_url,
            "",
            "$ git fetch origin --prune",
            fetch,
            "",
            f"$ git reset --hard origin/{branch}",
            reset,
            "",
            f"after: {after}",
        ]
    ).strip()

    return out, log1, updated
