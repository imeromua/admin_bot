from pathlib import Path

from app.context import Context
from app.core.exec import run_command
from app.core.targets import Target


def python_for_target(target: Target) -> Path:
    if target.python_exe and target.python_exe.exists():
        return target.python_exe
    return Path(__import__("sys").executable)


def pip_install(target: Target, *, ctx: Context) -> str:
    py = python_for_target(target)
    req = target.resolved_req_file()
    return run_command([str(py), "-m", "pip", "install", "-r", str(req)], timeout=300, max_output_size=ctx.config.max_output_size)


def pip_freeze(target: Target, *, ctx: Context) -> str:
    py = python_for_target(target)
    return run_command([str(py), "-m", "pip", "freeze"], timeout=60, max_output_size=ctx.config.max_output_size)


def pip_outdated(target: Target, *, ctx: Context) -> str:
    py = python_for_target(target)
    return run_command([str(py), "-m", "pip", "list", "--outdated"], timeout=90, max_output_size=ctx.config.max_output_size)
