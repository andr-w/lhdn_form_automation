import logging
from datetime import datetime, timezone

from requests.exceptions import RequestException, Timeout as RequestsTimeout

from lhdn_automation.authentication import auth
from lhdn_automation.config.constants import AUTOFILL_STATUSES, STALE_PROCESSING_TIMEOUT
from lhdn_automation.models import FirmData
from lhdn_automation.sharepoint.token import get_access_token
from lhdn_automation.sharepoint.client import get_list_items, update_item
from lhdn_automation.sharepoint.processing import is_processing_stale
from lhdn_automation.sharepoint.autofill import handle_autofill


def poll_for_changes(firmdata: FirmData, headless=True):
    """
    Passively checks Pending, Awaiting Review, and Approved SharePoint
    entries for missing company numbers and autofills them, and fails any
    entry that's been stuck in Processing for too long (see
    STALE_PROCESSING_TIMEOUT). Runs unattended, so the CTOS lookup driver
    defaults to headless and never blocks for operator input - Failed items
    and driving the eStamp form itself are handled on demand via
    handle_approved()/process_approved_item() instead.
    """
    try:
        token = get_access_token(allow_interactive=False)
        items = get_list_items(token)
    except (RequestsTimeout, RequestException, RuntimeError, ValueError, auth.SignInRequired) as error:
        logging.warning("Skipping poll cycle after SharePoint/Graph error: %s", error)
        return

    try:
        items = sorted(items, key=lambda item: int(item.get("id", 0)))
    except (TypeError, ValueError):
        logging.debug("Unable to sort poll items by numeric id; processing in API order")

    now = datetime.now(timezone.utc)
    for item in items:
        fields = item.get("fields", {})
        if is_processing_stale(fields, now=now):
            logging.warning(
                "Item %s stuck in Processing since %s (over %d minutes ago), marking Failed",
                item["id"],
                fields.get("Modified"),
                STALE_PROCESSING_TIMEOUT.total_seconds() // 60,
            )
            update_item(token, item["id"], {"Status": "Failed"})

    autofill_items = [
        item for item in items
        if item.get("fields", {}).get("Status") in AUTOFILL_STATUSES
    ]
    for item in autofill_items:
        handle_autofill(token, item["id"], item["fields"], headless=headless)