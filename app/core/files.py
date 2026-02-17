import logging
from pathlib import Path


logger = logging.getLogger("admin_bot")


def read_file(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("Failed to read %s: %s", path, e)
        return f"Error reading file: {e}"


def write_file(path: Path, content: str) -> bool:
    try:
        path.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        logger.error("Failed to write %s: %s", path, e)
        return False
