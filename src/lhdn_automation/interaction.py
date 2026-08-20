import logging

# Set by whichever entry point (cli.py, gui/app.py) is loaded - the CLI's
# _cli_confirm or the GUI's PauseManager.confirm - before any automation runs.
PAUSE_HANDLER = None


def pause_for_manual_step(message, allow_abort=False):
    PAUSE_HANDLER(message, allow_abort=allow_abort)


def pause_before_retry(error):
    logging.exception(error)
    pause_for_manual_step(
        "Automation paused due to an exception. Inspect the browser and continue when ready.",
        allow_abort=True,
    )
