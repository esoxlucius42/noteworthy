import json
from datetime import date, datetime, timezone

from noteworthy.filters import note_matches
from noteworthy.models import Group, Note
from noteworthy.storage import Storage, StorageError


def test_filter_searches_title_and_body_case_insensitively():
    note = Note("Buy Coffee", "Remember the oat milk")
    assert note_matches(note, "coffee", titles_only=True)
    assert not note_matches(note, "oat", titles_only=True)
    assert note_matches(note, "OAT")


def test_status_and_date_filters_can_be_combined():
    note = Note("Today", status="done", created_at=datetime.now(timezone.utc).isoformat())
    assert note_matches(note, status="done", date_filter="today")
    assert not note_matches(note, status="todo", date_filter="today")


def test_invalid_status_falls_back_to_todo():
    note = Note("Broken", status="invalid")
    assert note.status == "todo"


def test_storage_round_trip(tmp_path):
    storage = Storage(tmp_path / "notes.json")
    groups = [Group("Work", [Note("Ship release", "Run the checks", "in_progress")])]
    storage.save(groups)
    loaded = storage.load()
    assert loaded[0].name == "Work"
    assert loaded[0].notes[0].status == "in_progress"


def test_malformed_json_is_not_silently_replaced(tmp_path):
    path = tmp_path / "notes.json"
    path.write_text("not json", encoding="utf-8")
    try:
        Storage(path).load()
    except StorageError:
        pass
    else:
        raise AssertionError("malformed JSON should raise StorageError")


def test_invalid_group_entry_raises_storage_error(tmp_path):
    path = tmp_path / "notes.json"
    path.write_text(json.dumps([{"name": "Valid", "notes": []}, "bad-entry"]), encoding="utf-8")
    try:
        Storage(path).load()
    except StorageError:
        pass
    else:
        raise AssertionError("invalid group entries should raise StorageError")


def test_invalid_note_entry_raises_storage_error(tmp_path):
    path = tmp_path / "notes.json"
    path.write_text(json.dumps([{"name": "Valid", "notes": [{"title": "Keep"}, "bad-entry"]}]), encoding="utf-8")
    try:
        Storage(path).load()
    except StorageError:
        pass
    else:
        raise AssertionError("invalid note entries should raise StorageError")
