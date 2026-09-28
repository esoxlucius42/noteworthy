from __future__ import annotations

from datetime import date, datetime, timedelta
from collections.abc import Iterable

from .models import Note


def note_matches(note: Note, query: str = "", titles_only: bool = False, status: str | Iterable[str] = "all", date_filter: str = "all") -> bool:
    selected_statuses = {status} if isinstance(status, str) else set(status)
    if selected_statuses and "all" not in selected_statuses and note.status not in selected_statuses:
        return False
    if query:
        query_lower = query.casefold()
        haystack = note.title if titles_only else f"{note.title}\n{note.body}"
        if query_lower not in haystack.casefold():
            return False
    if date_filter != "all":
        try:
            created = datetime.fromisoformat(note.created_at).date()
        except ValueError:
            return False
        today = date.today()
        if date_filter == "today" and created != today:
            return False
        if date_filter == "7d" and created < today - timedelta(days=6):
            return False
        if date_filter == "30d" and created < today - timedelta(days=29):
            return False
    return True
