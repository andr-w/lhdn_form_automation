import time
import logging
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    InvalidSessionIdException,
    TimeoutException,
    ElementNotInteractableException,
    NoSuchElementException,
    SessionNotCreatedException,
    StaleElementReferenceException,
)

from lhdn_automation.browser.actions import input_credentials, click_login, choose_profile
from lhdn_automation.browser.driver import setup_driver, replace_driver
from lhdn_automation.browser.forms.sekuriti import fill_makluman_am, fill_bahagian_a, fill_bahagian_b, fill_bahagian_c
from lhdn_automation.config.constants import WAIT_TIME, BASE_URL, MAX_RETRY_ATTEMPTS, PROD_IC, PROD_PASSWORD
from lhdn_automation.config.validation import validate_firm_data
from lhdn_automation.interaction import pause_before_retry


def main_flow(driver, ClientData, FirmData):
    input_credentials(driver, PROD_IC, PROD_PASSWORD)
    click_login(driver)
    driver.implicitly_wait(WAIT_TIME)
    choose_profile(driver)
    driver.implicitly_wait(WAIT_TIME)
    fill_makluman_am(driver, ClientData.EffectiveDate)
    driver.implicitly_wait(WAIT_TIME)
    fill_bahagian_a(driver, ClientData.SSMOption, FirmData, ClientData)
    driver.implicitly_wait(WAIT_TIME)
    fill_bahagian_b(driver, ClientData)
    driver.implicitly_wait(WAIT_TIME)
    fill_bahagian_c(driver)


def main_automate_form(ClientData, FirmData, on_attempt=None):
    validate_firm_data(FirmData)

    retry_attempts = MAX_RETRY_ATTEMPTS
    driver = None
    success = False

    try:
        driver = setup_driver(BASE_URL)

        for attempt in range(retry_attempts):
            try:
                main_flow(driver, ClientData, FirmData)
                success = True
                if on_attempt:
                    on_attempt(attempt + 1, "Completed")
                break

            except (
                TimeoutException,
                ElementNotInteractableException,
                NoSuchElementException,
                StaleElementReferenceException,
                ElementClickInterceptedException,
                ValueError,
                RuntimeError,
            ) as error:

                if attempt < retry_attempts - 1:
                    logging.exception(
                        "Error on attempt %d: %s",
                        attempt + 1,
                        error
                    )
                    if on_attempt:
                        on_attempt(attempt + 1, "Exception", str(error))
                    pause_before_retry(error)
                    driver = replace_driver(driver, BASE_URL)
                    time.sleep(2)
                    continue

                logging.exception("Final attempt failed.")
                raise

            except (
                SessionNotCreatedException,
                InvalidSessionIdException,
            ) as error:

                if attempt < retry_attempts - 1:
                    logging.exception(
                        "Session error on attempt %d: %s",
                        attempt + 1,
                        error
                    )
                    if on_attempt:
                        on_attempt(attempt + 1, "Exception", str(error))

                    driver = replace_driver(driver, BASE_URL)
                    time.sleep(2)
                    continue

                logging.exception("Final session attempt failed.")
                raise

    finally:
        # Left open intentionally to allow reviewing of the
        # submitted form (on success) or diagnose what went wrong (on
        # failure) - closed only via close_last_driver() or manually.
        if success:
            logging.info("Automation completed successfully. Browser left open for review.")
        else:
            logging.error("Automation failed. Browser left open for debugging.")
