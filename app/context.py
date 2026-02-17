from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from app.core.config import Config
from app.core.targets import Target
from app.storage.selection import SelectionStore


@dataclass
class Context:
    config: Config
    targets: Dict[str, Target]
    selection: SelectionStore
    repo_root: Path

    def get_active_target(self, chat_id: int) -> Target:
        key = self.selection.get(chat_id)
        if key and key in self.targets:
            return self.targets[key]
        first_key = next(iter(self.targets.keys()))
        self.selection.set(chat_id, first_key)
        return self.targets[first_key]

    def set_active_target(self, chat_id: int, key: str) -> None:
        if key not in self.targets:
            raise KeyError(key)
        self.selection.set(chat_id, key)
