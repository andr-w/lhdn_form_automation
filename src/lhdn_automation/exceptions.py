from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout as RequestsTimeout


class AutomationAborted(Exception):
    """Raised when the operator aborts automation during a manual pause."""