"""Persistence helper for settings.json, which can be found in the directory specified by secure_storage.app_data_dir()"""

import json
import os
import sys

from lhdn_automation.authentication import secure_storage

def _settings_path():
    """Refers to the directory returned by secure_storage.app_data_dir() and appends "settings.json" to it."""
    return os.path.join(secure_storage.app_data_dir(), "settings.json")

_APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
EXPORT_FILENAME = "settings_export.json"

def export_path():
    """Same directory as .env - src/lhdn_automation/config in dev, next to the executable when frozen."""
    return os.path.join(_APP_DIR, EXPORT_FILENAME)

def load():
    """Returns the stored {key: value} dict, or {} if none saved yet / unreadable."""
    path = _settings_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def save(values):
    with open(_settings_path(), "w", encoding="utf-8") as f:
        json.dump(values, f, indent=2)


def update(partial):
    """
    Merges 'partial', which is the new {key: value} dict, into the existing settings.json file
    before saving to prevent overwriting existing settings with just the new values.
    """
    current = load()
    current.update(partial)
    save(current)

def export_settings():
    """
    Writes the current settings.json contents to settings_export.json next to
    .env (src/lhdn_automation/config in dev, next to the executable when
    frozen), so the file can be handed to another install or committed
    alongside the rest of the app's local config.

    settings.json only ever holds operator-editable values (poll/timeout
    tuning, SharePoint hostname/site path/list names, eStamp base URL, firm
    data) - never the tenant/client IDs, SharePoint site/list GUIDs, or any
    other value sourced from .env, since those live only in constants.py's
    os.getenv() calls and are never written back to settings.json. So the
    literal file contents can be exported as-is with no filtering needed.

    Returns the path written to.
    """
    current = load()
    path = export_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return path

def import_settings(path=None):
    """
    Reads a settings export JSON file and merges it into settings.json (in
    secure_storage.app_data_dir()), the same way update() does - so the
    imported values are persisted to appdata, not just held in memory.

    `path` defaults to export_path() (see export_settings()) for backward
    compatibility; pass an explicit path to import a file the user picked
    via a file dialog instead. Returns the imported dict. Raises
    FileNotFoundError if no file exists at the resolved path.
    """
    if path is None:
        path = export_path()
    with open(path, "r", encoding="utf-8") as f:
        imported = json.load(f)
    update(imported)
    return imported
