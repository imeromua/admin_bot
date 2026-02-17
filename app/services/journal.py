from typing import Optional

from app.context import Context
from app.core.exec import run_command


def journalctl_lines(service: str, *, ctx: Context, n: int = 100, since: Optional[str] = None) -> str:
    args = ["journalctl", "-u", service, "--no-pager"]
    if since:
        args += ["--since", since]
    else:
        args += ["-n", str(n)]
    return run_command(args, timeout=20, max_output_size=ctx.config.max_output_size)
