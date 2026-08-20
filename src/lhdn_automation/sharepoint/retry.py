from lhdn_automation.config.constants import REQUEST_RETRIES, REQUEST_RETRY_DELAY, REQUEST_TIMEOUT
import requests
import logging
import time
from lhdn_automation.exceptions import RequestsTimeout, RequestsConnectionError

def request_with_retries(method, url, *, retries=None, retry_delay=None, timeout=None, **kwargs):
    if retries is None:
        retries = REQUEST_RETRIES
    if retry_delay is None:
        retry_delay = REQUEST_RETRY_DELAY
    if timeout is None:
        timeout = REQUEST_TIMEOUT
    last_error = None

    for attempt in range(retries):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except (RequestsTimeout, RequestsConnectionError) as error:
            last_error = error
            if attempt == retries - 1:
                break
            logging.warning(
                "Request %s %s failed on attempt %d/%d: %s",
                method,
                url,
                attempt + 1,
                retries,
                error,
            )
            time.sleep(retry_delay)

    raise last_error
