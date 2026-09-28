import json
from datetime import date, datetime, timezone
from pathlib import Path

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
    groups = [
        Group("Work", [Note("Ship release", "Run the checks", "in_progress")], id="group-1"),
        Group("Home", [Note("Buy milk", "Semi-skimmed", "todo")], id="group-2"),
    ]
    storage.save(groups)
    loaded = storage.load()
    assert [group.id for group in loaded] == ["group-1", "group-2"]
    assert [group.name for group in loaded] == ["Work", "Home"]
    assert loaded[0].notes[0].status == "in_progress"


def test_empty_array_loads_default_group(tmp_path):
    path = tmp_path / "notes.json"
    path.write_text("[]", encoding="utf-8")
    loaded = Storage(path).load()
    assert len(loaded) == 1
    assert loaded[0].name == "New Group"


def test_save_cleans_up_temporary_file_on_failure(tmp_path, monkeypatch):
    storage = Storage(tmp_path / "notes.json")
    original_replace = Path.replace

    def fail_replace(self, target):
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    try:
        try:
            storage.save([Group("Work", [Note("Ship release")], id="group-1")])
        except StorageError:
            pass
        else:
            raise AssertionError("save should raise StorageError when replace fails")
    finally:
        monkeypatch.setattr(Path, "replace", original_replace)

    leftover_files = [path for path in tmp_path.iterdir() if path.name != "notes.json"]
    assert leftover_files == []


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


def test_missing_group_name_raises_storage_error(tmp_path):
    path = tmp_path / "notes.json"
    path.write_text(json.dumps([{"id": "group-1", "notes": []}]), encoding="utf-8")
    try:
        Storage(path).load()
    except StorageError:
        pass
    else:
        raise AssertionError("groups missing a name should raise StorageError")


def test_missing_note_fields_raise_storage_error(tmp_path):
    path = tmp_path / "notes.json"
    path.write_text(
        json.dumps([{"id": "group-1", "name": "Valid", "notes": [{"id": "note-1", "body": "Missing title"}]}]),
        encoding="utf-8",
    )
    try:
        Storage(path).load()
    except StorageError:
        pass
    else:
        raise AssertionError("notes missing required fields should raise StorageError")
