import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str
    admin_id: int
    self_service_name: str
    targets_str: str
    self_git_url: str = ""
    self_git_branch: str = "main"
    max_output_size: int = 4000
    # Нові параметри для watchdog
    alerts_enabled: bool = False
    alert_interval: int = 300  # секунд (за замовчуванням 5 хв)
    alert_on_critical_errors: bool = True


def load_config() -> Config:
    load_dotenv()

    token = os.getenv("ADMIN_BOT_TOKEN")
    admin_id_str = os.getenv("ADMIN_BOT_ADMIN_ID")
    self_service_name = os.getenv("ADMIN_BOT_SELF_SERVICE", "admin_bot")
    targets_str = (os.getenv("ADMIN_TARGETS", "") or "").strip()

    self_git_url = (os.getenv("ADMIN_BOT_GIT_URL", "") or "").strip()
    self_git_branch = (os.getenv("ADMIN_BOT_GIT_BRANCH", "main") or "main").strip() or "main"

    # Нові параметри
    alerts_enabled = os.getenv("ADMIN_BOT_ALERTS_ENABLED", "false").lower() in ("true", "1", "yes")
    alert_interval = int(os.getenv("ADMIN_BOT_ALERT_INTERVAL", "300"))
    alert_on_critical_errors = os.getenv("ADMIN_BOT_ALERT_ON_CRITICAL", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    if not token:
        raise RuntimeError("ADMIN_BOT_TOKEN is not set in environment")
    if not admin_id_str:
        raise RuntimeError("ADMIN_BOT_ADMIN_ID is not set in environment")

    try:
        admin_id = int(admin_id_str)
    except ValueError as e:
        raise RuntimeError(f"ADMIN_BOT_ADMIN_ID must be integer, got: {admin_id_str}") from e

    if not targets_str:
        raise RuntimeError("ADMIN_TARGETS is empty. Define at least one target.")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    return Config(
        token=token,
        admin_id=admin_id,
        self_service_name=self_service_name,
        targets_str=targets_str,
        self_git_url=self_git_url,
        self_git_branch=self_git_branch,
        alerts_enabled=alerts_enabled,
        alert_interval=alert_interval,
        alert_on_critical_errors=alert_on_critical_errors,
    )
