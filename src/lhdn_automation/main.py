import time
import logging

from lhdn_automation.config.constants import BASE_URL, POLL_INTERVAL
from lhdn_automation.config.validation import validate_runtime_config
from lhdn_automation.models import default_firm_data
from lhdn_automation.browser.driver import setup_driver
from lhdn_automation.browser.cleanup import cleanup_test_entries
from lhdn_automation.exceptions import AutomationAborted
from lhdn_automation.sharepoint.token import get_access_token
from lhdn_automation.sharepoint.processing import handle_approved
from lhdn_automation.sharepoint.polling import poll_for_changes


def main():
    validate_runtime_config()

    firm_data = default_firm_data()

    print(
        "\n=== LHDN Automation Script ==="
        "\nSelect mode:"  
        "\n1. Polling"
        "\n2. Edit"
        "\n3. Polling + Edit"
        "\n4. Cleanup"
    )

    mode = input("\nChoice: ").strip()

    if mode == "4":
        driver = setup_driver(BASE_URL)
        try:
            cleanup_test_entries(driver, "10/07/2026")
        except AutomationAborted:
            logging.info("Cleanup aborted by user.")
        finally:
            logging.info("Browser left open for review. Call close_last_driver() or close it manually.")
        return

    if mode == "2":
        token = get_access_token()
        handle_approved(token, firm_data)
        return

    if mode == "1":
        while True:
            try:
                poll_for_changes(firm_data)
            except Exception:
                logging.exception("Unhandled error during poll cycle, continuing")
            time.sleep(POLL_INTERVAL)

    if mode == "3":
        while True:
            try:
                poll_for_changes(firm_data)
            except Exception:
                logging.exception("Unhandled error during poll cycle, continuing")

            choice = input(
                "\nProcess an Approved/Failed SharePoint item? (y/n): "
            ).strip().lower()

            if choice == "y":
                token = get_access_token()
                handle_approved(token, firm_data)

            time.sleep(POLL_INTERVAL)

    print("Invalid mode selected.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()



