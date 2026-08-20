from lhdn_automation.config.constants import SHAREPOINT_HOSTNAME, SHAREPOINT_SITE_PATH, SHAREPOINT_SITE_ID, SHAREPOINT_LIST_NAME, SHAREPOINT_LIST_ID, _INITIAL_SHAREPOINT_HOSTNAME, _INITIAL_SHAREPOINT_SITE_PATH, _INITIAL_SHAREPOINT_LIST_NAME
from lhdn_automation.sharepoint.retry import request_with_retries

def get_site_id(token, hostname=SHAREPOINT_HOSTNAME, site_path=SHAREPOINT_SITE_PATH):
    url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:{site_path}:"
    headers = {"Authorization": f"Bearer {token}"}
    resp = request_with_retries("GET", url, headers=headers)
    resp.raise_for_status()
    return resp.json()["id"]

def get_list_id(token, site_id=SHAREPOINT_SITE_ID, list_name=SHAREPOINT_LIST_NAME):
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
    headers = {"Authorization": f"Bearer {token}"}
    resp = request_with_retries("GET", url, headers=headers)
    resp.raise_for_status()
    for lst in resp.json()["value"]:
        if lst["displayName"] == list_name:
            return lst["id"]
    raise ValueError(f"List '{list_name}' not found")

_site_id_cache = {}
_list_id_cache = {}

def get_effective_site_id(token):
    """
    If SHAREPOINT_HOSTNAME/SITE_PATH are still the original values, return them.
    Otherwise, cache the resolved site ID and return it.
    """
    if (
        SHAREPOINT_HOSTNAME == _INITIAL_SHAREPOINT_HOSTNAME
        and SHAREPOINT_SITE_PATH == _INITIAL_SHAREPOINT_SITE_PATH
        and SHAREPOINT_SITE_ID  
    ):
        return SHAREPOINT_SITE_ID

    cache_key = (SHAREPOINT_HOSTNAME, SHAREPOINT_SITE_PATH)
    if _site_id_cache.get("key") != cache_key:
        _site_id_cache["key"] = cache_key
        _site_id_cache["value"] = get_site_id(token, hostname=SHAREPOINT_HOSTNAME, site_path=SHAREPOINT_SITE_PATH)
    return _site_id_cache["value"]

def get_effective_list_id(token, list_name):
    """
    If SHAREPOINT_LIST_NAME is still the original value, return SHAREPOINT_LIST_ID.
    Otherwise, cache the resolved list ID and return it.
    """
    site_id = get_effective_site_id(token)
    if (
        site_id == SHAREPOINT_SITE_ID
        and list_name == _INITIAL_SHAREPOINT_LIST_NAME
        and SHAREPOINT_LIST_ID
    ):
        return SHAREPOINT_LIST_ID

    cache_key = (site_id, list_name)
    if cache_key not in _list_id_cache:
        _list_id_cache[cache_key] = get_list_id(token, site_id=site_id, list_name=list_name)
    return _list_id_cache[cache_key]

def get_list_items(token, site_id=None, list_id=None):
    """
    Fetch all items (with expanded fields) from the target SharePoint list.
    Handles pagination via @odata.nextLink.
    """
    if site_id is None:
        site_id = get_effective_site_id(token)
    if list_id is None:
        list_id = get_effective_list_id(token, SHAREPOINT_LIST_NAME)

    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?$expand=fields"
    all_items = []

    while url:
        resp = request_with_retries("GET", url, headers=headers)
        data = resp.json()
        all_items.extend(data["value"])
        url = data.get("@odata.nextLink")

    return all_items

def get_selectable_items(token):
    """Fetch all SharePoint entries valid for editing (Approved or Failed)."""
    items = get_list_items(token)
    return [
        item
        for item in items
        if item.get("fields", {}).get("Status") in ("Approved", "Failed")
    ]

def update_item(token, item_id, fields_dict, site_id=None, list_id=None):
    """
    PATCH specific column(s) on a single SharePoint list item.
    fields_dict example: {"Status": "Processing"}
    """
    if site_id is None:
        site_id = get_effective_site_id(token)
    if list_id is None:
        list_id = get_effective_list_id(token, SHAREPOINT_LIST_NAME)

    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items/{item_id}/fields"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    resp = request_with_retries("PATCH", url, headers=headers, json=fields_dict)
    return resp
