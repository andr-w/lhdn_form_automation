import logging
from lhdn_automation.cli import PAUSE_HANDLER

class AutomationAborted(Exception):
    """Raised when the operator aborts automation during a manual pause."""

def pause_for_manual_step(message, allow_abort=False):
    PAUSE_HANDLER(message, allow_abort=allow_abort)

def pause_before_retry(error):
    logging.exception(error)
    pause_for_manual_step(
        "Automation paused due to an exception. Inspect the browser and continue when ready.",
        allow_abort=True,
    )