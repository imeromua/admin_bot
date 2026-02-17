from typing import Tuple

from app.context import Context
from app.core.exec import run_command
from app.core.targets import Target


def git_pull(target: Target, *, ctx: Context) -> Tuple[str, str, bool]:
    pull = run_command(["git", "pull"], cwd=target.path, timeout=60, max_output_size=ctx.config.max_output_size)
    log1 = run_command(
        ["git", "log", "-1", "--format=%h - %s (%cr) <%an>"],
        cwd=target.path,
        timeout=30,
        max_output_size=ctx.config.max_output_size,
    )
    updated = ("Updating" in pull) or ("Fast-forward" in pull)
    return pull, log1, updated
