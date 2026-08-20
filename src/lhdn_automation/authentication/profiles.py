"""
Per-person credential profiles (name + IC number + eStamp password), stored
in profiles.json under secure_storage.app_data_dir() with the IC/password
fields DPAPI-encrypted via secure_storage.encrypt/decrypt. Allows multiple profiles 
to be saved and selected.
"""

import json
import os
import uuid

from lhdn_automation.authentication import secure_storage


def _profiles_path():
    return os.path.join(secure_storage.app_data_dir(), "profiles.json")


class ProfileStore:
    def __init__(self):
        self._path = _profiles_path()
        self._data = self._load()

    def _load(self):
        if not os.path.exists(self._path):
            return {"profiles": {}, "last_used": None}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"profiles": {}, "last_used": None}
        data.setdefault("profiles", {})
        data.setdefault("last_used", None)
        return data

    def _save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def list_profiles(self):
        """Returns [(profile_id, name), ...] for every saved profile."""
        return [(profile_id, entry["name"]) for profile_id, entry in self._data["profiles"].items()]

    def get_last_used(self):
        return self._data.get("last_used")

    def set_last_used(self, profile_id):
        self._data["last_used"] = profile_id
        self._save()

    def get_credentials(self, profile_id):
        entry = self._data["profiles"][profile_id]
        return secure_storage.decrypt(entry["ic"]), secure_storage.decrypt(entry["password"])

    def add_profile(self, name, ic, password):
        profile_id = uuid.uuid4().hex
        self._data["profiles"][profile_id] = {
            "name": name,
            "ic": secure_storage.encrypt(ic),
            "password": secure_storage.encrypt(password),
        }
        self._save()
        return profile_id

    def rename_profile(self, profile_id, new_name):
        if profile_id in self._data["profiles"]:
            self._data["profiles"][profile_id]["name"] = new_name
            self._save()

    def delete_profile(self, profile_id):
        if profile_id in self._data["profiles"]:
            del self._data["profiles"][profile_id]
            if self._data.get("last_used") == profile_id:
                self._data["last_used"] = None
            self._save()
