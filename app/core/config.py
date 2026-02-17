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
    admin_repo: str | None = None
    max_output_size: int = 4000


def load_config() -> Config:
    load_dotenv()

    token = os.getenv("ADMIN_BOT_TOKEN")
    admin_id_str = os.getenv("ADMIN_BOT_ADMIN_ID")
    self_service_name = os.getenv("ADMIN_BOT_SELF_SERVICE", "admin_bot")
    targets_str = (os.getenv("ADMIN_TARGETS", "") or "").strip()
    admin_repo = (os.getenv("ADMIN_BOT_REPO", "") or "").strip() or None

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
        admin_repo=admin_repo,
    )
