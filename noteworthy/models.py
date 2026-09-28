from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

STATUSES = ("todo", "in_progress", "done", "cancelled")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid4().hex


@dataclass
class Note:
    title: str
    body: str = ""
    status: str = "todo"
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            self.status = "todo"

    def touch(self) -> None:
        self.updated_at = now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Note:
        body = str(data.get("body", ""))
        title = str(data.get("title", "")).strip()
        if not title:
            title = body.splitlines()[0][:80] if body else "Untitled note"
        return cls(
            id=str(data.get("id") or new_id()),
            title=title,
            body=body,
            status=str(data.get("status", "todo")),
            created_at=str(data.get("created_at") or now_iso()),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now_iso()),
        )


@dataclass
class Group:
    name: str
    notes: list[Note] = field(default_factory=list)
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "notes": [note.to_dict() for note in self.notes]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Group:
        raw_notes = data.get("notes", [])
        notes = [Note.from_dict(item) for item in raw_notes if isinstance(item, dict)]
        return cls(id=str(data.get("id") or new_id()), name=str(data.get("name") or "New Group"), notes=notes)
