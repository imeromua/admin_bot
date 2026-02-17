from typing import Optional

from app.context import Context
from app.core.exec import run_command


def systemctl_status(service: str, *, ctx: Context) -> str:
    return run_command(["systemctl", "status", service], timeout=15, max_output_size=ctx.config.max_output_size)


def systemctl_is_active(service: str, *, ctx: Context) -> str:
    return run_command(["systemctl", "is-active", service], timeout=10, max_output_size=ctx.config.max_output_size)


def sudo_systemctl_restart(service: str, *, ctx: Context) -> str:
    return run_command(["sudo", "systemctl", "restart", service], timeout=30, max_output_size=ctx.config.max_output_size)
