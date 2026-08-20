
from lhdn_automation.exceptions import AutomationAborted
from lhdn_automation.sharepoint.client import get_selectable_items
import logging

def _cli_confirm(message, allow_abort=False):
    print(f"\n{message}")
    if allow_abort:
        choice = input("Press Enter to continue, or type 'abort' to stop: ").strip().lower()
        if choice == "abort":
            raise AutomationAborted("User aborted during manual pause.")
    else:
        input("Press Enter to continue...")

def select_approved_item(selectable_items):
    """CLI fallback selector used when running lhdn_automation.py directly."""
    if not selectable_items:
        print("No selectable SharePoint entries are available.")
        return None

    print("\nSelectable SharePoint entries:")
    for index, item in enumerate(selectable_items, start=1):
        summary = summarise_item(item)
        print(
            f"{index}. "
            f"ID = {summary['id']} | "
            f"Status = {summary['status']} | "
            f"Client = {summary['client_name']} | "
            f"Effective = {summary['effective_date']} | "
            f"Created = {summary['created_date']}"
        )

    while True:
        choice = input("Select an entry by number (blank to skip): ").strip()
        if not choice:
            return None
        try:
            selected_index = int(choice)
        except ValueError:
            print("Please enter a valid number from the list.")
            continue

        if 1 <= selected_index <= len(selectable_items):
            return selectable_items[selected_index - 1]

        print("Selection out of range. Try again.")

PAUSE_HANDLER = _cli_confirm

def choose_sharepoint_item(token):
    return select_approved_item(get_selectable_items(token))