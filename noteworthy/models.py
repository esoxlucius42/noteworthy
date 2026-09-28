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
        if not isinstance(data, dict):
            raise ValueError("note entries must be objects")
        required_fields = ("id", "title", "body", "created_at", "updated_at", "status")
        if any(field not in data for field in required_fields):
            raise ValueError("note entries must include id, title, body, created_at, updated_at, and status")
        if any(not isinstance(data[field], str) for field in required_fields):
            raise ValueError("note entry fields must be strings")
        title = data["title"].strip()
        if not title:
            raise ValueError("note title must not be empty")
        return cls(
            id=data["id"],
            title=title,
            body=data["body"],
            status=data["status"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
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
        if not isinstance(data, dict):
            raise ValueError("group entries must be objects")
        required_fields = ("id", "name", "notes")
        if any(field not in data for field in required_fields):
            raise ValueError("group entries must include id, name, and notes")
        if not isinstance(data["id"], str):
            raise ValueError("group id must be a string")
        if not isinstance(data["name"], str) or not data["name"].strip():
            raise ValueError("group name must be a non-empty string")
        raw_notes = data["notes"]
        if not isinstance(raw_notes, list):
            raise ValueError("group notes must be an array")
        if any(not isinstance(item, dict) for item in raw_notes):
            raise ValueError("group notes must contain only objects")
        notes = [Note.from_dict(item) for item in raw_notes]
        return cls(id=data["id"], name=data["name"].strip(), notes=notes)
