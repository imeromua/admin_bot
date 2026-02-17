from pathlib import Path
from typing import Dict

from app.core.files import read_file, write_file


def parse_env_file(path: Path) -> Dict[str, str]:
    env_vars: Dict[str, str] = {}
    content = read_file(path)
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()
    return env_vars


def write_env_file(path: Path, env_vars: Dict[str, str]) -> bool:
    content = "".join(f"{k}={v}\n" for k, v in sorted(env_vars.items()))
    return write_file(path, content)
