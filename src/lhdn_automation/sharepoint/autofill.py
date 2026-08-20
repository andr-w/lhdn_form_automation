import json
import logging
from contextlib import suppress
from lhdn_automation.sharepoint.client import update_item
from lhdn_automation.browser.driver import setup_driver, safe_quit_driver
from lhdn_automation.browser.ctos_lookup import findCompanyNumber

def handle_autofill(token, item_id, fields, headless=True):
    """
    Ensures an entry's JSON has both OldCompanyNumber and NewCompanyNumber,
    attempting a CTOS lookup to fill in whichever is missing. Runs against
    Pending and Awaiting Review entries, since they can
    reach this point still missing a company number.

    Only Pending entries have their Status advanced (to Awaiting Review,
    or Failed on error) as a result of this.
    The CTOS lookup driver defaults to headless
    since this runs unattended during passive polling.
    """
    status = fields.get("Status", "")
    raw_json = fields.get("JSON")
    if not raw_json:
        logging.info("Item %s has no JSON field, skipping", item_id)
        return

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        logging.error("Error parsing JSON for item %s: %s", item_id, raw_json)
        if status == "Pending":
            update_item(token, item_id, {"Status": "Failed"})
        return

    if data.get("OldCompanyNumber") and data.get("NewCompanyNumber"): # both numbers already present, skip autofill
        if status == "Pending":
            update_item(token, item_id, {"Status": "Awaiting Review"})
            logging.info("[Pending -> Awaiting Review] Item %s has company numbers, skipping autofill", item_id)
        return

    logging.info("Item %s (%s) is missing company numbers, attempting to autofill", item_id, status)
    driver = None
    try:
        driver = setup_driver("https://businessreport.ctoscredit.com.my/oneoffreport/home", headless=headless)
        temp_old_number, temp_new_number = findCompanyNumber(
            driver,
            data.get("OldCompanyNumber"),
            data.get("NewCompanyNumber"),
            data.get("ClientName")
        )
        if temp_old_number:
            data["OldCompanyNumber"] = temp_old_number
        if temp_new_number:
            data["NewCompanyNumber"] = temp_new_number

        if data.get("OldCompanyNumber") and data.get("NewCompanyNumber"):
            fields_to_update = {"JSON": json.dumps(data)}
            if status == "Pending":
                fields_to_update["Status"] = "Awaiting Review"
                logging.info("[Pending -> Awaiting Review] Item %s autofilled", item_id)
            else:
                logging.info("Item %s autofilled (Status remains %s)", item_id, status)
            update_item(token, item_id, fields_to_update)
        else:
            logging.warning("Item %s company numbers still missing after autofill", item_id)
    except Exception:
        logging.exception("Error while resolving company number for item %s", item_id)
        if status == "Pending":
            update_item(token, item_id, {"Status": "Failed"})
    finally:
        safe_quit_driver(driver)