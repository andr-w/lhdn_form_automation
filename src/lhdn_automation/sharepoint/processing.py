import json
from contextlib import suppress
from lhdn_automation.models import ClientQuotationData
from lhdn_automation.sharepoint.client import update_item


def parse_client_data(raw_json):
    data = json.loads(raw_json)
    return ClientQuotationData(
        ClientName=data.get("ClientName", ""),
        BusinessType=data.get("BusinessType", ""),
        CompanyLocationType=data.get("CompanyLocationType", "Local"),
        City=data.get("City", ""),
        State=data.get("State", ""),
        Postcode=data.get("Postcode", ""),
        TelephoneNumber=data.get("TelephoneNumber") or "12345678910",
        EmailAddress=data.get("EmailAddress", ""),
        QuoteDate=data.get("QuoteDate", ""),
        EffectiveDate=data.get("EffectiveDate", ""),

        AddressLine1=data.get("AddressLine1", ""),
        AddressLine2=data.get("AddressLine2", ""),
        AddressLine3=data.get("AddressLine3", ""),

        SSMOption=data.get("SSMOption", "Syarikat_SSM_True"),

        NetTotal=data.get("NetTotal", "0"),
        QuotationQuantity=str(data.get("QuotationQuantity", "1")),
        OwnerName=data.get("OwnerName", ""),
        OwnerNationality=data.get("OwnerNationality", ""),
        OldCompanyNumber=data.get("OldCompanyNumber", ""),
        NewCompanyNumber=data.get("NewCompanyNumber", ""),
    )

def summarise_item(item):
    """Build a plain-data display summary for a SharePoint item, usable by any frontend."""
    fields = item.get("fields", {})
    raw_json = fields.get("JSON", "")
    client_name = fields.get("ClientName", "")
    effective_date = fields.get("EffectiveDate", "")
    quote_date = fields.get("QuoteDate", "")
    created_date = fields.get("Created", "")
    created_date = created_date.split("T")[0] if "T" in created_date else created_date

    if raw_json:
        with suppress(Exception):
            parsed = json.loads(raw_json)
            client_name = parsed.get("ClientName", client_name)
            effective_date = parsed.get("EffectiveDate", effective_date)
            quote_date = parsed.get("QuoteDate", quote_date)

    return {
        "id": item["id"],
        "status": fields.get("Status", ""),
        "client_name": client_name,
        "effective_date": effective_date,
        "quote_date": quote_date,
        "created_date": created_date,
    }

def handle_approved(token, firmdata):
    """
    Displays all approved SharePoint entries, lets the user choose one,
    parses the selected JSON payload, and runs the automation for it.
    """

    selected_item = choose_sharepoint_item(token)
    if selected_item is None:
        return

    process_approved_item(token, selected_item, firmdata)

def process_approved_item(token, item, firmdata):
    item_id = item["id"]
    fields = item.get("fields", {})
    raw_json = fields.get("JSON")
    if not raw_json:
        logging.error("Item %s has no JSON field, marking Failed", item_id)
        update_item(token, item_id, {"Status": "Failed"})
        return

    log_item_id = None
    try:
        client_data = parse_client_data(raw_json)
        update_item(token, item_id, {"Status": "Processing"})

        try:
            log_item_id = create_automation_log(token, client_data.ClientName, item_id, MAX_RETRY_ATTEMPTS)
        except Exception:
            logging.exception("Failed to create Automation Logs entry for item %s", item_id)

        def on_attempt(attempt, status, exception_message=""):
            # Best-effort - a logging failure here shouldn't abort the actual
            # eStamp automation or mask its real success/failure.
            if log_item_id is None:
                return
            with suppress(Exception):
                update_automation_log(
                    token, log_item_id,
                    attempt=attempt, max_attempts=MAX_RETRY_ATTEMPTS,
                    status=status, exception_message=exception_message,
                )

        main_automate_form(client_data, firmdata, on_attempt=on_attempt)
        update_item(token, item_id, {"Status": "Completed"})
        logging.info("[Approved -> Completed] Item %s processed", item_id)
    except Exception as error:
        update_item(token, item_id, {"Status": "Failed"})
        if log_item_id is not None:
            with suppress(Exception):
                update_automation_log(
                    token, log_item_id,
                    attempt=MAX_RETRY_ATTEMPTS, max_attempts=MAX_RETRY_ATTEMPTS,
                    status="Failed", exception_message=str(error),
                )
        logging.exception("[Approved -> Failed] Item %s error: %s", item_id, error)

def parse_graph_datetime(value):
    """Parses a Graph/SharePoint ISO 8601 timestamp (e.g. '2024-01-15T10:30:00Z') into an aware UTC datetime, or None if missing/unparseable."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logging.debug("Unable to parse timestamp: %r", value)
        return None

def is_processing_stale(fields, now=None):
    """True if `fields` is Status == 'Processing' and hasn't been touched in over STALE_PROCESSING_TIMEOUT."""
    if fields.get("Status") != "Processing":
        return False
    modified = _parse_graph_datetime(fields.get("Modified"))
    if modified is None:
        return False
    now = now or datetime.now(timezone.utc)
    return (now - modified) > STALE_PROCESSING_TIMEOUT