# Noteworthy

Noteworthy is a dark-themed desktop note manager built with Python and PySide6. Notes are organized into draggable groups and saved automatically to `notes.json`.

## Run from source

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
python -m noteworthy.main
```

The data file is created in the project directory when running from source. A packaged executable resolves its data file beside the application package.

## Test

```bash
pytest
```

The test suite covers filtering, serialization, round trips, and malformed JSON recovery. The UI can also be smoke-tested headlessly with `QT_QPA_PLATFORM=offscreen`.
