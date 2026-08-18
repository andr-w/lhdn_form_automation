"""Persistence helper for settings.json, which can be found in the directory specified by secure_storage.app_data_dir()"""

import json
import os

import secure_storage

def _settings_path():
    """Refers to the directory returned by secure_storage.app_data_dir() and appends "settings.json" to it."""
    return os.path.join(secure_storage.app_data_dir(), "settings.json")

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
