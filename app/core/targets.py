from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import os


@dataclass(frozen=True)
class Target:
    key: str
    service: str
    path: Path
    repo: Optional[str] = None
    python_exe: Optional[Path] = None
    env_file: Optional[Path] = None
    req_file: Optional[Path] = None
    log_file: Optional[Path] = None

    def resolved_env_file(self) -> Path:
        return self.env_file or (self.path / ".env")

    def resolved_req_file(self) -> Path:
        return self.req_file or (self.path / "requirements.txt")

    def resolved_log_file(self) -> Path:
        return self.log_file or (self.path / "bot.log")


def load_targets(targets_str: str) -> Dict[str, Target]:
    keys = [k.strip() for k in targets_str.split(",") if k.strip()]
    targets: Dict[str, Target] = {}

    for key in keys:
        prefix = f"ADMIN_TARGET_{key.upper()}_"
        service = os.getenv(prefix + "SERVICE")
        path = os.getenv(prefix + "PATH")
        if not service or not path:
            raise RuntimeError(f"Target '{key}' requires {prefix}SERVICE and {prefix}PATH")

        repo = os.getenv(prefix + "REPO")
        python_exe = os.getenv(prefix + "PYTHON")

        env_file = os.getenv(prefix + "ENV_FILE")
        req_file = os.getenv(prefix + "REQ_FILE")
        log_file = os.getenv(prefix + "LOG_FILE")

        targets[key] = Target(
            key=key,
            service=service,
            path=Path(path),
            repo=repo,
            python_exe=Path(python_exe) if python_exe else None,
            env_file=Path(env_file) if env_file else None,
            req_file=Path(req_file) if req_file else None,
            log_file=Path(log_file) if log_file else None,
        )

    if not targets:
        raise RuntimeError("No targets loaded from ADMIN_TARGETS")

    return targets
