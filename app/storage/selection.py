import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class SelectionStore:
    path: Path
    _data: Dict[str, str]

    @classmethod
    def load(cls, path: Path) -> "SelectionStore":
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return cls(path=path, _data={str(k): str(v) for k, v in raw.items()})
            except Exception:
                pass
        return cls(path=path, _data={})

    def get(self, chat_id: int) -> Optional[str]:
        return self._data.get(str(chat_id))

    def set(self, chat_id: int, target_key: str) -> None:
        self._data[str(chat_id)] = target_key
        self._flush()

    def _flush(self) -> None:
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
