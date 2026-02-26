"""Сервіс журналу аудиту для відстеження адміністративних дій."""
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
    """Записати адміністративну дію в audit.log.

    Args:
        user_id: Telegram ID користувача, який виконав дію
        action: Тип дії (restart, git_pull, env_edit, pip_install тощо)
        target: Назва цільового сервісу (generator_bot, inventory_bot, admin_bot)
        status: Результат дії (success, failed, error)
        repo_root: Кореневий шлях репозиторію
        details: Опціональні додаткові деталі або повідомлення про помилку
    """
    try:
        log_file = repo_root / "audit.log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        details_str = f" | {details}" if details else ""
        log_entry = f"{timestamp} | {user_id} | {action} | {target} | {status}{details_str}\n"

        with log_file.open("a", encoding="utf-8") as f:
            f.write(log_entry)

        logger.info("Audit: %s on %s by %s -> %s", action, target, user_id, status)
    except Exception as e:
        logger.error("Помилка запису журналу аудиту: %s", e)


def get_recent_logs(repo_root: Path, limit: int = 50) -> str:
    """Отримати останні записи журналу аудиту.

    Args:
        repo_root: Кореневий шлях репозиторію
        limit: Максимальна кількість останніх записів для повернення

    Returns:
        Форматований рядок з останніми записами аудиту
    """
    try:
        log_file = repo_root / "audit.log"
        if not log_file.exists():
            return "Журнал аудиту порожній."

        with log_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        recent = lines[-limit:] if len(lines) > limit else lines
        return "".join(recent)
    except Exception as e:
        logger.error("Помилка читання журналу аудиту: %s", e)
        return f"Помилка читання журналу аудиту: {e}"
