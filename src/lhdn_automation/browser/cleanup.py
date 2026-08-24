import time
import logging
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
)
from lhdn_automation.browser.actions import input_credentials, click_login, choose_profile
from lhdn_automation.browser.driver import wait_and_click, wait_and_send_keys, select_dropdown
from lhdn_automation.config import constants
from lhdn_automation.config.constants import WAIT_TIME, MAX_RETRY_ATTEMPTS
from lhdn_automation.interaction import pause_for_manual_step, pause_before_retry


def _sign_in_attempt(driver):
    input_credentials(driver, constants.PROD_IC, constants.PROD_PASSWORD)
    click_login(driver)
    driver.implicitly_wait(WAIT_TIME)
    choose_profile(driver)
    driver.implicitly_wait(WAIT_TIME)

def cleanup_sign_in(driver):
    """
    Login and profile selection to bring straight to dashboard for cleanup_loop().

    Wrapped with the same manual Continue/Abort retry as cleanup_loop() - a
    slow login page or unexpected element previously threw straight through
    uncaught, since this ran before any of cleanup_loop()'s protection.
    """
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            return _sign_in_attempt(driver)
        except (
            TimeoutException,
            NoSuchElementException,
            StaleElementReferenceException,
            ElementClickInterceptedException,
            ElementNotInteractableException,
        ) as error:
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                logging.exception("Error on cleanup sign-in attempt %d: %s", attempt + 1, error)
                pause_before_retry(error)
                continue
            logging.exception("Final cleanup sign-in attempt failed.")
            raise

def _scan_and_cancel_one_attempt(driver, date):

    driver.get("https://stamps.hasil.gov.my/stamps/utama/senarai/permohonan/4")
    driver.implicitly_wait(WAIT_TIME)
    select_dropdown(driver, By.ID, "dropdown_status")
    driver.implicitly_wait(WAIT_TIME)
    wait_and_click(driver, By.XPATH, "//option[@value='1' and text()='Dalam Simpanan']")
    driver.implicitly_wait(WAIT_TIME)

    pause_for_manual_step(
        "Confirm the target entry is currently on screen and the table has finished loading, then click Continue to proceed with the automated cleanup, or Abort to leave it untouched.",
        allow_abort=True,
    )

    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    target_row = None

    for row in rows:
        logging.debug("Row: %r", row.text)  
        cells = row.find_elements(By.TAG_NAME, "td")
        logging.debug("Number of cells: %d", len(cells))
        for i, cell in enumerate(cells):
            logging.debug("%d: %r", i, cell.text)

        if len(cells) >= 6 and cells[5].text.strip() == date and cells[4].text.strip() == "Perjanjian Perkhidmatan":
            target_row = row
            break

    if target_row is None:
        logging.info("No matching entry found for %s.", date)
        return False

    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});"
        "arguments[0].style.backgroundColor = '#fff3a3';"
        "arguments[0].style.outline = '3px solid #d9534f';",
        target_row,
    )
    entry_summary = " | ".join(cell.text.strip() for cell in target_row.find_elements(By.TAG_NAME, "td"))

    pause_for_manual_step(
        f"Found and highlighted an entry matching {date}:\n{entry_summary}\n\n"
        "Continue to cancel it, or Abort to leave it untouched.",
        allow_abort=True,
    )

    link = target_row.find_element(By.XPATH, "./td[2]//a")
    link.click()
    driver.implicitly_wait(WAIT_TIME)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    wait_and_click(driver, By.XPATH, "//button[@id='btn-main-batal']")
    wait_and_send_keys(driver, By.XPATH, "//textarea[@id='alasan-batal']", "Automated test cleanup")
    wait_and_click(driver, By.XPATH, "//button[@id='btn-batal-suratcara']")
    time.sleep(1)
    return True

def cleanup_loop(driver, date):
    """
    Navigates to the 'Dalam Simpanan' listing and cancels the first entry
    matching `date` (dd/mm/yyyy). Returns True if a match was found and cancelled,
    False otherwise.

    Pauses for a manual Continue/Abort twice: once after selecting the
    'Dalam Simpanan' filter, so the operator can confirm the table has
    actually finished loading before the row search runs against it, and
    again right before the destructive cancel click, with the matched row
    highlighted directly in the browser.

    Transient Selenium failures (stale table, slow page, a fumbled click)
    pause for a manual Continue/Abort instead of silently propagating, the
    same as main_automate_form()'s retry loop - otherwise the operator has
    no chance to fix the page and retry, or to deliberately stop.
    """
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            return _scan_and_cancel_one_attempt(driver, date)
        except (
            TimeoutException,
            NoSuchElementException,
            StaleElementReferenceException,
            ElementClickInterceptedException,
            ElementNotInteractableException,
        ) as error:
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                logging.exception("Error on cleanup attempt %d: %s", attempt + 1, error)
                pause_before_retry(error)
                continue
            logging.exception("Final cleanup attempt failed.")
            raise

def cleanup_test_entries(driver, date):  # date in the form of dd/mm/yyyy
    """Signs in once, then cancels every matching entry until none remain."""
    cleanup_sign_in(driver)
    while cleanup_loop(driver, date):
        pass
    time.sleep(1)  # or use WebDriverWait
