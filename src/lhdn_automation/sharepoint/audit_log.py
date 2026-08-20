import logging
import re
import requests
from datetime import datetime, timezone

from lhdn_automation.sharepoint.client import get_effective_site_id, get_effective_list_id
from lhdn_automation.sharepoint.retry import request_with_retries
from lhdn_automation.config.constants import SHAREPOINT_LOG_LIST_NAME



_log_field_map_cache = {}

def _normalise_field_name(name):
    """Case/whitespace-insensitive key for matching a column's displayName - 'Main Sharepoint ID' should still match 'Main  SharePoint ID'."""
    return re.sub(r"\s+", " ", name).strip().lower()

def _get_automation_log_list(token):
    """Returns (site_id, list_id, {normalised displayName: internalName}) for the Automation Logs list, caching the column map per list."""
    site_id = get_effective_site_id(token)
    list_id = get_effective_list_id(token, SHAREPOINT_LOG_LIST_NAME)

    cache_key = (site_id, list_id)
    if cache_key not in _log_field_map_cache:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/columns"
        columns = []
        while url:
            resp = request_with_retries("GET", url, headers=headers)
            data = resp.json()
            columns.extend(data["value"])
            url = data.get("@odata.nextLink")
        _log_field_map_cache[cache_key] = {_normalise_field_name(col["displayName"]): col["name"] for col in columns}

    return site_id, list_id, _log_field_map_cache[cache_key]

def _resolve_log_field(field_map, display_name):
    """
    Looks up display_name's actual internal Graph field name. Raises rather
    than silently falling back to the display name itself as a guessed
    internal name - SharePoint internal names for columns with spaces (e.g.
    "Main Sharepoint ID") are never literally that string (typically
    something like "Main_x0020_Sharepoint_x0020_ID"), so a wrong/missing
    match previously produced a request with a bogus field key that Graph
    would reject or silently ignore - indistinguishable from "can't write to
    the list" with no obvious cause.
    """
    key = _normalise_field_name(display_name)
    if key not in field_map:
        raise ValueError(
            f"Automation Logs list has no column matching '{display_name}' "
            f"(checked case/spacing-insensitively). Check the column's exact "
            f"display name in SharePoint and update lhdn_automation.py to match."
        )
    return field_map[key]

def _graph_timestamp():
    """Microsoft Graph/SharePoint's native UTC datetime format (e.g. '2024-01-15T10:30:00Z')."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _request_logging_graph_errors(method, url, **kwargs):
    """
    Same as request_with_retries, but logs Graph's actual error body (error.code/
    message) on a 4xx/5xx before re-raising - a bare "403"/"400" alone doesn't
    say whether it's a missing scope, a SharePoint-level list permission, an
    unrecognized field name, or a column-type/choice mismatch, which makes an
    Automation Logs write failure otherwise nearly undiagnosable.
    """
    try:
        return request_with_retries(method, url, **kwargs)
    except requests.exceptions.HTTPError as error:
        body = error.response.text[:2000] if error.response is not None else "(no response body)"
        logging.error("Graph error writing Automation Logs (%s %s): %s", method, url, body)
        raise

def create_automation_log(token, client_name, sharepoint_item_id, max_attempts):
    """
    Creates a new row in the Automation Logs list when processing an item
    starts. Returns the new log item's id so later lifecycle events
    (Exception/Failed/Completed) can update the same row via
    update_automation_log() instead of creating a new one per event.
    """
    site_id, list_id, field_map = _get_automation_log_list(token)
    fields = {
        _resolve_log_field(field_map, "Title"): client_name,
        _resolve_log_field(field_map, "Main Sharepoint ID"): str(sharepoint_item_id),
        _resolve_log_field(field_map, "Timestamp"): _graph_timestamp(),
        _resolve_log_field(field_map, "Retry Attempt"): f"0 / {max_attempts}",
        _resolve_log_field(field_map, "Status"): "Processing",
        _resolve_log_field(field_map, "Exception Message"): "",
    }
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = _request_logging_graph_errors("POST", url, headers=headers, json={"fields": fields})
    return resp.json()["id"]

def update_automation_log(token, log_item_id, *, attempt, max_attempts, status, exception_message=""):
    """Updates the Timestamp/Retry Attempt/Status/Exception Message columns on an existing Automation Logs row."""
    site_id, list_id, field_map = _get_automation_log_list(token)
    fields = {
        _resolve_log_field(field_map, "Timestamp"): _graph_timestamp(),
        _resolve_log_field(field_map, "Retry Attempt"): f"{attempt} / {max_attempts}",
        _resolve_log_field(field_map, "Status"): status,
        _resolve_log_field(field_map, "Exception Message"): exception_message,
    }
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items/{log_item_id}/fields"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    return _request_logging_graph_errors("PATCH", url, headers=headers, json=fields)

def diagnose_automation_log_access(token):
    """
    On-demand diagnostic for the Automation Logs list: checks that it can be
    resolved, read, and written to as three independent steps, since a 403
    could originate from any one of them (wrong list resolved, an app/site
    Graph-scope issue, or a SharePoint-native list/item-level permission
    restricting just item creation) - each is reported separately rather
    than collapsing to a single pass/fail bit.

    Graph has no endpoint that reports a list's effective create-permission
    without attempting it, so this creates one throwaway test row (clearly
    marked, via the same field-resolution path create_automation_log uses)
    and deletes it immediately after, to verify create access directly.

    Returns an ordered list of (step_name, ok, detail) tuples. If step 1
    (resolving the list) fails, the remaining steps are meaningless and are
    skipped - each other step's failure doesn't prevent the next from
    running, so e.g. a failed create is still followed by a (skipped)
    cleanup rather than aborting the whole diagnostic.
    """
    results = []

    try:
        site_id, list_id, field_map = _get_automation_log_list(token)
        results.append(("Resolve list", True, f"site={site_id}, list={list_id}"))
    except Exception as error:
        results.append(("Resolve list", False, str(error)))
        return results

    headers = {"Authorization": f"Bearer {token}"}

    try:
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?$top=1"
        _request_logging_graph_errors("GET", url, headers=headers)
        results.append(("Read items", True, "OK"))
    except Exception as error:
        results.append(("Read items", False, str(error)))

    test_item_id = None
    try:
        fields = {
            _resolve_log_field(field_map, "Title"): "[Diagnostic Test - safe to delete]",
            _resolve_log_field(field_map, "Main Sharepoint ID"): "0",
            _resolve_log_field(field_map, "Timestamp"): _graph_timestamp(),
            _resolve_log_field(field_map, "Retry Attempt"): "0 / 0",
            _resolve_log_field(field_map, "Status"): "Processing",
            _resolve_log_field(field_map, "Exception Message"): "Created by Configuration > Test Automation Logs Access",
        }
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items"
        create_headers = {**headers, "Content-Type": "application/json"}
        resp = _request_logging_graph_errors("POST", url, headers=create_headers, json={"fields": fields})
        test_item_id = resp.json()["id"]
        results.append(("Create test item", True, f"item id {test_item_id}"))
    except Exception as error:
        results.append(("Create test item", False, str(error)))

    if test_item_id is not None:
        try:
            url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items/{test_item_id}"
            _request_logging_graph_errors("DELETE", url, headers=headers)
            results.append(("Clean up test item", True, "deleted"))
        except Exception as error:
            results.append((
                "Clean up test item", False,
                f"{error} - manually delete item {test_item_id} from Automation Logs",
            ))

    return results
