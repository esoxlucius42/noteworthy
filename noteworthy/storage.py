from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from .models import Group


def data_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "notes.json"
    return Path(__file__).resolve().parent.parent / "notes.json"


class StorageError(Exception):
    """Raised when persisted data cannot be safely loaded or saved."""


class Storage:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or data_path()

    def load(self) -> list[Group]:
        if not self.path.exists():
            return [Group("New Group")]
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError("top-level JSON value must be an array")
            if any(not isinstance(item, dict) for item in raw):
                raise ValueError("top-level array entries must be objects")
            groups = [Group.from_dict(item) for item in raw]
            return groups or [Group("New Group")]
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise StorageError(f"Could not load {self.path.name}: {exc}") from exc

    def save(self, groups: list[Group]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([group.to_dict() for group in groups], indent=2, ensure_ascii=False)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)
            temporary_path.replace(self.path)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise StorageError(f"Could not save {self.path.name}: {exc}") from exc
