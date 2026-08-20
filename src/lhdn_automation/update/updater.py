from contextlib import suppress
from lhdn_automation.config.constants import APP_VERSION, GITHUB_RELEASES_API
from lhdn_automation.sharepoint.retry import request_with_retries

def _version_tuple(version_string):
    """Parses a dotted version string into a tuple of ints for numeric comparison, ignoring any non-numeric parts (e.g. a leading 'v')."""
    parts = []
    for part in version_string.split("."):
        with suppress(ValueError):
            parts.append(int(part))
    return tuple(parts)

def check_for_update():
    """
    Queries the GitHub releases API for the latest published release and
    compares it against APP_VERSION. Returns (update_available, latest_version).
    Raises on network/API failure - callers should catch and treat that as
    "couldn't check" rather than "no update available".
    """
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "LHDN-Automation"}
    resp = request_with_retries("GET", GITHUB_RELEASES_API, headers=headers, timeout=5, retries=1)
    latest_version = resp.json().get("tag_name", "").lstrip("vV")
    update_available = _version_tuple(latest_version) > _version_tuple(APP_VERSION)
    return update_available, latest_version