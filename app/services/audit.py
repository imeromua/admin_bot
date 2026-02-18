"""Audit logging service for tracking admin actions."""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


logger = logging.getLogger("admin_bot")


def log_action(
    user_id: int,
    action: str,
    target: str,
    status: str,
    repo_root: Path,
    details: Optional[str] = None,
) -> None:
    """Log administrative action to audit.log.

    Args:
        user_id: Telegram user ID who performed the action
        action: Action type (restart, git_pull, env_edit, pip_install, etc.)
        target: Target service name (generator_bot, inventory_bot, admin_bot)
        status: Action result (success, failed, error)
        repo_root: Repository root path
        details: Optional additional details or error message
    """
    try:
        log_file = repo_root / "audit.log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        details_str = f" | {details}" if details else ""
        log_entry = f"{timestamp} | {user_id} | {action} | {target} | {status}{details_str}\n"

        with log_file.open("a", encoding="utf-8") as f:
            f.write(log_entry)

        logger.info(f"Audit: {action} on {target} by {user_id} -> {status}")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")


def get_recent_logs(repo_root: Path, limit: int = 50) -> str:
    """Get recent audit log entries.

    Args:
        repo_root: Repository root path
        limit: Maximum number of recent entries to return

    Returns:
        Formatted string with recent audit entries
    """
    try:
        log_file = repo_root / "audit.log"
        if not log_file.exists():
            return "Audit log is empty."

        with log_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        recent = lines[-limit:] if len(lines) > limit else lines
        return "".join(recent)
    except Exception as e:
        logger.error(f"Failed to read audit log: {e}")
        return f"Error reading audit log: {e}"
